"""Data structures for JSON schemas exchanged between agents."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# --- Sub-structures ---

@dataclass
class Risk:
    severity: str = "medium"
    title: str = ""
    evidence: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Risk:
        return cls(
            severity=data.get("severity", "medium"),
            title=data.get("title", ""),
            evidence=data.get("evidence", ""),
        )


@dataclass
class Suggestion:
    id: str = ""
    priority: str = "medium"
    action: str = ""
    rationale: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> Suggestion:
        return cls(
            id=data.get("id", ""),
            priority=data.get("priority", "medium"),
            action=data.get("action", ""),
            rationale=data.get("rationale", ""),
        )


@dataclass
class ReviewSummary:
    project_state: str = ""
    health: str = "mixed"
    top_priority: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> ReviewSummary:
        return cls(
            project_state=data.get("project_state", ""),
            health=data.get("health", "mixed"),
            top_priority=data.get("top_priority", ""),
        )

    def to_dict(self) -> dict:
        return {
            "project_state": self.project_state,
            "health": self.health,
            "top_priority": self.top_priority,
        }


@dataclass
class ReviewFinding:
    id: str = ""
    severity: str = "medium"
    title: str = ""
    why_it_matters: str = ""
    evidence: list[str] = field(default_factory=list)
    impact_scope: list[str] = field(default_factory=list)
    recommended_this_round: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> ReviewFinding:
        return cls(
            id=data.get("id", ""),
            severity=data.get("severity", "medium"),
            title=data.get("title", ""),
            why_it_matters=data.get("why_it_matters", ""),
            evidence=data.get("evidence", []),
            impact_scope=data.get("impact_scope", []),
            recommended_this_round=data.get("recommended_this_round", True),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "severity": self.severity,
            "title": self.title,
            "why_it_matters": self.why_it_matters,
            "evidence": self.evidence,
            "impact_scope": self.impact_scope,
            "recommended_this_round": self.recommended_this_round,
        }


@dataclass
class ReviewOpportunity:
    id: str = ""
    area: str = "engineering"
    title: str = ""
    benefit: str = ""
    evidence: list[str] = field(default_factory=list)
    priority: str = "medium"

    @classmethod
    def from_dict(cls, data: dict) -> ReviewOpportunity:
        return cls(
            id=data.get("id", ""),
            area=data.get("area", "engineering"),
            title=data.get("title", ""),
            benefit=data.get("benefit", ""),
            evidence=data.get("evidence", []),
            priority=data.get("priority", "medium"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "area": self.area,
            "title": self.title,
            "benefit": self.benefit,
            "evidence": self.evidence,
            "priority": self.priority,
        }


@dataclass
class ReviewRecommendedScope:
    in_scope: list[str] = field(default_factory=list)
    not_now: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> ReviewRecommendedScope:
        return cls(
            in_scope=data.get("in_scope", []),
            not_now=data.get("not_now", []),
        )

    def to_dict(self) -> dict:
        return {
            "in_scope": self.in_scope,
            "not_now": self.not_now,
        }


@dataclass
class ReviewFindings:
    review_direction: str = ""
    summary: ReviewSummary = field(default_factory=ReviewSummary)
    findings: list[ReviewFinding] = field(default_factory=list)
    opportunities: list[ReviewOpportunity] = field(default_factory=list)
    recommended_scope: ReviewRecommendedScope = field(default_factory=ReviewRecommendedScope)

    @classmethod
    def from_dict(cls, data: dict) -> ReviewFindings:
        return cls(
            review_direction=data.get("review_direction", ""),
            summary=ReviewSummary.from_dict(data.get("summary", {})),
            findings=[ReviewFinding.from_dict(item) for item in data.get("findings", [])],
            opportunities=[ReviewOpportunity.from_dict(item) for item in data.get("opportunities", [])],
            recommended_scope=ReviewRecommendedScope.from_dict(data.get("recommended_scope", {})),
        )

    def to_dict(self) -> dict:
        return {
            "review_direction": self.review_direction,
            "summary": self.summary.to_dict(),
            "findings": [item.to_dict() for item in self.findings],
            "opportunities": [item.to_dict() for item in self.opportunities],
            "recommended_scope": self.recommended_scope.to_dict(),
        }


@dataclass
class ReviewPlanStep:
    id: str = ""
    title: str = ""
    description: str = ""
    affected_files: list[str] = field(default_factory=list)
    risk_level: str = "medium"
    rollback_point: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> ReviewPlanStep:
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            affected_files=data.get("affected_files", []),
            risk_level=data.get("risk_level", "medium"),
            rollback_point=data.get("rollback_point", ""),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "affected_files": self.affected_files,
            "risk_level": self.risk_level,
            "rollback_point": self.rollback_point,
        }


@dataclass
class ReviewPlanRisk:
    severity: str = "medium"
    title: str = ""
    mitigation: str = ""
    rollback: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> ReviewPlanRisk:
        return cls(
            severity=data.get("severity", "medium"),
            title=data.get("title", ""),
            mitigation=data.get("mitigation", ""),
            rollback=data.get("rollback", ""),
        )

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "title": self.title,
            "mitigation": self.mitigation,
            "rollback": self.rollback,
        }


@dataclass
class ReviewPlan:
    goal: str = ""
    scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    not_recommended_now: list[str] = field(default_factory=list)
    recommended_executor: str = "save_only"
    ordered_steps: list[ReviewPlanStep] = field(default_factory=list)
    risks: list[ReviewPlanRisk] = field(default_factory=list)
    expected_benefits: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> ReviewPlan:
        return cls(
            goal=data.get("goal", ""),
            scope=data.get("scope", []),
            out_of_scope=data.get("out_of_scope", []),
            not_recommended_now=data.get("not_recommended_now", []),
            recommended_executor=data.get("recommended_executor", "save_only"),
            ordered_steps=[ReviewPlanStep.from_dict(item) for item in data.get("ordered_steps", [])],
            risks=[ReviewPlanRisk.from_dict(item) for item in data.get("risks", [])],
            expected_benefits=data.get("expected_benefits", []),
        )

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "scope": self.scope,
            "out_of_scope": self.out_of_scope,
            "not_recommended_now": self.not_recommended_now,
            "recommended_executor": self.recommended_executor,
            "ordered_steps": [item.to_dict() for item in self.ordered_steps],
            "risks": [item.to_dict() for item in self.risks],
            "expected_benefits": self.expected_benefits,
        }


@dataclass
class ApprovedReviewPlan(ReviewPlan):
    approved_executor: str = "save_only"
    approved_at: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> ApprovedReviewPlan:
        return cls(
            goal=data.get("goal", ""),
            scope=data.get("scope", []),
            out_of_scope=data.get("out_of_scope", []),
            not_recommended_now=data.get("not_recommended_now", []),
            recommended_executor=data.get("recommended_executor", "save_only"),
            ordered_steps=[ReviewPlanStep.from_dict(item) for item in data.get("ordered_steps", [])],
            risks=[ReviewPlanRisk.from_dict(item) for item in data.get("risks", [])],
            expected_benefits=data.get("expected_benefits", []),
            approved_executor=data.get("approved_executor", "save_only"),
            approved_at=data.get("approved_at", ""),
        )

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["approved_executor"] = self.approved_executor
        data["approved_at"] = self.approved_at
        return data


# --- Requirements Brief (DEPRECATED: use PlanOutput.must_have/constraints/out_of_scope instead) ---

@dataclass
class RequirementsBrief:
    task_summary: str = ""
    must_have: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    tech_stack: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> RequirementsBrief:
        return cls(
            task_summary=data.get("task_summary", ""),
            must_have=data.get("must_have", []),
            constraints=data.get("constraints", []),
            acceptance_criteria=data.get("acceptance_criteria", []),
            out_of_scope=data.get("out_of_scope", []),
            tech_stack=data.get("tech_stack", ""),
        )

    def to_dict(self) -> dict:
        return {
            "task_summary": self.task_summary,
            "must_have": self.must_have,
            "constraints": self.constraints,
            "acceptance_criteria": self.acceptance_criteria,
            "out_of_scope": self.out_of_scope,
            "tech_stack": self.tech_stack,
        }


# --- Plan ---

@dataclass
class PlanOutput:
    goal: str = ""
    files: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    risks: list[Risk] = field(default_factory=list)
    test_strategy: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    # Embedded requirements (merged from RequirementsBrief — Change B)
    must_have: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    tech_stack: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> PlanOutput:
        return cls(
            goal=data.get("goal", ""),
            files=data.get("files", []),
            steps=data.get("steps", []),
            risks=[Risk.from_dict(r) for r in data.get("risks", [])],
            test_strategy=data.get("test_strategy", ""),
            acceptance_criteria=data.get("acceptance_criteria", []),
            must_have=data.get("must_have", []),
            constraints=data.get("constraints", []),
            out_of_scope=data.get("out_of_scope", []),
            tech_stack=data.get("tech_stack", ""),
        )

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "files": self.files,
            "steps": self.steps,
            "risks": [{"severity": r.severity, "title": r.title, "evidence": r.evidence} for r in self.risks],
            "test_strategy": self.test_strategy,
            "acceptance_criteria": self.acceptance_criteria,
            "must_have": self.must_have,
            "constraints": self.constraints,
            "out_of_scope": self.out_of_scope,
            "tech_stack": self.tech_stack,
        }


# --- Plan Review (simplified — no weighted scoring) ---

@dataclass
class PlanReview:
    timestamp: str = ""
    task_id: str = ""
    iteration: int = 1

    verdict: str = "pass"  # pass / revise / block
    summary_for_user: str = ""

    missing_requirements: list[str] = field(default_factory=list)
    incorrect_assumptions: list[str] = field(default_factory=list)
    risks: list[Risk] = field(default_factory=list)
    suggestions: list[Suggestion] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> PlanReview:
        return cls(
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            task_id=data.get("task_id", ""),
            iteration=data.get("iteration", 1),
            verdict=data.get("verdict", "pass"),
            summary_for_user=data.get("summary_for_user", ""),
            missing_requirements=data.get("missing_requirements", []),
            incorrect_assumptions=data.get("incorrect_assumptions", []),
            risks=[Risk.from_dict(r) for r in data.get("risks", [])],
            suggestions=[Suggestion.from_dict(s) for s in data.get("suggestions", [])],
        )

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "iteration": self.iteration,
            "verdict": self.verdict,
            "summary_for_user": self.summary_for_user,
            "missing_requirements": self.missing_requirements,
            "incorrect_assumptions": self.incorrect_assumptions,
            "risks": [{"severity": r.severity, "title": r.title, "evidence": r.evidence} for r in self.risks],
            "suggestions": [{"id": s.id, "priority": s.priority, "action": s.action, "rationale": s.rationale} for s in self.suggestions],
        }


# --- Writer Summary ---

@dataclass
class WriterSummary:
    executor: str = "codex"
    changed_files: list[str] = field(default_factory=list)
    rationale: str = ""
    remaining_risks: list[str] = field(default_factory=list)
    escalate_recommended: bool = False
    escalate_reason: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> WriterSummary:
        return cls(
            executor=data.get("executor", "codex"),
            changed_files=data.get("changed_files", []),
            rationale=data.get("rationale", ""),
            remaining_risks=data.get("remaining_risks", []),
            escalate_recommended=data.get("escalate_recommended", False),
            escalate_reason=data.get("escalate_reason", ""),
        )

    def to_dict(self) -> dict:
        return {
            "executor": self.executor,
            "changed_files": self.changed_files,
            "rationale": self.rationale,
            "remaining_risks": self.remaining_risks,
            "escalate_recommended": self.escalate_recommended,
            "escalate_reason": self.escalate_reason,
        }


# --- Change Manifest ---

@dataclass
class ChangeManifest:
    staged: list[str] = field(default_factory=list)
    unstaged: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "staged": self.staged,
            "unstaged": self.unstaged,
            "untracked": self.untracked,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ChangeManifest:
        return cls(
            staged=data.get("staged", []),
            unstaged=data.get("unstaged", []),
            untracked=data.get("untracked", []),
        )


# --- Patch Review ---

@dataclass
class PatchReview:
    timestamp: str = ""
    task_id: str = ""
    iteration: int = 1

    verdict: str = "pass"  # pass / revise / block
    summary_for_user: str = ""

    # Workflow checks (Full Mode)
    workflow_checks: dict = field(default_factory=dict)

    # Change context
    change_manifest: ChangeManifest = field(default_factory=ChangeManifest)
    changed_files: list[str] = field(default_factory=list)
    loc_delta: str = ""

    # Issues
    requirements_missed: list[str] = field(default_factory=list)
    critical_issues: list[str] = field(default_factory=list)
    risks: list[Risk] = field(default_factory=list)
    suggestions: list[Suggestion] = field(default_factory=list)
    notes: str = ""

    # Structured acceptance criteria verification (Change E)
    # Each dict: {"criterion": "...", "met": bool, "evidence": "..."}
    acceptance_checks: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> PatchReview:
        return cls(
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            task_id=data.get("task_id", ""),
            iteration=data.get("iteration", 1),
            verdict=data.get("verdict", "pass"),
            summary_for_user=data.get("summary_for_user", ""),
            workflow_checks=data.get("workflow_checks", {}),
            change_manifest=ChangeManifest.from_dict(data.get("change_manifest", {})),
            changed_files=data.get("changed_files", []),
            loc_delta=data.get("loc_delta", ""),
            requirements_missed=data.get("requirements_missed", []),
            critical_issues=data.get("critical_issues", []),
            risks=[Risk.from_dict(r) for r in data.get("risks", [])],
            suggestions=[Suggestion.from_dict(s) for s in data.get("suggestions", [])],
            notes=data.get("notes", ""),
            acceptance_checks=data.get("acceptance_checks", []),
        )

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "iteration": self.iteration,
            "verdict": self.verdict,
            "summary_for_user": self.summary_for_user,
            "workflow_checks": self.workflow_checks,
            "change_manifest": self.change_manifest.to_dict(),
            "changed_files": self.changed_files,
            "loc_delta": self.loc_delta,
            "requirements_missed": self.requirements_missed,
            "critical_issues": self.critical_issues,
            "risks": [{"severity": r.severity, "title": r.title, "evidence": r.evidence} for r in self.risks],
            "suggestions": [{"id": s.id, "priority": s.priority, "action": s.action, "rationale": s.rationale} for s in self.suggestions],
            "notes": self.notes,
            "acceptance_checks": self.acceptance_checks,
        }


# --- Writer Feedback (generated after every review, injected into next writer prompt) ---

@dataclass
class WriterFeedback:
    verdict: str = "pass"
    must_fix: list[str] = field(default_factory=list)
    avoid_next_time: list[str] = field(default_factory=list)
    nice_to_have: list[str] = field(default_factory=list)
    writer_instruction: str = ""
    # Scoped feedback injection (Change F)
    task_area: str = ""  # frontend / backend / config / testing / infra / docs
    affected_files: list[str] = field(default_factory=list)

    @classmethod
    def from_review(cls, review: PatchReview) -> WriterFeedback:
        """Generate writer feedback from a patch review."""
        must_fix = list(review.critical_issues)
        for s in review.suggestions:
            if s.priority == "high":
                must_fix.append(s.action)

        avoid = []
        nice = []
        for s in review.suggestions:
            if s.priority == "medium":
                avoid.append(s.action)
            elif s.priority == "low":
                nice.append(s.action)

        instruction = ""
        if review.verdict == "revise":
            instruction = "Fix the must_fix items, then re-run. Do not add new features."
        elif review.verdict == "block":
            instruction = "Critical issues found. Address must_fix items only — minimal changes."

        return cls(
            verdict=review.verdict,
            must_fix=must_fix,
            avoid_next_time=avoid,
            nice_to_have=nice,
            writer_instruction=instruction,
        )

    @classmethod
    def from_dict(cls, data: dict) -> WriterFeedback:
        return cls(
            verdict=data.get("verdict", "pass"),
            must_fix=data.get("must_fix", []),
            avoid_next_time=data.get("avoid_next_time", []),
            nice_to_have=data.get("nice_to_have", []),
            writer_instruction=data.get("writer_instruction", ""),
            task_area=data.get("task_area", ""),
            affected_files=data.get("affected_files", []),
        )

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "must_fix": self.must_fix,
            "avoid_next_time": self.avoid_next_time,
            "nice_to_have": self.nice_to_have,
            "writer_instruction": self.writer_instruction,
            "task_area": self.task_area,
            "affected_files": self.affected_files,
        }

    def save(self, runtime_dir: str) -> Path:
        """Save writer_feedback.json to the given runtime directory."""
        path = Path(runtime_dir) / "writer_feedback.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path


# --- Validation Result ---

@dataclass
class ValidationResult:
    command: str = ""
    passed: bool = False
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 1

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "passed": self.passed,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:500],
            "stderr": self.stderr[:500],
        }
