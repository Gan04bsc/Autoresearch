import urllib.error
import xml.etree.ElementTree as ET

from litagent import cli
from litagent.provider_diagnostics import (
    semantic_scholar_error_diagnostic,
    smoke_test_semantic_scholar,
)
from litagent.providers import (
    SEMANTIC_SCHOLAR_DEFAULT_BASE_URL,
    SemanticScholarProvider,
    map_arxiv_entry,
    map_openalex_item,
    map_semantic_scholar_item,
    reconstruct_openalex_abstract,
)


def test_semantic_scholar_mapping_uses_prd_fields() -> None:
    mapped = map_semantic_scholar_item(
        {
            "paperId": "S2-1",
            "title": "Traceable Literature Agents",
            "authors": [{"name": "Ada Lovelace"}],
            "year": 2025,
            "venue": "AI Systems",
            "abstract": "A system paper.",
            "externalIds": {"DOI": "https://doi.org/10.1000/test", "ArXiv": "2501.00001"},
            "citationCount": 7,
            "referenceCount": 11,
            "url": "https://semanticscholar.org/paper/S2-1",
            "openAccessPdf": {"url": "https://example.org/test.pdf"},
        }
    )

    assert mapped["semantic_scholar_id"] == "S2-1"
    assert mapped["doi"] == "10.1000/test"
    assert mapped["arxiv_id"] == "2501.00001"
    assert mapped["pdf_url"] == "https://example.org/test.pdf"
    assert mapped["source"] == ["semantic_scholar"]


def test_openalex_mapping_reconstructs_abstract() -> None:
    abstract_index = {"Traceable": [0], "agents": [1], "work": [2]}

    mapped = map_openalex_item(
        {
            "id": "https://openalex.org/W1",
            "display_name": "Open Literature Workbench",
            "authorships": [{"author": {"display_name": "Grace Hopper"}}],
            "publication_year": 2024,
            "primary_location": {
                "source": {"display_name": "Open Venue"},
                "landing_page_url": "https://example.org/work",
            },
            "abstract_inverted_index": abstract_index,
            "doi": "https://doi.org/10.1000/openalex",
            "cited_by_count": 12,
            "referenced_works_count": 20,
            "best_oa_location": {"pdf_url": "https://example.org/open.pdf"},
        }
    )

    assert reconstruct_openalex_abstract(abstract_index) == "Traceable agents work"
    assert mapped["openalex_id"] == "https://openalex.org/W1"
    assert mapped["abstract"] == "Traceable agents work"
    assert mapped["doi"] == "10.1000/openalex"


def test_arxiv_mapping_extracts_pdf_link() -> None:
    xml = """<entry xmlns="http://www.w3.org/2005/Atom"
        xmlns:arxiv="http://arxiv.org/schemas/atom">
      <id>https://arxiv.org/abs/2401.00001v2</id>
      <published>2024-01-01T00:00:00Z</published>
      <title> An arXiv Paper </title>
      <summary> Abstract text. </summary>
      <author><name>Alan Turing</name></author>
      <arxiv:doi>10.1000/arxiv</arxiv:doi>
      <link title="pdf" href="https://arxiv.org/pdf/2401.00001v2" type="application/pdf" />
    </entry>"""

    mapped = map_arxiv_entry(ET.fromstring(xml))

    assert mapped["title"] == "An arXiv Paper"
    assert mapped["authors"] == ["Alan Turing"]
    assert mapped["year"] == 2024
    assert mapped["arxiv_id"] == "2401.00001"
    assert mapped["pdf_url"] == "https://arxiv.org/pdf/2401.00001v2"


def test_semantic_scholar_provider_uses_official_key_header(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fetch(url: str, headers: dict[str, str] | None) -> bytes:
        seen["url"] = url
        seen["headers"] = headers
        return b'{"data": []}'

    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "official-key")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_BASE_URL", SEMANTIC_SCHOLAR_DEFAULT_BASE_URL)
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_AUTH_MODE", "x-api-key")

    SemanticScholarProvider(fetch=fetch).search("semantic", 1)

    assert str(seen["url"]).startswith(SEMANTIC_SCHOLAR_DEFAULT_BASE_URL)
    assert seen["headers"] == {"x-api-key": "official-key"}


