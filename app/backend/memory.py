"""
Infinity AI - Three-Layer Memory Subsystem
Layers:
1. Short-Term Memory: Active conversation session context.
2. Project Memory: Persistent context, guidelines, and facts specific to the active project.
3. Long-Term Memory: User-approved persistent global facts, preferences, and workflows.
Provides: View, Edit, Forget, Clear Project Memory without storing credentials or sensitive data.
"""

from typing import List, Dict, Any, Optional
from backend.db import get_memories, save_memory, delete_memory, clear_project_memories


class MemoryManager:
    def __init__(self, project_id: str = "default"):
        self.project_id = project_id

    def set_project(self, project_id: str):
        self.project_id = project_id

    def get_project_memories(self) -> List[Dict[str, Any]]:
        """Retrieve memories scoped to the active project."""
        return get_memories(project_id=self.project_id, category="project_knowledge")

    def get_long_term_memories(self) -> List[Dict[str, Any]]:
        """Retrieve user-approved persistent global memories."""
        return get_memories(project_id="global", category="user_preference")

    def remember(self, key: str, value: str, is_project_scoped: bool = True) -> str:
        """Store a new memory item."""
        pid = self.project_id if is_project_scoped else "global"
        cat = "project_knowledge" if is_project_scoped else "user_preference"
        return save_memory(key=key, value=value, project_id=pid, category=cat, approved=True)

    def forget(self, memory_id: str):
        """Remove a specific memory item."""
        delete_memory(memory_id)

    def clear_project(self):
        """Clear all memories associated with current project."""
        clear_project_memories(self.project_id)

    def build_memory_prompt_injection(self) -> str:
        """Formats active project and user memories for injection into system prompts."""
        p_mems = self.get_project_memories()
        lt_mems = self.get_long_term_memories()

        if not p_mems and not lt_mems:
            return ""

        parts = ["--- PERSISTENT MEMORY CONTEXT ---"]
        if p_mems:
            parts.append("Project Memories:")
            for m in p_mems:
                parts.append(f"- {m['memory_key']}: {m['memory_value']}")
        if lt_mems:
            parts.append("User Preferences & Long-Term Context:")
            for m in lt_mems:
                parts.append(f"- {m['memory_key']}: {m['memory_value']}")
        parts.append("--- END MEMORY CONTEXT ---\n")
        return "\n".join(parts)


# Global instance
memory_service = MemoryManager()
