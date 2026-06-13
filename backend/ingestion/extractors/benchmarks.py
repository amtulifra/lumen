import json

import anthropic

from config import settings

SYSTEM_PROMPT = """You are extracting benchmark results from an ML paper.
Extract every dataset evaluation that reports a numerical result.
Be precise: use the exact dataset name, exact metric name, and exact numerical value (no % sign).

Return a JSON array:
[
  {
    "dataset": "<exact dataset name, e.g. ImageNet, MMLU, HumanEval>",
    "metric": "<exact metric name, e.g. top-1 accuracy, pass@1, BLEU>",
    "value": <number only, no % sign, e.g. 89.2>,
    "model": "<model or system name being evaluated>",
    "split": "<test/val/train/dev>",
    "prompt_method": "<cot/zero-shot/few-shot/none if not stated>",
    "benchmark_ver": "<benchmark version if stated>",
    "eval_framework": "<evaluation framework/setup if stated>",
    "notes": "<short caveat/context note>",
    "evidence_span": "<direct quote or close paraphrase of the reported result>"
  }
]

If no benchmark results are reported, return an empty array [].
Return ONLY the JSON array. No preamble, no explanation, no markdown fences."""


async def extract_benchmarks(paper_text: str) -> list[dict]:
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
