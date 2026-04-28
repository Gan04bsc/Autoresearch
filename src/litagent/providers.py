from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import Any, Protocol

from litagent.schema import normalize_arxiv_id, normalize_doi, normalize_whitespace
from litagent.secrets import get_config_value

FetchBytes = Callable[[str, dict[str, str] | None], bytes]

USER_AGENT = "litagent/0.1 (mailto:litagent@example.invalid)"
SEMANTIC_SCHOLAR_DEFAULT_BASE_URL = "https://api.semanticscholar.org"
SEMANTIC_SCHOLAR_SEARCH_PATH = "/graph/v1/paper/search"
SEMANTIC_SCHOLAR_FIELDS = [
    "title",
    "authors",
    "year",
    "venue",
    "abstract",
    "externalIds",
    "citationCount",
    "referenceCount",
    "url",
    "openAccessPdf",
]


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """Return papers mapped to the litagent paper schema."""


def default_fetch_bytes(url: str, headers: dict[str, str] | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def get_json(
    url: str, headers: dict[str, str] | None = None, fetch: FetchBytes = default_fetch_bytes
) -> Any:
    return json.loads(fetch(url, headers).decode("utf-8"))


def normalize_semantic_scholar_auth_mode(value: str | None) -> str:
    mode = (value or "x-api-key").strip().lower().replace("-", "_")
    if mode in {"bearer", "authorization", "authorization_bearer"}:
        return "authorization_bearer"
    return "x_api_key"


def reconstruct_openalex_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    if not inverted_index:
        return ""
    words_by_position: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for position in positions:
            words_by_position[int(position)] = word
    return " ".join(words_by_position[position] for position in sorted(words_by_position))


def map_semantic_scholar_item(item: dict[str, Any]) -> dict[str, Any]:
    external_ids = item.get("externalIds") or {}
    open_access_pdf = item.get("openAccessPdf") or {}
    return {
        "title": item.get("title") or "",
        "authors": [author.get("name", "") for author in item.get("authors") or []],
        "year": item.get("year"),
        "venue": item.get("venue") or "",
        "abstract": item.get("abstract") or "",
        "doi": normalize_doi(external_ids.get("DOI")),
        "arxiv_id": normalize_arxiv_id(external_ids.get("ArXiv")),
        "semantic_scholar_id": item.get("paperId"),
        "openalex_id": None,
        "citation_count": item.get("citationCount") or 0,
        "reference_count": item.get("referenceCount") or 0,
        "url": item.get("url"),
        "pdf_url": open_access_pdf.get("url"),
        "source": ["semantic_scholar"],
    }


def map_openalex_item(item: dict[str, Any]) -> dict[str, Any]:
    primary_location = item.get("primary_location") or {}
    best_oa_location = item.get("best_oa_location") or {}
    source = primary_location.get("source") or {}
    ids = item.get("ids") or {}
    doi = item.get("doi") or ids.get("doi")
    return {
        "title": item.get("display_name") or item.get("title") or "",
        "authors": [
            (authorship.get("author") or {}).get("display_name", "")
            for authorship in item.get("authorships") or []
        ],
        "year": item.get("publication_year"),
        "venue": source.get("display_name") or "",
        "abstract": reconstruct_openalex_abstract(item.get("abstract_inverted_index")),
        "doi": normalize_doi(doi),
        "arxiv_id": normalize_arxiv_id(ids.get("arxiv")),
        "semantic_scholar_id": None,
        "openalex_id": item.get("id") or ids.get("openalex"),
        "citation_count": item.get("cited_by_count") or 0,
        "reference_count": item.get("referenced_works_count") or 0,
        "url": primary_location.get("landing_page_url") or item.get("id"),
        "pdf_url": best_oa_location.get("pdf_url") or primary_location.get("pdf_url"),
        "source": ["openalex"],
    }


def map_arxiv_entry(entry: ET.Element) -> dict[str, Any]:
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    entry_id = entry.findtext("atom:id", default="", namespaces=ns)
    published = entry.findtext("atom:published", default="", namespaces=ns)
    doi = entry.findtext("arxiv:doi", default=None, namespaces=ns)
    authors = [
        normalize_whitespace(author.findtext("atom:name", default="", namespaces=ns))
        for author in entry.findall("atom:author", ns)
    ]

    pdf_url = None
    for link in entry.findall("atom:link", ns):
        if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
            pdf_url = link.attrib.get("href")
            break

    arxiv_id = normalize_arxiv_id(entry_id)
    if not pdf_url and arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    return {
        "title": normalize_whitespace(entry.findtext("atom:title", default="", namespaces=ns)),
        "authors": [author for author in authors if author],
        "year": int(published[:4]) if published[:4].isdigit() else None,
        "venue": "arXiv",
        "abstract": normalize_whitespace(entry.findtext("atom:summary", default="", namespaces=ns)),
        "doi": normalize_doi(doi),
        "arxiv_id": arxiv_id,
        "semantic_scholar_id": None,
        "openalex_id": None,
        "citation_count": 0,
        "reference_count": 0,
        "url": entry_id or None,
        "pdf_url": pdf_url,
        "source": ["arxiv"],
    }


class ArxivProvider:
    name = "arxiv"

    def __init__(self, fetch: FetchBytes = default_fetch_bytes) -> None:
        self.fetch = fetch

    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "search_query": query,
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
        )
        url = f"https://export.arxiv.org/api/query?{params}"
        root = ET.fromstring(self.fetch(url, None))
        return [
            map_arxiv_entry(entry) for entry in root.findall("{http://www.w3.org/2005/Atom}entry")
        ]


