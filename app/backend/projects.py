"""
Infinity AI - Projects Management Subsystem
Provides Claude-style projects with isolated context, instructions, files, and settings.
"""

from typing import List, Dict, Any, Optional
from backend.db import get_projects, get_project, save_project, get_connection
from backend.memory import memory_service


class ProjectManager:
    def __init__(self):
        self._active_project_id = "default"

    @property
    def active_project_id(self) -> str:
        return self._active_project_id

    def set_active_project(self, project_id: str) -> Dict[str, Any]:
        proj = get_project(project_id)
        if not proj:
            project_id = "default"
            proj = get_project(project_id)
        self._active_project_id = project_id
        memory_service.set_project(project_id)
        return proj or {}

    def get_active_project(self) -> Dict[str, Any]:
        proj = get_project(self._active_project_id)
        if not proj:
            proj = self.set_active_project("default")
        return proj

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        return get_project(project_id)

    def list_projects(self) -> List[Dict[str, Any]]:
        return get_projects()

    def create_or_update_project(
        self,
        project_id: str,
        name: str,
        description: str,
        system_instructions: str,
        model_preference: str = "Balanced"
    ) -> Dict[str, Any]:
        save_project(project_id, name, description, system_instructions, model_preference)
        return get_project(project_id) or {}

    def get_project_files(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        pid = project_id or self._active_project_id
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM project_files WHERE project_id = ? ORDER BY indexed_at DESC", (pid,)
            ).fetchall()
            return [dict(r) for r in rows]

    def remove_project_file(self, file_id: str):
        from backend.vector_store import remove_document_chunks
        with get_connection() as conn:
            row = conn.execute("SELECT doc_id FROM project_files WHERE id = ?", (file_id,)).fetchone()
            if row and row[0]:
                try:
                    remove_document_chunks(row[0])
                except Exception:
                    pass
            conn.execute("DELETE FROM project_files WHERE id = ?", (file_id,))
            conn.commit()


# Global project instance
project_service = ProjectManager()
