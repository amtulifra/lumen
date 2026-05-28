import io
import re

import httpx
import pdfplumber

SECTION_PRIORITY = ["abstract", "introduction", "method", "result", "conclusion", "limitation"]
CHARS_PER_TOKEN = 4
MAX_CHARS = 12000 * CHARS_PER_TOKEN


async def download_pdf(url: str) -> bytes:
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


def extract_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages)


def clean_text(raw: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", raw)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


def truncate_to_budget(text: str) -> str:
    if len(text) <= MAX_CHARS:
        return text

    sections: dict[str, str] = {}
    current_section = "preamble"
    current_lines: list[str] = []

    for line in text.splitlines():
        lower = line.lower().strip()
        matched = next((s for s in SECTION_PRIORITY if s in lower and len(line) < 80), None)
        if matched:
            sections[current_section] = "\n".join(current_lines)
            current_section = matched
            current_lines = [line]
        else:
            current_lines.append(line)

    sections[current_section] = "\n".join(current_lines)

    ordered = [sections.get(s, "") for s in SECTION_PRIORITY]
    ordered += [v for k, v in sections.items() if k not in SECTION_PRIORITY]

    separator = "\n\n"
    separator_cost = len(separator)
    budget = MAX_CHARS
    result_parts: list[str] = []

    for part in ordered:
        if budget <= 0:
            break
        if result_parts:
            budget -= separator_cost
        if budget <= 0:
            break
        chunk = part[:budget]
        result_parts.append(chunk)
        budget -= len(chunk)

    return separator.join(result_parts)


async def extract_paper_text(pdf_url: str) -> str:
    pdf_bytes = await download_pdf(pdf_url)
    raw = extract_text(pdf_bytes)
    cleaned = clean_text(raw)
    return truncate_to_budget(cleaned)
