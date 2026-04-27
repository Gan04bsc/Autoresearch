from litagent.classifier import classify_paper
from litagent.dedup import deduplicate, score_paper


def test_deduplicate_merges_same_doi_and_sources() -> None:
    rows = [
        {
            "title": "Agentic Literature Review: A Survey",
            "authors": ["A"],
            "doi": "10.1000/example",
            "citation_count": 3,
            "source": ["semantic_scholar"],
        },
        {
            "title": "Agentic Literature Review - A Survey",
            "authors": ["B"],
            "doi": "https://doi.org/10.1000/example",
            "citation_count": 10,
            "source": ["openalex"],
        },
    ]

    papers = deduplicate(rows)

    assert len(papers) == 1
    assert papers[0]["doi"] == "10.1000/example"
    assert papers[0]["citation_count"] == 10
    assert papers[0]["source"] == ["openalex", "semantic_scholar"]


def test_score_paper_prefers_keyword_and_recent_work() -> None:
    plan = {
        "include_keywords": ["agentic", "literature", "survey"],
        "date_range": {"from": 2018, "to": 2026},
    }
    paper = {
        "title": "Agentic Literature Survey",
        "abstract": "A survey about agentic literature tools.",
        "year": 2025,
        "citation_count": 30,
        "reference_count": 80,
        "pdf_url": "mock://pdf/test",
        "source": ["arxiv"],
    }

    scored = score_paper(paper, plan)

    assert scored["relevance_score"] > 0.5
    assert scored["importance_score"] > 0
    assert scored["recency_score"] > 0.8
    assert scored["final_score"] > 0.5


def test_classifier_identifies_expected_types() -> None:
    assert classify_paper({"title": "A Survey of Literature Agents"})[0] == "survey"
    assert classify_paper({"title": "BenchLit: Benchmarking Literature Agents"})[0] == "benchmark"
    assert classify_paper({"title": "OpenLitSet Dataset"})[0] == "dataset"
    assert classify_paper({"title": "A Position Paper on Traceability"})[0] == "position"
    assert classify_paper({"title": "A System Architecture for Research Agents"})[0] == "system"
    assert (
        classify_paper({"abstract": "We propose an algorithm for ranking papers."})[0]
        == "technical"
    )


def test_classifier_prefers_system_for_implemented_research_workbench() -> None:
    paper_type, evidence = classify_paper(
        {
            "title": "Ralph: An Agentic Research Workbench for Open Literature Review",
            "abstract": (
                "Ralph describes a system and workbench architecture for open literature "
                "review automation with planner, search, reader, synthesis, and audit agents."
            ),
        }
    )

    assert paper_type == "system"
    assert "system" in evidence


def test_classifier_does_not_mark_position_as_survey_due_to_review_word() -> None:
    paper_type, evidence = classify_paper(
        {
            "title": "Research Agents Need Traceable Evidence: A Position Paper",
            "abstract": (
                "This position paper argues that literature research agents need transparent "
                "citation trails, failure logs, and human review loops."
            ),
        }
    )

    assert paper_type == "position"
    assert "position" in evidence
