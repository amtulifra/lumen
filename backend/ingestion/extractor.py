import json

import anthropic

from config import settings

EXTRACTION_SYSTEM_PROMPT = """You are a structured ML paper extractor. Given a paper's full text, extract
a JSON object with EXACTLY these fields. Be precise and conservative.

{
  "claims": [
    {
      "text": "<one sentence, the core contribution>",
      "confidence": <0.0-1.0, how explicitly stated vs implied>,
      "evidence": "<direct quote or close paraphrase from paper>"
    }
  ],
  "methods": [
    {
      "name": "<method/technique/architecture name>",
      "description": "<one sentence>",
      "is_novel": <true if introduced in this paper, false if borrowed>
    }
  ],
  "benchmarks": [
    {
      "dataset": "<exact dataset name>",
      "metric": "<exact metric name>",
      "value": <number only, no % sign>,
      "model": "<model name being evaluated>",
      "split": "<test/val/train>"
    }
  ],
  "limitations": ["<one per item, stated by the authors>"],
  "open_problems": ["<explicit future work items stated in the paper>"],
  "related_work": ["<exact titles of papers they cite that matter most>"],
  "keywords": ["<5-10 technical terms that characterize this work>"]
}

Return ONLY the JSON object. No preamble, no explanation, no markdown fences."""


def extract_knowledge(paper_text: str) -> dict:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def call_claude(extra_context: str = "") -> str:
        user_content = extra_context + paper_text if extra_context else paper_text
        message = client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        return message.content[0].text

    raw_response = call_claude()

    try:
        return json.loads(raw_response)
    except json.JSONDecodeError as first_error:
        retry_context = (
            f"Previous attempt returned invalid JSON: {first_error}\n"
            "Return ONLY valid JSON, nothing else.\n\n"
        )
        raw_response = call_claude(retry_context)
        return json.loads(raw_response)
