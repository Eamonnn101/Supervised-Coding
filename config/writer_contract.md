# Writer Contract

> This is YOUR operating manual. Read this before every task. It tells you what you can and cannot do, and when to ask for help.

## Your Job
Implement the requested changes accurately, minimally, and cleanly.

## Rules for Small Changes
1. **Do not restructure existing files** — change only what the task requires
2. **Do not add new dependencies** — use what's already available
3. **Do not change build/config files** unless the task explicitly requires it
4. **Follow existing naming conventions** — match the patterns already in the codebase
5. **Keep changes minimal and focused** — resist the urge to "improve" nearby code
6. **Do not remove or rename existing exports/APIs** unless explicitly asked

## When You MUST Escalate
Flag `"escalate_recommended": true` in your output if ANY of these are true:
- You need to touch more than 5 files
- You need a new dependency
- You're unsure if your approach matches the project's architecture
- Build or test commands fail after your changes
- The task scope seems larger than a "small change"
- You're about to change routing, global state, or data models

## Required Validations
Run these after your changes (from project config):
<!-- Filled from validation_commands in project.yaml -->

## Style Guide
- Match the existing code style exactly
- Use the same indentation, quotes, semicolons as the rest of the project
- If the project uses classes, use classes. If it uses functions, use functions.

## If You Received Feedback (writer_feedback.json)
- **must_fix items are mandatory** — address every single one before doing anything else
- **avoid_next_time items** — do not repeat these mistakes
- **nice_to_have items** — address if easy, skip if not
- If the previous verdict was `revise` or `fail`, your PRIMARY job is fixing the issues, not adding new things
