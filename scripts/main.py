#!/usr/bin/env python3
"""AI Supervised Coding MVP — Main Orchestrator (CI/headless mode only).

For interactive use, use the /supervised-coding skill in Claude Code.
This script is kept for CI pipelines and non-interactive automation.

Usage:
    python scripts/main.py --task "Add a user profile page" --config config/project.yaml
    python scripts/main.py --task-file runtime/task.md --config config/project.yaml
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

# Add scripts directory to path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))

from cli_runner import CLINotFoundError, OrchestratorError, check_cli_available
from config import Config, load_config, task_artifact_path
from git_utils import create_snapshot, ensure_git_initialized, get_full_diff
from display import (
    console,
    show_error,
    show_plan_summary,
    show_review,
    show_step,
    show_success,
    show_validation_results,
    prompt_user_choice,
)
from execute import execute_fix, execute_plan, generate_writer_feedback
from report import generate_report
from review_patch import review_patch
from review_plan import review_plan
from run_plan import generate_plan, generate_revised_plan
from validate import run_validations

logger = logging.getLogger(__name__)

TOTAL_STEPS = 6


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def read_task(task: str | None, task_file: str | None) -> str:
    """Read task description from argument or file."""
    if task:
        return task
    if task_file:
        path = Path(task_file)
        if not path.exists():
            raise click.BadParameter(f"Task file not found: {task_file}")
        return path.read_text(encoding="utf-8").strip()
    raise click.UsageError("Either --task or --task-file is required.")


def save_task(task_text: str, config: Config) -> None:
    """Save the task description to runtime/task.md."""
    task_path = task_artifact_path(config, "task.md")
    task_path.write_text(task_text, encoding="utf-8")


@click.command()
@click.option("--task", "-t", help="Task description (natural language)")
@click.option("--task-file", "-f", help="Path to task description file")
@click.option(
    "--config", "-c", "config_path",
    default="config/project.yaml",
    help="Path to project config YAML",
)
@click.option("--non-interactive", is_flag=True, help="Run without user prompts")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def main(task, task_file, config_path, non_interactive, verbose):
    """AI Supervised Coding MVP — Orchestrate Writer + Reviewer agents."""
    setup_logging(verbose)

    # Load config
    try:
        config = load_config(config_path)
    except FileNotFoundError as e:
        show_error(str(e))
        sys.exit(1)

    Path(config.runtime_dir).mkdir(parents=True, exist_ok=True)

    # Check CLI tools are available
    try:
        check_cli_available(config.writer_cli)
        check_cli_available(config.reviewer_cli)
    except CLINotFoundError as e:
        show_error(str(e))
        sys.exit(1)

    # Read task
    try:
        task_text = read_task(task, task_file)
    except (click.BadParameter, click.UsageError) as e:
        show_error(str(e))
        sys.exit(1)

    save_task(task_text, config)
    console.print(f"\n[bold]Task:[/bold] {task_text[:200]}{'...' if len(task_text) > 200 else ''}")

    try:
        _run_workflow(task_text, config, non_interactive)
    except OrchestratorError as e:
        show_error(f"Workflow failed: {e}")
        console.print("[dim]Intermediate artifacts have been preserved in runtime/[/dim]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(130)


def _run_workflow(task_text: str, config: Config, non_interactive: bool) -> None:
    """Execute the full orchestration workflow."""

    # === Phase 1: Generate Plan ===
    show_step(1, TOTAL_STEPS, "Generating plan...")
    plan = generate_plan(task_text, config)
    show_plan_summary(plan)

    # === Phase 2: Review Plan ===
    show_step(2, TOTAL_STEPS, "Reviewing plan...")
    plan_rev = review_plan(task_text, plan, config)
    show_review(plan_rev)

    # === Phase 3: User Decision ===
    user_choice = "execute as-is"

    if plan_rev.verdict == "block":
        show_error("Plan blocked by reviewer. Please revise the task and try again.")
        sys.exit(1)

    if plan_rev.verdict == "revise":
        if non_interactive:
            choice = 2  # auto-revise in non-interactive mode
        else:
            choice = prompt_user_choice([
                "Execute with current plan",
                "Revise plan per review suggestions",
            ])

        if choice == 2:
            user_choice = "revised per review suggestions"
            console.print("[dim]Revising plan...[/dim]")
            plan = generate_revised_plan(task_text, plan_rev, plan, config)
            show_plan_summary(plan)

            # Re-review the revised plan
            plan_rev = review_plan(task_text, plan, config)
            show_review(plan_rev)

            if plan_rev.verdict == "block":
                show_error("Revised plan still blocked. Please revise manually.")
                sys.exit(1)

    approved_plan = plan

    # Ensure git baseline before code changes
    ensure_git_initialized(config.project_root)

    # Snapshot current state for diff
    create_snapshot(config.project_root, "snapshot before AI implementation")

    # === Phase 4: Execute ===
    show_step(3, TOTAL_STEPS, "Implementing code...")
    writer_summary = execute_plan(task_text, approved_plan, config)

    # === Phase 5: Validate ===
    show_step(4, TOTAL_STEPS, "Running validations...")
    validations = run_validations(config)
    if validations:
        show_validation_results(validations)
    else:
        console.print("[dim]No validation commands configured.[/dim]")

    # === Phase 6: Patch Review ===
    show_step(5, TOTAL_STEPS, "Reviewing patch...")
    git_diff = get_full_diff(config.project_root)
    test_results_path = task_artifact_path(config, "test_results.txt")
    test_results = test_results_path.read_text(encoding="utf-8") if test_results_path.exists() else ""

    patch_rev = review_patch(task_text, approved_plan, writer_summary, git_diff, test_results, config)
    show_review(patch_rev)
    generate_writer_feedback(config, patch_review=patch_rev, writer_summary=writer_summary)

    # === Patch Revision Loop ===
    had_patch_revision = False

    if patch_rev.verdict == "revise" and config.max_patch_revision > 0:
        console.print("[yellow]Patch needs revision. Running fix cycle...[/yellow]")
        had_patch_revision = True

        writer_summary = execute_fix(task_text, approved_plan, patch_rev, config)

        # Re-validate
        validations = run_validations(config)
        if validations:
            show_validation_results(validations)

        # Re-review
        git_diff = get_full_diff(config.project_root)
        test_results = test_results_path.read_text(encoding="utf-8") if test_results_path.exists() else ""
        patch_rev = review_patch(task_text, approved_plan, writer_summary, git_diff, test_results, config)
        show_review(patch_rev)
        generate_writer_feedback(config, patch_review=patch_rev, writer_summary=writer_summary)

    if patch_rev.verdict == "block":
        show_error("Patch blocked by reviewer. Manual intervention required.")
        # Still generate report before exiting

    # === Phase 7: Report ===
    show_step(6, TOTAL_STEPS, "Generating report...")
    report_path = generate_report(
        task=task_text,
        plan=approved_plan,
        plan_review=plan_rev,
        user_choice=user_choice,
        writer_summary=writer_summary,
        validations=validations,
        patch_review=patch_rev,
        had_patch_revision=had_patch_revision,
        config=config,
    )

    if patch_rev.verdict == "block":
        show_error(f"Workflow completed with BLOCK verdict. Report: {report_path}")
        sys.exit(1)
    else:
        show_success(f"Workflow completed successfully!\nReport: {report_path}")


if __name__ == "__main__":
    main()