class SemanticScholarProvider:
    name = "semantic_scholar"

    def __init__(self, fetch: FetchBytes = default_fetch_bytes) -> None:
        self.fetch = fetch

    def base_url(self) -> str:
        return (
            get_config_value("SEMANTIC_SCHOLAR_API_BASE_URL")
            or SEMANTIC_SCHOLAR_DEFAULT_BASE_URL
        ).rstrip("/")

    def auth_mode(self) -> str:
        return normalize_semantic_scholar_auth_mode(
            get_config_value("SEMANTIC_SCHOLAR_API_AUTH_MODE")
        )

    def headers(self) -> dict[str, str]:
        api_key = get_config_value("SEMANTIC_SCHOLAR_API_KEY")
        if not api_key:
            return {}
        if self.auth_mode() == "authorization_bearer":
            return {"Authorization": f"Bearer {api_key}"}
        return {"x-api-key": api_key}

    def endpoint_url(self, query: str, max_results: int) -> str:
        fields = ",".join(SEMANTIC_SCHOLAR_FIELDS)
        params = urllib.parse.urlencode({"query": query, "limit": max_results, "fields": fields})
        return f"{self.base_url()}{SEMANTIC_SCHOLAR_SEARCH_PATH}?{params}"

    def diagnostic_context(self) -> dict[str, Any]:
        base_url = self.base_url()
        return {
            "provider": self.name,
            "base_url": base_url,
            "base_url_type": (
                "official" if base_url == SEMANTIC_SCHOLAR_DEFAULT_BASE_URL else "custom"
            ),
            "auth_mode": self.auth_mode(),
            "key_present": bool(get_config_value("SEMANTIC_SCHOLAR_API_KEY")),
            "endpoint": f"{base_url}{SEMANTIC_SCHOLAR_SEARCH_PATH}",
        }

    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        data = get_json(
            self.endpoint_url(query, max_results),
            headers=self.headers(),
            fetch=self.fetch,
        )
        return [map_semantic_scholar_item(item) for item in data.get("data", [])]


class OpenAlexProvider:
    name = "openalex"

    def __init__(self, fetch: FetchBytes = default_fetch_bytes) -> None:
        self.fetch = fetch

    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "search": query,
                "per-page": max_results,
                "sort": "relevance_score:desc",
            }
        )
        data = get_json(f"https://api.openalex.org/works?{params}", fetch=self.fetch)
        return [map_openalex_item(item) for item in data.get("results", [])]


