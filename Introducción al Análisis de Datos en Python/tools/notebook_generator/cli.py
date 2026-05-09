#!/usr/bin/env python3
"""CLI for the notebook generator v2."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .models import (
    Blueprint,
    CellSpec,
    InterviewResult,
    Language,
    NotebookCell,
    CellType,
)
from .generator import (
    generate_interview_questions,
    generate_blueprint,
    modify_blueprint,
    generate_part,
    repair_cell,
)
from .validator import ValidationSession
from .formatter import create_notebook_json
from .input_parsers import parse_input

# ---------------------------------------------------------------------------
# Terminal colours
# ---------------------------------------------------------------------------
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
DIM = "\033[2m"
RESET = "\033[0m"

MAX_REPAIR_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_header(title: str):
    print(f"\n{BOLD}{CYAN}{'=' * 50}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 50}{RESET}")


def _ask_language() -> Language:
    """Prompt the user to select the output language."""
    print(f"\n{BOLD}Select output language:{RESET}")
    print("  1. English (en)")
    print("  2. Spanish (es)")
    while True:
        choice = input("> ").strip().lower()
        if choice in ("1", "en", "english"):
            return Language.ENGLISH
        if choice in ("2", "es", "spanish", ""):
            return Language.SPANISH
        print("Invalid choice. Enter 1 or 2.")


def _display_blueprint(blueprint: Blueprint):
    """Print the blueprint as a readable tree in the terminal."""
    total_cells = sum(len(p.cells) for p in blueprint.parts)
    print(f"\n{BOLD}=== Proposed Outline ({total_cells} cells) ==={RESET}\n")

    for part in blueprint.parts:
        print(f"  {BOLD}Part {part.part_number}: {part.part_title}{RESET}  ({len(part.cells)} cells)")
        for cell in part.cells:
            tag = "[md]" if cell.cell_type == CellType.MARKDOWN else "[py]"
            role_tag = f"{DIM}({cell.role.value}){RESET}"
            brief = cell.content_brief[:80]
            print(f"    {CYAN}{tag}{RESET} {brief} {role_tag}")
        print()


def _progress_bar(current: int, total: int, width: int = 30) -> str:
    """Return a simple ASCII progress bar."""
    filled = int(width * current / total) if total > 0 else 0
    bar = "=" * filled + " " * (width - filled)
    return f"[{bar}] {current}/{total} cells"


# ---------------------------------------------------------------------------
# Interview phase
# ---------------------------------------------------------------------------

def _run_interview(goal: str, context_text: str) -> dict[str, str]:
    """Run the interactive interview and return {question: answer} pairs."""
    print(f"\n{BOLD}Generating tailored questions...{RESET}")
    questions = generate_interview_questions(goal, context_text)

    print(f"\n{BOLD}I have a few questions to tailor this notebook:{RESET}\n")
    answers: dict[str, str] = {}
    for i, question in enumerate(questions, 1):
        print(f"{BOLD}[{i}/{len(questions)}]{RESET} {question}")
        answer = input("> ").strip()
        if answer:
            answers[question] = answer
        else:
            answers[question] = "(skipped)"
        print()

    return answers


# ---------------------------------------------------------------------------
# Blueprint approval loop
# ---------------------------------------------------------------------------

def _blueprint_loop(
    goal: str,
    answers: dict[str, str],
    context_text: str,
    language: Language,
) -> Blueprint:
    """Generate, display, and let the user approve/edit/regenerate the blueprint."""
    print(f"\n{BOLD}Generating outline...{RESET}")
    blueprint = generate_blueprint(goal, answers, context_text, language)

    while True:
        _display_blueprint(blueprint)
        print(f"{BOLD}[Y]{RESET} Approve  {BOLD}[E]{RESET} Edit  {BOLD}[R]{RESET} Regenerate")
        choice = input("> ").strip().lower()

        if choice in ("y", "yes", ""):
            return blueprint
        elif choice in ("r", "regenerate"):
            print(f"\n{BOLD}Regenerating outline...{RESET}")
            blueprint = generate_blueprint(goal, answers, context_text, language)
        elif choice in ("e", "edit"):
            print(f"\n{BOLD}Describe what you'd like to change:{RESET}")
            feedback = input("> ").strip()
            if feedback:
                print(f"\n{BOLD}Applying changes...{RESET}")
                blueprint = modify_blueprint(blueprint, feedback)
            else:
                print("No changes specified.")
        else:
            print("Please enter Y, E, or R.")


# ---------------------------------------------------------------------------
# Generation + validation
# ---------------------------------------------------------------------------

def _validate_and_repair(
    cells: List[NotebookCell],
    cell_specs: List[CellSpec],
    validator: ValidationSession,
) -> List[NotebookCell]:
    """Execute code cells, repair failures up to MAX_REPAIR_ATTEMPTS."""
    for i, cell in enumerate(cells):
        if cell.cell_type != CellType.CODE:
            continue

        spec = cell_specs[i] if i < len(cell_specs) else None
        attempts = 0
        code = cell.source

        while attempts <= MAX_REPAIR_ATTEMPTS:
            success, stdout, stderr = validator.execute_cell(
                NotebookCell(cell_type=CellType.CODE, source=code)
            )

            if success:
                cell.source = code
                cell.outputs = ValidationSession.format_cell_outputs(stdout, "")
                break

            attempts += 1
            if attempts > MAX_REPAIR_ATTEMPTS:
                print(f"    {RED}Failed after {MAX_REPAIR_ATTEMPTS} repair attempts{RESET}")
                last_line = stderr.strip().splitlines()[-1] if stderr.strip() else "Unknown error"
                print(f"    {RED}{last_line}{RESET}")
                cell.source = code
                cell.outputs = ValidationSession.format_cell_outputs(
                    "", f"# VALIDATION ERROR:\n{stderr}"
                )
                break

            print(f"    {YELLOW}Repair attempt {attempts}/{MAX_REPAIR_ATTEMPTS}...{RESET}")
            if spec:
                code = repair_cell(
                    failing_code=code,
                    error=stderr,
                    context_summary=validator.get_context_summary(),
                    code_history=validator.get_full_code_history(),
                    cell_spec=spec,
                )
            else:
                # No spec available -- cannot repair meaningfully
                break

    return cells


def _generate_notebook(blueprint: Blueprint, save_plan: Optional[str] = None) -> List[NotebookCell]:
    """Generate the full notebook part-by-part with validation."""
    if save_plan:
        plan_path = Path(save_plan)
        plan_path.write_text(blueprint.model_dump_json(indent=2), encoding="utf-8")
        print(f"\n{GREEN}Blueprint saved to: {plan_path}{RESET}")

    validator = ValidationSession()
    all_cells: List[NotebookCell] = []
    total_cells = sum(len(p.cells) for p in blueprint.parts)
    generated_count = 0

    for part_idx, part in enumerate(blueprint.parts):
        print(f"\n{BOLD}Generating Part {part.part_number}: {part.part_title}...{RESET}")

        part_cells = generate_part(blueprint, part_idx, all_cells)

        # Ensure we have the right number (pad/truncate if LLM miscounted)
        expected = len(part.cells)
        if len(part_cells) < expected:
            for _ in range(expected - len(part_cells)):
                part_cells.append(NotebookCell(cell_type=CellType.MARKDOWN, source=""))
        elif len(part_cells) > expected:
            part_cells = part_cells[:expected]

        # Validate code cells
        part_cells = _validate_and_repair(part_cells, part.cells, validator)

        # Execute any successfully repaired cells that weren't yet in the namespace
        for cell in part_cells:
            if cell.cell_type == CellType.CODE and not cell.outputs:
                success, stdout, _ = validator.execute_cell(cell)
                if success:
                    cell.outputs = ValidationSession.format_cell_outputs(stdout, "")

        all_cells.extend(part_cells)
        generated_count += len(part_cells)
        print(f"  {GREEN}{_progress_bar(generated_count, total_cells)}{RESET}")

    return all_cells


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate pedagogical Jupyter Notebooks (v2).",
        usage="python -m tools.notebook_generator GOAL [--context FILES...] [--output PATH] [--language LANG] [--save-plan PATH]",
    )
    parser.add_argument(
        "goal",
        help="Session goal / topic description (e.g., 'Teach functions and basic algorithms')",
    )
    parser.add_argument(
        "--context", "-c",
        nargs="+",
        default=[],
        help="Context files (.ipynb, .md, .txt) from prior sessions or notes",
    )
    parser.add_argument(
        "--output", "-o",
        default="notebook.ipynb",
        help="Output notebook path (default: notebook.ipynb)",
    )
    parser.add_argument(
        "--language", "-l",
        choices=["en", "es"],
        default=None,
        help="Output language (en/es). If omitted, you'll be prompted.",
    )
    parser.add_argument(
        "--save-plan",
        default=None,
        help="Path to save the blueprint JSON for inspection",
    )

    args = parser.parse_args()

    _print_header("Notebook Generator")

    # 1. Load context files
    context_parts: List[str] = []
    for file_path in args.context:
        try:
            content = parse_input(file_path)
            context_parts.append(f"--- SOURCE: {file_path} ---\n{content}")
            print(f"  {GREEN}Loaded:{RESET} {file_path}")
        except Exception as e:
            print(f"  {RED}Error loading {file_path}: {e}{RESET}")

    context_text = "\n\n".join(context_parts)

    # 2. Language
    if args.language:
        language = Language(args.language)
    else:
        language = _ask_language()

    # 3. Interview
    answers = _run_interview(args.goal, context_text)

    # 4. Blueprint
    blueprint = _blueprint_loop(args.goal, answers, context_text, language)

    # 5. Generation
    _print_header("Generating Notebook")
    all_cells = _generate_notebook(blueprint, save_plan=args.save_plan)

    # 6. Export
    notebook_json = create_notebook_json(all_cells)
    output_path = Path(args.output)
    output_path.write_text(notebook_json, encoding="utf-8")

    total = len(all_cells)
    code_cells = sum(1 for c in all_cells if c.cell_type == CellType.CODE)
    valid_code = sum(
        1 for c in all_cells
        if c.cell_type == CellType.CODE
        and not any("VALIDATION ERROR" in str(o) for o in c.outputs)
    )

    print(f"\n{GREEN}{'=' * 50}{RESET}")
    print(f"{GREEN}  Done! Saved to {output_path}{RESET}")
    print(f"{GREEN}  {total} cells ({code_cells} code, {total - code_cells} markdown){RESET}")
    print(f"{GREEN}  Code validation: {valid_code}/{code_cells} passed{RESET}")
    print(f"{GREEN}{'=' * 50}{RESET}")


if __name__ == "__main__":
    main()
