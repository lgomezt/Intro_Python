"""Core generator logic for the notebook generator."""

import json
import logging
from pathlib import Path
from typing import List, Any

from google.genai import types

from .config import client, MODEL_NAME, DEFAULT_TEMPERATURE
from .models import (
    Blueprint,
    PartSpec,
    CellSpec,
    NotebookCell,
    CellType,
    Language,
)

logger = logging.getLogger(__name__)
PROMPTS_DIR = Path(__file__).parent / "prompts"

LANGUAGE_NAMES = {
    Language.ENGLISH: "English",
    Language.SPANISH: "Spanish",
}


# ---------------------------------------------------------------------------
# Utility helpers (kept from v1)
# ---------------------------------------------------------------------------

def _load_prompt(filename: str) -> str:
    """Load a prompt template."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = DEFAULT_TEMPERATURE,
    response_schema: Any = None,
) -> str:
    """Execute LLM call."""
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_prompt)],
        )
    ]

    config_args = {
        "system_instruction": system_prompt,
        "temperature": temperature,
    }

    if response_schema:
        config_args["response_mime_type"] = "application/json"
        config_args["response_schema"] = response_schema

    config = types.GenerateContentConfig(**config_args)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=config,
    )
    return response.text


def _clean_json_response(text: str) -> str:
    """Strip markdown code fences from JSON response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _fix_invalid_json_escapes(text: str) -> str:
    """Fix invalid JSON escape sequences (e.g. \\L from LaTeX \\log).

    Only called as a fallback when json.loads fails with a decode error.
    Valid JSON escapes: \\\" \\\\ \\/ \\b \\f \\n \\r \\t \\uXXXX
    Any other \\X is replaced with \\\\X (double-escaped).
    """
    import re

    def _fix(m: re.Match) -> str:
        char = m.group(1)
        if char in ('"', "\\", "/", "b", "f", "n", "r", "t", "u"):
            return m.group(0)
        return "\\\\" + char

    return re.sub(r"\\(.)", _fix, text)


