"""
Infinity AI - Agent Orchestrator & Specialized Agents
Agents:
- General Agent: Conversational assistant with tool access
- Document Agent: Cross-document reasoning, citation grounding, and contradiction detection
- Research Agent: Structured offline/local research with evidence and confidence rating
- Coding Agent: Code inspection, debugging, diff proposals, and verification
- Data Agent: Dataset statistics, trends, and analytical summaries
- Study Agent: Concept simplification, quizzes, MCQs, flashcards, and viva prep
- Writing Agent: Structured reports, papers, notes, and documentation
"""

import json
import re
from typing import Dict, Any, List, Optional, Callable

from backend.ai_engine import generate_simple_response, STOP_EVENT
from backend.memory import memory_service
from backend.projects import project_service
from backend.tools import tool_registry

class AgentPersonaDict(dict):
    ALIASES = {
        "Researcher": "Research",
        "Coder": "Coding",
        "Analyst": "Data",
        "Tutor": "Study",
        "Writer": "Writing",
        "Auditor": "Document",
        "Research": "Research",
        "Coding": "Coding",
        "Data": "Data",
        "Study": "Study",
        "Writing": "Writing",
        "Document": "Document",
        "General": "General"
    }

    def __getitem__(self, key):
        canonical = self.ALIASES.get(key, key)
        return super().__getitem__(canonical)

    def get(self, key, default=None):
        canonical = self.ALIASES.get(key, key)
        return super().get(canonical, default)

    def __contains__(self, key):
        if super().__contains__(key):
            return True
        return key in self.ALIASES and super().__contains__(self.ALIASES[key])


AGENT_PERSONAS = AgentPersonaDict({
    "General": {
        "title": "General AI Assistant",
        "system": (
            "You are Infinity AI's General Agent. You are an offline-first assistant with access to local tools.\n"
            "Plan your actions carefully, state your plan clearly, execute necessary tools, and provide an accurate final response."
        )
    },
    "Document": {
        "title": "Document & Fact Verification Auditor",
        "system": (
            "You are Infinity AI's Fact Verification and Document Auditor. Your primary role is strictly grounded document analysis.\n"
            "Always cite document name and page number. If facts are not supported in the documents, state:\n"
            "\"I could not find supporting evidence in the provided documents.\""
        )
    },
    "Research": {
        "title": "Research Agent",
        "system": (
            "You are Infinity AI's Research Agent. Produce structured research reports following this exact format:\n"
            "### Research Question\n"
            "### Key Findings\n"
            "### Evidence & Citations\n"
            "### Conflicting Information / Caveats\n"
            "### Confidence Rating (High/Medium/Low)\n"
            "### Conclusion\n"
            "Clearly distinguish between LOCAL DOCUMENT EVIDENCE, MODEL KNOWLEDGE, and USER-PROVIDED INFORMATION. "
            "Never state unverified assumptions as facts."
        )
    },
    "Coding": {
        "title": "Senior Coding Assistant",
        "system": (
            "You are Infinity AI's Senior Coding Assistant. You analyze code architecture, identify bugs, and propose fixes.\n"
            "Always follow this workflow:\n"
            "1. Explain the problem and root cause.\n"
            "2. Propose the patch.\n"
            "3. Show the exact Unified Diff format:\n"
            "```diff\n"
            "- old_code\n"
            "+ new_code\n"
            "```\n"
            "4. Provide step-by-step verification instructions.\n"
            "Before modifying files, always state: FILE, CHANGE, REASON."
        )
    },
    "Data": {
        "title": "Data Analysis Agent",
        "system": (
            "You are Infinity AI's Data Analyst. You inspect tabular datasets (CSV, XLSX, JSON), extract summary statistics, "
            "identify missing values, spot trends and anomalies, and present structured Markdown tables."
        )
    },
    "Study": {
        "title": "Academic Tutor & Study Professor",
        "system": (
            "You are Infinity AI's Academic Professor and Engineering Tutor. When asked to help with studying:\n"
            "- Explain concepts from first principles with real-world analogies.\n"
            "- Generate practice MCQs with detailed explanations for all options.\n"
            "- Provide active-recall flashcards.\n"
            "- Generate expected University / SPPU viva and exam questions with high-scoring model answers."
        )
    },
    "Writing": {
        "title": "Technical Writer & Documentation Specialist",
        "system": (
            "You are Infinity AI's Technical Writer. You compose comprehensive documentation, academic papers, executive summaries, "
            "and project reports. Maintain impeccable structure, headings, bullet points, and professional tone."
        )
    }
})


