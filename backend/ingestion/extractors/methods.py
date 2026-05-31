import json

import anthropic

from config import settings

SYSTEM_PROMPT = """You are extracting methods from an ML paper.
A method is any technique, architecture, algorithm, training procedure, or approach used.
Distinguish between methods introduced in this paper (novel) and borrowed from prior work.

Return a JSON array:
[
  {
    "name": "<method/technique/architecture name>",
    "description": "<one sentence explaining what it does>",
    "is_novel": <true if first introduced in this paper, false if borrowed>
  }
]

Return ONLY the JSON array. No preamble, no explanation, no markdown fences."""


async def extract_methods(paper_text: str) -> list[dict]:
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