def mock_search_results(topic: str) -> list[dict[str, Any]]:
    topic_title = topic.strip() or "Literature Research Agents"
    rows = [
        {
            "title": f"{topic_title}: A Survey of Agentic Literature Research",
            "authors": ["Mira Chen", "Noah Patel"],
            "year": 2025,
            "venue": "Journal of AI Research Tools",
            "abstract": (
                "This survey reviews agentic literature research systems, taxonomies, "
                "retrieval strategies, traceable synthesis, and open problems."
            ),
            "doi": "10.1234/litagent.survey",
            "citation_count": 86,
            "reference_count": 120,
            "url": "https://example.org/survey",
            "pdf_url": "mock://pdf/survey",
            "source": ["semantic_scholar"],
        },
        {
            "title": f"{topic_title}: A Survey of Agentic Literature Research",
            "authors": ["Mira Chen", "Noah Patel"],
            "year": 2025,
            "venue": "OpenAlex Mock Venue",
            "abstract": (
                "A survey and taxonomy of agentic literature review automation tools "
                "with emphasis on evidence tracking."
            ),
            "doi": "10.1234/litagent.survey",
            "openalex_id": "https://openalex.org/W123",
            "citation_count": 90,
            "reference_count": 122,
            "url": "https://example.org/survey-openalex",
            "pdf_url": "mock://pdf/survey",
            "source": ["openalex"],
        },
        {
            "title": "LitGraph: Multi-Agent Literature Discovery with Traceable Evidence",
            "authors": ["Ava Singh", "Luis Romero"],
            "year": 2024,
            "venue": "arXiv",
            "abstract": (
                "We propose a multi-agent system for literature discovery that combines "
                "query planning, paper ranking, and citation-grounded report generation."
            ),
            "arxiv_id": "2401.00001",
            "citation_count": 42,
            "reference_count": 55,
            "url": "https://arxiv.org/abs/2401.00001",
            "pdf_url": "mock://pdf/litgraph",
            "source": ["arxiv"],
        },
        {
            "title": "BenchLit: Benchmarking Literature Research Agents",
            "authors": ["Jia Wang"],
            "year": 2024,
            "venue": "Proceedings of Evaluation for AI",
            "abstract": (
                "BenchLit introduces a benchmark and evaluation protocol for literature "
                "research agents, measuring retrieval quality, citation faithfulness, "
                "and synthesis."
            ),
            "doi": "10.1234/litagent.benchmark",
            "citation_count": 35,
            "reference_count": 48,
            "url": "https://example.org/benchlit",
            "pdf_url": "mock://pdf/benchlit",
            "source": ["semantic_scholar"],
        },
        {
            "title": "OpenLitSet: An Open Dataset for Literature Mining Workflows",
            "authors": ["Sam Rivera", "Iris Okafor"],
            "year": 2023,
            "venue": "Dataset Track",
            "abstract": (
                "OpenLitSet is an open dataset and corpus for training and evaluating "
                "literature mining workflows, paper classification, and metadata extraction."
            ),
            "doi": "10.1234/litagent.dataset",
            "citation_count": 28,
            "reference_count": 31,
            "url": "https://example.org/openlitset",
            "pdf_url": "mock://pdf/openlitset",
            "source": ["openalex"],
        },
        {
            "title": "Ralph: An Agentic Research Workbench for Open Literature Review",
            "authors": ["Elena Garcia"],
            "year": 2025,
            "venue": "Systems for Research Automation",
            "abstract": (
                "Ralph describes a system and workbench architecture for open literature "
                "review automation with planner, search, reader, synthesis, and audit agents."
            ),
            "doi": "10.1234/litagent.system",
            "citation_count": 22,
            "reference_count": 40,
            "url": "https://example.org/ralph",
            "pdf_url": "mock://pdf/ralph",
            "source": ["semantic_scholar"],
        },
        {
            "title": "Research Agents Need Traceable Evidence: A Position Paper",
            "authors": ["Omar Hassan"],
            "year": 2025,
            "venue": "AI Research Methods",
            "abstract": (
                "This position paper argues that literature research agents need transparent "
                "citation trails, failure logs, and human review loops."
            ),
            "doi": "10.1234/litagent.position",
            "citation_count": 15,
            "reference_count": 20,
            "url": "https://example.org/position",
            "pdf_url": "mock://pdf/position",
            "source": ["openalex"],
        },
    ]
    return rows


def default_providers() -> dict[str, SearchProvider]:
    return {
        "arxiv": ArxivProvider(),
        "semantic_scholar": SemanticScholarProvider(),
        "openalex": OpenAlexProvider(),
    }
