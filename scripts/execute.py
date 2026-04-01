"""Step: Execute code implementation via Writer (Codex CLI)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from cli_runner import run_writer
from config import Config, skill_config_path, task_artifact_path
from schemas import ApprovedReviewPlan, PatchReview, PlanOutput, WriterFeedback, WriterSummary

logger = logging.getLogger(__name__)

SUMMARY_SCHEMA = """{
  "changed_files": ["list of files that were modified or created"],
  "rationale": "string — why these changes were made",
  "remaining_risks": ["list of known risks or TODOs"]
}"""

FAST_SUMMARY_SCHEMA = """{
  "changed_files": ["list of files modified or created"],
  "rationale": "why you made these specific changes",
  "remaining_risks": ["any known issues or edge cases"],
  "escalate_recommended": false,
  "escalate_reason": ""
}"""


def _load_writer_context(config: Config, target_files: list[str] | None = None) -> tuple[str, str]:
    """Load writer_contract.md and relevant writer_feedback.json entries.

    Returns (contract_text, feedback_section).
    The feedback_section is either empty or a formatted block ready to inject.

    Scoped injection (Change F): scans recent task directories for feedback,
    only injects feedback where affected_files overlap with target_files or
    task_area matches. Falls back to most recent feedback if no match found.
    """
    # Load writer contract
    contract_path = skill_config_path("writer_contract.md")
    if contract_path.exists():
        contract = contract_path.read_text(encoding="utf-8")
    else:
        contract = "(No writer contract found)"

    # Collect feedback from recent tasks
    feedback_entries = []
    runtime_base = Path(config.runtime_dir)

    # Scan task directories (sorted newest first)
    if runtime_base.exists():
        task_dirs = sorted(
            [d for d in runtime_base.iterdir() if d.is_dir() and d.name.startswith("task-")],
            key=lambda d: d.name,
            reverse=True,
        )[:5]  # Only check 5 most recent

        for task_dir in task_dirs:
            fb_path = task_dir / "writer_feedback.json"
            if fb_path.exists():
                try:
                    fb = json.loads(fb_path.read_text(encoding="utf-8"))
                    feedback_entries.append(fb)
                except (json.JSONDecodeError, KeyError):
                    pass

    # Also check global latest
    global_fb = runtime_base / "writer_feedback.json"
    if global_fb.exists() and not feedback_entries:
        try:
            fb = json.loads(global_fb.read_text(encoding="utf-8"))
            feedback_entries.append(fb)
        except (json.JSONDecodeError, KeyError):
            pass

    if not feedback_entries:
        return contract, ""

    # Filter for relevant feedback
    relevant = []
    fallback = feedback_entries[0] if feedback_entries else None

    for fb in feedback_entries:
        fb_files = set(fb.get("affected_files", []))
        fb_area = fb.get("task_area", "")

        # Check file overlap
        if target_files and fb_files:
            if fb_files & set(target_files):
                relevant.append(fb)
                continue

        # Note: task_area matching is not implemented yet because the current
        # task's area is unknown at this point (no plan in Fast Mode, plan not
        # yet parsed in Full Mode). For now, include any feedback with must_fix
        # items regardless of area, as these represent critical issues.
        if fb.get("must_fix"):
            relevant.append(fb)
            continue

    # If no relevant feedback found, use most recent as fallback
    if not relevant and fallback:
        relevant = [fallback]

    # Cap at 3 entries
    relevant = relevant[:3]

    # Format feedback section
    sections = []
    for i, fb in enumerate(relevant):
        lines = []
        if i == 0:
            lines.append("## Previous Review Feedback (you MUST address this)")
        else:
            lines.append(f"## Additional Relevant Feedback #{i + 1}")

        lines.append(f"Previous verdict: **{fb.get('verdict', 'unknown')}**")

        if fb.get("must_fix"):
            lines.append("\n**MUST FIX (mandatory — do these first):**")
            for item in fb["must_fix"]:
                lines.append(f"- {item}")

        if fb.get("avoid_next_time"):
            lines.append("\n**AVOID (do not repeat these):**")
            for item in fb["avoid_next_time"]:
                lines.append(f"- {item}")

        if fb.get("nice_to_have"):
            lines.append("\n**Nice to have (if easy):**")
            for item in fb["nice_to_have"]:
                lines.append(f"- {item}")

        if fb.get("writer_instruction"):
            lines.append(f"\n**Reviewer instruction:** {fb['writer_instruction']}")

        sections.append("\n".join(lines))

    feedback_section = "\n\n".join(sections)
    return contract, feedback_section


def _load_prompt_template(name: str = "writer_execute.md") -> str:
    """Load a prompt template by name."""
    template_path = Path(__file__).parent.parent / "prompts" / name
    return template_path.read_text(encoding="utf-8")


def _save_writer_summary(summary: WriterSummary, config: Config, filename: str = "writer_summary.json") -> Path:
    path = task_artifact_path(config, filename)
    path.write_text(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Writer summary saved to {path}")
    return path


def _infer_task_area(changed_files: list[str]) -> str:
    """Infer task area from file extensions/paths."""
    frontend_ext = {".tsx", ".jsx", ".css", ".scss", ".html", ".vue", ".svelte"}
    backend_ext = {".py", ".go", ".rs", ".java", ".rb"}
    config_ext = {".yaml", ".yml", ".toml", ".ini", ".env"}
    docs_ext = {".md", ".rst", ".txt"}

    counts: dict[str, int] = {}
    for f in changed_files:
        p = Path(f)
        suffix = p.suffix.lower()
        name = p.name.lower()

        if "test" in f.lower() or "spec" in f.lower():
            area = "testing"
        elif suffix in frontend_ext:
            area = "frontend"
        elif suffix in backend_ext:
            area = "backend"
        elif suffix in config_ext or name in {"package.json", "tsconfig.json", "dockerfile", "makefile"}:
            area = "config"
        elif suffix in docs_ext:
            area = "docs"
        else:
            area = "infra"

        counts[area] = counts.get(area, 0) + 1

    if not counts:
        return ""
    return max(counts, key=counts.get)


def generate_writer_feedback(
    config: Config,
    patch_review: PatchReview,
    writer_summary: WriterSummary | None = None,
) -> WriterFeedback:
    """Generate, enrich, and save writer_feedback.json from a real patch review.

    patch_review is mandatory — feedback is only generated from genuine reviewer judgment.
    writer_summary is optional enrichment for affected_files and task_area.
    Saves to both task-specific runtime (if set) and global runtime (latest).
    """
    feedback = WriterFeedback.from_review(patch_review)

    if writer_summary:
        feedback.affected_files = list(writer_summary.changed_files)
        feedback.task_area = _infer_task_area(writer_summary.changed_files)

    if config.task_runtime_dir:
        feedback.save(config.task_runtime_dir)
    feedback.save(config.runtime_dir)
    logger.info("Writer feedback saved (verdict=%s, must_fix=%d)", feedback.verdict, len(feedback.must_fix))
    return feedback


def execute_plan(task: str, approved_plan: PlanOutput, config: Config) -> WriterSummary:
    """Execute the approved plan by calling the writer CLI to modify code (Full Mode)."""
    approved_path = task_artifact_path(config, "approved_plan.json")
    approved_path.write_text(
        json.dumps(approved_plan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    template = _load_prompt_template("writer_execute.md")
    plan_json = json.dumps(approved_plan.to_dict(), indent=2, ensure_ascii=False)
    contract, feedback_section = _load_writer_context(config, target_files=approved_plan.files)

    prompt = (
        template
        .replace("{task_description}", task)
        .replace("{approved_plan_json}", plan_json)
        .replace("{summary_schema}", SUMMARY_SCHEMA)
        .replace("{writer_contract}", contract)
        .replace("{feedback_section}", feedback_section)
    )

    logger.info("Executing plan via writer CLI (Full Mode)...")
    result = run_writer(prompt, config, step_name="execute", cwd=config.project_root)

    summary = WriterSummary.from_dict(result)
    summary.executor = "codex"
    _save_writer_summary(summary, config)
    return summary


def execute_fast(task: str, config: Config) -> WriterSummary:
    """Execute a task directly without a plan (Fast Mode).

    Writer receives: task + writer_contract + latest feedback. No plan.
    """
    template = _load_prompt_template("writer_fast.md")
    contract, feedback_section = _load_writer_context(config)

    prompt = (
        template
        .replace("{task_description}", task)
        .replace("{writer_contract}", contract)
        .replace("{feedback_section}", feedback_section)
    )

    logger.info("Executing task via writer CLI (Fast Mode)...")
    result = run_writer(prompt, config, step_name="fast_execute", cwd=config.project_root)

    summary = WriterSummary.from_dict(result)
    summary.executor = "codex"
    _save_writer_summary(summary, config)
    return summary


def execute_fix(
    task: str,
    approved_plan: PlanOutput,
    patch_review: PatchReview,
    config: Config,
) -> WriterSummary:
    """Execute a targeted fix based on patch review feedback."""
    template = _load_prompt_template("writer_execute.md")
    plan_json = json.dumps(approved_plan.to_dict(), indent=2, ensure_ascii=False)
    contract, feedback_section = _load_writer_context(config, target_files=approved_plan.files)

    prompt = (
        template
        .replace("{task_description}", task)
        .replace("{approved_plan_json}", plan_json)
        .replace("{summary_schema}", SUMMARY_SCHEMA)
        .replace("{writer_contract}", contract)
        .replace("{feedback_section}", feedback_section)
    )

    # Append fix context from patch review
    prompt += f"""

