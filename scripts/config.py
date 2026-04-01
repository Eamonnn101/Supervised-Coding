"""Configuration loading, validation, and task session management."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml


@dataclass
class Config:
    project_name: str = "unnamed-project"
    writer_model: str = "gpt-5.4"
    reviewer_model: str = "claude-sonnet-4-6"
    max_plan_revision: int = 1
    max_patch_revision: int = 1
    validation_commands: list[str] = field(default_factory=list)
    writer_cli: str = "codex"
    reviewer_cli: str = "claude"
    project_root: str = "."
    runtime_dir: str = "runtime"
    timeout_seconds: int = 300

    # Resolved at runtime — not from YAML
    task_id: str = ""
    task_runtime_dir: str = ""


def load_config(path: str) -> Config:
    """Load config from a YAML file and return a Config object."""
    config_path = Path(path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    config = Config(
        project_name=raw.get("project_name", Config.project_name),
        writer_model=raw.get("writer_model", Config.writer_model),
        reviewer_model=raw.get("reviewer_model", Config.reviewer_model),
        max_plan_revision=raw.get("max_plan_revision", Config.max_plan_revision),
        max_patch_revision=raw.get("max_patch_revision", Config.max_patch_revision),
        validation_commands=raw.get("validation_commands", []),
        writer_cli=raw.get("writer_cli", Config.writer_cli),
        reviewer_cli=raw.get("reviewer_cli", Config.reviewer_cli),
        project_root=raw.get("project_root", "."),
        runtime_dir=raw.get("runtime_dir", "runtime"),
        timeout_seconds=raw.get("timeout_seconds", Config.timeout_seconds),
    )

    # Resolve paths relative to config file location
    config_dir = config_path.parent
    config.project_root = str((config_dir / config.project_root).resolve())
    config.runtime_dir = str((config_dir / ".." / config.runtime_dir).resolve())

    return config


def init_task_session(config: Config, task_id: str = "") -> Config:
    """Initialize a task session with an isolated runtime directory.

    Creates runtime/<task_id>/ and sets config.task_runtime_dir.
    Returns the updated config.
    """
    if not task_id:
        task_id = "task-" + datetime.now().strftime("%Y%m%d-%H%M%S")

    config.task_id = task_id
    config.task_runtime_dir = str(Path(config.runtime_dir) / task_id)
    Path(config.task_runtime_dir).mkdir(parents=True, exist_ok=True)

    return config


def runtime_artifact_path(config: Config, filename: str) -> Path:
    """Return the path for an artifact stored at the runtime root."""
    path = Path(config.runtime_dir) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def task_artifact_path(config: Config, filename: str) -> Path:
    """Return the path for an artifact stored in the active task runtime dir."""
    runtime_dir = config.task_runtime_dir or config.runtime_dir
    path = Path(runtime_dir) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def skill_config_path(filename: str) -> Path:
    """Resolve a skill-owned config/policy file relative to the package root."""
    return Path(__file__).parent.parent / "config" / filename


def validate_project_root(config: Config, allow_missing: bool = False) -> None:
    """Validate that project_root is a git repo.

    Args:
        config: The project config.
        allow_missing: If True (Full Mode), skip the git check — the skill
            handles directory creation and git init with user confirmation.
            If False (Fast Mode), require an existing git repo.
    """
    if allow_missing:
        return

    project_path = Path(config.project_root)
    if not project_path.exists():
        raise RuntimeError(
            f"project_root does not exist: {config.project_root}\n"
            f"For new projects, use: /supervised-coding full <request>"
        )

    git_dir = project_path / ".git"
    if not git_dir.exists():
        raise RuntimeError(
            f"project_root is not a git repository: {config.project_root}\n"
            f"For new projects, use: /supervised-coding full <request>\n"
            f"For existing projects, run 'git init' in the target directory first."
        )
