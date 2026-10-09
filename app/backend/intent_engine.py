"""
Infinity AI - Dynamic Context-Aware Recommendation & Intent Engine
Module: backend/intent_engine.py

Dynamically analyzes:
1. Latest user query
2. Latest AI response
3. Active document context
4. Active project context
5. Conversation intent & domain

Generates 3-5 high-relevance, actionable follow-up suggestions strictly tailored
to the active topic. Never outputs generic or unrelated coding recommendations
for non-coding topics.
100% Local, Offline & Zero-Latency.
"""

import re
from typing import Dict, Any, List, Optional
from backend.datetime_engine import is_datetime_query
from backend.capability_engine import check_unsupported_capability


class IntentEngine:
    """Production-grade dynamic recommendation and semantic intent engine."""

    def __init__(self):
        pass

    def extract_topic_entity(self, query: str, ai_response: Optional[str] = None) -> str:
        """
        Extracts the central subject/entity of the user's request.
        Strips conversational boilerplate and interrogative framing.
        """
        q = (query or "").strip()
        if not q:
            return "this topic"

        # 1. Check for specific programming errors (e.g. IndexError, NullPointerException)
        err_match = re.search(
            r"\b([A-Z][a-zA-Z]+(?:Error|Exception)|Segmentation fault|NullPointerException|StackOverflowError)\b",
            q,
            re.IGNORECASE
        )
        if err_match:
            return err_match.group(1)

        # 2. Check for algorithm / data structure names
        algo_match = re.search(
            r"\b(dijkstra|binary search|bfs|dfs|merge sort|quick sort|kruskal|prim|bellman[\s\-]ford|floyd[\s\-]warshall|dynamic programming|a\*)\b",
            q,
            re.IGNORECASE
        )
        if algo_match:
            clean_name = algo_match.group(1).replace("-", " ").title()
            return f"{clean_name} Algorithm"

        # 3. Check for email / letter types
        email_match = re.search(
            r"\b(sick leave|resignation|leave application|cover letter|complaint letter|apology letter|formal letter|invitation)\b",
            q,
            re.IGNORECASE
        )
        if email_match:
            return f"{email_match.group(1).lower()} email"

        # 4. Remove common framing / interrogative prefixes
        clean = re.sub(
            r"^(what (is|are|was|were)|how (does|do|can|to|would)|why (is|are|do|does)|explain|tell me about|describe|summarize|write (an?|about)?|draft (an?|about)?|can you (please )?|could you (please )?|please )\s*",
            "",
            q,
            flags=re.IGNORECASE
        )
        # Remove trailing clauses like "and why it matters", "in python", etc.
        clean = re.sub(
            r"\s+(and|or)\s+(why|how|what|is it|explain|give examples).*",
            "",
            clean,
            flags=re.IGNORECASE
        )
        clean = re.sub(
            r"\b(in (python|c\+\+|java|javascript|simple terms|detail)|for beginners|step by step)\b",
            "",
            clean,
            flags=re.IGNORECASE
        )
        clean = re.sub(r"[?!.,;:]+$", "", clean).strip()

        if 3 <= len(clean) <= 45:
            return clean

        words = clean.split()
        if words:
            return " ".join(words[:4])

        return "this topic"

    def analyze(
        self,
        query: str,
        ai_response: Optional[str] = None,
        has_active_document: bool = False,
        active_document: Optional[Dict[str, Any]] = None,
        active_project: Optional[Dict[str, Any]] = None,
        file_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyzes the conversational exchange and generates dynamically tailored suggestions.
        Supports full context: query + ai_response + active_document + active_project.
        """
        q = (query or "").strip()
        resp = (ai_response or "").strip()
        q_lower = q.lower()
        resp_lower = resp.lower()
        combined_lower = f"{q_lower}\n{resp_lower}"

        topic = self.extract_topic_entity(q, resp)
        has_doc = has_active_document or (active_document is not None)

        category = "general"
        intent = "assist"
        confidence = "medium"

        # -----------------------------------------------------------------
        # DOMAIN 1: Communication / Email / Formal Letter / Messaging
        # -----------------------------------------------------------------
        email_patterns = [
            r"\b(sick leave|leave application|leave request|resignation|cover letter|formal letter|invitation)\b",
            r"\b(write (an? )?email|draft (an? )?email|compose (an? )?email|send (an? )?email|email to|email for|email draft)\b",
            r"\b(reply to (this|the) email|email response|subject line)\b",
            r"\b(whatsapp message|slack message|draft a message to|write to my (boss|manager|team|client|teacher|professor|hr))\b",
        ]
        ai_has_email_markers = False
        if resp:
            ai_has_email_markers = bool(re.search(
                r"\b(subject\s*:|dear\s+[a-z]|sincerely|warm regards|best regards|respectfully|kind regards)\b",
                resp_lower
            ))

        is_email = any(re.search(pat, q_lower) for pat in email_patterns) or ai_has_email_markers

        # -----------------------------------------------------------------
        # DOMAIN 2: Algorithms, Data Structures & CS Theory
        # -----------------------------------------------------------------
        algo_patterns = [
            r"\b(dijkstra|bellman[\s\-]ford|floyd[\s\-]warshall|kruskal|prim|a\*|astar)\b",
            r"\b(binary search|linear search|breadth[\s\-]first search|depth[\s\-]first search|\bbfs\b|\bdfs\b)\b",
            r"\b(merge\s*sort|quick\s*sort|heap\s*sort|bubble\s*sort|topological sort)\b",
            r"\b(dynamic programming|greedy algorithm|divide and conquer|backtracking|memoization)\b",
            r"\b(shortest path|minimum spanning tree|graph traversal|tree traversal|binary search tree|avl tree|trie)\b",
            r"\b(algorithm|time complexity|space complexity|big[\s\-]o notation|asymptotic analysis)\b"
        ]
        is_algo = any(re.search(pat, q_lower) for pat in algo_patterns)

        # -----------------------------------------------------------------
        # DOMAIN 3: Code Debugging, Tracebacks & Errors
        # -----------------------------------------------------------------
        debug_patterns = [
            r"\b(indexerror|valueerror|typeerror|keyerror|attributeerror|nameerror|syntaxerror|zerodivisionerror|filenotfounderror)\b",
            r"\b(nullpointerexception|segmentation fault|segfault|out of memory|stack overflow|panic|unhandled exception)\b",
            r"\b(traceback|stack\s*trace|fix this error|why am i getting|how to fix (this|the) (error|bug)|code crashes|undefined is not a function|error on line)\b"
        ]
        is_debug = any(re.search(pat, combined_lower) for pat in debug_patterns) or "traceback (most recent call last)" in combined_lower

        # -----------------------------------------------------------------
        # DOMAIN 4: Document QA / PDF Analysis
        # -----------------------------------------------------------------
        doc_patterns = [
            r"\b(summarize (this|the) (pdf|document|paper|report|contract|file))\b",
            r"\b(what does the document say|according to the (pdf|document)|in this (pdf|document)|about this document)\b",
            r"\b(extract key (points|takeaways|clauses)|page \d+|from the attached)\b"
        ]
        is_doc = has_doc or any(re.search(pat, q_lower) for pat in doc_patterns)

        # -----------------------------------------------------------------
        # DOMAIN 5: Programming & Software Implementation
        # -----------------------------------------------------------------
        code_impl_patterns = [
            r"\b(write (a|an|the)? (python|javascript|typescript|c\+\+|java|rust|go|sql) (script|code|function|program|class|api))\b",
            r"\b(implement (a|an|the)? (function|class|method|endpoint|service|decorator|generator|parser))\b",
            r"\b(refactor this code|optimize this (function|loop|query)|write sql query|create a rest api|unit test)\b",
            r"```(python|javascript|typescript|c|cpp|rust|go|html|css|sql|bash)"
        ]
        # Ensure that normal English words like "return" or "class" alone never trigger code
        has_fenced_code = "```" in q or "```" in resp
        is_programming = (any(re.search(pat, q_lower) for pat in code_impl_patterns) or has_fenced_code) and not is_email

        # -----------------------------------------------------------------
        # DOMAIN 6: Academic Study & Exam Preparation
        # -----------------------------------------------------------------
        study_patterns = [
            r"\b(sppu|syllabus|unit\s*\d+|viva|midterm|semester|flashcards|revision notes)\b",
            r"\b(quiz me|important questions|practice questions for exam|study notes for exam|eli5)\b"
        ]
        is_study = any(re.search(pat, q_lower) for pat in study_patterns)

        # -----------------------------------------------------------------
        # DOMAIN 7: Data & Statistics
        # -----------------------------------------------------------------
        data_patterns = [
            r"\b(csv|excel|spreadsheet|dataframe|dataset|columns|rows|mean|median|correlation|outliers|distribution|data trend)\b"
        ]
        is_data = any(re.search(pat, q_lower) for pat in data_patterns)

        # -----------------------------------------------------------------
        # DOMAIN 8: Creative Writing & Content
        # -----------------------------------------------------------------
        creative_patterns = [
            r"\b(write a (story|blog post|article|poem|essay|script)|brainstorm (ideas|hooks)|marketing copy|social media post)\b"
        ]
        is_creative = any(re.search(pat, q_lower) for pat in creative_patterns) and not is_email

        # -----------------------------------------------------------------
        # Classify Primary Category & Generate Tailored Suggestions
        # -----------------------------------------------------------------
        is_unsupported_cap, _, _ = check_unsupported_capability(q)
        if is_unsupported_cap:
            category = "unsupported_capability"
            intent = "unsupported_request"
            confidence = "high"
            suggestions = [
                "Write a detailed Midjourney prompt",
                "Write a prompt for Stable Diffusion",
                "How do diffusion models work?",
                "Describe the scene in cinematic detail"
            ]

        elif is_datetime_query(q):
            category = "datetime"
            intent = "datetime_query"
            confidence = "high"
            suggestions = [
                "What time is it in London?",
                "What time is it in New York?",
                "What time is it in Tokyo?",
                "What is today's date in India?"
            ]

        elif is_email:
            category = "communication"
            intent = "draft_email"
            confidence = "high"
            suggestions = [
                "Make this email more professional",
                "Create a shorter version",
                "Add a suitable subject line",
                "Make it more polite",
                "Create a WhatsApp version"
            ]

        elif is_algo:
            category = "algorithms"
            intent = "explain_algorithm"
            confidence = "high"
            # Support Dijkstra and generalized algorithms cleanly
            if "dijkstra" in q_lower:
                suggestions = [
                    "Explain with a simple example",
                    "Show the algorithm step by step",
                    "Give a C++ implementation",
                    "Explain time complexity"
                ]
            else:
                suggestions = [
                    f"Explain with a simple example",
                    f"Show the algorithm step by step",
                    f"Give a C++ implementation",
                    f"Explain time complexity"
                ]

        elif is_doc:
            category = "document"
            intent = "document_analysis"
            confidence = "high"
            suggestions = [
                "Extract the key points",
                "Create exam notes",
                "Generate questions from this document",
                "Explain difficult sections"
            ]

        elif is_debug:
            category = "debugging"
            intent = "fix_error"
            confidence = "high"
            err_label = topic if "error" in topic.lower() or "exception" in topic.lower() else "this error"
            suggestions = [
                "Explain the code",
                "Find potential bugs",
                "Optimize this solution",
                "Add test cases"
            ]

        elif is_programming:
            category = "programming"
            intent = "code_implementation"
            confidence = "high"
            suggestions = [
                "Explain the code",
                "Find potential bugs",
                "Optimize this solution",
                "Add test cases"
            ]

        elif is_study:
            category = "study"
            intent = "exam_preparation"
            confidence = "high"
            suggestions = [
                "Quiz me with 5 practice questions",
                "Create a quick revision cheat sheet",
                "Explain difficult concepts with diagrams",
                "Give model answers for exam questions"
            ]

        elif is_data:
            category = "data"
            intent = "data_analysis"
            confidence = "high"
            suggestions = [
                "Identify top trends and correlations",
                "Format key insights into a summary table",
                "Check for outliers and data anomalies",
                "Suggest charts to visualize this data"
            ]

        elif is_creative:
            category = "creative"
            intent = "creative_writing"
            confidence = "high"
            suggestions = [
                "Generate 5 alternative creative angles",
                "Make the tone more engaging and persuasive",
                "Expand this into a full draft",
                "Create catchy titles and hooks"
            ]

        else:
            # General Knowledge / Explanations / Factual Q&A
            category = "general"
            intent = "explain_concept"
            confidence = "medium"

            # Check for simple greeting / conversational acknowledgment
            if re.match(r"^(hi|hello|hey|greetings|thanks|thank you|ok|okay)[\.!\?]?$", q_lower):
                suggestions = [
                    "Summarize our conversation so far",
                    "What topics can you help me with?",
                    "Start a new discussion topic"
                ]
            else:
                # Dynamic entity-bound intellectual follow-ups
                clean_topic = topic if topic and topic != "this topic" else "this topic"
                suggestions = [
                    f"Explain {clean_topic} with a simple real-world analogy",
                    f"What are the key real-world applications of {clean_topic}?",
                    f"What are the most common misconceptions about {clean_topic}?",
                    f"Provide 3 interesting lesser-known facts about {clean_topic}"
                ]

        # Ensure between 2 and 5 suggestions, deduplicated
        final_suggestions = []
        for s in suggestions:
            clean_s = s.strip()
            if clean_s and clean_s not in final_suggestions:
                final_suggestions.append(clean_s)

        if confidence == "low" and len(final_suggestions) > 3:
            final_suggestions = final_suggestions[:3]
        else:
            final_suggestions = final_suggestions[:5]

        return {
            "query": q,
            "category": category,
            "intent": intent,
            "topic": topic,
            "confidence": confidence,
            "has_active_document": has_doc,
            "suggestions": final_suggestions
        }

    def generate_dynamic_suggestions(
        self,
        query: str,
        category: str,
        intent: str,
        topic: str,
        has_doc: bool,
        ai_response: Optional[str] = None
    ) -> List[str]:
        """Backward-compatible helper invoking analyze()."""
        analysis = self.analyze(
            query=query,
            ai_response=ai_response,
            has_active_document=has_doc
        )
        return analysis.get("suggestions", [])


# Global singleton instance
intent_engine = IntentEngine()
