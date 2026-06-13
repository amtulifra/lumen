import re

SECTION_PATTERNS = {
    "abstract": re.compile(r"^\s*(abstract)\s*$", re.IGNORECASE),
    "introduction": re.compile(r"^\s*(\d+\.?\s*)?(introduction)\s*$", re.IGNORECASE),
    "method": re.compile(
        r"^\s*(\d+\.?\s*)?(method|methods|approach|methodology|experimental setup)\s*$",
        re.IGNORECASE,
    ),
    "results": re.compile(r"^\s*(\d+\.?\s*)?(results?|experiments?)\s*$", re.IGNORECASE),
    "discussion": re.compile(r"^\s*(\d+\.?\s*)?(discussion|analysis)\s*$", re.IGNORECASE),
    "limitations": re.compile(r"^\s*(\d+\.?\s*)?(limitations?)\s*$", re.IGNORECASE),
    "conclusion": re.compile(r"^\s*(\d+\.?\s*)?(conclusion|conclusions?)\s*$", re.IGNORECASE),
}

SECTION_ORDER = [
    "abstract",
    "introduction",
    "method",
    "results",
    "discussion",
    "limitations",
    "conclusion",
]

MIN_SECTION_CHARS = 120
MAX_SECTIONS = 8


def chunk_by_sections(paper_text: str) -> list[dict]:
    text = (paper_text or "").strip()
    if not text:
        return []

    chunks: list[dict] = []
    current_section = "preamble"
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        normalized = line.strip()
        if _is_heading_line(normalized):
            if current_lines:
                content = "\n".join(current_lines).strip()
                if len(content) >= MIN_SECTION_CHARS:
                    chunks.append({"section": current_section, "text": content})
            current_section = _classify_heading(normalized)
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        content = "\n".join(current_lines).strip()
        if len(content) >= MIN_SECTION_CHARS:
            chunks.append({"section": current_section, "text": content})

    if not chunks:
        return [{"section": "full_text", "text": text}]

    return _prioritize_chunks(chunks)


def _is_heading_line(line: str) -> bool:
    if not line or len(line) > 90:
        return False
    return any(pattern.match(line) for pattern in SECTION_PATTERNS.values())


def _classify_heading(line: str) -> str:
    for section, pattern in SECTION_PATTERNS.items():
        if pattern.match(line):
            return section
    return "other"


def _prioritize_chunks(chunks: list[dict]) -> list[dict]:
    rank = {name: i for i, name in enumerate(SECTION_ORDER)}
    ordered = sorted(
        chunks,
        key=lambda c: (rank.get(c["section"], 999), -len(c["text"])),
    )
    return ordered[:MAX_SECTIONS]
