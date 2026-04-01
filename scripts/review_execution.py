"""Shared review execution helpers for Claude and Codex execution paths."""

from __future__ import annotations

import json
from pathlib import Path

from config import Config, task_artifact_path
from git_utils import create_snapshot, get_change_manifest, get_full_diff, get_loc_delta
from report import generate_review_execution_report
from review_project import approve_review_plan as _approve_review_plan
from schemas import ApprovedReviewPlan, ReviewPlan, WriterSummary
from validate import run_validations


def approve_review_plan(review_plan: ReviewPlan, executor: str, config: Config) -> ApprovedReviewPlan:
    """Persist the approved review plan for the chosen executor."""
    return _approve_review_plan(review_plan, executor, config)


def prepare_execution_baseline(config: Config, label: str) -> None:
    """Create a git snapshot baseline before executing a review plan."""
    create_snapshot(config.project_root, label)


def collect_post_execution_state(config: Config) -> dict:
    """Collect and persist shared post-execution artifacts."""
    validations = run_validations(config)
    manifest = get_change_manifest(config.project_root)
    full_diff = get_full_diff(config.project_root)
    loc_delta = get_loc_delta(config.project_root)

    manifest_path = task_artifact_path(config, "change_manifest.json")
    manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    full_diff_path = task_artifact_path(config, "full_diff.txt")
    full_diff_path.write_text(full_diff, encoding="utf-8")

    return {
        "validations": validations,
        "change_manifest": manifest,
        "change_manifest_path": manifest_path,
        "full_diff": full_diff,
        "full_diff_path": full_diff_path,
        "loc_delta": loc_delta,
    }


def save_execution_artifacts(
    task: str,
    review_plan: ReviewPlan,
    approved_review_plan: ApprovedReviewPlan,
    writer_summary: WriterSummary,
    execution_state: dict,
    config: Config,
) -> Path:
    """Generate the shared review execution report after code changes complete."""
    report_path = generate_review_execution_report(
        task=task,
        review_plan=review_plan,
        approved_review_plan=approved_review_plan,
        writer_summary=writer_summary,
        validations=execution_state["validations"],
        change_manifest=execution_state["change_manifest"].to_dict(),
        loc_delta=execution_state["loc_delta"],
        config=config,
    )
    return Path(report_path)
