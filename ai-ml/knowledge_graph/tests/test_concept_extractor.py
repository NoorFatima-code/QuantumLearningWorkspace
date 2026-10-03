"""
Tests for concept_extractor.py. All Groq calls are mocked — these
test the module's own logic (JSON parsing, validation, fallback
safety), not the LLM itself.

Run: pytest knowledge_graph/tests/test_concept_extractor.py
"""
from unittest.mock import patch, MagicMock

import pytest

import knowledge_graph.app.utils.concept_extractor as ce


@pytest.fixture(autouse=True)
def reset_client():
    ce._client = None
    yield
    ce._client = None


def test_missing_api_key_falls_back_to_empty_list(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert ce.extract_concepts("some text") == []


def test_empty_text_short_circuits():
    assert ce.extract_concepts("") == []
    assert ce.extract_concepts("   ") == []


def test_clean_response_parses_correctly(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    with patch("knowledge_graph.app.utils.concept_extractor.Groq") as MockGroq:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            '[{"name": "Supervised Learning", "level": "topic", "parent": null}, '
            '{"name": "Linear Regression", "level": "subtopic", "parent": "Supervised Learning"}]'
        )
        MockGroq.return_value.chat.completions.create.return_value = mock_response

        result = ce.extract_concepts("Linear regression is a supervised learning technique...")
        assert result == [
            {"name": "Supervised Learning", "level": "topic", "parent": None},
            {"name": "Linear Regression", "level": "subtopic", "parent": "Supervised Learning"},
        ]


def test_markdown_fenced_response_still_parses(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    with patch("knowledge_graph.app.utils.concept_extractor.Groq") as MockGroq:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            '```json\n[{"name": "Neural Networks", "level": "topic", "parent": null}]\n```'
        )
        MockGroq.return_value.chat.completions.create.return_value = mock_response

        result = ce.extract_concepts("Neural networks are...")
        assert result == [{"name": "Neural Networks", "level": "topic", "parent": None}]


def test_malformed_json_falls_back_safely(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    with patch("knowledge_graph.app.utils.concept_extractor.Groq") as MockGroq:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "this is not json at all"
        MockGroq.return_value.chat.completions.create.return_value = mock_response

        assert ce.extract_concepts("some text") == []


def test_invalid_entries_filtered_valid_ones_kept(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    with patch("knowledge_graph.app.utils.concept_extractor.Groq") as MockGroq:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = """[
            {"name": "Valid Topic", "level": "topic", "parent": null},
            {"name": "Bad Level Entry", "level": "nonsense", "parent": null},
            {"level": "topic", "parent": null},
            {"name": "Orphan Subtopic", "level": "subtopic", "parent": null},
            {"name": "Valid Topic", "level": "topic", "parent": null}
        ]"""
        MockGroq.return_value.chat.completions.create.return_value = mock_response

        result = ce.extract_concepts("some text")
        assert len(result) == 1
        assert result[0]["name"] == "Valid Topic"


def test_api_failure_falls_back_safely(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    with patch("knowledge_graph.app.utils.concept_extractor.Groq") as MockGroq:
        MockGroq.return_value.chat.completions.create.side_effect = Exception("network error")

        assert ce.extract_concepts("some text") == []


def test_non_list_response_falls_back_safely(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    with patch("knowledge_graph.app.utils.concept_extractor.Groq") as MockGroq:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"not": "a list"}'
        MockGroq.return_value.chat.completions.create.return_value = mock_response

        assert ce.extract_concepts("some text") == []