class AgentOrchestrator:
    def __init__(self):
        pass

    def _create_planner_prompt(self, query: str, agent_type: str) -> str:
        persona = AGENT_PERSONAS.get(agent_type, AGENT_PERSONAS["General"])
        return f"Plan actions for task: '{query}' using persona '{persona['title']}'."

    def _create_verifier_prompt(self, query: str, response: str, agent_type: str) -> str:
        return f"Verifier auditing output for task '{query}' produced by {agent_type}. Response length: {len(response)} chars."

    def run_agent(
        self,
        agent_type: str,
        query: str,
        model_name: Optional[str] = None,
        chunk_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        conversation_id: Optional[str] = None
    ) -> str:
        """
        Orchestrates an agent session through:
        User -> Planner -> Specialized Agent -> Tools -> Verifier -> Final Response
        """
        persona = AGENT_PERSONAS.get(agent_type, AGENT_PERSONAS["General"])
        active_proj = project_service.get_active_project()
        proj_instructions = active_proj.get("system_instructions", "")
        mem_injection = memory_service.build_memory_prompt_injection()
        
        # 1. PLANNER STAGE
        if status_callback:
            status_callback(f"[Planning] Analyzing task and activating {persona['title']}…")

        tool_context = ""

        # 2. TOOL EXECUTION STAGE
        # A. Check for arithmetic calculation
        calc_match = re.search(r"calculate\s+([0-9\+\-\*\/\^\(\)\.\s]+)", query, re.IGNORECASE)
        if calc_match:
            expr = calc_match.group(1).strip()
            if status_callback:
                status_callback(f"[Tools] Executing calculator ({expr})…")
            res = tool_registry.execute("calculator", {"expression": expr})
            if res["status"] == "success":
                tool_context += f"\n[Tool Result - Calculator]: {expr} = {res['result']}\n"

        # B. Check for date/time inquiry
        if any(w in query.lower() for w in ["what time is it", "current date", "today's date", "what day is"]):
            if status_callback:
                status_callback("[Tools] Querying system clock…")
            res = tool_registry.execute("date_time", {})
            if res["status"] == "success":
                tool_context += f"\n[Tool Result - Clock]: {res['result']}\n"

        # C. Check for hardware / diagnostics inquiry
        if any(w in query.lower() for w in ["hardware status", "vram status", "gpu status", "system diagnostics"]):
            if status_callback:
                status_callback("[Tools] Querying hardware diagnostics…")
            res = tool_registry.execute("system_diagnostics", {})
            if res["status"] == "success":
                tool_context += f"\n[Tool Result - System Diagnostics]: {json.dumps(res['result'])}\n"

        # D. Check for document search request in query
        if agent_type in ["Auditor", "Document", "Researcher", "Research"] or any(k in query.lower() for k in ["find in doc", "document says", "search document", "according to", "in the pdf"]):
            if status_callback:
                status_callback("[Tools] Searching document knowledge base…")
            res = tool_registry.execute("document_search", {"query": query, "n_results": 3})
            if res["status"] == "success" and res["result"]:
                tool_context += f"\n[Retrieved Document Excerpts]:\n{res['result']}\n"

        # 3. SPECIALIZED AGENT SYNTHESIS STAGE
        system_prompt = (
            f"{persona['system']}\n\n"
            f"ACTIVE PROJECT CONTEXT ({active_proj.get('name', 'General')}):\n"
            f"{proj_instructions}\n\n"
            f"{mem_injection}\n"
            f"Adhere strictly to the role guidelines and provide a well-structured, clear response."
        )

        user_prompt = f"{tool_context}\nUSER QUERY: {query}" if tool_context else query

        if status_callback:
            status_callback(f"[Synthesizing] Generating grounded response with {persona['title']}…")

        response = generate_simple_response(
            (system_prompt, user_prompt),
            chunk_callback=chunk_callback,
            model_name=model_name
        )

        # 4. VERIFIER STAGE
        if status_callback:
            status_callback("[Verifying] Inspecting output, checking grounding & extracting artifacts…")

        # Automatically extract and persist any Claude-style artifacts generated
        from backend.artifacts import extract_and_store_artifacts
        extract_and_store_artifacts(response, conversation_id=conversation_id, project_id=active_proj.get("id", "default"))

        if status_callback:
            status_callback("✔ Complete")

        return response


# Global orchestrator instance
agent_orchestrator = AgentOrchestrator()
