"""Step: Run configurable validation commands."""

from __future__ import annotations

import logging
import subprocess

from config import Config, task_artifact_path
from schemas import ValidationResult

logger = logging.getLogger(__name__)


def run_validations(config: Config) -> list[ValidationResult]:
    """Run all configured validation commands and collect results."""
    if not config.validation_commands:
        logger.warning("No validation commands configured. Skipping validation.")
        return []

    results: list[ValidationResult] = []
    all_output_lines: list[str] = []

    for cmd in config.validation_commands:
        logger.info(f"Running validation: {cmd}")
        all_output_lines.append(f"=== {cmd} ===")

        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=config.project_root,
            )
            result = ValidationResult(
                command=cmd,
                passed=proc.returncode == 0,
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            logger.warning(f"Validation command timed out: {cmd}")
            result = ValidationResult(
                command=cmd,
                passed=False,
                stdout="",
                stderr="Command timed out after 120 seconds",
                exit_code=-1,
            )
        except FileNotFoundError:
            logger.warning(f"Validation command not found: {cmd}")
            result = ValidationResult(
                command=cmd,
                passed=False,
                stdout="",
                stderr=f"Command not found: {cmd}",
                exit_code=-1,
            )

        results.append(result)
        all_output_lines.append(f"Exit code: {result.exit_code}")
        if result.stdout:
            all_output_lines.append(result.stdout)
        if result.stderr:
            all_output_lines.append(f"STDERR: {result.stderr}")
        all_output_lines.append("")

    # Save combined output
    test_results_path = task_artifact_path(config, "test_results.txt")
    test_results_path.write_text("\n".join(all_output_lines), encoding="utf-8")
    logger.info(f"Validation results saved to {test_results_path}")

    return results
