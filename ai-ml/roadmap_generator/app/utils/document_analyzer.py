"""
Deep content analysis for mode="document" roadmap generation.

Goes beyond plain keyword extraction (topic_extractor.py, used by
mode="topic"/"quiz_performance" fallback paths): identifies the
document's actual sub-topics/sub-modules in a logical learning order,
and for each, what KINDS of content it contains — formulas, diagrams,
numerical problems, examples, case studies, practical exercises —
so the generated roadmap can name real sub-topics and tell the
student exactly what to study, practice, and revise, instead of a
fixed "Learn the basics -> Practice -> Revise" shape regardless of
document.
"""

import json

from groq import Groq

from roadmap_generator.app.config import GROQ_API_KEY, GROQ_MODEL
MAX_INPUT_CHARS = 18000


def analyze_document_content(full_text: str, max_sections: int = 10) -> list[dict]:
    """
    Returns a list of section dicts, ordered the way they logically
    build on each other for learning (not necessarily the document's
    original page order):

      {
        "sub_module": str,
        "key_concepts": [str],
        "formulas": [str],
        "diagrams": [str],
        "numericals": bool,
        "examples": [str],
        "case_studies": [str],
        "exercises": [str],
      }

    Fields are empty/false when that kind of content genuinely isn't
    present — the model is explicitly instructed not to invent
    content that isn't in the material.
    """
    if not full_text or not full_text.strip():
        return []
    if len(full_text) > MAX_INPUT_CHARS:
        full_text = full_text[:MAX_INPUT_CHARS]

    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""
    Analyze the following study material and break it into its real
    sub-topics/sub-modules, in a logical learning order (foundational
    concepts before advanced ones).

    For EACH sub-topic, identify:
    - key_concepts: the main ideas/terms covered
    - formulas: any named formulas or equations present (plain text)
    - diagrams: any diagrams, architectures, or figures described or referenced
    - numericals: true if the material includes worked numerical problems or calculations for this sub-topic, else false
    - examples: short descriptions of worked examples present
    - case_studies: short descriptions of case studies or applied scenarios present
    - exercises: short descriptions of practice problems/exercises present

    Only include items that are ACTUALLY present in the material —
    use empty lists or false for anything not present. Do not invent
    content.

    Identify at most {max_sections} sub-topics.

    Respond with ONLY a JSON array, no other text, in this exact shape:
    [
      {{
        "sub_module": "...",
        "key_concepts": ["...", "..."],
        "formulas": ["..."],
        "diagrams": ["..."],
        "numericals": true,
        "examples": ["..."],
        "case_studies": [],
        "exercises": ["..."]
      }}
    ]

    Study material:
    {full_text}
    """

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    raw = response.choices[0].message.content or ""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        sections = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"analyze_document_content: could not parse LLM response as JSON: {exc}"
        ) from exc

    return sections


def build_step_description(section: dict) -> str:
    """
    Composes a concrete, content-aware description from an analyzed
    section — explicitly calling out formulas/diagrams/numericals/
    examples/case studies/exercises when present, matching the
    phrasing style requested: "Practice the numerical problems
    related to X", "Study and understand the Y diagram", etc.
    """
    parts: list[str] = []
    sub_module = section.get("sub_module") or "this topic"

    concepts = section.get("key_concepts") or []
    if concepts:
        parts.append(f"Learn: {', '.join(concepts)}.")

    formulas = section.get("formulas") or []
    if formulas:
        parts.append(
            f"Review the key formulas and practice applying them: {', '.join(formulas)}."
        )

    diagrams = section.get("diagrams") or []
    if diagrams:
        parts.append(f"Study and understand the following diagram(s): {', '.join(diagrams)}.")

    if section.get("numericals"):
        parts.append(f"Practice the numerical problems related to {sub_module}.")

    examples = section.get("examples") or []
    if examples:
        parts.append(f"Work through the examples: {', '.join(examples)}.")

    case_studies = section.get("case_studies") or []
    if case_studies:
        parts.append(f"Review the case study: {', '.join(case_studies)}.")

    exercises = section.get("exercises") or []
    if exercises:
        parts.append(f"Complete the practice exercises: {', '.join(exercises)}.")

    if not parts:
        parts.append(f"Study and revise {sub_module}.")

    return " ".join(parts)


def estimate_duration(section: dict) -> str:
    """
    Lightweight heuristic duration estimate based on how much content
    a section actually has — avoids a second LLM call just for
    timing. Not a guarantee, just a reasonable suggestion.
    """
    richness = (
        len(section.get("key_concepts") or [])
        + len(section.get("formulas") or [])
        + len(section.get("diagrams") or [])
        + (1 if section.get("numericals") else 0)
        + len(section.get("examples") or [])
        + len(section.get("case_studies") or [])
        + len(section.get("exercises") or [])
    )

    if richness <= 3:
        return "1-2 days"
    if richness <= 6:
        return "2-3 days"
    return "3-4 days"