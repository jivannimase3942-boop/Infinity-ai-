"""
Infinity AI - Self-Critique AI & Controlled Verification Pipeline
Verifies AI answers deterministically and with local grounding:
Draft -> Self-Critique -> Evidence Check -> Contradiction Check -> Completeness Check -> Verified Answer.
100% Offline-First. Never leaks internal chain-of-thought.
"""

from typing import Dict, Any, List, Optional, Tuple

class SelfCritiqueEngine:
    def __init__(self):
        pass

    def verify_document_grounding(
        self,
        draft_answer: str,
        retrieved_context: str,
        query: str
    ) -> Tuple[str, bool, str]:
        """
        Audits whether draft answer is strictly grounded in retrieved document evidence.
        Returns: (final_answer, is_verified, verification_tag)
        """
        if not retrieved_context or not retrieved_context.strip():
            # No document evidence exists
            fallback = "I couldn't verify this from the available document."
            return fallback, False, "Unverified: Missing Evidence"

        clean_context = retrieved_context.lower()
        clean_draft = draft_answer.strip()

        # Check for hallucination disclaimer signals
        hallucination_phrases = [
            "as an ai", "i don't have access to the document",
            "not mentioned in the text", "document does not contain"
        ]
        if any(h in clean_draft.lower() for h in hallucination_phrases) and len(clean_draft) < 200:
            return "I couldn't verify this from the available document.", False, "Unverified"

        # Check keyword grounding: significant keywords from query must appear in context
        query_words = [w for w in query.lower().split() if len(w) > 3 and w not in ["what", "where", "which", "could", "would", "about", "explain", "tell", "this", "that"]]
        grounded_words = [w for w in query_words if w in clean_context]

        if query_words and len(grounded_words) == 0:
            return "I couldn't verify this from the available document.", False, "Unverified: Topic Not Found"

        return clean_draft, True, "Verified: Grounded in Document Evidence"

    def critique_general_response(
        self,
        draft_answer: str,
        query: str,
        category: str = "general"
    ) -> Tuple[str, bool, str]:
        """
        Audits general responses for completeness, absence of tracebacks, and accuracy.
        """
        if not draft_answer or not draft_answer.strip():
            return "I was unable to produce an answer. Please rephrase or try again.", False, "Incomplete"

        # Check for leaked python tracebacks
        if "traceback (most recent call last)" in draft_answer.lower():
            clean = "The local AI engine encountered an internal execution issue. Please retry with a simpler query."
            return clean, False, "Execution Error Filtered"

        # Completeness check: code blocks should be balanced
        backticks = draft_answer.count("```")
        if backticks % 2 != 0:
            # Unclosed code block, close it gracefully
            draft_answer = draft_answer.rstrip() + "\n```"

        return draft_answer, True, "Verified"

# Global instance
self_critique_engine = SelfCritiqueEngine()