def _safe_json_loads(text: str):
    """Parse JSON, retrying with escape-fix on failure."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        fixed = _fix_invalid_json_escapes(text)
        return json.loads(fixed)


# ---------------------------------------------------------------------------
# Interview
# ---------------------------------------------------------------------------

def generate_interview_questions(goal: str, context_text: str) -> List[str]:
    """Generate tailored interview questions from the session goal and context."""
    prompt = _load_prompt("interview.md")
    system_prompt = (
        prompt
        .replace("{goal}", goal)
        .replace("{context_text}", context_text or "(No context provided)")
    )

    response = _call_llm(
        system_prompt,
        "Generate interview questions.",
        temperature=0.5,
    )
    return _safe_json_loads(_clean_json_response(response))


# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

def generate_blueprint(
    goal: str,
    answers: dict[str, str],
    context_text: str,
    language: Language,
) -> Blueprint:
    """Generate a cell-by-cell structural blueprint for the notebook."""
    prompt = _load_prompt("blueprint.md")
    lang_name = LANGUAGE_NAMES[language]

    answers_text = "\n".join(
        f"  Q: {q}\n  A: {a}" for q, a in answers.items()
    )

    system_prompt = (
        prompt
        .replace("{goal}", goal)
        .replace("{answers}", answers_text or "(No answers)")
        .replace("{context_text}", context_text or "(No context provided)")
        .replace("{language}", language.value)
        .replace("{language_name}", lang_name)
    )

    response = _call_llm(
        system_prompt,
        "Generate the notebook blueprint.",
        temperature=0.4,
    )
    data = _safe_json_loads(_clean_json_response(response))
    return Blueprint(**data)


def modify_blueprint(blueprint: Blueprint, user_feedback: str) -> Blueprint:
    """Regenerate the blueprint incorporating user feedback."""
    prompt = _load_prompt("blueprint.md")
    lang_name = LANGUAGE_NAMES[blueprint.language]

    system_prompt = (
        prompt
        .replace("{goal}", blueprint.title)
        .replace("{answers}", "(see existing blueprint)")
        .replace("{context_text}", "(see existing blueprint)")
        .replace("{language}", blueprint.language.value)
        .replace("{language_name}", lang_name)
    )

    user_prompt = (
        f"Here is the current blueprint:\n\n"
        f"```json\n{blueprint.model_dump_json(indent=2)}\n```\n\n"
        f"The user wants these changes:\n{user_feedback}\n\n"
        f"Regenerate the full blueprint incorporating the feedback. "
        f"Keep cell_ids sequential starting from 0."
    )

    response = _call_llm(system_prompt, user_prompt, temperature=0.4)
    data = _safe_json_loads(_clean_json_response(response))
    return Blueprint(**data)


# ---------------------------------------------------------------------------
# Part generation
# ---------------------------------------------------------------------------

def _format_previous_cells(cells: List[NotebookCell]) -> str:
    """Format previously generated cells as text for the LLM."""
    if not cells:
        return "(This is the first part — no previous cells.)"

    parts = []
    for i, cell in enumerate(cells):
        if cell.cell_type == CellType.MARKDOWN:
            parts.append(f"--- Cell {i} [markdown] ---\n{cell.source}")
        else:
            parts.append(f"--- Cell {i} [code] ---\n```python\n{cell.source}\n```")
    return "\n\n".join(parts)


def generate_part(
    blueprint: Blueprint,
    part_number: int,
    previous_cells: List[NotebookCell],
) -> List[NotebookCell]:
    """Generate full content for one Part of the notebook."""
    prompt = _load_prompt("part_generation.md")
    lang_name = LANGUAGE_NAMES[blueprint.language]

    part: PartSpec = blueprint.parts[part_number]
    cell_ids = [c.cell_id for c in part.cells]
    cell_id_start = min(cell_ids)
    cell_id_end = max(cell_ids)

    system_prompt = (
        prompt
        .replace("{language_name}", lang_name)
        .replace("{part_number}", str(part.part_number))
        .replace("{part_title}", part.part_title)
        .replace("{blueprint_json}", blueprint.model_dump_json(indent=2))
        .replace("{cell_id_start}", str(cell_id_start))
        .replace("{cell_id_end}", str(cell_id_end))
        .replace("{previous_cells_text}", _format_previous_cells(previous_cells))
        .replace("{num_cells}", str(len(part.cells)))
    )

    response = _call_llm(
        system_prompt,
        f"Generate content for Part {part.part_number}: {part.part_title}",
        temperature=0.3,
    )

    cells_data = _safe_json_loads(_clean_json_response(response))
    return [NotebookCell(**c) for c in cells_data]


# ---------------------------------------------------------------------------
# Cell repair
# ---------------------------------------------------------------------------

def repair_cell(
    failing_code: str,
    error: str,
    context_summary: str,
    code_history: str,
    cell_spec: CellSpec,
) -> str:
    """Attempt to fix a failing code cell. Returns the repaired code string."""
    prompt = _load_prompt("cell_repair.md")

    system_prompt = (
        prompt
        .replace("{failing_code}", failing_code)
        .replace("{error}", error)
        .replace("{cell_role}", cell_spec.role.value)
        .replace("{content_brief}", cell_spec.content_brief)
        .replace("{defines}", ", ".join(cell_spec.defines) or "(none)")
        .replace("{uses}", ", ".join(cell_spec.uses) or "(none)")
        .replace("{context_summary}", context_summary or "(empty namespace)")
        .replace("{code_history}", code_history or "(no prior code)")
    )

    response = _call_llm(
        system_prompt,
        "Fix this code cell.",
        temperature=0.2,
    )

    # The response should be raw code, but strip fences just in case
    code = response.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines)

    return code.strip()
