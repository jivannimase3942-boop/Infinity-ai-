"""
Infinity AI - Offline-First Deep Research Engine
Executes structured local research workflows:
Research Goal -> Break into subtopics -> Search LOCAL knowledge/documents -> Retrieve evidence -> Analyze -> Cross-check -> Identify uncertainty -> Generate Report.
100% Offline-First. Never fakes internet search if offline.
"""

from typing import Dict, Any, List, Optional, Callable
from backend.rag_engine import retrieve_context_with_citations
from backend.ai_engine import generate_simple_response

class DeepResearchEngine:
    def __init__(self):
        pass

    def run_research(
        self,
        topic: str,
        model_name: Optional[str] = None,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """Executes the deep research pipeline and formats structured output."""
        if status_callback:
            status_callback(f"[Research] Formulating goal and decomposing '{topic}' into subtopics…")

        subtopics = [
            f"Core fundamentals and definitions of {topic}",
            f"Key mechanisms, architectures, and state-of-the-art of {topic}",
            f"Practical applications, limitations, and challenges in {topic}"
        ]

        if status_callback:
            status_callback("[Research] Querying local document vectors and knowledge base…")

        local_evidence = []
        citations_found = []

        for sub in subtopics:
            rag_res = retrieve_context_with_citations(sub, n_results=2)
            if rag_res.get("context"):
                local_evidence.append(rag_res["context"])
            if rag_res.get("citations"):
                citations_found.extend(rag_res["citations"])

        has_local_data = len(local_evidence) > 0
        evidence_text = "\n\n".join(local_evidence) if has_local_data else "No specific local document evidence found."

        if status_callback:
            status_callback("[Research] Synthesizing findings and cross-checking evidence…")

        prompt = (
            f"You are Infinity AI's Deep Research Agent. Produce a comprehensive, structured research report on: '{topic}'.\n\n"
            f"LOCAL EVIDENCE RETRIEVED:\n{evidence_text}\n\n"
            f"OUTPUT FORMAT REQUIREMENT:\n"
            f"Produce your final report using these EXACT markdown headers:\n"
            f"# Research Report: {topic}\n\n"
            f"## Executive Summary\n"
            f"(2-3 paragraphs synthesizing the core thesis)\n\n"
            f"## Key Findings\n"
            f"(Bulleted analysis of critical insights)\n\n"
            f"## Evidence & Citations\n"
            f"({ 'Grounded citations from local files: ' + str([c['document'] for c in citations_found]) if citations_found else 'Note: Sourced from local offline model knowledge; no matching local documents in workspace.' })\n\n"
            f"## Contradictions / Uncertainty\n"
            f"(Analysis of caveats, competing viewpoints, or limitations)\n\n"
            f"## Conclusions\n"
            f"(Strategic implications and practical takeaways)\n\n"
            f"## References\n"
            f"(List references and local knowledge sources)"
        )

        report = generate_simple_response(
            ("You are an expert research scientist. Provide a rigorous, grounded, high-signal research report.", prompt),
            model_name=model_name
        )

        if status_callback:
            status_callback("✔ Research Report Complete")

        return report

# Global instance
deep_research_engine = DeepResearchEngine()
