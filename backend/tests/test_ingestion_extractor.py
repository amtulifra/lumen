import json
from unittest.mock import MagicMock, patch

import pytest

from ingestion.extractor import extract_knowledge
from tests.conftest import FAKE_EXTRACTED


def make_claude_response(content: str) -> MagicMock:
    message = MagicMock()
    message.content = [MagicMock(text=content)]
    return message


class TestExtractKnowledge:
    def test_parses_valid_json_response(self):
        valid_json = json.dumps(FAKE_EXTRACTED)

        with patch("ingestion.extractor.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create.return_value = make_claude_response(valid_json)

            result = extract_knowledge("some paper text")

        assert result["claims"][0]["text"] == FAKE_EXTRACTED["claims"][0]["text"]
        assert result["methods"][0]["name"] == "Self-Attention"
        assert result["benchmarks"][0]["value"] == 28.4

    def test_retries_on_invalid_json(self):
        valid_json = json.dumps(FAKE_EXTRACTED)

        with patch("ingestion.extractor.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create.side_effect = [
                make_claude_response("this is not json {{{"),
                make_claude_response(valid_json),
            ]

            result = extract_knowledge("some paper text")

        assert mock_client.messages.create.call_count == 2
        assert "claims" in result

    def test_raises_after_two_invalid_json_responses(self):
        with patch("ingestion.extractor.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create.return_value = make_claude_response("not json at all")

            with pytest.raises(json.JSONDecodeError):
                extract_knowledge("some paper text")

    def test_passes_paper_text_to_claude(self):
        valid_json = json.dumps(FAKE_EXTRACTED)
        paper_text = "This is a very specific paper about attention mechanisms."

        with patch("ingestion.extractor.anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create.return_value = make_claude_response(valid_json)

            extract_knowledge(paper_text)

        call_args = mock_client.messages.create.call_args
        assert paper_text in call_args.kwargs["messages"][0]["content"]
