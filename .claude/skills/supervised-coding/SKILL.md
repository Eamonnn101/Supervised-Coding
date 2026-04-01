---
name: supervised-coding
description: "Unified AI supervised coding workflow. Default is Fast Mode for small changes; prefix with 'full' for new projects or major changes. Use whenever the user wants to make code changes — features, bug fixes, refactoring. Always use this skill when the user says /supervised-coding."
---

# Supervised Coding

Codex (writer) generates code, you (reviewer/orchestrator) review it.

## Usage

```
/supervised-coding <request>        Fast Mode (default)
/supervised-coding full <request>   Full Mode (new projects, major changes)
/supervised-coding review [focus]   Review Planning Mode (project improvement review)
```

Tip: If the request is a brand-new project, use `full`.

---

## Mode Selection (simple rule)

**Parse the user's input after `/supervised-coding`:**

1. If the text starts with `full ` (case-insensitive) → **Full Mode**. Strip the `full ` prefix; the rest is the task.
2. If the text is exactly `review` or starts with `review ` (case-insensitive) → **Review Planning Mode**. Strip the `review` prefix; the rest is the optional focus string.
3. Otherwise → **Fast Mode**. The entire text is the task.
4. **Escalate Mode** is never selected directly — it triggers automatically from Fast Mode when escalation conditions are met.

That's it. No project-state inference, no "is this a new project?" guessing.

**One exception:** If you're in Fast Mode and the task is obviously asking to create an entirely new project (e.g. "build a Tetris game from scratch"), do NOT auto-switch. Instead, give a one-line hint:

> This looks like a new project. Consider using `/supervised-coding full <request>` for the full workflow with planning.

Then proceed with Fast Mode as requested (it will likely fail at the git check, which is fine — the error message also points to `full`).

---

## Setup (every invocation)

**Config**: Use `config/test-project.yaml` (or user-specified). All commands run from `ai-supervised-coding-mvp/`.

**Task ID**: Generate `task-YYYYMMDD-HHMMSS`. Use for ALL commands in this session.

**Pre-flight** (differs by mode):

### Fast Mode Pre-flight
1. `which codex` — verify Codex CLI on PATH
2. Verify `<project_root>` exists AND has `.git` — if not, tell user:
   > "Target project is not a git repository. For new projects, use `/supervised-coding full <request>`."
   Then STOP.

### Review Planning Mode Pre-flight
1. `which codex` — verify Codex CLI on PATH (needed if user later chooses Codex execution)
2. Verify `<project_root>` exists AND has `.git`
3. Initialize a task session using the existing config/task runtime system
4. Use config-derived paths only:
   - `project_root`
   - `runtime_dir`
   - `task_runtime_dir`
5. Do NOT invent `runtime/<task_id>/...` paths manually. Use the helpers in `scripts/config.py` and the review helpers in `scripts/review_project.py` / `scripts/review_execution.py`

### Full Mode Pre-flight
1. `which codex` — verify Codex CLI on PATH
2. If `<project_root>` does not exist → ask user to confirm, then `mkdir -p <project_root>`
3. If `<project_root>` has no `.git` → ask user to confirm, then `cd <project_root> && git init`
4. **CRITICAL**: Only run `git init` inside the exact `project_root` path. NEVER in a parent directory.

---

## Fast Mode

### Step 1: Git Snapshot

```bash
cd <mvp_dir> && python3 scripts/codex_cli.py snapshot \
  --config config/<config>.yaml \
  -m "snapshot before fast mode [<task_id>]"
```

### Step 2: Execute via Codex

```bash
cd <mvp_dir> && python3 scripts/codex_cli.py fast \
  --task "<task_description>" \
  --config config/<config>.yaml \
  --task-id <task_id>
```

Read `writer_summary.json` from the active task runtime. Check escalation triggers (see Escalation Check). If any fire → switch to Escalate Mode.

### Step 3: Run Validations

```bash
cd <mvp_dir> && python3 scripts/codex_cli.py validate \
  --config config/<config>.yaml \
  --task-id <task_id>
```

If any validation fails → escalation trigger.

### Step 4: In-Context Review (YOU do this)

Review the changes directly — no subprocess call needed:

1. `git diff HEAD` in project root
2. Read the changed files
3. Apply **Patch Review Criteria** (see In-Context Review Standards below)
4. Check: Does the change match the task? Obvious bugs? Scope creep?