## Patch Review Feedback (must be addressed)
Verdict: {patch_review.verdict}
Summary: {patch_review.summary_for_user}

Issues to fix:
{json.dumps([s.__dict__ for s in patch_review.suggestions], indent=2, ensure_ascii=False)}

Risks identified:
{json.dumps([r.__dict__ for r in patch_review.risks], indent=2, ensure_ascii=False)}

Please make targeted fixes to address the above issues. Minimize changes beyond what is needed.
"""

    logger.info("Executing targeted fix via writer CLI...")
    result = run_writer(prompt, config, step_name="execute_fix", cwd=config.project_root)

    summary = WriterSummary.from_dict(result)
    summary.executor = "codex"
    _save_writer_summary(summary, config, filename="writer_summary_fix.json")
    return summary


def execute_review_plan(task: str, approved_review_plan: ApprovedReviewPlan, config: Config) -> WriterSummary:
    """Execute an approved review plan via the writer CLI."""
    approved_path = task_artifact_path(config, "approved_review_plan.json")
    approved_path.write_text(
        json.dumps(approved_review_plan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    template = _load_prompt_template("writer_execute_review.md")
    plan_json = json.dumps(approved_review_plan.to_dict(), indent=2, ensure_ascii=False)
    target_files = []
    for step in approved_review_plan.ordered_steps:
        target_files.extend(step.affected_files)
    contract, feedback_section = _load_writer_context(config, target_files=target_files)

    prompt = (
        template
        .replace("{task_description}", task)
        .replace("{approved_review_plan_json}", plan_json)
        .replace("{summary_schema}", SUMMARY_SCHEMA)
        .replace("{writer_contract}", contract)
        .replace("{feedback_section}", feedback_section)
    )

    logger.info("Executing approved review plan via writer CLI...")
    result = run_writer(prompt, config, step_name="execute_review", cwd=config.project_root)

    summary = WriterSummary.from_dict(result)
    summary.executor = "codex"
    _save_writer_summary(summary, config)
    return summary
