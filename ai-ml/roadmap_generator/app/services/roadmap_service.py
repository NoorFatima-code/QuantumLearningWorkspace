from roadmap_generator.app.generators.roadmap_generator import RoadmapGenerator
from roadmap_generator.app.models.topic import Topic
from roadmap_generator.app.models.roadmap import Roadmap, RoadmapStep
from roadmap_generator.app.validators.topic_validator import (
    validate_topic_names,
    validate_step_count,
)
from roadmap_generator.app.utils.document_analyzer import (
    analyze_document_content,
    build_step_description,
    estimate_duration,
)
from roadmap_generator.app.config import DEFAULT_STEP_COUNT

from embedding.chroma_store import get_document_chunks

# Cross-module import, same convention already used elsewhere
# (e.g. weak_topic_detection/app/main.py importing quiz_generator's
# auth) — not an HTTP call, a direct Python import within the same
# codebase.
from weak_topic_detection.app.services.weak_topic_service import WeakTopicService


class RoadmapService:
    """
    Coordinates roadmap generation across all three supported modes:
      - "topic"            — caller supplies topic names directly
      - "document"          — deep content analysis of an ingested document
      - "quiz_performance"  — topics come from Weak Topic Detection's output
    """

    def __init__(self):
        self.generator = RoadmapGenerator()
        self._weak_topic_service: WeakTopicService | None = None

    def _get_weak_topic_service(self) -> WeakTopicService:
        # Lazy — avoids paying WeakTopicService's init cost for
        # callers who only ever use mode="topic" or mode="document".
        if self._weak_topic_service is None:
            self._weak_topic_service = WeakTopicService()
        return self._weak_topic_service

    # ------------------------------------------------------------------
    # mode="topic" — unchanged
    # ------------------------------------------------------------------
    def generate_roadmap(
        self,
        topic_names: list[str],
        subject: str = "",
        step_count: int = DEFAULT_STEP_COUNT,
        priorities: dict[str, str] | None = None,
    ) -> Roadmap:
        validate_topic_names(topic_names)
        validate_step_count(step_count)

        priorities = priorities or {}
        topics = [Topic(name=name, priority=priorities.get(name)) for name in topic_names]

        return self.generator.generate(topics, subject=subject, step_count=step_count)

    # ------------------------------------------------------------------
    # mode="document" — now content-aware
    # ------------------------------------------------------------------
    def generate_roadmap_from_document(
        self,
        user_id: str,
        document_id: str,
        subject: str = "",
        step_count: int = DEFAULT_STEP_COUNT,
    ) -> Roadmap:
        """
        Builds a roadmap from an already-ingested document's actual
        content — not just keyword topics. Identifies real
        sub-modules/sub-topics in logical learning order, and for
        each, surfaces the specific formulas, diagrams, numerical
        problems, examples, case studies, and exercises it actually
        contains, so each step tells the student concretely what to
        study, practice, and revise — grounded in the real document,
        not generic placeholders.

        Ownership of the document (document_id + user_id) is enforced
        by get_document_chunks() — a caller can't analyze a document
        that isn't theirs.

        Step descriptions are built deterministically from the
        analysis (build_step_description), not from a second free-form
        LLM generation pass — this keeps wording grounded in exactly
        what was extracted, with no risk of the roadmap mentioning a
        formula or diagram that isn't actually in the document.
        """
        validate_step_count(step_count)

        chunks = get_document_chunks(document_id=document_id, user_id=user_id)
        if not chunks:
            raise ValueError(
                f"No content found for document_id '{document_id}'. It may not "
                "exist, may still be processing, or may belong to another user."
            )

        full_text = "\n\n".join(chunks)
        sections = analyze_document_content(full_text, max_sections=step_count)
        if not sections:
            raise ValueError("Could not analyze any content for this document.")

        steps = [
            RoadmapStep(
                step_number=idx + 1,
                topic=section.get("sub_module") or f"Topic {idx + 1}",
                description=build_step_description(section),
                estimated_duration=estimate_duration(section),
            )
            for idx, section in enumerate(sections[:step_count])
        ]

        return Roadmap(
            subject=subject or f"Document {document_id}",
            steps=steps,
            total_steps=len(steps),
        )

    # ------------------------------------------------------------------
    # mode="quiz_performance" — unchanged
    # ------------------------------------------------------------------
    def generate_roadmap_from_quiz_performance(
        self,
        user_id: str,
        subject: str = "",
        step_count: int = DEFAULT_STEP_COUNT,
    ) -> Roadmap:
        """
        Builds a roadmap focused on topics the user is weak in, using
        Weak Topic Detection's output. Weak topics are marked "high"
        priority so the generator sequences them early.

        NOTE (known limitation): WeakTopicService currently reads a
        static demo dataset, not this user's live quiz history.
        """
        validate_step_count(step_count)

        weak_topics = self._get_weak_topic_service().get_weak_topics()
        if not weak_topics:
            raise ValueError(
                "No weak topics found — take a quiz first to get a personalized roadmap."
            )

        topic_names = [wt.get("topic", "Unknown Topic") for wt in weak_topics]
        topics = [Topic(name=name, priority="high") for name in topic_names]

        return self.generator.generate(
            topics,
            subject=subject or "Focus Areas From Your Quiz Performance",
            step_count=step_count,
        )