from __future__ import annotations

import re
from typing import Any

HIGH_VALUE_SECTIONS = {
    "Method",
    "System Design",
    "Framework",
    "Pipeline",
    "Evaluation",
    "Results",
    "Discussion",
    "Limitations",
}

MEDIUM_VALUE_SECTIONS = {
    "Abstract",
    "Introduction",
    "Background",
    "Related Work",
    "Conclusion",
}

NOISE_SECTIONS = {
    "References",
    "Bibliography",
    "Appendix",
    "Acknowledgments",
    "Prompt",
    "Code",
    "Supplementary Material",
    "Tables",
    "Figure Captions",
}

SECTION_PATTERNS: list[tuple[str, str]] = [
    (r"\breferences?\b|\bbibliography\b|\bliterature cited\b", "References"),
    (r"\bappendix\b|\bappendices\b", "Appendix"),
    (r"\backnowledg(e)?ments?\b", "Acknowledgments"),
    (r"\bprompt template\b|\bprompts?\b", "Prompt"),
    (r"\bcode listing\b|\bsource code\b|\bcode\b", "Code"),
    (r"\bsupplementary\b|\bsupplemental\b", "Supplementary Material"),
    (r"\btables?\b", "Tables"),
    (r"\bfigure captions?\b|\bfigures?\b", "Figure Captions"),
    (r"\blimitations?\b|\bfuture work\b", "Limitations"),
    (r"\bconclusions?\b", "Conclusion"),
    (r"\bdiscussion\b", "Discussion"),
    (r"\bresults?\b|\bfindings?\b", "Results"),
    (r"\bevaluation\b|\bevaluate\b|\bexperiments?\b|\bbenchmark\b", "Evaluation"),
    (r"\bsystem design\b|\bsystem architecture\b", "System Design"),
    (r"\bframework\b", "Framework"),
    (r"\bpipeline\b|\bworkflow\b", "Pipeline"),
    (r"\bmethodology\b|\bmethods?\b|\bapproach\b", "Method"),
    (r"\brelated work\b|\bprior work\b", "Related Work"),
    (r"\bbackground\b|\bpreliminaries\b", "Background"),
    (r"\bintroduction\b", "Introduction"),
    (r"\babstract\b", "Abstract"),
]

REFERENCE_PATTERNS = [
    r"^\s*\[\d+\]",
    r"^\s*\d+\.\s+[A-Z][A-Za-z-]+,\s+[A-Z]",
    r"\b(arxiv preprint|proceedings of|journal of|conference on)\b",
    r"\bdoi:\s*10\.\d{4,9}/",
]

CONTENT_BONUSES: list[tuple[str, str, float]] = [
    ("system_component", r"\b(framework|architecture|system|module|component|tool)\b", 0.1),
    (
        "agent_roles",
        r"\b(agent|agents|planner|collector|writer|reviewer|critic|coordinator|role)\b",
        0.12,
    ),
    (
        "pipeline_stages",
        r"\b(pipeline|workflow|stage|step|retrieval|screening|planning|writing|revision)\b",
        0.12,
    ),
    (
        "citation_or_evidence",
        r"\b(citation|citations|evidence|grounding|faithfulness|graph|reference checking)\b",
        0.1,
    ),
    (
        "evaluation_setup",
        r"\b(evaluation|experiment|benchmark|dataset|metric|baseline|human evaluation)\b",
        0.12,
    ),
    ("explicit_method", r"\b(we propose|we present|we introduce|we design|we implement)\b", 0.08),
]


