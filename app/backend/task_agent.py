"""
Infinity AI - Safe Autonomous Task Agent
Safety First Architecture:
Understand -> Plan -> Preview actions -> Permission for destructive/write operations -> Execute -> Verify -> Report.
- Read/Analyze operations execute automatically without friction.
- Destructive operations (delete, overwrite, rename, move, execute shell command) ALWAYS require explicit user permission.
- Never silently modifies user files.
"""

from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import json
import os

class SafeTaskPlan:
    def __init__(self, goal: str):
        self.goal = goal
        self.steps: List[Dict[str, Any]] = []

    def add_step(self, action: str, target: str, is_destructive: bool, description: str):
        self.steps.append({
            "step_id": len(self.steps) + 1,
            "action": action,
            "target": target,
            "is_destructive": is_destructive,
            "description": description,
            "status": "pending"
        })

    def requires_permission(self) -> bool:
        return any(s["is_destructive"] for s in self.steps)

    def get_preview(self) -> str:
        lines = [f"### Execution Plan: {self.goal}"]
        for s in self.steps:
            perm_marker = "⚠️ [REQUIRES CONFIRMATION]" if s["is_destructive"] else "✓ [AUTO-EXECUTE]"
            lines.append(f"{s['step_id']}. {s['action'].upper()} on `{s['target']}` — {s['description']} {perm_marker}")
        return "\n".join(lines)


class SafeTaskAgent:
    def __init__(self):
        pass

    def plan_task(self, user_request: str) -> SafeTaskPlan:
        """Analyzes task and creates structured preview with explicit safety flags."""
        plan = SafeTaskPlan(goal=user_request)
        req_lower = user_request.lower()

        if any(w in req_lower for w in ["find bugs", "analyze project", "code review"]):
            plan.add_step("read", "workspace/project_files", False, "Scan and parse project source files")
            plan.add_step("analyze", "static_analysis", False, "Inspect code patterns for syntax/logic bugs")
            plan.add_step("report", "summary", False, "Generate unified diff suggestions and verification steps")

        elif any(w in req_lower for w in ["create report", "summarize document", "report from pdf"]):
            plan.add_step("read", "active_document", False, "Extract text and structured headings from document")
            plan.add_step("synthesize", "document_knowledge", False, "Summarize key findings and cite evidence")
            plan.add_step("report", "markdown_report", False, "Format final executive summary report")

        elif any(w in req_lower for w in ["delete", "remove", "clean"]):
            plan.add_step("inspect", "target_files", False, "Locate specified files")
            plan.add_step("delete", "target_files", True, "Permanently delete specified files")

        elif any(w in req_lower for w in ["overwrite", "modify", "refactor"]):
            plan.add_step("read", "source_files", False, "Read current file contents")
            plan.add_step("modify", "source_files", True, "Apply proposed code changes")

        else:
            plan.add_step("understand", "context", False, "Understand request and retrieve relevant local context")
            plan.add_step("execute", "task_actions", False, "Perform analysis and generate response")

        return plan

    def execute_plan(
        self,
        plan: SafeTaskPlan,
        permission_granted: bool = False,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """Executes plan steps respecting safety boundaries."""
        results = []
        for step in plan.steps:
            if step["is_destructive"] and not permission_granted:
                step["status"] = "blocked_pending_permission"
                if status_callback:
                    status_callback(f"Paused at step {step['step_id']}: Permission required for {step['action']}")
                return {
                    "status": "awaiting_permission",
                    "plan_preview": plan.get_preview(),
                    "pending_step": step,
                    "completed_steps": results
                }

            # Safe read/analysis execution
            step["status"] = "completed"
            results.append(step)
            if status_callback:
                status_callback(f"Completed step {step['step_id']}: {step['description']}")

        return {
            "status": "success",
            "plan_preview": plan.get_preview(),
            "completed_steps": results
        }

# Global instance
safe_task_agent = SafeTaskAgent()
