import json

import anthropic

from config import settings

LIMITATIONS_PROMPT = """You are extracting limitations from an ML paper.
Extract ONLY limitations explicitly acknowledged by the authors themselves.
Do not infer limitations — only report what the paper admits.

Return a JSON array of strings:
["<one limitation per item>"]

If no limitations are stated, return [].
Return ONLY the JSON array. No preamble, no explanation, no markdown fences."""

OPEN_PROBLEMS_PROMPT = """You are extracting future work and open problems from an ML paper.
Extract explicit future work items and open questions stated by the authors.
These are things the authors say remain to be done, could be improved, or are worth investigating.

Return a JSON array of strings:
["<one future work item per string>"]

If no future work is stated, return [].
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


async def extract_limitations(paper_text: str) -> list[str]:
    return await _extract_list(LIMITATIONS_PROMPT, paper_text)


async def extract_open_problems(paper_text: str) -> list[str]:
    return await _extract_list(OPEN_PROBLEMS_PROMPT, paper_text)
