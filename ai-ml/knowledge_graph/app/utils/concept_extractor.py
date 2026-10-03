"""
[Objective 6] Extracts a topic hierarchy from a document's text —
broad topics, their sub-topics, and specific concepts — rather than
treating a document as one flat blob. This is the foundation for
building real hierarchy in the knowledge graph (e.g. Machine Learning
-> Supervised Learning -> Linear Regression -> Cost Function), instead
of only connecting whole documents by similarity.

Uses Groq (same provider as relationship_classifier.py and
definition_generator.py) — no new API dependency.

Falls back to an empty list on any failure (missing key, network
error, malformed JSON) so a bad extraction never breaks graph
building — callers should treat an empty list as "no concepts
extracted for this document" rather than an error.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent.parent / ".env")

VALID_LEVELS = {"topic", "subtopic", "concept"}

_PROMPT_TEMPLATE = """Extract the key topics, sub-topics, and specific concepts covered in this document, as a hierarchy.

Rules:
- "topic": a broad subject area (e.g. "Supervised Learning")
- "subtopic": a narrower area within a topic (e.g. "Linear Regression")
- "concept": a specific, concrete idea within a subtopic (e.g. "Cost Function")
- Each subtopic/concept should reference its parent by exact name via "parent"
- "topic" entries have parent: null
- Extract at most 8 items total. Only include things actually covered in the text, not inferred.
- Respond with ONLY a JSON array, no other text, no markdown fences.

Format:
[{{"name": "Supervised Learning", "level": "topic", "parent": null}}, {{"name": "Linear Regression", "level": "subtopic", "parent": "Supervised Learning"}}]

Document text:
{text}

JSON array:"""

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        _client = Groq(api_key=api_key)
    return _client


def _validate_concepts(raw: list) -> list:
    """
    Filters out malformed entries rather than rejecting the whole
    batch — one bad entry from the LLM shouldn't discard everything
    else it got right.
    """
    valid = []
    names_seen = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        level = item.get("level")
        parent = item.get("parent")

        if not name or not isinstance(name, str):
            continue
        if level not in VALID_LEVELS:
            continue
        if level == "topic" and parent is not None:
            parent = None  # topics are always root-level, ignore a spurious parent
        if level != "topic" and (not parent or not isinstance(parent, str)):
            continue  # subtopic/concept without a valid parent is unusable
        if name in names_seen:
            continue  # drop duplicates

        names_seen.add(name)
        valid.append({"name": name, "level": level, "parent": parent})

    return valid


def extract_concepts(text: str, model: str = "openai/gpt-oss-20b") -> list:
    """
    Returns a list of {"name": str, "level": "topic"|"subtopic"|"concept", "parent": str|None}.
    Returns [] on any failure or if nothing could be confidently extracted.
    """
    if not text or not text.strip():
        return []

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": _PROMPT_TEMPLATE.format(text=text[:3000]),
            }],
            temperature=0.2,
            max_tokens=500,
            reasoning_effort="low",
        )
        raw_output = response.choices[0].message.content.strip()

        # strip accidental markdown fences, since models sometimes add them
        # despite being told not to
        if raw_output.startswith("```"):
            raw_output = raw_output.strip("`")
            if raw_output.startswith("json"):
                raw_output = raw_output[4:]
            raw_output = raw_output.strip()

        parsed = json.loads(raw_output)
        if not isinstance(parsed, list):
            return []

        return _validate_concepts(parsed)

    except Exception:
        return []