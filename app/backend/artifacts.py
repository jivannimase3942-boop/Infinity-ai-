"""
Infinity AI - Claude-Style Artifacts Management Subsystem
Provides:
- Automatic extraction and parsing of standalone artifacts from AI responses
- Storage & versioning of generated documents, code files, reports, and study notes in SQLite
- Safe local export without overwriting user files
"""

import re
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from backend.db import save_artifact, get_artifacts, get_artifact, delete_artifact
from backend.file_ops import safe_export_content


ARTIFACT_TAG_REGEX = re.compile(
    r":::artifact\s*\{title=\"([^\"]+)\"(?:[,\s]+type=\"([^\"]+)\")?(?:[,\s]+lang=\"([^\"]+)\")?\}\s*\n(.*?):::",
    re.DOTALL
)

CODE_BLOCK_ARTIFACT_REGEX = re.compile(
    r"```([a-zA-Z0-9_\-]+)\s*\n(?:\/\/|#)\s*(?:filename|file|title):\s*([^\n]+)\n(.*?)\n```",
    re.DOTALL
)


def extract_and_store_artifacts(
    response_text: str,
    conversation_id: Optional[str] = None,
    project_id: str = "default"
) -> List[Dict[str, Any]]:
    """
    Scans an AI response for structured artifact tags or standalone file blocks.
    Persists discovered artifacts to SQLite and returns metadata.
    """
    found_artifacts = []

    # 1. Match explicit :::artifact tags
    for match in ARTIFACT_TAG_REGEX.finditer(response_text):
        title = match.group(1).strip()
        art_type = match.group(2) or "document"
        lang = match.group(3) or "markdown"
        content = match.group(4).strip()

        aid = save_artifact(
            title=title,
            content=content,
            artifact_type=art_type,
            language=lang,
            conversation_id=conversation_id,
            project_id=project_id
        )
        found_artifacts.append({
            "id": aid,
            "title": title,
            "artifact_type": art_type,
            "language": lang,
            "content": content
        })

    # 2. Match annotated code blocks (e.g. ```python \n # filename: main.py)
    for match in CODE_BLOCK_ARTIFACT_REGEX.finditer(response_text):
        lang = match.group(1).strip()
        title = match.group(2).strip()
        content = match.group(3).strip()

        # Avoid duplicates if already caught
        if any(a["title"] == title for a in found_artifacts):
            continue

        aid = save_artifact(
            title=title,
            content=content,
            artifact_type="code",
            language=lang,
            conversation_id=conversation_id,
            project_id=project_id
        )
        found_artifacts.append({
            "id": aid,
            "title": title,
            "artifact_type": "code",
            "language": lang,
            "content": content
        })

    return found_artifacts


def export_artifact(
    artifact_id: str,
    target_path: Optional[str] = None
) -> Dict[str, Any]:
    """Exports an artifact to disk safely without overwriting unless intended."""
    art = get_artifact(artifact_id)
    if not art:
        return {"status": "error", "message": f"Artifact '{artifact_id}' not found."}

    fname = art["title"]
    # Ensure standard extension
    if not Path(fname).suffix:
        ext = ".py" if art.get("language") == "python" else ".md"
        fname += ext

    if target_path:
        out_p = Path(target_path)
        if out_p.is_dir():
            out_p = out_p / fname
    else:
        out_dir = Path(__file__).resolve().parent.parent / "data" / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_p = out_dir / fname

    try:
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(art["content"])
        return {"status": "success", "file_path": str(out_p)}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
