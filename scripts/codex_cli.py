#!/usr/bin/env python3
"""Standalone CLI for invoking Codex operations. Used by Claude Code skills.

Usage:
    python3 scripts/codex_cli.py plan --task "..." --config config/project.yaml --task-id task-20260330-023000
    python3 scripts/codex_cli.py plan-revise --task "..." --review-file <path>/review_plan.json --config ... --task-id ...
    python3 scripts/codex_cli.py execute --task "..." --config ... --task-id ...
    python3 scripts/codex_cli.py approve-review --executor codex --config ... --task-id ...
    python3 scripts/codex_cli.py prepare-review --config ... --task-id ...
    python3 scripts/codex_cli.py execute-review --task "..." --config ... --task-id ...
    python3 scripts/codex_cli.py finalize-review --config ... --task-id ...
    python3 scripts/codex_cli.py fix --task "..." --review-file <path>/review_patch.json --config ... --task-id ...
    python3 scripts/codex_cli.py generate-feedback --config ... --task-id ...
    python3 scripts/codex_cli.py validate --config ... --task-id ...
    python3 scripts/codex_cli.py snapshot --config ...
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import click

from cli_runner import run_writer
from config import load_config, init_task_session, task_artifact_path, validate_project_root
from review_execution import (
    approve_review_plan as approve_review_execution_plan,
    collect_post_execution_state,
    prepare_execution_baseline,
    save_execution_artifacts,
)
from schemas import ApprovedReviewPlan, PatchReview, PlanOutput, PlanReview, ReviewPlan, WriterSummary
from run_plan import generate_plan, generate_revised_plan
from execute import execute_fast, execute_fix, execute_plan, execute_review_plan, generate_writer_feedback
from validate import run_validations
from git_utils import create_snapshot, validate_git_repo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")


def _load_and_init(config_path: str, task_id: str):
    """Load config, validate git, init task session."""
    config = load_config(config_path)
    validate_project_root(config)
    if task_id:
        init_task_session(config, task_id)
    else:
        init_task_session(config)
    return config


@click.group()
def cli():
    """Codex CLI operations for AI Supervised Coding."""
    pass


@cli.command()
@click.option("--task", "-t", required=True, help="Task description")
@click.option("--config", "-c", "config_path", default="config/project.yaml")
@click.option("--task-id", default="", help="Task session ID")
def plan(task, config_path, task_id):
    """Generate an implementation plan via Codex."""
    config = _load_and_init(config_path, task_id)

    # Save task
    (Path(config.task_runtime_dir) / "task.md").write_text(task, encoding="utf-8")

    result = generate_plan(task, config)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


@cli.command("plan-revise")
@click.option("--task", "-t", required=True, help="Task description")
@click.option("--review-file", required=True, help="Path to review_plan.json")
@click.option("--config", "-c", "config_path", default="config/project.yaml")
@click.option("--task-id", default="", help="Task session ID")
def plan_revise(task, review_file, config_path, task_id):
    """Generate a revised plan incorporating review feedback."""
    config = _load_and_init(config_path, task_id)

    plan_path = Path(config.task_runtime_dir) / "plan.json"
    original_plan = PlanOutput.from_dict(json.loads(plan_path.read_text(encoding="utf-8")))
    review = PlanReview.from_dict(json.loads(Path(review_file).read_text(encoding="utf-8")))

    result = generate_revised_plan(task, review, original_plan, config)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


@cli.command()
@click.option("--task", "-t", required=True, help="Task description")
@click.option("--config", "-c", "config_path", default="config/project.yaml")
@click.option("--task-id", default="", help="Task session ID")
def fast(task, config_path, task_id):
    """Execute a task directly in Fast Mode (no plan)."""
    config = _load_and_init(config_path, task_id)

    # Save task
    (Path(config.task_runtime_dir) / "task.md").write_text(task, encoding="utf-8")

    result = execute_fast(task, config)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


@cli.command()
@click.option("--task", "-t", required=True, help="Task description")
@click.option("--config", "-c", "config_path", default="config/project.yaml")
@click.option("--task-id", default="", help="Task session ID")
def execute(task, config_path, task_id):
    """Execute the approved plan via Codex."""
    config = _load_and_init(config_path, task_id)

    approved_path = Path(config.task_runtime_dir) / "approved_plan.json"
    if not approved_path.exists():
        click.echo("Error: No approved_plan.json found. Run plan-review first.", err=True)
        sys.exit(1)

    approved_plan = PlanOutput.from_dict(json.loads(approved_path.read_text(encoding="utf-8")))
    result = execute_plan(task, approved_plan, config)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


@cli.command("approve-review")
@click.option("--executor", required=True, type=click.Choice(["claude", "codex", "save_only"]))
@click.option("--config", "-c", "config_path", default="config/project.yaml")
@click.option("--task-id", default="", help="Task session ID")
def approve_review(executor, config_path, task_id):
    """Approve the current review_plan.json for the chosen executor."""
    config = _load_and_init(config_path, task_id)

    review_plan_path = task_artifact_path(config, "review_plan.json")
    if not review_plan_path.exists():
        click.echo("Error: No review_plan.json found. Run review mode first.", err=True)
        sys.exit(1)

    review_plan = ReviewPlan.from_dict(json.loads(review_plan_path.read_text(encoding="utf-8")))
    approved = approve_review_execution_plan(review_plan, executor, config)
    print(json.dumps(approved.to_dict(), indent=2, ensure_ascii=False))


@cli.command("prepare-review")
@click.option("--config", "-c", "config_path", default="config/project.yaml")
@click.option("--task-id", default="", help="Task session ID")
@click.option("--label", default="snapshot before review execution")
def prepare_review(config_path, task_id, label):
    """Create the shared baseline snapshot for review-plan execution."""
    config = _load_and_init(config_path, task_id)
    prepare_execution_baseline(config, label)
    click.echo(f"Review execution baseline prepared: {label}")


@cli.command("execute-review")
@click.option("--task", "-t", required=True, help="Review task description")
@click.option("--config", "-c", "config_path", default="config/project.yaml")
@click.option("--task-id", default="", help="Task session ID")
def execute_review(task, config_path, task_id):
    """Execute the approved review plan via Codex."""
    config = _load_and_init(config_path, task_id)

    approved_path = task_artifact_path(config, "approved_review_plan.json")
    if not approved_path.exists():
        click.echo("Error: No approved_review_plan.json found. Run approve-review first.", err=True)
        sys.exit(1)

    (Path(config.task_runtime_dir) / "task.md").write_text(task, encoding="utf-8")
    approved_review_plan = ApprovedReviewPlan.from_dict(json.loads(approved_path.read_text(encoding="utf-8")))
    result = execute_review_plan(task, approved_review_plan, config)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


@cli.command("finalize-review")
@click.option("--config", "-c", "config_path", default="config/project.yaml")
@click.option("--task-id", default="", help="Task session ID")
def finalize_review(config_path, task_id):
    """Collect shared post-execution artifacts for review-plan execution."""
    config = _load_and_init(config_path, task_id)

    task_path = task_artifact_path(config, "task.md")
    approved_path = task_artifact_path(config, "approved_review_plan.json")
    summary_path = task_artifact_path(config, "writer_summary.json")
    if not approved_path.exists():
        click.echo("Error: Missing approved_review_plan.json.", err=True)
        sys.exit(1)

    task_text = task_path.read_text(encoding="utf-8").strip() if task_path.exists() else "Review execution"
    approved_plan = ApprovedReviewPlan.from_dict(json.loads(approved_path.read_text(encoding="utf-8")))
    review_plan = ReviewPlan.from_dict(json.loads(approved_path.read_text(encoding="utf-8")))
    execution_state = collect_post_execution_state(config)
    if summary_path.exists():
        writer_summary = WriterSummary.from_dict(json.loads(summary_path.read_text(encoding="utf-8")))
    else:
        manifest = execution_state["change_manifest"]
        changed_files = sorted(set(manifest.staged + manifest.unstaged + manifest.untracked))
        writer_summary = WriterSummary(
            executor=approved_plan.approved_executor,
            changed_files=changed_files,
            rationale=f"{approved_plan.approved_executor} executed the approved review plan in-session.",
            remaining_risks=[],
        )
        summary_path.write_text(json.dumps(writer_summary.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    report_path = save_execution_artifacts(
        task=task_text,
        review_plan=review_plan,
        approved_review_plan=approved_plan,
        writer_summary=writer_summary,
        execution_state=execution_state,
        config=config,
    )
    click.echo(f"Review execution finalized: {report_path}")


@cli.command()
@click.option("--task", "-t", required=True, help="Task description")
@click.option("--review-file", required=True, help="Path to review_patch.json")
@click.option("--config", "-c", "config_path", default="config/project.yaml")
@click.option("--task-id", default="", help="Task session ID")
def fix(task, review_file, config_path, task_id):
    """Execute a targeted fix based on patch review feedback."""
    config = _load_and_init(config_path, task_id)

    approved_path = Path(config.task_runtime_dir) / "approved_plan.json"
    approved_plan = PlanOutput.from_dict(json.loads(approved_path.read_text(encoding="utf-8")))
    patch_review = PatchReview.from_dict(json.loads(Path(review_file).read_text(encoding="utf-8")))

    result = execute_fix(task, approved_plan, patch_review, config)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


@cli.command("generate-feedback")
@click.option("--config", "-c", "config_path", default="config/project.yaml")
@click.option("--task-id", default="", help="Task session ID")
def generate_feedback(config_path, task_id):
    """Generate writer_feedback.json from review_patch.json in the active task runtime.

    Requires review_patch.json to exist (real reviewer judgment).
    Prefers writer_summary_fix.json over writer_summary.json for enrichment.
    """
    config = _load_and_init(config_path, task_id)

    review_path = task_artifact_path(config, "review_patch.json")
    if not review_path.exists():
        click.echo("Error: No review_patch.json found. Cannot generate feedback without a real review.", err=True)
        sys.exit(1)

    patch_review = PatchReview.from_dict(json.loads(review_path.read_text(encoding="utf-8")))

    # Prefer fix-cycle summary (most recent changed_files), fall back to original
    writer_summary = None
    for name in ("writer_summary_fix.json", "writer_summary.json"):
        summary_path = task_artifact_path(config, name)
        if summary_path.exists():
            writer_summary = WriterSummary.from_dict(json.loads(summary_path.read_text(encoding="utf-8")))
            break

    feedback = generate_writer_feedback(config, patch_review=patch_review, writer_summary=writer_summary)
    click.echo(f"Writer feedback generated (verdict={feedback.verdict}, must_fix={len(feedback.must_fix)})")
    click.echo(f"  Task: {task_artifact_path(config, 'writer_feedback.json')}")
    click.echo(f"  Global: {Path(config.runtime_dir) / 'writer_feedback.json'}")


@cli.command()
@click.option("--config", "-c", "config_path", default="config/project.yaml")
@click.option("--task-id", default="", help="Task session ID")
def validate(config_path, task_id):
    """Run validation commands."""
    config = _load_and_init(config_path, task_id)
    results = run_validations(config)
    print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))


@cli.command()
@click.option("--config", "-c", "config_path", default="config/project.yaml")
@click.option("--message", "-m", default="snapshot before AI implementation")
def snapshot(config_path, message):
    """Create a git snapshot (stage all + commit) for diff tracking."""
    config = load_config(config_path)
    validate_project_root(config)
    create_snapshot(config.project_root, message)
    click.echo(f"Snapshot created: {message}")


if __name__ == "__main__":
    cli()
