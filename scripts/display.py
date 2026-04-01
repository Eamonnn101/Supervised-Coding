"""Terminal output formatting using rich."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt
from rich.table import Table
from rich.text import Text

from schemas import PatchReview, PlanOutput, PlanReview, ValidationResult

console = Console()

VERDICT_COLORS = {
    "pass": "green",
    "revise": "yellow",
    "block": "red",
}


def show_step(step: int, total: int, description: str) -> None:
    """Show a workflow step indicator."""
    console.print(f"\n[bold cyan][{step}/{total}][/bold cyan] {description}")


def show_plan_summary(plan: PlanOutput) -> None:
    """Display the plan in a formatted panel."""
    lines = [f"[bold]Goal:[/bold] {plan.goal}", ""]

    if plan.files:
        lines.append("[bold]Files:[/bold]")
        for f in plan.files:
            lines.append(f"  - {f}")
        lines.append("")

    if plan.steps:
        lines.append("[bold]Steps:[/bold]")
        for i, s in enumerate(plan.steps, 1):
            lines.append(f"  {i}. {s}")
        lines.append("")

    if plan.risks:
        lines.append("[bold]Risks:[/bold]")
        for r in plan.risks:
            lines.append(f"  [{r.severity}] {r.title}")

    console.print(Panel("\n".join(lines), title="Implementation Plan", border_style="blue"))


def show_review(review: PlanReview | PatchReview) -> None:
    """Display a review verdict with color coding."""
    verdict = review.verdict.lower()
    color = VERDICT_COLORS.get(verdict, "white")
    label = "Plan Review" if isinstance(review, PlanReview) else "Patch Review"

    lines = [
        f"[bold]Verdict:[/bold] [{color}]{verdict.upper()}[/{color}]",
        f"[bold]Summary:[/bold] {review.summary_for_user}",
    ]

    if isinstance(review, PlanReview):
        if review.missing_requirements:
            lines.append("\n[bold]Missing Requirements:[/bold]")
            for m in review.missing_requirements:
                lines.append(f"  - {m}")
        if review.incorrect_assumptions:
            lines.append("\n[bold]Incorrect Assumptions:[/bold]")
            for a in review.incorrect_assumptions:
                lines.append(f"  - {a}")

    if review.risks:
        lines.append("\n[bold]Risks:[/bold]")
        for r in review.risks:
            sev_color = {"high": "red", "medium": "yellow", "low": "green"}.get(r.severity, "white")
            lines.append(f"  [{sev_color}][{r.severity}][/{sev_color}] {r.title}: {r.evidence}")

    if review.suggestions:
        lines.append("\n[bold]Suggestions:[/bold]")
        for s in review.suggestions:
            lines.append(f"  [{s.id}] ({s.priority}) {s.action}")
            if s.rationale:
                lines.append(f"       Rationale: {s.rationale}")

    console.print(Panel("\n".join(lines), title=label, border_style=color))


def prompt_user_choice(options: list[str]) -> int:
    """Show numbered options and return the user's choice (1-indexed)."""
    console.print("\n[bold]Please choose:[/bold]")
    for i, opt in enumerate(options, 1):
        console.print(f"  {i}. {opt}")

    return IntPrompt.ask("Your choice", choices=[str(i) for i in range(1, len(options) + 1)])


def show_validation_results(results: list[ValidationResult]) -> None:
    """Display validation results in a table."""
    table = Table(title="Validation Results")
    table.add_column("Command", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Exit Code", justify="center")

    for r in results:
        status = Text("PASS", style="green") if r.passed else Text("FAIL", style="red")
        table.add_row(r.command, status, str(r.exit_code))

    console.print(table)


def show_error(message: str) -> None:
    """Display an error message."""
    console.print(Panel(message, title="Error", border_style="red"))


def show_success(message: str) -> None:
    """Display a success message."""
    console.print(Panel(message, title="Done", border_style="green"))
