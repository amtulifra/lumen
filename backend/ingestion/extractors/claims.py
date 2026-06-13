import json

import anthropic

from config import settings

SYSTEM_PROMPT = """You are extracting claims from an ML paper.
A claim is a core contribution or finding stated or clearly implied by the authors.
Focus on what the paper asserts as novel or scientifically important.
Extract 3-8 claims. Be precise and conservative — only include well-supported claims.

Return a JSON array:
[
  {
    "text": "<one sentence, the core contribution>",
    "confidence": <0.0-1.0, how explicitly stated vs implied>,
    "evidence_span": "<direct quote or close paraphrase from the paper body>",
    "section": "<best section label if known, e.g. abstract/method/results/discussion>",
    "page_number": <integer page number if known, otherwise null>
  }
]

Return ONLY the JSON array. No preamble, no explanation, no markdown fences."""


async def extract_claims(paper_text: str) -> list[dict]:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def call(extra: str = "") -> str:
        msg = await client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": extra + paper_text}],
        )
        return msg.content[0].text

    raw = await call()
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        raw = await call("Return ONLY valid JSON array, nothing else.\n\n")
        try:
            result = json.loads(raw)
            return result if isinstance(result, list) else []
        except json.JSONDecodeError:
            return []
