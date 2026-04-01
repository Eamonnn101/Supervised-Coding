"""Subprocess wrapper for invoking Codex CLI and Claude Code CLI."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)


class OrchestratorError(Exception):
    """Base exception for orchestrator errors."""


class CLITimeoutError(OrchestratorError):
    """CLI command timed out."""


class CLIExecutionError(OrchestratorError):
    """CLI command returned non-zero exit code."""


class OutputParseError(OrchestratorError):
    """Failed to parse JSON from CLI output."""


class CLINotFoundError(OrchestratorError):
    """Required CLI tool is not installed."""


def check_cli_available(cli_name: str) -> None:
    """Verify that a CLI tool is available on PATH."""
    if not shutil.which(cli_name):
        raise CLINotFoundError(
            f"'{cli_name}' not found on PATH. Please install it first."
        )


def _parse_json_output(raw: str, step_name: str, runtime_dir: str) -> dict:
    """Parse JSON from CLI output with multiple fallback strategies."""
    # Strategy 1: direct parse
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass

    # Strategy 2: strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*\n?", "", raw).strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        pass

    # Strategy 3: extract first JSON object via brace matching
    start = raw.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[start : i + 1])
                    except json.JSONDecodeError:
                        break

    # All strategies failed — save raw output for debugging
    debug_path = Path(runtime_dir) / f"debug_{step_name}_raw.txt"
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    debug_path.write_text(raw, encoding="utf-8")
    raise OutputParseError(
        f"Failed to parse JSON from {step_name} output. Raw output saved to {debug_path}"
    )


def _extract_text_from_claude_json(raw: str) -> str:
    """Extract text content from Claude's JSON output format.

    Claude with --output-format json returns a JSON array of message objects.
    We need to extract the text content from assistant messages.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw

    # Claude outputs a list of message events; find assistant text
    if isinstance(data, list):
        texts = []
        for item in data:
            if isinstance(item, dict):
                # Handle {"type": "result", "result": "text"} format
                if item.get("type") == "result" and isinstance(item.get("result"), str):
                    return item["result"]
                # Handle {"role": "assistant", "content": [{"type": "text", "text": "..."}]}
                if item.get("role") == "assistant":
                    for block in item.get("content", []):
                        if isinstance(block, dict) and block.get("type") == "text":
                            texts.append(block["text"])
        if texts:
            return "\n".join(texts)

    # If it's a dict with a "result" key
    if isinstance(data, dict):
        if "result" in data:
            return data["result"]

    return raw


def run_writer(
    prompt: str,
    config: Config,
    step_name: str = "writer",
    cwd: str | None = None,
    timeout: int | None = None,
) -> dict:
    """Call Codex CLI and return parsed JSON output."""
    check_cli_available(config.writer_cli)
    timeout = timeout or config.timeout_seconds

    cmd = [
        config.writer_cli,
        "exec",
        "--model", config.writer_model,
        "--full-auto",
        "--skip-git-repo-check",
        prompt,
    ]

    logger.info(f"Running writer: {config.writer_cli} exec (model={config.writer_model})")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or config.project_root,
        )
    except subprocess.TimeoutExpired as e:
        raise CLITimeoutError(
            f"Writer CLI timed out after {timeout}s. Partial output: {e.stdout[:200] if e.stdout else 'none'}"
        )

    if result.returncode != 0:
        logger.error(f"Writer stderr: {result.stderr[:500]}")
        raise CLIExecutionError(
            f"Writer CLI exited with code {result.returncode}: {result.stderr[:300]}"
        )

    return _parse_json_output(result.stdout, step_name, config.runtime_dir)


def run_reviewer(
    prompt: str,
    config: Config,
    step_name: str = "reviewer",
    timeout: int | None = None,
) -> dict:
    """Call Claude Code CLI and return parsed JSON output."""
    check_cli_available(config.reviewer_cli)
    timeout = timeout or config.timeout_seconds

    cmd = [
        config.reviewer_cli,
        "-p",
        prompt,
        "--output-format", "json",
        "--max-turns", "1",
    ]

    logger.info(f"Running reviewer: {config.reviewer_cli} -p (model implied)")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=config.project_root,
        )
    except subprocess.TimeoutExpired as e:
        raise CLITimeoutError(
            f"Reviewer CLI timed out after {timeout}s. Partial output: {e.stdout[:200] if e.stdout else 'none'}"
        )

    if result.returncode != 0:
        logger.error(f"Reviewer stderr: {result.stderr[:500]}")
        raise CLIExecutionError(
            f"Reviewer CLI exited with code {result.returncode}: {result.stderr[:300]}"
        )

    # Claude with --output-format json wraps content in message objects
    text_content = _extract_text_from_claude_json(result.stdout)
    return _parse_json_output(text_content, step_name, config.runtime_dir)
