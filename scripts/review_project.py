"""Review mode helpers: bounded context gathering and artifact persistence."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from config import Config, skill_config_path, task_artifact_path
from schemas import ApprovedReviewPlan, ReviewFindings, ReviewPlan

REVIEW_FINDINGS_FILE = "review_findings.json"
REVIEW_PLAN_FILE = "review_plan.json"
APPROVED_REVIEW_PLAN_FILE = "approved_review_plan.json"
REVIEW_REPORT_FILE = "review_report.md"

RULE_FILES = [
    "project_contract.md",
    "writer_contract.md",
    "review_policy.json",
]

CONFIG_PRIORITY_NAMES = [
    "package.json",
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "vite.config.js",
    "vite.config.ts",
    "next.config.js",
    "next.config.mjs",
    "webpack.config.js",
    "tsconfig.json",
]

SOURCE_PRIORITY_PARTS = [
    "src/main",
    "src/index",
    "src/app",
    "src/App",
    "app/",
    "pages/",
    "components/",
    "lib/",
]

RUNTIME_ARTIFACT_CANDIDATES = [
    "final_report.md",
    "review_patch.json",
    "writer_feedback.json",
    "review_plan.json",
    "approved_plan.json",
]


def _read_text_limited(path: Path, max_chars: int = 6000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"[read failed: {exc}]"
    return text[:max_chars]


def _score_project_file(path: Path) -> tuple[int, str]:
    rel = path.as_posix()
    score = 0
    if path.name in CONFIG_PRIORITY_NAMES:
        score += 100
    if any(part in rel for part in SOURCE_PRIORITY_PARTS):
        score += 60
    if path.suffix in {".ts", ".tsx", ".js", ".jsx", ".py", ".json", ".md", ".css", ".html"}:
        score += 20
    if "test" in rel.lower():
        score -= 15
    return score, rel


def _is_ignored_path(path: Path, runtime_root: Path) -> bool:
    ignored_parts = {".git", "node_modules", "dist", "build", "coverage", ".next", ".cache", "__pycache__"}
    if any(part in ignored_parts for part in path.parts):
        return True
    try:
        path.relative_to(runtime_root)
        return True
    except ValueError:
        return False


def _select_project_files(config: Config, max_files: int = 10) -> list[Path]:
    project_root = Path(config.project_root)
    runtime_root = Path(config.runtime_dir)
    candidates: list[Path] = []

    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        if _is_ignored_path(path, runtime_root):
            continue
        candidates.append(path.relative_to(project_root))

    ranked = sorted(candidates, key=_score_project_file, reverse=True)
    return [project_root / rel for rel in ranked[:max_files]]


def _task_relevance_score(task_dir: Path, review_direction: str) -> int:
    score = 0
    lowered_direction = review_direction.lower()
    for name in ("review_patch.json", "writer_feedback.json", "final_report.md"):
        path = task_dir / name
        if not path.exists():
            continue
        text = _read_text_limited(path, max_chars=4000).lower()
        if any(token in text for token in ("must_fix", "revise", "fail", "block", "critical")):
            score += 40
        if lowered_direction:
            for token in lowered_direction.split():
                if token and token in text:
                    score += 10
    return score


def _select_runtime_artifacts(task_dir: Path, review_direction: str, max_artifacts: int = 2) -> list[Path]:
    chosen: list[tuple[int, Path]] = []
    lowered_direction = review_direction.lower()
    for name in RUNTIME_ARTIFACT_CANDIDATES:
        path = task_dir / name
        if not path.exists():
            continue
        text = _read_text_limited(path, max_chars=3000).lower()
        score = 0
        if name == "final_report.md":
            score += 40
        if name in {"review_patch.json", "writer_feedback.json"}:
            score += 30
        if any(token in text for token in ("must_fix", "revise", "fail", "block", "critical")):
            score += 20
        if lowered_direction:
            for token in lowered_direction.split():
                if token and token in text:
                    score += 10
        chosen.append((score, path))
    return [path for _, path in sorted(chosen, key=lambda item: item[0], reverse=True)[:max_artifacts]]


def gather_review_context(
    config: Config,
    review_direction: str = "",
    max_code_files: int = 10,
    max_runtime_tasks: int = 5,
    max_selected_runtime_tasks: int = 5,
    max_artifacts_per_task: int = 2,
) -> dict:
    """Collect bounded context for review mode without scanning the whole repo."""
    rule_context = {
        name: _read_text_limited(skill_config_path(name), max_chars=5000)
        for name in RULE_FILES
        if skill_config_path(name).exists()
    }

    claude_path = Path(__file__).parent.parent / "CLAUDE.md"
    if claude_path.exists():
        rule_context["CLAUDE.md"] = _read_text_limited(claude_path, max_chars=5000)

    project_files = []
    for path in _select_project_files(config, max_files=max_code_files):
        project_files.append(
            {
                "path": str(path.relative_to(Path(config.project_root))),
                "content": _read_text_limited(path),
            }
        )

    runtime_root = Path(config.runtime_dir)
    task_dirs = []
    if runtime_root.exists():
        task_dirs = sorted(
            [path for path in runtime_root.iterdir() if path.is_dir() and path.name.startswith("task-")],
            key=lambda path: path.name,
            reverse=True,
        )[:max_runtime_tasks]

    ranked_tasks = sorted(
        task_dirs,
        key=lambda task_dir: (_task_relevance_score(task_dir, review_direction), task_dir.name),
        reverse=True,
    )[:max_selected_runtime_tasks]

    runtime_samples = []
    for task_dir in ranked_tasks:
        artifacts = []
        for path in _select_runtime_artifacts(task_dir, review_direction, max_artifacts=max_artifacts_per_task):
            artifacts.append(
                {
                    "path": str(path.relative_to(runtime_root)),
                    "content": _read_text_limited(path),
                }
            )
        if artifacts:
            runtime_samples.append({"task_id": task_dir.name, "artifacts": artifacts})

    git_status = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=config.project_root,
        capture_output=True,
        text=True,
    )

    return {
        "review_direction": review_direction,
        "project_root": config.project_root,
        "runtime_root": config.runtime_dir,
        "task_runtime_dir": config.task_runtime_dir,
        "validation_commands": config.validation_commands,
        "rules": rule_context,
        "project_files": project_files,
        "runtime_samples": runtime_samples,
        "project_state": {
            "git_status": git_status.stdout.strip(),
            "has_uncommitted_changes": bool(git_status.stdout.strip()),
        },
    }


def save_review_findings(findings: ReviewFindings, config: Config) -> Path:
    path = task_artifact_path(config, REVIEW_FINDINGS_FILE)
    path.write_text(json.dumps(findings.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def save_review_plan(review_plan: ReviewPlan, config: Config) -> Path:
    path = task_artifact_path(config, REVIEW_PLAN_FILE)
    path.write_text(json.dumps(review_plan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def approve_review_plan(review_plan: ReviewPlan, executor: str, config: Config) -> ApprovedReviewPlan:
    approved = ApprovedReviewPlan(
        goal=review_plan.goal,
        scope=review_plan.scope,
        out_of_scope=review_plan.out_of_scope,
        not_recommended_now=review_plan.not_recommended_now,
        recommended_executor=review_plan.recommended_executor,
        ordered_steps=review_plan.ordered_steps,
        risks=review_plan.risks,
        expected_benefits=review_plan.expected_benefits,
        approved_executor=executor,
        approved_at=datetime.now().isoformat(),
    )
    path = task_artifact_path(config, APPROVED_REVIEW_PLAN_FILE)
    path.write_text(json.dumps(approved.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return approved


def generate_review_report(
    findings: ReviewFindings,
    review_plan: ReviewPlan,
    config: Config,
    approved_plan: ApprovedReviewPlan | None = None,
) -> Path:
    """Create a concise human-readable review report in the task runtime dir."""
    lines = [
        "# AI Supervised Coding — Review Report",
        f"",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Project**: {config.project_name}",
        f"**Review Direction**: {findings.review_direction or 'General project review'}",
        "",
        "## Summary",
        f"- State: {findings.summary.project_state}",
        f"- Health: {findings.summary.health}",
        f"- Top Priority: {findings.summary.top_priority}",
        "",
        "## Key Findings",
    ]

    if findings.findings:
        for item in findings.findings:
            lines.append(f"- [{item.severity}] {item.title}: {item.why_it_matters}")
    else:
        lines.append("- No major findings recorded.")

    lines.extend(["", "## Opportunities"])
    if findings.opportunities:
        for item in findings.opportunities:
            lines.append(f"- [{item.area}/{item.priority}] {item.title}: {item.benefit}")
    else:
        lines.append("- No additional opportunities recorded.")

    lines.extend(["", "## Improvement Plan", f"- Goal: {review_plan.goal}"])
    if review_plan.scope:
        lines.append("- Scope: " + "; ".join(review_plan.scope))
    if review_plan.out_of_scope:
        lines.append("- Out of Scope: " + "; ".join(review_plan.out_of_scope))

    if review_plan.ordered_steps:
        lines.extend(["", "## Recommended Steps"])
        for step in review_plan.ordered_steps:
            lines.append(f"1. {step.title}: {step.description}")

    if approved_plan:
        lines.extend(
            [
                "",
                "## Approval",
                f"- Approved Executor: {approved_plan.approved_executor}",
                f"- Approved At: {approved_plan.approved_at}",
            ]
        )

    path = task_artifact_path(config, REVIEW_REPORT_FILE)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
