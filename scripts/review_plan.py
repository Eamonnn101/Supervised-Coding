"""Step: Review implementation plan via Reviewer (Claude Code CLI).

Used by main.py (CI/headless mode) and as Final Gate subprocess in Escalate Mode.
In SKILL.md interactive mode, plan review is done in-context by the orchestrator.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from cli_runner import run_reviewer
from config import Config, task_artifact_path
from schemas import PlanOutput, PlanReview

logger = logging.getLogger(__name__)

REVIEW_SCHEMA = """{
  "verdict": "pass | revise | block",
  "summary_for_user": "string — concise summary for the user",
  "missing_requirements": ["list of requirements not addressed by the plan"],
  "incorrect_assumptions": ["list of wrong assumptions in the plan"],
  "risks": [{"severity": "low|medium|high", "title": "string", "evidence": "string"}],
  "suggestions": [{"id": "S1", "priority": "high|medium|low", "action": "string", "rationale": "string"}]
}"""


def _load_prompt_template() -> str:
    """Load the reviewer_plan.md prompt template."""
    template_path = Path(__file__).parent.parent / "prompts" / "reviewer_plan.md"
    return template_path.read_text(encoding="utf-8")


def review_plan(task: str, plan: PlanOutput, config: Config) -> PlanReview:
    """Review the implementation plan by calling the reviewer CLI."""
    template = _load_prompt_template()
    plan_json = json.dumps(plan.to_dict(), indent=2, ensure_ascii=False)

    prompt = (
        template
        .replace("{task_description}", task)
        .replace("{plan_json}", plan_json)
        .replace("{review_schema}", REVIEW_SCHEMA)
    )

    logger.info("Reviewing plan via reviewer CLI...")
    result = run_reviewer(prompt, config, step_name="review_plan")

    review = PlanReview.from_dict(result)

    # Save to task-specific runtime dir for isolation
    review_path = task_artifact_path(config, "review_plan.json")
    review_path.write_text(json.dumps(review.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Plan review saved to {review_path}")

    return review
