"""Step: Generate final report."""

from __future__ import annotations

import logging
from datetime import datetime

from config import Config, task_artifact_path
from schemas import ApprovedReviewPlan, PatchReview, PlanOutput, PlanReview, ReviewPlan, ValidationResult, WriterSummary

logger = logging.getLogger(__name__)


def generate_report(
    task: str,
    plan: PlanOutput,
    plan_review: PlanReview,
    user_choice: str,
    writer_summary: WriterSummary,
    validations: list[ValidationResult],
    patch_review: PatchReview,
    had_patch_revision: bool,
    config: Config,
) -> str:
    """Generate a final markdown report and save to the active task runtime."""
    lines = [
        "# AI Supervised Coding — Final Report",
        f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Project**: {config.project_name}",
        f"**Writer Model**: {config.writer_model}",
        f"**Reviewer Model**: {config.reviewer_model or 'environment default'}",
        "",
        "---",
        "",
        "## Task",
        task,
        "",
        "---",
        "",
        "## Plan",
        f"**Goal**: {plan.goal}",
        "",
    ]

    if plan.steps:
        lines.append("**Steps**:")
        for i, s in enumerate(plan.steps, 1):
            lines.append(f"{i}. {s}")
        lines.append("")

    if plan.files:
        lines.append("**Files involved**: " + ", ".join(f"`{f}`" for f in plan.files))
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Plan Review",
        f"**Verdict**: {plan_review.verdict.upper()}",
        f"**Summary**: {plan_review.summary_for_user}",
        "",
    ])

    if plan_review.suggestions:
        lines.append("**Suggestions**:")
        for s in plan_review.suggestions:
            lines.append(f"- [{s.id}] ({s.priority}) {s.action}")
        lines.append("")

    lines.extend([
        f"**User Decision**: {user_choice}",
        "",
        "---",
        "",
        "## Implementation",
        f"**Executor**: {writer_summary.executor}",
        f"**Rationale**: {writer_summary.rationale}",
        "",
    ])

    if writer_summary.changed_files:
        lines.append("**Changed Files**:")
        for f in writer_summary.changed_files:
            lines.append(f"- `{f}`")
        lines.append("")

    if writer_summary.remaining_risks:
        lines.append("**Remaining Risks**:")
        for r in writer_summary.remaining_risks:
            lines.append(f"- {r}")
        lines.append("")

    lines.extend(["---", "", "## Validation Results", ""])

    if validations:
        lines.append("| Command | Status | Exit Code |")
        lines.append("|---------|--------|-----------|")
        for v in validations:
            status = "PASS" if v.passed else "FAIL"
            lines.append(f"| `{v.command}` | {status} | {v.exit_code} |")
    else:
        lines.append("_No validation commands configured._")

    lines.extend([
        "",
        "---",
        "",
        "## Patch Review",
        f"**Verdict**: {patch_review.verdict.upper()}",
        f"**Summary**: {patch_review.summary_for_user}",
        "",
    ])

    if patch_review.acceptance_checks:
        lines.append("**Acceptance Criteria**:")
        lines.append("")
        lines.append("| Criterion | Status | Evidence |")
        lines.append("|-----------|--------|----------|")
        for check in patch_review.acceptance_checks:
            status = "PASS" if check.get("met") else "FAIL"
            criterion = check.get("criterion", "")
            evidence = check.get("evidence", "")
            lines.append(f"| {criterion} | {status} | {evidence} |")
        lines.append("")

    if patch_review.risks:
        lines.append("**Risks**:")
        for r in patch_review.risks:
            lines.append(f"- [{r.severity}] {r.title}: {r.evidence}")
        lines.append("")

    if had_patch_revision:
        lines.append("_Note: A patch revision cycle was performed._")
        lines.append("")

    all_passed = all(v.passed for v in validations) if validations else True
    final_ok = patch_review.verdict == "pass" and all_passed

    lines.extend([
        "---",
        "",
        "## Final Status",
        f"**Overall**: {'SUCCESS' if final_ok else 'NEEDS ATTENTION'}",
    ])

    report_text = "\n".join(lines)

    report_path = task_artifact_path(config, "final_report.md")
    report_path.write_text(report_text, encoding="utf-8")
    logger.info(f"Final report saved to {report_path}")

    return str(report_path)


def generate_review_execution_report(
    task: str,
    review_plan: ReviewPlan,
    approved_review_plan: ApprovedReviewPlan,
    writer_summary: WriterSummary,
    validations: list[ValidationResult],
    change_manifest: dict,
    loc_delta: str,
    config: Config,
) -> str:
    """Generate a review-execution report in the active task runtime."""
    lines = [
        "# AI Supervised Coding — Review Execution Report",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Project**: {config.project_name}",
        f"**Executor**: {writer_summary.executor}",
        f"**Approved Executor**: {approved_review_plan.approved_executor}",
        "",
        "---",
        "",
        "## Review Task",
        task,
        "",
        "---",
        "",
        "## Approved Review Plan",
        f"**Goal**: {review_plan.goal}",
        f"**Scope**: {'; '.join(review_plan.scope) if review_plan.scope else '(none recorded)'}",
        f"**Out of Scope**: {'; '.join(review_plan.out_of_scope) if review_plan.out_of_scope else '(none recorded)'}",
        "",
    ]

    if review_plan.ordered_steps:
        lines.append("**Ordered Steps**:")
        for idx, step in enumerate(review_plan.ordered_steps, 1):
            lines.append(f"{idx}. {step.title}: {step.description}")
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## Execution Summary",
            f"**Rationale**: {writer_summary.rationale}",
            f"**LOC Delta**: {loc_delta or '(unavailable)'}",
            "",
        ]
    )

    if writer_summary.changed_files:
        lines.append("**Changed Files**:")
        for item in writer_summary.changed_files:
            lines.append(f"- `{item}`")
        lines.append("")

    if validations:
        lines.append("## Validation Results")
        lines.append("")
        lines.append("| Command | Status | Exit Code |")
        lines.append("|---------|--------|-----------|")
        for result in validations:
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"| `{result.command}` | {status} | {result.exit_code} |")
        lines.append("")

    lines.extend(
        [
            "## Change Manifest",
            f"- Staged: {len(change_manifest.get('staged', []))}",
            f"- Unstaged: {len(change_manifest.get('unstaged', []))}",
            f"- Untracked: {len(change_manifest.get('untracked', []))}",
        ]
    )

    if writer_summary.remaining_risks:
        lines.extend(["", "## Remaining Risks"])
        for risk in writer_summary.remaining_risks:
            lines.append(f"- {risk}")

    report_path = task_artifact_path(config, "review_execution_report.md")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(f"Review execution report saved to {report_path}")
    return str(report_path)
