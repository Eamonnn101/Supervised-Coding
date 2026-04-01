# AI Supervised Coding MVP

Dual-agent coding: Codex (writer) generates code, Claude Code (reviewer/orchestrator) reviews it. Writer feedback loop for continuous improvement.

## Usage (Primary: SKILL.md)

```
/supervised-coding <request>        Fast Mode (default)
/supervised-coding full <request>   Full Mode (new projects, major changes)
/supervised-coding review [focus]   Review Planning Mode (project improvement review)
```

**Primary orchestration**: `.claude/skills/supervised-coding/SKILL.md` — Claude Code is the orchestrator.
**CI/headless fallback**: `scripts/main.py` — for non-interactive pipelines only.

**Fast Mode**: Codex executes directly → validate → in-context review → writer feedback. Requires existing git repo.

**Full Mode**: Plan (with embedded requirements) → in-context plan review → execute → validate → patch review → writer feedback. Can bootstrap new projects.

**Review Planning Mode**: Claude reviews project goals, representative code, key config, and recent runtime history → saves `review_findings.json` + `review_plan.json` → user chooses Claude execute / Codex execute / save-only.

**Escalate Mode**: Auto-triggered from Fast when escalation thresholds are exceeded. Not manually invoked.

## Runtime Location

Runtime artifacts are stored **inside the target project** at `<project_root>/.supervised-coding/`, not in this tool repo. Each task gets an isolated subdirectory: `.supervised-coding/task-YYYYMMDD-HHMMSS/`.

Target projects should add `.supervised-coding/` to their `.gitignore`.

The `runtime_dir` config value is resolved relative to `project_root`. Default: `.supervised-coding`.

## Writer Feedback Loop (HARD REQUIREMENT)

Every patch review that produces `review_patch.json` generates `writer_feedback.json` with: verdict, must_fix, avoid_next_time, nice_to_have, writer_instruction, task_area, affected_files. Injected into writer's next prompt automatically. Only relevant feedback is injected (matched by task_area or file overlap).

**Auto-generation:** Feedback is generated from real `review_patch.json` artifacts via `generate_writer_feedback()` in `execute.py` or the `generate-feedback` CLI command. Feedback is only produced when a genuine reviewer judgment exists — never synthesized as a placeholder. Trigger: run immediately after every newly saved `review_patch.json` (first review + any re-review after fix cycle).

**Review Planning Mode** does not produce writer feedback (no patch review step exists).

## Task Isolation

Interactive/skill paths use isolated task runtimes: `.supervised-coding/task-YYYYMMDD-HHMMSS/` with all artifacts per task. `main.py` (CI/headless) still writes to the runtime root unless explicitly migrated to task sessions.

## Git Safety

Will NOT auto-init git in Fast Mode. Full Mode can bootstrap with user confirmation.

## Reviewer Model Precedence

1. **Explicit override**: set `reviewer_model` in config YAML → passed as `--model` to Claude CLI
2. **Environment default**: omit `reviewer_model` → inherits from the active Claude Code session

Interactive use should omit `reviewer_model`. CI/headless mode should set it explicitly.

## User-Facing Language

`user_language` config (default: `"auto"`). When user writes in Chinese, Claude responds in Chinese. Internal Codex communication (prompts, contracts, structured JSON) stays in English. See SKILL.md for full rules.

## Codex Execution Status

Periodic heartbeat status updates are logged while Codex runs (every 15s). States: starting → running → completed / failed / timed out. Claude should surface these to the user in their language.

## Key Files

- `.claude/skills/supervised-coding/` — Primary orchestration skill
- `scripts/codex_cli.py` — CLI tool: plan, plan-revise, fast, execute, fix, generate-feedback, validate, snapshot
- `scripts/review_project.py` — Bounded review-context gathering + review artifact persistence
- `scripts/review_execution.py` — Shared snapshot/validate/diff/manifest/report helpers for review execution
- `scripts/schemas.py` — Data structures: PlanOutput, PlanReview, WriterSummary, PatchReview, WriterFeedback
- `scripts/execute.py` — Writer execution with contract + scoped feedback injection
- `scripts/config.py` — Config + task session management
- `scripts/git_utils.py` — Git validation, diff, change manifest
- `scripts/main.py` — CI/headless orchestrator (not primary path)
- `config/review_policy.json` — Escalation + final gate thresholds
- `config/writer_contract.md` — Standing rules for the writer
