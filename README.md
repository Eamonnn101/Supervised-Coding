# Supervised Coding

A dual-agent system where **Codex writes code** and **Claude reviews it**, with an automatic feedback loop that improves writer output over time.

Built as a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill. Claude Code acts as the orchestrator — it invokes Codex for code generation, performs in-context reviews, and manages the feedback cycle.

## How It Works

```
User Request
    │
    ├─ Fast Mode ──→ Execute → Validate → Review → Feedback
    │
    ├─ Full Mode ──→ Plan → Plan Review → Execute → Validate → Patch Review → Feedback
    │
    └─ Review Mode → Gather Context → Findings → Improvement Plan → Choose Executor
```

**Writer feedback loop**: Every patch review that produces `review_patch.json` automatically generates `writer_feedback.json`. This feedback is injected into the writer's next prompt — scoped by affected files and task area — so the writer learns from past reviews.

## Prerequisites

- Python 3.10+
- [Codex CLI](https://github.com/openai/codex) installed and authenticated
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated

```bash
codex --version
claude --version
```

## Setup

```bash
cd Supervised-Coding
pip install -r requirements.txt
```

Create a config for your project:

```bash
cp config/project.yaml config/my-project.yaml
```

Edit `config/my-project.yaml`:

```yaml
project_name: my-project
writer_cli: codex
writer_model: o3                    # Codex writer model
reviewer_cli: claude
# reviewer_model: claude-sonnet-4-6  # omit to inherit from Claude Code environment
project_root: ../../my-project      # relative to config/
runtime_dir: .supervised-coding     # relative to project_root
validation_commands:
  - npm test                        # your test commands
  - npm run lint
timeout_seconds: 300
max_plan_revision: 1
max_patch_revision: 1
user_language: auto                 # "auto", "zh", or "en"
```

## Usage

### Primary: Claude Code Skill

```
/supervised-coding <request>        Fast Mode (default, small changes)
/supervised-coding full <request>   Full Mode (new projects, major changes)
/supervised-coding review [focus]   Review Planning Mode (project improvement)
```

### CI / Headless

```bash
# With inline task
python scripts/main.py --task "Add user authentication" --config config/my-project.yaml

# With task file
python scripts/main.py --task-file task.md --config config/my-project.yaml

# Non-interactive (auto-revise on plan review)
python scripts/main.py --task "Fix login bug" --config config/my-project.yaml --non-interactive
```

## Modes

### Fast Mode

For small, focused changes on existing projects. Requires an existing git repo.

1. **Snapshot** — git baseline for diff tracking
2. **Execute** — Codex writes code directly (no plan)
3. **Validate** — run configured test/lint commands
4. **Review** — in-context patch review by Claude
5. **Feedback** — auto-generate `writer_feedback.json` from review

Escalation: if changes exceed thresholds (files, LOC, new deps, failed tests), automatically escalates to Full Mode.

### Full Mode

For new projects or major changes. Can bootstrap git repos.

1. **Plan** — Codex generates an implementation plan with requirements
2. **Plan Review** — Claude reviews the plan in-context
3. **User Decision** — approve, revise (max 1), or abandon
4. **Execute** — Codex implements the approved plan
5. **Validate** — run configured test/lint commands
6. **Patch Review** — Claude reviews the implementation. Optional Final Gate (subprocess) for large changes
7. **Feedback + Decision** — auto-generate feedback; fix cycle (max 1) if verdict is `revise`

### Review Planning Mode

For project-level improvement, not feature implementation.

1. **Gather Context** — bounded read of contracts, representative code, recent runtime history
2. **Review Findings** — Claude identifies issues, opportunities, recommended scope
3. **Improvement Plan** — ordered steps with risks and rollback points
4. **Choose Executor** — Claude execute (in-session) / Codex execute / save-only

## Output Artifacts

Each task gets an isolated runtime directory inside the target project: `<project_root>/.supervised-coding/task-YYYYMMDD-HHMMSS/`

**Important**: Add `.supervised-coding/` to your project's `.gitignore`.

| Artifact | Description |
|----------|-------------|
| `task.md` | Input task description |
| `plan.json` | Implementation plan (Full Mode) |
| `review_plan.json` | Plan review verdict + suggestions |
| `approved_plan.json` | Approved plan for execution |
| `writer_summary.json` | What the writer changed and why |
| `test_results.txt` | Validation command output |
| `review_patch.json` | Patch review verdict + suggestions |
| `writer_feedback.json` | Auto-generated feedback for next writer invocation |
| `final_report.md` | Complete workflow report |

Review Mode additionally produces: `review_findings.json`, `review_plan.json`, `approved_review_plan.json`, `review_report.md`, `review_execution_report.md`.

## Writer Feedback Loop

The core mechanism that makes the writer improve over time:

1. Every patch review saves structured `review_patch.json`
2. `generate-feedback` reads it and produces `writer_feedback.json` with: verdict, must_fix, avoid_next_time, nice_to_have, writer_instruction, task_area, affected_files
3. On the next writer invocation, `execute.py` loads relevant feedback (scoped by file overlap and task area) and injects it into the writer's prompt
4. The writer sees what to fix, what to avoid, and what went well

Feedback is only generated from real reviewer judgment — never synthesized as a placeholder.

## Review Verdicts

| Verdict | Meaning |
|---------|---------|
| **pass** | Ready to accept |
| **revise** | Specific improvements needed, direction is correct |
| **block** | Critical issues, needs manual intervention |

## CLI Commands

`scripts/codex_cli.py` provides subcommands used by the skill:

```
plan              Generate implementation plan
plan-revise       Revise plan per review feedback
fast              Execute without plan (Fast Mode)
execute           Execute approved plan (Full Mode)
fix               Targeted fix from patch review
generate-feedback Generate writer_feedback.json from review_patch.json
validate          Run validation commands
snapshot          Create git baseline
approve-review    Approve review plan for execution
prepare-review    Create baseline before review execution
execute-review    Execute approved review plan
finalize-review   Collect post-execution artifacts
```

## Project Structure

```
Supervised-Coding/
├── .claude/skills/supervised-coding/
│   └── SKILL.md              # Primary orchestration (Claude Code skill)
├── config/
│   ├── project.yaml           # Default config template
│   ├── project_contract.md    # Project-level rules
│   ├── writer_contract.md     # Standing rules for the writer
│   └── review_policy.json     # Escalation + final gate thresholds
├── prompts/
│   ├── writer_execute.md      # Full Mode writer prompt
│   ├── writer_fast.md         # Fast Mode writer prompt
│   ├── writer_execute_review.md # Review execution writer prompt
│   ├── writer_plan.md         # Plan generation prompt
│   ├── reviewer_patch.md      # Patch review prompt (subprocess)
│   └── reviewer_plan.md       # Plan review prompt (subprocess)
├── scripts/
│   ├── codex_cli.py           # CLI subcommands for skill
│   ├── execute.py             # Writer execution + feedback generation
│   ├── schemas.py             # Data structures
│   ├── config.py              # Config + task session management
│   ├── git_utils.py           # Git operations
│   ├── validate.py            # Validation runner
│   ├── report.py              # Report generation
│   ├── review_project.py      # Review mode context + artifacts
│   ├── review_execution.py    # Review execution helpers
│   ├── review_patch.py        # Patch review (subprocess)
│   ├── review_plan.py         # Plan review (subprocess)
│   ├── run_plan.py            # Plan generation
│   ├── cli_runner.py          # CLI invocation helpers
│   ├── display.py             # Terminal output formatting
│   └── main.py                # CI/headless orchestrator
├── CLAUDE.md                  # Project context for Claude Code
├── requirements.txt           # pyyaml, rich, click
└── .gitignore

# In the target project:
<project_root>/
└── .supervised-coding/          # Runtime artifacts (add to .gitignore)
    ├── task-YYYYMMDD-HHMMSS/    # Per-task isolated artifacts
    ├── writer_feedback.json     # Global latest feedback
    └── scores.tsv               # Metrics tracking
```

## Reviewer Model Precedence

1. **Explicit override**: set `reviewer_model` in config YAML → passed as `--model` to Claude CLI
2. **Environment default**: omit or leave empty → inherits from the active Claude Code session

For interactive use, omitting `reviewer_model` is recommended. For CI/headless mode, set it explicitly.

## Codex Execution Status

While Codex is running, periodic heartbeat status updates are logged every 15 seconds. States:

- **Starting**: Codex process launched
- **Running**: heartbeat every 15s with elapsed time
- **Completed**: Codex finished successfully
- **Failed**: Codex exited with an error
- **Timed out**: Codex exceeded the configured timeout

These are honest heartbeat-style updates — detailed per-step progress is not available from the Codex CLI.

## User-Facing Language

Set `user_language` in config (default: `"auto"`):
- `"auto"`: detect language from user's conversation
- `"zh"`: always respond to user in Chinese
- `"en"`: always respond in English

**Boundary**: All user-facing output (status, reviews, explanations) follows the user's language. Internal Codex communication (prompts, contracts, JSON artifacts) stays in English.

## Cost Optimization

- Reviewer model inherits from environment by default (no unnecessary model forcing)
- Reviews happen only at key checkpoints (plan + patch), not on every edit
- Max 1 plan revision + 1 patch revision bounds costs
- Review Mode uses bounded context with token budgets (max 10 project files, 5 recent tasks)
- Writer feedback is scoped — only relevant feedback is injected, not the full history

## License

MIT