Verdict: **pass** / **revise** / **block**

**Save the structured review** as `review_patch.json` in the active task runtime. Minimum required fields:

```json
{
  "verdict": "pass|revise|block",
  "summary_for_user": "one-line summary of the review",
  "critical_issues": ["list of critical issues, empty if pass"],
  "suggestions": [{"id": "s1", "action": "description", "priority": "high|medium|low"}],
  "risks": [],
  "acceptance_checks": []
}
```

### Step 5: Generate Writer Feedback

**Mandatory after every saved `review_patch.json`.** Run immediately:

```bash
cd <mvp_dir> && python3 scripts/codex_cli.py generate-feedback \
  --config config/<config>.yaml \
  --task-id <task_id>
```

This reads `review_patch.json` from the active task runtime and generates `writer_feedback.json` in both the task runtime and `runtime/writer_feedback.json` (global latest).

If **pass**: Tell user, done.
If **revise/block**: Show issues, offer options (fix cycle or pause). If fix cycle runs and produces a new `review_patch.json`, run `generate-feedback` again.

---

## Review Planning Mode

This mode is for project-level optimization review, not patch review and not normal feature execution.

### Phase 1: Gather Context

Use the active config and task session. Do NOT invent paths manually. Review Mode must reuse:
- `load_config()`
- `init_task_session()`
- `task_artifact_path()`
- `runtime_artifact_path()`

Bound the context:
1. Read skill-owned rules and contracts:
   - `project_contract.md`
   - `writer_contract.md`
   - `review_policy.json`
   - relevant sections of `CLAUDE.md`
2. Read representative project files only:
   - entrypoints
   - key config/build/test files
   - representative core modules/components
3. Read only recent runtime history:
   - inspect at most 5 recent task directories
   - select 3 to 5 most relevant tasks
   - read at most 2 artifacts per task
4. Confirm current state:
   - `git status --short --branch`
   - obvious config/build/test smells

Use `scripts/review_project.py` helpers when saving or gathering review artifacts.

### Phase 2: Produce Review Findings

Generate and save `review_findings.json` in the active task runtime.

Required structure:
- `review_direction`
- `summary`
- `findings`
- `opportunities`
- `recommended_scope`

If user provided no focus, review from product, engineering, structure, and UX angles.
If user provided a focus, prioritize it but you may add 1 to 2 higher-priority issues you discover.

### Phase 3: Produce Improvement Plan

Generate and save `review_plan.json` in the active task runtime.

Required structure:
- `goal`
- `scope`
- `out_of_scope`
- `not_recommended_now`
- `recommended_executor`
- `ordered_steps`
- `risks`
- `expected_benefits`

Also generate `review_report.md` for the human-readable summary.

### Phase 4: Choose Executor

Present exactly these options after the findings + plan:
1. Claude execute
2. Codex execute
3. Save only

Do NOT auto-execute.

### If User Chooses Claude Execute

1. Approve the review plan:
```bash
cd <mvp_dir> && python3 scripts/codex_cli.py approve-review \
  --executor claude \
  --config config/<config>.yaml \
  --task-id <task_id>
```
2. Prepare shared execution baseline:
```bash
cd <mvp_dir> && python3 scripts/codex_cli.py prepare-review \
  --config config/<config>.yaml \
  --task-id <task_id> \
  --label "snapshot before review execution [<task_id>]"
```
3. Claude implements the approved review plan directly in the current session
4. Finalize through the shared execution backbone:
```bash
cd <mvp_dir> && python3 scripts/codex_cli.py finalize-review \
  --config config/<config>.yaml \
  --task-id <task_id>
```

### If User Chooses Codex Execute

1. Approve the review plan:
```bash
cd <mvp_dir> && python3 scripts/codex_cli.py approve-review \
  --executor codex \
  --config config/<config>.yaml \
  --task-id <task_id>
```
2. Prepare shared execution baseline:
```bash
cd <mvp_dir> && python3 scripts/codex_cli.py prepare-review \
  --config config/<config>.yaml \
  --task-id <task_id> \
  --label "snapshot before review execution [<task_id>]"
```
3. Execute via Codex:
```bash
cd <mvp_dir> && python3 scripts/codex_cli.py execute-review \
  --task "<review_goal_or_focus>" \
  --config config/<config>.yaml \
  --task-id <task_id>
```
4. Finalize through the shared execution backbone:
```bash
cd <mvp_dir> && python3 scripts/codex_cli.py finalize-review \
  --config config/<config>.yaml \
  --task-id <task_id>
```

