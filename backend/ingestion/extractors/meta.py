import json

import anthropic

from config import settings

RELATED_WORK_PROMPT = """You are extracting the most important cited papers from an ML paper's related work.
Identify the 5-15 most significant papers cited, focusing on direct predecessors, baselines, and key related work.

Return a JSON array of exact paper titles as strings:
["<exact paper title>"]

Return ONLY the JSON array. No preamble, no explanation, no markdown fences."""

KEYWORDS_PROMPT = """You are extracting technical keywords from an ML paper.
Extract 5-10 technical terms that best characterize this paper's topic, methods, and contributions.
Use precise ML terminology (e.g., "attention mechanism", "contrastive learning", "sparse retrieval").

Return a JSON array of strings:
["<keyword>"]

Return ONLY the JSON array. No preamble, no explanation, no markdown fences."""


async def _extract_list(system_prompt: str, paper_text: str) -> list[str]:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def call(extra: str = "") -> str:
        msg = await client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": extra + paper_text}],
        )
        return msg.content[0].text

    raw = await call()
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        raw = await call("Return ONLY valid JSON array of strings, nothing else.\n\n")
        try:
            result = json.loads(raw)
            return result if isinstance(result, list) else []
        except json.JSONDecodeError:
            return []


async def extract_related_work(paper_text: str) -> list[str]:
    return await _extract_list(RELATED_WORK_PROMPT, paper_text)


async def extract_keywords(paper_text: str) -> list[str]:
    return await _extract_list(KEYWORDS_PROMPT, paper_text)
