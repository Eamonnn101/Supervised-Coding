"""Git utilities: validation, diff collection, change manifest."""

from __future__ import annotations

import subprocess
from pathlib import Path

from schemas import ChangeManifest


def validate_git_repo(project_root: str) -> bool:
    """Check if project_root is a valid git repo."""
    return (Path(project_root) / ".git").exists()


def ensure_git_initialized(project_root: str) -> None:
    """Ensure the target project has a git repo for diff tracking.

    If no .git exists, initializes one and creates a baseline commit.
    Used by CI/headless mode (main.py) to bootstrap projects without git.
    """
    git_dir = Path(project_root) / ".git"
    if git_dir.exists():
        return

    subprocess.run(["git", "init"], cwd=project_root, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=project_root, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline before AI changes", "--allow-empty"],
        cwd=project_root, capture_output=True,
    )


def create_snapshot(project_root: str, message: str = "snapshot before AI implementation") -> None:
    """Stage all and commit as a snapshot baseline for diff tracking."""
    subprocess.run(["git", "add", "-A"], cwd=project_root, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message, "--allow-empty"],
        cwd=project_root, capture_output=True,
    )


def get_change_manifest(project_root: str) -> ChangeManifest:
    """Collect a structured manifest of all changes: staged, unstaged, untracked."""
    staged = []
    unstaged = []
    untracked = []

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_root, capture_output=True, text=True,
    )

    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        index_status = line[0]
        worktree_status = line[1]
        filepath = line[3:]

        if index_status == "?":
            untracked.append(filepath)
        else:
            if index_status in ("A", "M", "D", "R"):
                staged.append(filepath)
            if worktree_status in ("M", "D"):
                unstaged.append(filepath)

    return ChangeManifest(staged=staged, unstaged=unstaged, untracked=untracked)


def get_full_diff(project_root: str) -> str:
    """Collect a comprehensive diff including tracked changes and full content of new files."""
    parts = []

    # 1. Diff of tracked files (staged + unstaged vs HEAD)
    result = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=project_root, capture_output=True, text=True,
    )
    if result.stdout.strip():
        parts.append(result.stdout)

    # 2. Full content of untracked files (new files not in git yet)
    manifest = get_change_manifest(project_root)
    for filepath in manifest.untracked:
        full_path = Path(project_root) / filepath
        if full_path.is_file():
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                parts.append(f"\n--- NEW FILE: {filepath} ---\n{content}\n")
            except Exception:
                parts.append(f"\n--- NEW FILE: {filepath} (binary or unreadable) ---\n")

    return "\n".join(parts)


def get_loc_delta(project_root: str) -> str:
    """Get lines added/removed summary."""
    result = subprocess.run(
        ["git", "diff", "HEAD", "--stat"],
        cwd=project_root, capture_output=True, text=True,
    )
    lines = result.stdout.strip().split("\n")
    if lines:
        return lines[-1].strip()  # e.g. "3 files changed, 120 insertions(+), 5 deletions(-)"
    return ""


def run_workflow_checks(project_root: str, runtime_dir: str, validation_results: list) -> dict:
    """Run workflow-level integrity checks."""
    checks = {}

    # 1. Git repo valid
    checks["git_repo_valid"] = validate_git_repo(project_root)

    # 2. Manifest complete (we can collect it)
    manifest = get_change_manifest(project_root)
    has_changes = bool(manifest.staged or manifest.unstaged or manifest.untracked)
    checks["manifest_complete"] = has_changes

    # 3. Validations present (at least one validation command was run)
    checks["validations_present"] = len(validation_results) > 0

    # 4. Required validations passed
    if validation_results:
        checks["required_validations_passed"] = all(v.passed for v in validation_results)
    else:
        checks["required_validations_passed"] = False

    # 5. Artifacts isolated (runtime dir is NOT inside project_root)
    runtime_resolved = str(Path(runtime_dir).resolve())
    project_resolved = str(Path(project_root).resolve())
    checks["artifacts_isolated"] = not runtime_resolved.startswith(project_resolved)

    return checks