### If User Chooses Save Only

- Keep `review_findings.json`, `review_plan.json`, and `review_report.md`
- Do not snapshot
- Do not execute code
- Tell the user they can later resume by approving the saved review plan

---

## Full Mode

### Phase 1: Project Bootstrap (if needed)

Only in Full Mode. If `project_root` didn't exist or had no git:
- Directory was created in pre-flight
- Git was initialized in pre-flight
- Tell the user: "Initialized new project at `<project_root>`."

### Phase 2: Plan Generation with Requirements (Codex)

Plan generation now includes requirements analysis (no separate brief.json step).

```bash
cd <mvp_dir> && python3 scripts/codex_cli.py plan \
  --task "<task_description>" \
  --config config/<config>.yaml \
  --task-id <task_id>
```

Display `plan.json` from the active task runtime: Goal, Must-have requirements, Constraints, Files, Steps, Risks, Test strategy, Acceptance criteria.

### Phase 3: Plan Review + User Confirmation (YOU do this — in-context)

Review as independent senior reviewer. Apply **Plan Review Criteria** (see In-Context Review Standards below). Also verify:
- Are the extracted `must_have` requirements complete and correct?
- Are `constraints` and `out_of_scope` reasonable?
- Does the user agree with the requirements interpretation?

Save `review_plan.json` in the active task runtime:

```json
{
  "timestamp": "<ISO 8601>",
  "task_id": "<task_id>",
  "iteration": 1,
  "verdict": "pass|revise|block",
  "summary_for_user": "...",
  "missing_requirements": [],
  "incorrect_assumptions": [],
  "risks": [],
  "suggestions": []
}
```

Present verdict and ask:
> 1. Approve and execute
> 2. Revise the plan (max 1 revision)
> 3. Abandon

**Wait for user choice.** On approve: copy `plan.json` → `approved_plan.json`.

On revise:
```bash
cd <mvp_dir> && python3 scripts/codex_cli.py plan-revise \
  --task "<task_description>" \
  --review-file <active-task-runtime>/review_plan.json \
  --config config/<config>.yaml \
  --task-id <task_id>
```

Re-review the revised plan (in-context). If still blocked after revision, stop.

### Phase 4: Git Snapshot + Execute

```bash
cd <mvp_dir> && python3 scripts/codex_cli.py snapshot \
  --config config/<config>.yaml \
  -m "snapshot before implementation [<task_id>]"
```

```bash
cd <mvp_dir> && python3 scripts/codex_cli.py execute \
  --task "<task_description>" \
  --config config/<config>.yaml \
  --task-id <task_id>
```

### Phase 5: Validate + Collect Diff

```bash
cd <mvp_dir> && python3 scripts/codex_cli.py validate \
  --config config/<config>.yaml \
  --task-id <task_id>
```

In project root:
- `git diff HEAD` for diff
- `git status --porcelain` for manifest
- Read full content of untracked files
- Save to the active task runtime as `full_diff.txt` and `change_manifest.json`

### Phase 6: Patch Review (YOU do this — in-context, with optional Final Gate)

**Default: In-context review.** Read actual code files, not just diff.

Apply **Patch Review Criteria** (see In-Context Review Standards below).

Additionally, perform **Acceptance Criteria Verification**: for each `acceptance_criteria` item from the approved plan, explicitly verify: met or not met, with evidence. Include this as `acceptance_checks` in the review JSON.

Workflow integrity checks:
| Check | Required |
|-------|----------|
| git_repo_valid | Yes |
| manifest_complete | Yes |
| required_validations_passed | Yes (if configured) |
| artifacts_isolated | Yes |

Save `review_patch.json` in the active task runtime.

**Immediately after saving `review_patch.json`, generate writer feedback:**
```bash
cd <mvp_dir> && python3 scripts/codex_cli.py generate-feedback \
  --config config/<config>.yaml \
  --task-id <task_id>
```

**Final Gate (subprocess)**: If changed files > 10 OR diff lines > 500, trigger one subprocess independent review using Claude CLI directly:
```bash
cd <project_root> && claude -p "$(cat <active-task-runtime>/final_gate_prompt.txt)" --output-format json --max-turns 1
```
Before running, write the prompt to `final_gate_prompt.txt` in the active task runtime containing: the task, approved plan, git diff, test results, and review instructions from `prompts/reviewer_patch.md`. Save the subprocess result as `final_gate_review.json` in the active task runtime. Merge subprocess findings with your in-context review. If the Final Gate changes the verdict, update `review_patch.json` and re-run `generate-feedback`.

