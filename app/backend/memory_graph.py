"""
Infinity AI - AI Workspace Memory Graph
Builds a local relationship layer above existing memory and vector infrastructure.
Entities:
- projects, documents, concepts, topics, decisions, tasks, preferences
Relationships:
- Project -> uses -> Technology
- Project -> contains -> Document
- Document -> discusses -> Concept
- Concept -> related_to -> Concept
- Task -> belongs_to -> Project
100% Local & Privacy-Safe. No cloud synchronization.
"""

import json
import sqlite3
import uuid
from typing import List, Dict, Any, Optional
from backend.db import get_connection

class MemoryGraphService:
    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workspace_memory_graph (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    properties TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def add_relationship(
        self,
        source_type: str,
        source_id: str,
        relationship: str,
        target_type: str,
        target_id: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> str:
        """Stores a relationship edge between two entities."""
        rel_id = f"rel-{uuid.uuid4().hex[:12]}"
        props_json = json.dumps(properties or {})
        with get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO workspace_memory_graph
                (id, source_type, source_id, relationship, target_type, target_id, properties)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (rel_id, source_type.lower(), source_id, relationship.lower(), target_type.lower(), target_id, props_json))
            conn.commit()
        return rel_id

    def get_relationships_for_source(self, source_type: str, source_id: str) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM workspace_memory_graph
                WHERE source_type = ? AND source_id = ?
            """, (source_type.lower(), source_id))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_relationships_for_target(self, target_type: str, target_id: str) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM workspace_memory_graph
                WHERE target_type = ? AND target_id = ?
            """, (target_type.lower(), target_id))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_project_entities(self, project_id: str) -> Dict[str, Any]:
        """Retrieves documents, technologies, tasks, and concepts linked to a project."""
        rels = self.get_relationships_for_source("project", project_id)
        result = {
            "project_id": project_id,
            "documents": [],
            "technologies": [],
            "tasks": [],
            "concepts": []
        }
        for r in rels:
            t_type = r["target_type"]
            t_id = r["target_id"]
            if t_type == "document":
                result["documents"].append(t_id)
            elif t_type in ["technology", "tech"]:
                result["technologies"].append(t_id)
            elif t_type == "task":
                result["tasks"].append(t_id)
            elif t_type == "concept":
                result["concepts"].append(t_id)

        # Also find tasks pointing to project
        task_rels = self.get_relationships_for_target("project", project_id)
        for r in task_rels:
            if r["source_type"] == "task" and r["source_id"] not in result["tasks"]:
                result["tasks"].append(r["source_id"])

        return result

    def link_document_concept(self, doc_name: str, concept: str):
        """Records that a document discusses a concept."""
        self.add_relationship("document", doc_name, "discusses", "concept", concept)

    def link_concepts(self, concept_a: str, concept_b: str):
        """Records that two concepts are related."""
        self.add_relationship("concept", concept_a, "related_to", "concept", concept_b)

    def link_project_tech(self, project_id: str, tech: str):
        """Records that a project uses a technology."""
        self.add_relationship("project", project_id, "uses", "technology", tech)

    def link_project_document(self, project_id: str, doc_name: str):
        """Records that a project contains a document."""
        self.add_relationship("project", project_id, "contains", "document", doc_name)

    def link_task_project(self, task_name: str, project_id: str):
        """Records that a task belongs to a project."""
        self.add_relationship("task", task_name, "belongs_to", "project", project_id)

    def build_graph_context_injection(self, project_id: Optional[str] = None, topic: Optional[str] = None) -> str:
        """Constructs concise relationship graph context for prompt injection."""
        lines = []
        if project_id:
            ents = self.get_project_entities(project_id)
            if any([ents["documents"], ents["technologies"], ents["tasks"], ents["concepts"]]):
                lines.append(f"Project '{project_id}' Graph:")
                if ents["technologies"]:
                    lines.append(f"  - Technologies: {', '.join(ents['technologies'])}")
                if ents["documents"]:
                    lines.append(f"  - Documents: {', '.join(ents['documents'])}")
                if ents["tasks"]:
                    lines.append(f"  - Active Tasks: {', '.join(ents['tasks'])}")
                if ents["concepts"]:
                    lines.append(f"  - Key Concepts: {', '.join(ents['concepts'])}")

        if topic:
            rels = self.get_relationships_for_source("concept", topic)
            related = [r["target_id"] for r in rels if r["relationship"] == "related_to"]
            if related:
                lines.append(f"Related concepts to '{topic}': {', '.join(related)}")

        return "\n".join(lines) if lines else ""

# Global instance
memory_graph_service = MemoryGraphService()