def test_semantic_scholar_provider_supports_bearer_proxy(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fetch(url: str, headers: dict[str, str] | None) -> bytes:
        seen["url"] = url
        seen["headers"] = headers
        return b'{"data": []}'

    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "proxy-key")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_BASE_URL", "https://s2api.example.test/s2")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_AUTH_MODE", "authorization_bearer")

    SemanticScholarProvider(fetch=fetch).search("semantic", 1)

    assert str(seen["url"]).startswith("https://s2api.example.test/s2/graph/v1/paper/search")
    assert seen["headers"] == {"Authorization": "Bearer proxy-key"}


def test_semantic_scholar_provider_trims_proxy_base_url(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fetch(url: str, headers: dict[str, str] | None) -> bytes:
        seen["url"] = url
        seen["headers"] = headers
        return b'{"data": []}'

    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "proxy-key")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_BASE_URL", "https://s2api.example.test/s2/")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_AUTH_MODE", "authorization_bearer")

    SemanticScholarProvider(fetch=fetch).search("semantic", 1)

    assert str(seen["url"]).startswith("https://s2api.example.test/s2/graph/v1/paper/search")
    assert "//graph" not in str(seen["url"])


def test_provider_smoke_success_schema_does_not_leak_key(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fetch(url: str, headers: dict[str, str] | None) -> bytes:
        seen["url"] = url
        seen["headers"] = headers
        return b'{"data": [{"title": "Literature Review Automation"}]}'

    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "secret-smoke-key")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_BASE_URL", "https://s2api.example.test/s2")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_AUTH_MODE", "authorization_bearer")

    result = smoke_test_semantic_scholar(fetch=fetch, limit=9)

    assert result["provider"] == "semantic_scholar"
    assert result["success"] is True
    assert result["status_code"] == 200
    assert result["limit"] == 3
    assert result["key_present"] is True
    assert result["auth_mode"] == "authorization_bearer"
    assert result["result_count"] == 1
    assert result["sample_titles"] == ["Literature Review Automation"]
    assert "secret-smoke-key" not in str(result)
    assert seen["headers"] == {"Authorization": "Bearer secret-smoke-key"}


def test_provider_smoke_403_diagnostic_does_not_leak_key(monkeypatch) -> None:
    def fetch(url: str, headers: dict[str, str] | None) -> bytes:
        raise urllib.error.HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "secret-forbidden-key")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_BASE_URL", "https://s2api.example.test/s2")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_AUTH_MODE", "authorization_bearer")

    result = smoke_test_semantic_scholar(fetch=fetch)

    assert result["success"] is False
    assert result["status_code"] == 403
    assert result["error_type"] == "forbidden"
    assert result["key_present"] is True
    assert "auth header mode" in result["likely_action"]
    assert "secret-forbidden-key" not in str(result)


def test_provider_smoke_429_diagnostic(monkeypatch) -> None:
    def fetch(url: str, headers: dict[str, str] | None) -> bytes:
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", hdrs=None, fp=None)

    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "secret-rate-key")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_BASE_URL", SEMANTIC_SCHOLAR_DEFAULT_BASE_URL)
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_AUTH_MODE", "x-api-key")

    result = smoke_test_semantic_scholar(fetch=fetch)

    assert result["status_code"] == 429
    assert result["error_type"] == "rate_limited"
    assert result["auth_mode"] == "x_api_key"
    assert "quota" in result["likely_action"]
    assert "secret-rate-key" not in str(result)


def test_semantic_scholar_error_diagnostic_schema(monkeypatch) -> None:
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "schema-key")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_BASE_URL", "https://s2api.example.test/s2")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_AUTH_MODE", "authorization_bearer")

    result = semantic_scholar_error_diagnostic(RuntimeError("HTTP Error 403: Forbidden"))

    assert {
        "provider",
        "base_url",
        "base_url_type",
        "auth_mode",
        "key_present",
        "endpoint",
        "status_code",
        "success",
        "error_type",
        "likely_action",
    } <= set(result)
    assert result["status_code"] == 403
    assert "schema-key" not in str(result)


def test_cli_provider_smoke_json_schema(monkeypatch, capsys) -> None:
    def fake_smoke_test_semantic_scholar(query: str, limit: int) -> dict[str, object]:
        return {
            "provider": "semantic_scholar",
            "query": query,
            "limit": limit,
            "success": True,
            "status_code": 200,
            "key_present": True,
            "auth_mode": "x_api_key",
        }

    monkeypatch.setattr(cli, "smoke_test_semantic_scholar", fake_smoke_test_semantic_scholar)

    assert cli.main(["provider-smoke", "semantic-scholar", "--json"]) == 0
    out = capsys.readouterr().out
    assert '"provider": "semantic_scholar"' in out
    assert "API_KEY" not in out