### Phase 7: User Decision

**PASS**: Accept → generate `final_report.md` in the active task runtime
**REVISE**: Fix cycle (max 1):
```bash
cd <mvp_dir> && python3 scripts/codex_cli.py fix \
  --task "<task_description>" \
  --review-file <active-task-runtime>/review_patch.json \
  --config config/<config>.yaml \
  --task-id <task_id>
```
Re-validate, re-review (in-context), save new `review_patch.json`, then run `generate-feedback` again.

**FAIL**: Pause for manual intervention.

---

## Escalation Check

After Fast Mode execution, check triggers. Thresholds from `config/review_policy.json`.

| Trigger | Check |
|---------|-------|
| Files changed > threshold | Count `changed_files` in writer_summary |
| Diff lines > threshold | `git diff HEAD --stat` |
| New dependency | package.json/requirements.txt etc. changed |
| Validation fails | Non-zero exit |
| Writer low confidence | `escalate_recommended: true` in writer_summary |
| Unresolved must_fix | Previous `writer_feedback.json` has non-empty must_fix |
| Config file changed | Matches `escalate_on_config_change_patterns` |

If ANY trigger fires → announce which ones, then continue as Full Mode from Phase 5 (Validate + Collect Diff) since code is already written. **Escalate Mode uses subprocess for patch review** (not in-context) to preserve independent review for high-risk changes.

---

## In-Context Review Standards

Use these criteria when doing in-context reviews (no subprocess).

### Plan Review Criteria
1. **Requirement coverage**: All `must_have` items addressed? Any missing?
2. **Assumptions**: Does the plan make incorrect assumptions about the codebase?
3. **Over-engineering**: Is the plan doing more than necessary? Could it be simpler?
4. **Under-specification**: Are steps too vague to execute?
5. **Risks**: What could go wrong? Edge cases? Side effects?
6. **File scope**: Are listed files appropriate? Missing or unnecessary?

Verdict: `pass` (ready to execute) / `revise` (direction correct, needs changes) / `block` (fundamentally wrong)

### Patch Review Criteria
1. **Requirement fulfillment**: Do changes satisfy the original task?
2. **Plan adherence**: Do changes follow the approved plan? Unauthorized deviations?
3. **Code quality**: Clean, readable, consistent with existing conventions?
4. **Correctness**: Bugs, edge cases, logic errors?
5. **Test results**: Did validations pass? Failures related to changes?
6. **Completeness**: Anything missing from the plan?

Verdict: `pass` / `revise` / `block`

### Acceptance Criteria Verification (Patch Review only)
For each `acceptance_criteria` from the plan:
- **met**: true / false
- **evidence**: what you observed (file, line, behavior)

Include as `acceptance_checks` array in review JSON.

---

## Writer Feedback Loop

Every review MUST produce `writer_feedback.json`. Non-negotiable.

**How:** Save `review_patch.json` first, then run `generate-feedback` CLI command. This reads the real review artifact and generates feedback automatically. Do NOT create `writer_feedback.json` manually.

```bash
cd <mvp_dir> && python3 scripts/codex_cli.py generate-feedback \
  --config config/<config>.yaml \
  --task-id <task_id>
```

**Trigger rule:** Run `generate-feedback` immediately after every newly saved `review_patch.json` — first review AND any re-review after a fix cycle.

1. Saved to `writer_feedback.json` in the active task runtime
2. Also saved to `runtime/writer_feedback.json` (global latest)
3. Auto-injected into writer's next prompt (handled by `execute.py`)
4. Enriched with `task_area` and `affected_files` for scoped injection

**Note:** Review Planning Mode does not currently produce `review_patch.json`, so it does not generate writer feedback. This is intentional — feedback requires genuine reviewer judgment on code changes.

---

## Rules

- NEVER skip writer feedback generation
- NEVER auto-approve — user decides at every decision point
- NEVER auto-switch from Fast to Full — only hint
- NEVER auto-execute after `/supervised-coding review`
- NEVER run `git init` outside the exact `project_root` path
- All artifacts to the config-derived active task runtime
- Max 1 plan revision, 1 fix cycle
