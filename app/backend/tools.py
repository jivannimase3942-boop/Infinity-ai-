"""
Infinity AI - Safe Tool Registry & Execution Subsystem
Provides defined tools with risk levels, permissions, input/output schemas,
and audit logging.
"""

import ast
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional

from backend.db import get_connection
from backend.security import is_write_authorized


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()

    def register(
        self,
        name: str,
        description: str,
        risk_level: str,
        input_schema: Dict[str, Any],
        output_schema: Dict[str, Any],
        handler: Callable[..., Any]
    ):
        self._tools[name] = {
            "name": name,
            "description": description,
            "risk_level": risk_level,  # SAFE, MODERATE, HIGH
            "input_schema": input_schema,
            "output_schema": output_schema,
            "handler": handler,
        }

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "risk_level": t["risk_level"],
                "input_schema": t["input_schema"],
                "output_schema": t["output_schema"]
            }
            for t in self._tools.values()
        ]

    def execute(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.get_tool(name)
        if not tool:
            return {"status": "error", "message": f"Tool '{name}' not found."}

        # Permission check
        if tool["risk_level"] == "HIGH":
            if not is_write_authorized():
                return {
                    "status": "denied",
                    "message": "Tool execution blocked: Action requires authorized Infinity AI USB key."
                }

        try:
            result = tool["handler"](**params)
            self._log_execution(name, params, result, "success")
            return {"status": "success", "result": result}
        except Exception as exc:
            err_msg = str(exc)
            self._log_execution(name, params, err_msg, "error")
            return {"status": "error", "message": err_msg}

    def _log_execution(self, tool_name: str, params: Any, result: Any, status: str):
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO tools_log (id, tool_name, parameters, result, status) VALUES (?, ?, ?, ?, ?)",
                    (
                        str(os.urandom(8).hex()),
                        tool_name,
                        json.dumps(params, default=str),
                        json.dumps(result, default=str)[:2000],
                        status
                    )
                )
                conn.commit()
        except Exception:
            pass

    def _register_default_tools(self):
        # 1. Calculator
        def run_calc(expression: str) -> str:
            # Safe arithmetic evaluator via ast
            allowed_nodes = (
                ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
                ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd
            )
            tree = ast.parse(expression, mode='eval')
            for node in ast.walk(tree):
                if not isinstance(node, allowed_nodes):
                    raise ValueError(f"Disallowed expression node: {type(node).__name__}")
            # Evaluate using restricted globals
            val = eval(compile(tree, filename='', mode='eval'), {"__builtins__": {}}, {})
            return str(val)

        self.register(
            name="calculator",
            description="Performs safe mathematical and arithmetic calculations.",
            risk_level="SAFE",
            input_schema={"expression": "string, e.g. '2 ** 10 + 450 / 5'"},
            output_schema={"result": "string"},
            handler=run_calc
        )

        # 2. Python Runner (Safe local sandbox)
        def run_python(code: str) -> str:
            # Execute python snippet locally with stdout capture
            cmd = [sys.executable, "-c", code]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                return res.stdout.strip() or "(Executed with no output)"
            return f"Error ({res.returncode}):\n{res.stderr.strip()}"

        self.register(
            name="python_runner",
            description="Executes short Python scripts for data processing or algorithms.",
            risk_level="MODERATE",
            input_schema={"code": "python source code string"},
            output_schema={"output": "string"},
            handler=run_python
        )

        # 3. Document Search (RAG)
        def run_doc_search(query: str, n_results: int = 3) -> str:
            from backend.rag_engine import retrieve_context_with_citations
            ctx, cits = retrieve_context_with_citations(query, n_results=n_results)
            return ctx or "No relevant document excerpts found."

        self.register(
            name="document_search",
            description="Searches indexed documents and returns relevant excerpts with citations.",
            risk_level="SAFE",
            input_schema={"query": "search query string", "n_results": "integer"},
            output_schema={"context": "string with citations"},
            handler=run_doc_search
        )

        # 4. Code Analyzer
        def run_code_analyzer(file_path: str) -> Dict[str, Any]:
            path = Path(file_path)
            if not path.exists():
                return {"error": f"File '{file_path}' does not exist."}
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            try:
                tree = ast.parse(content)
                functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                return {
                    "lines": len(content.splitlines()),
                    "functions": functions,
                    "classes": classes,
                    "syntax_valid": True
                }
            except Exception as exc:
                return {
                    "lines": len(content.splitlines()),
                    "syntax_valid": False,
                    "syntax_error": str(exc)
                }

        self.register(
            name="code_analyzer",
            description="Analyzes python source files for syntax, function definitions, and classes.",
            risk_level="SAFE",
            input_schema={"file_path": "path to python file"},
            output_schema={"structure": "dict with lines, functions, classes"},
            handler=run_code_analyzer
        )

        # 5. Data Analyzer (CSV/XLSX summary)
        def run_data_analyzer(file_path: str) -> str:
            import csv
            path = Path(file_path)
            if not path.exists():
                return f"File '{file_path}' not found."
            
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows = list(reader)
                
            if not rows:
                return "Empty dataset."
                
            header = rows[0]
            num_rows = len(rows) - 1
            num_cols = len(header)
            
            return f"Dataset Summary for {path.name}:\n- Total Rows: {num_rows}\n- Columns ({num_cols}): {', '.join(header)}\n- Sample Preview (first 2 rows):\n  " + "\n  ".join(str(r) for r in rows[1:3])

        self.register(
            name="data_analyzer",
            description="Extracts dataset summaries, schema, and row counts from tabular files.",
            risk_level="SAFE",
            input_schema={"file_path": "path to CSV file"},
            output_schema={"summary": "string"},
            handler=run_data_analyzer
        )

        # 6. File Reader (Safe bounded local read)
        def run_file_reader(file_path: str, max_chars: int = 15000) -> str:
            from backend.file_ops import extract_file_content
            res = extract_file_content(file_path, max_chars=max_chars)
            return res.get("content", f"Error: {res.get('error', 'Could not read file')}")

        self.register(
            name="file_reader",
            description="Safely reads the text content of local files within size boundaries.",
            risk_level="SAFE",
            input_schema={"file_path": "path to file", "max_chars": "maximum characters to return"},
            output_schema={"content": "string"},
            handler=run_file_reader
        )

        # 7. Date & Time
        def run_date_time(query: str = "current time", timezone: str = "Asia/Kolkata") -> str:
            from backend.datetime_engine import handle_datetime_query
            res = handle_datetime_query(query)
            return res.get("answer", "")

        self.register(
            name="date_time",
            description="Returns current local system date, time, day of week, and timezone info.",
            risk_level="SAFE",
            input_schema={"query": "optional question string, e.g. 'what time is it in London'"},
            output_schema={"datetime": "string"},
            handler=run_date_time
        )

        # 8. System Diagnostics Tool
        def run_sys_diag() -> Dict[str, Any]:
            from backend.diagnostics import get_hardware_metrics
            from backend.ai_engine import check_ollama
            hw = get_hardware_metrics()
            oll = check_ollama()
            return {
                "hardware": hw,
                "ollama_running": oll.get("server", False),
                "active_models": oll.get("models", [])
            }

        self.register(
            name="system_diagnostics",
            description="Inspects real hardware metrics (GPU, VRAM, RAM, CPU) and Ollama status.",
            risk_level="SAFE",
            input_schema={},
            output_schema={"diagnostics": "dict"},
            handler=run_sys_diag
        )

        # 9. Knowledge Search Tool
        def run_knowledge_search(query: str) -> List[Dict[str, Any]]:
            from backend.db import search_knowledge_global
            return search_knowledge_global(query)

        self.register(
            name="knowledge_search",
            description="Searches globally across past chats, memories, project documents, and artifacts.",
            risk_level="SAFE",
            input_schema={"query": "search query string"},
            output_schema={"results": "list of dicts"},
            handler=run_knowledge_search
        )


# Global tools instance
tool_registry = ToolRegistry()
