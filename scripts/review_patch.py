"""Step: Review code patch via Reviewer (Claude Code CLI).

Used by main.py (CI/headless mode), as Final Gate subprocess in Full Mode
(when changes exceed thresholds), and for independent review in Escalate Mode.
In SKILL.md interactive mode, patch review is done in-context by default.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from cli_runner import run_reviewer
from config import Config, task_artifact_path
from schemas import PatchReview, PlanOutput, WriterSummary

logger = logging.getLogger(__name__)

PATCH_REVIEW_SCHEMA = """{
  "verdict": "pass | revise | block",
  "summary_for_user": "string — concise summary for the user",
  "risks": [{"severity": "low|medium|high", "title": "string", "evidence": "string"}],
  "suggestions": [{"id": "P1", "priority": "high|medium|low", "action": "string", "rationale": "string"}],
  "acceptance_checks": [{"criterion": "string", "met": true|false, "evidence": "string"}]
}"""


def _load_prompt_template() -> str:
    """Load the reviewer_patch.md prompt template."""
    template_path = Path(__file__).parent.parent / "prompts" / "reviewer_patch.md"
    return template_path.read_text(encoding="utf-8")


def review_patch(
    task: str,
    approved_plan: PlanOutput,
    writer_summary: WriterSummary,
    git_diff: str,
    test_results: str,
    config: Config,
) -> PatchReview:
    """Review the code patch by calling the reviewer CLI."""
    template = _load_prompt_template()
    plan_json = json.dumps(approved_plan.to_dict(), indent=2, ensure_ascii=False)
    summary_json = json.dumps(writer_summary.to_dict(), indent=2, ensure_ascii=False)

    # Format acceptance criteria from the plan
    acceptance_criteria = "\n".join(
        f"- {c}" for c in approved_plan.acceptance_criteria
    ) if approved_plan.acceptance_criteria else "(no acceptance criteria defined)"

    prompt = (
        template
        .replace("{task_description}", task)
        .replace("{approved_plan_json}", plan_json)
        .replace("{git_diff}", git_diff or "(no diff available)")
        .replace("{test_results}", test_results or "(no test results)")
        .replace("{writer_summary_json}", summary_json)
        .replace("{patch_review_schema}", PATCH_REVIEW_SCHEMA)
        .replace("{acceptance_criteria}", acceptance_criteria)
    )

    logger.info("Reviewing patch via reviewer CLI...")
    result = run_reviewer(prompt, config, step_name="review_patch")

    review = PatchReview.from_dict(result)

    # Save to task-specific runtime dir for isolation
    review_path = task_artifact_path(config, "review_patch.json")
    review_path.write_text(json.dumps(review.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Patch review saved to {review_path}")

    return review