def normalize_evidence_text(text: str) -> str:
    cleaned = text.replace("\x00", " ")
    cleaned = re.sub(r"(\w)-\s+(\w)", r"\1\2", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def normalize_section_title(raw: str) -> str:
    title = raw.strip()
    title = re.sub(r"^#+\s*", "", title)
    title = re.sub(r"^\d+(\.\d+)*\.?\s+", "", title)
    title = re.sub(r"^[IVXLC]+\.\s+", "", title, flags=re.IGNORECASE)
    title = title.strip(" :-–—\t")
    title = re.sub(r"\s+", " ", title)
    lower = title.lower()
    for pattern, section in SECTION_PATTERNS:
        if re.search(pattern, lower):
            return section
    return "Unknown"


def section_from_heading(line: str) -> str | None:
    clean = line.strip()
    if not clean:
        return None
    markdown_heading = re.match(r"^#{1,6}\s+(.+)$", clean)
    numbered_heading = re.match(r"^(\d+(\.\d+)*\.?|[IVXLC]+\.?)\s+(.{3,90})$", clean)
    words = clean.split()
    short_keyword_heading = (
        len(clean) <= 90
        and len(words) <= 8
        and clean[-1:] not in {".", ",", ";", ":"}
        and normalize_section_title(clean) != "Unknown"
    )
    if not (markdown_heading or numbered_heading or short_keyword_heading):
        return None
    section = normalize_section_title(clean)
    return section if section != "Unknown" else None


def sentence_like_units(text: str) -> list[str]:
    clean = normalize_evidence_text(text)
    if not clean:
        return []
    if len(clean) <= 700:
        return [clean]
    return [
        unit
        for unit in (normalize_evidence_text(part) for part in re.split(r"(?<=[.!?])\s+", clean))
        if unit
    ]


def sectioned_units(text: str) -> list[dict[str, str]]:
    normalized = re.sub(r"(\w)-\n(\w)", r"\1\2", text.replace("\x00", " "))
    units: list[dict[str, str]] = []
    current_section = "Unknown"
    in_code_block = False

    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("```"):
            in_code_block = not in_code_block
            current_section = "Code" if in_code_block else current_section
            continue
        if in_code_block:
            for unit in sentence_like_units(line):
                units.append({"text": unit, "section": "Code"})
            continue

        heading_section = section_from_heading(line)
        if heading_section:
            current_section = heading_section
            continue

        section = current_section
        if re.match(r"^(fig\.?|figure)\s+\d+", line, flags=re.IGNORECASE):
            section = "Figure Captions"
        elif re.match(r"^table\s+\d+", line, flags=re.IGNORECASE):
            section = "Tables"

        for unit in sentence_like_units(line):
            units.append({"text": unit, "section": section})
    return units


def clean_snippet(raw: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    snippet = raw.replace("\x00", " ")
    snippet = re.sub(r"(\w)-\s+(\w)", r"\1\2", snippet)
    snippet = re.sub(r"^\s*[-*•]\s+", "", snippet)
    snippet = re.sub(r"\s+", " ", snippet).strip()

    urls = re.findall(r"https?://\S+|www\.\S+", snippet)
    if urls:
        url_chars = sum(len(url) for url in urls)
        if len(urls) >= 2 or url_chars / max(1, len(snippet)) > 0.25:
            flags.append("url_heavy")
        snippet = re.sub(r"https?://\S+|www\.\S+", "", snippet)
        snippet = normalize_evidence_text(snippet)

    lower = snippet.lower()
    if any(re.search(pattern, lower, flags=re.IGNORECASE) for pattern in REFERENCE_PATTERNS):
        flags.append("reference_like")
    if re.search(r"\b(arxiv:\d{4}\.\d+|submitted to|license:|copyright)\b", lower):
        flags.append("metadata_noise")
    if re.search(r"\b(prompt template|system prompt|user prompt|you are an? )\b", lower):
        flags.append("code_or_prompt")
    if "```" in snippet or re.search(r"^\s*(def |class |import |from \w+ import)", snippet):
        flags.append("code_or_prompt")
    if snippet.count("|") >= 3 or "\t" in snippet or re.search(r"\s{3,}\d+(\.\d+)?\s{2,}", raw):
        flags.append("table_like")
    if re.match(r"^(fig\.?|figure)\s+\d+", snippet, flags=re.IGNORECASE):
        flags.append("figure_caption")
    if re.match(r"^(\d+\s*){4,}$", snippet) or re.search(r"\.{6,}", snippet):
        flags.append("layout_artifact")
    if len(re.findall(r"\[\d+(,\s*\d+)*\]|\([A-Z][A-Za-z-]+ et al\.,? \d{4}\)", snippet)) >= 3:
        flags.append("citation_dense")
    if len(snippet) < 45:
        flags.append("too_short")
    if len(snippet) > 700:
        flags.append("too_long")
        snippet = snippet[:700].rsplit(" ", 1)[0].strip()
    if not snippet:
        flags.append("empty_after_cleaning")
    return snippet, sorted(set(flags))


def score_snippet(
    raw: str,
    *,
    section: str = "Unknown",
    target_terms: list[str] | None = None,
) -> dict[str, Any]:
    snippet, flags = clean_snippet(raw)
    canonical_section = section if section else "Unknown"
    score = 0.35
    positive: list[str] = []
    negative: list[str] = []

    if canonical_section in HIGH_VALUE_SECTIONS:
        score += 0.25
        positive.append(f"{canonical_section} 章节")
    elif canonical_section in MEDIUM_VALUE_SECTIONS:
        score += 0.08
        positive.append(f"{canonical_section} 章节")
    elif canonical_section in NOISE_SECTIONS:
        score -= 0.35
        flags.append("noise_section")
        negative.append(f"{canonical_section} 属于低优先级或噪声章节")
    else:
        score -= 0.12
        flags.append("unknown_section")
        negative.append("未识别章节")

    lower = snippet.lower()
    matched_terms = [
        term for term in (target_terms or []) if term and str(term).lower() in lower
    ]
    if matched_terms:
        bonus = min(0.18, 0.08 + 0.03 * len(matched_terms))
        score += bonus
        positive.append("匹配主题词: " + ", ".join(matched_terms[:4]))
    else:
        score -= 0.08
        flags.append("weak_theme_match")
        negative.append("与目标主题只有弱匹配")

    content_bonus_count = 0
    for label, pattern, bonus in CONTENT_BONUSES:
        if re.search(pattern, lower):
            score += bonus
            content_bonus_count += 1
            positive.append(label)

    length = len(snippet)
    if 120 <= length <= 520:
        score += 0.08
        positive.append("片段长度适中")
    elif 60 <= length < 120:
        score += 0.02
    elif 45 <= length < 60:
        score -= 0.08
        flags.append("short_context")
        negative.append("片段上下文偏短")
    elif length < 45:
        score -= 0.25
        negative.append("片段过短")
    else:
        score -= 0.12
        negative.append("片段过长")

    if content_bonus_count == 0 and len(matched_terms) <= 1:
        flags.append("generic_or_weak")
        score -= 0.08
        negative.append("缺少具体方法、组件、评估或证据处理细节")

    penalties = {
        "reference_like": 0.35,
        "url_heavy": 0.25,
        "code_or_prompt": 0.3,
        "table_like": 0.25,
        "metadata_noise": 0.25,
        "citation_dense": 0.15,
        "layout_artifact": 0.2,
        "too_short": 0.25,
        "too_long": 0.15,
        "short_context": 0.08,
        "figure_caption": 0.15,
        "empty_after_cleaning": 0.5,
    }
    for flag in sorted(set(flags)):
        penalty = penalties.get(flag)
        if penalty:
            score -= penalty
            negative.append(flag)

    score = max(0.0, min(1.0, score))
    quality_flags = sorted(set(flags))
    explanation = (
        "加分：" + ("、".join(positive) if positive else "无")
        + "；扣分：" + ("、".join(negative) if negative else "无")
    )
    return {
        "snippet": snippet,
        "section": canonical_section,
        "snippet_score": round(score, 3),
        "snippet_score_explanation": explanation,
        "quality_flags": quality_flags,
    }


def confidence_from_score(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"
