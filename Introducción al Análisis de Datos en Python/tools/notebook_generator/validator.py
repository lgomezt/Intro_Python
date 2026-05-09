"""Validate notebook code by executing it in a persistent context."""

import sys
import io
import contextlib
import traceback
import types as builtin_types
from typing import Dict, Any, Tuple, List
from .models import NotebookCell, CellType


class ValidationSession:
    """Maintains state across multiple cell executions."""

    def __init__(self):
        self.namespace: Dict[str, Any] = {}
        self.executed_code: List[str] = []

    def reset(self):
        """Clear namespace and execution history."""
        self.namespace.clear()
        self.executed_code.clear()

    def execute_cell(self, cell: NotebookCell) -> Tuple[bool, str, str]:
        """Execute a single code cell.

        Returns:
            (success, stdout, stderr/error_message)
        """
        if cell.cell_type != CellType.CODE:
            return True, "", ""

        code = cell.source

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        success = True
        error_msg = ""

        try:
            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                exec(code, self.namespace)
        except Exception:
            success = False
            error_msg = traceback.format_exc()

        stdout = stdout_capture.getvalue()
        stderr = stderr_capture.getvalue() + error_msg

        if success:
            self.executed_code.append(code)

        return success, stdout, stderr

    def get_defined_functions(self) -> List[str]:
        """Return names of user-defined functions in the namespace."""
        return [
            name for name, val in self.namespace.items()
            if not name.startswith("__")
            and isinstance(val, builtin_types.FunctionType)
        ]

    def get_context_summary(self) -> str:
        """Return a summary of defined variables for LLM context."""
        vars_summary = []
        for name, val in self.namespace.items():
            if name.startswith("__"):
                continue
            type_name = type(val).__name__
            val_str = str(val)
            if len(val_str) > 50:
                val_str = val_str[:50] + "..."
            vars_summary.append(f"{name}: {type_name} = {val_str}")

        return "\n".join(vars_summary)

    def get_full_code_history(self) -> str:
        """Return all successfully executed code."""
        return "\n\n".join(self.executed_code)

    @staticmethod
    def format_cell_outputs(stdout: str, stderr: str) -> List[Dict[str, Any]]:
        """Format execution results as notebook cell outputs."""
        outputs: List[Dict[str, Any]] = []
        if stdout:
            outputs.append({
                "output_type": "stream",
                "name": "stdout",
                "text": stdout.splitlines(keepends=True),
            })
        if stderr:
            outputs.append({
                "output_type": "stream",
                "name": "stderr",
                "text": stderr.splitlines(keepends=True),
            })
        return outputs
