"""Step: Generate implementation plan via Writer (Codex CLI)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from cli_runner import run_writer
from config import Config, task_artifact_path
from schemas import PlanOutput, PlanReview

logger = logging.getLogger(__name__)

PLAN_SCHEMA = """{
  "goal": "string — high-level objective",
  "must_have": ["key requirements extracted from the task"],
  "constraints": ["technical or scope constraints"],
  "out_of_scope": ["what NOT to do"],
  "tech_stack": "string — technology choices",
  "files": ["list of file paths to create or modify"],
  "steps": ["ordered list of implementation steps"],
  "risks": [{"severity": "low|medium|high", "title": "string", "evidence": "string"}],
  "test_strategy": "string — how to verify the implementation",
  "acceptance_criteria": ["list of verifiable criteria for success"]
}"""


def _load_prompt_template() -> str:
    """Load the writer_plan.md prompt template."""
    template_path = Path(__file__).parent.parent / "prompts" / "writer_plan.md"
    return template_path.read_text(encoding="utf-8")


def generate_plan(task: str, config: Config) -> PlanOutput:
    """Generate an implementation plan by calling the writer CLI."""
    template = _load_prompt_template()
    prompt = template.replace("{task_description}", task).replace("{plan_schema}", PLAN_SCHEMA)

    logger.info("Generating plan via writer CLI...")
    result = run_writer(prompt, config, step_name="plan")

    plan = PlanOutput.from_dict(result)

    # Save to task runtime dir
    plan_path = task_artifact_path(config, "plan.json")
    plan_path.write_text(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Plan saved to {plan_path}")

    return plan


def generate_revised_plan(
    task: str, review: PlanReview, original_plan: PlanOutput, config: Config
) -> PlanOutput:
    """Generate a revised plan incorporating review feedback."""
    template = _load_prompt_template()
    prompt = template.replace("{task_description}", task).replace("{plan_schema}", PLAN_SCHEMA)

    # Append revision context
    prompt += f"""

## Previous Plan (needs revision)
{json.dumps(original_plan.to_dict(), indent=2, ensure_ascii=False)}

## Review Feedback
Verdict: {review.verdict}
Summary: {review.summary_for_user}

Missing requirements: {json.dumps(review.missing_requirements, ensure_ascii=False)}
Incorrect assumptions: {json.dumps(review.incorrect_assumptions, ensure_ascii=False)}

Suggestions:
{json.dumps([s.__dict__ for s in review.suggestions], indent=2, ensure_ascii=False)}

Please revise the plan to address the above feedback. Output the revised plan in the same JSON format.
"""

    logger.info("Generating revised plan via writer CLI...")
    result = run_writer(prompt, config, step_name="plan_revised")

    plan = PlanOutput.from_dict(result)

    plan_path = task_artifact_path(config, "plan_revised.json")
    plan_path.write_text(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Revised plan saved to {plan_path}")

    return plan
