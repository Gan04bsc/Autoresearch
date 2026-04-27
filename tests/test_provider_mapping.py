import xml.etree.ElementTree as ET

from litagent.providers import (
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
