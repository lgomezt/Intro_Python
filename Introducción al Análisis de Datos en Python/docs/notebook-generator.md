# Notebook Generator v2

An AI-assisted CLI tool for generating high-quality, pedagogical Jupyter Notebooks for the "Introduction to Data Analysis in Python" course (MEcA - Universidad de los Andes).

---

## Overview

The tool generates ~30-cell cohesive notebooks with deep markdown explanations, progressive code complexity, strategic formatting (tables, pseudocode, visual traces), and a capstone integrator. It uses a **blueprint-driven, part-by-part generation** strategy with automatic code validation and repair.

Core principles:
- **Blueprint-first**: A cell-by-cell structural plan is generated and approved before any content is written.
- **Part-by-part generation**: Content is generated in logical Parts (5-11 cells each), preserving narrative flow within parts and cross-part coherence via the blueprint.
- **Validation + repair**: Every code cell is executed after generation. Failing cells are automatically repaired (up to 3 LLM attempts).
- **Natural examples**: Domains are chosen to best illustrate each concept. Economics examples are preferred for the integrator but not forced everywhere.

---

## Setup

### Requirements

- `google-genai` (Gemini API)
- `pydantic`
- `python-dotenv`

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Gemini API key |
| `GEMINI_MODEL` | No | Override the model name (default: `gemini-3-pro-preview`) |
---

## Usage

```bash
# Basic usage
python -m tools.notebook_generator "Teach functions and basic algorithms" \
    --context clase3.ipynb notes.md \
    --output clase4.ipynb \
    --language es

# Minimal (will prompt for language)
python -m tools.notebook_generator "Teach pandas basics"

# Save the blueprint for inspection
python -m tools.notebook_generator "Teach OOP" --save-plan plan.json
```

### CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `GOAL` (positional) | required | Session goal / topic description |
| `--context`, `-c` | none | Context files (.ipynb, .md, .txt) from prior sessions |
| `--output`, `-o` | `notebook.ipynb` | Output notebook path |
| `--language`, `-l` | prompted | Output language (`en` or `es`) |
| `--save-plan` | none | Path to save the blueprint JSON |

---

## The Generation Pipeline

```
GOAL + Context files
        │
        ▼
┌─────────────────┐
│  1. Interview    │  LLM generates 3-5 tailored questions → user answers in terminal
└────────┬────────┘
         ▼
┌─────────────────┐
│  2. Blueprint    │  LLM generates cell-by-cell spec (28-32 cells) → user approves/edits/regenerates
└────────┬────────┘
         ▼
┌─────────────────┐
│  3. Generation   │  For each Part (3-5 LLM calls):
│     + Validation │    → generate 5-11 cells with full blueprint + previous cells as context
│     + Repair     │    → execute code cells, repair failures (up to 3 attempts)
└────────┬────────┘
         ▼
┌─────────────────┐
│  4. Export       │  Assemble cells into .ipynb, report stats
└─────────────────┘
```

### Phase 1: Interview

The LLM generates 3-5 short questions tailored to the session goal and context material. Questions avoid asking what's already evident from context files. The user answers interactively in the terminal (Enter to skip any question).

### Phase 2: Blueprint

The LLM produces a `Blueprint` -- a cell-by-cell structural specification for the entire notebook. Each cell gets:
- **Type** (markdown/code) and **role** (e.g., `concept_deep`, `example_base`, `distinction`, `integrator_code`)
- **Content brief** describing what the cell should contain
- **Pedagogical elements** to include (table, pseudocode, syntax template, visual trace, etc.)
- **Defines/uses** tracking which variables and functions each cell creates or references

The blueprint is displayed as a tree in the terminal. The user can:
- **[Y] Approve** -- proceed to generation
- **[E] Edit** -- describe changes in natural language, LLM regenerates
- **[R] Regenerate** -- completely new blueprint

### Phase 3: Part-by-Part Generation + Validation

Each Part (5-11 cells) is generated in a single LLM call that receives:
1. The **full blueprint** (so the LLM knows where this Part fits in the whole)
2. **All previously generated cells** (full text, not just variable summaries)

After each Part, every code cell is executed in a persistent `ValidationSession`. If a cell fails:
1. The error + cell spec + namespace context are sent to the repair prompt
2. The LLM returns fixed code
3. Up to 3 repair attempts per cell

### Phase 4: Export

All cells are assembled into a valid `.ipynb` (NBFormat v4) and saved. The terminal shows final stats: total cells, code/markdown split, validation pass rate.

---

## Architecture

```
tools/notebook_generator/
├── __init__.py
├── __main__.py          # Entry point (calls cli.main)
├── cli.py               # CLI flow: interview → blueprint → generation → export
├── config.py            # Gemini client, MODEL_NAME, temperature defaults
├── models.py            # Pydantic models: Blueprint, PartSpec, CellSpec, CellRole, etc.
├── generator.py         # LLM calls: interview, blueprint, part generation, cell repair
├── validator.py         # Persistent Python execution context (ValidationSession)
├── formatter.py         # Converts NotebookCell list to .ipynb JSON
├── input_parsers.py     # Reads .ipynb, .txt, .md files as context text
└── prompts/
    ├── interview.md         # Generates tailored questions from goal + context
    ├── blueprint.md         # Generates cell-by-cell structural blueprint
    ├── part_generation.md   # Generates content for one Part (5-11 cells)
    └── cell_repair.md       # Fixes failing code cells
```

### Data Models (`models.py`)

| Model | Purpose |
|-------|---------|
| `Language` | Enum: `en`, `es` |
| `CellType` | Enum: `markdown`, `code` |
| `CellRole` | Enum with 13 roles: `header`, `introduction`, `concept_deep`, `example_base`, `example_extension`, `example_composition`, `distinction`, `algorithm_steps`, `visual_trace`, `verification`, `integrator_setup`, `integrator_code`, `summary` |
| `CellSpec` | Blueprint spec for one cell: id, type, role, content_brief, pedagogical_elements, defines, uses |
| `PartSpec` | A logical Part: number, title, narrative_arc, list of CellSpecs |
| `Blueprint` | Full notebook spec: title, language, introduction_connects_to, list of PartSpecs |
| `InterviewResult` | Collected interview data: goal, context_text, answers, language |
| `NotebookCell` | A realized cell: type, source, outputs, execution_count, metadata |

### Generator Functions (`generator.py`)

| Function | LLM Call | Temperature | Purpose |
|----------|----------|-------------|---------|
| `generate_interview_questions()` | 1 call | 0.5 | Generate 3-5 tailored questions |
| `generate_blueprint()` | 1 call | 0.4 | Cell-by-cell notebook specification |
| `modify_blueprint()` | 1 call | 0.4 | Incorporate user edit feedback |
| `generate_part()` | 1 call per Part | 0.3 | Generate content for one Part |
| `repair_cell()` | 1 call per failure | 0.2 | Fix a failing code cell |

Typical notebook generation: **1 (interview) + 1 (blueprint) + 4 (parts) + 0-5 (repairs) = 6-11 LLM calls**.

### Where the Gemini Model is Called

All LLM calls flow through a single function in `generator.py`:

```
config.py:12  →  MODEL_NAME = "gemini-3-pro-preview"
                 ↓
generator.py:63 →  client.models.generate_content(model=MODEL_NAME, ...)
                   (called by _call_llm(), which is used by all 5 generator functions)
```

**To change the model**, edit `config.py` line 12 to change the default

### Validator (`validator.py`)

`ValidationSession` maintains a persistent Python namespace across all cell executions:

| Method | Purpose |
|--------|---------|
| `execute_cell()` | Run code via `exec()`, capture stdout/stderr |
| `reset()` | Clear namespace and history |
| `get_defined_functions()` | List user-defined functions in namespace |
| `get_context_summary()` | Variable summary for LLM context |
| `get_full_code_history()` | All successfully executed code |
| `format_cell_outputs()` | Format stdout/stderr as notebook output dicts |

---

## Pedagogical Patterns (Encoded in Prompts)

These patterns are derived from the golden example notebook (`Clase 4. Funciones y Algoritmos/Funciones y Algoritmos (Profesor).ipynb`) and enforced via the blueprint and part generation prompts:

- **28-32 cells** targeting a 1-hour class
- Every major concept has a markdown cell with **3+ pedagogical elements** (comparison table, pseudocode, visual trace, syntax template, analogy, callout)
- Code follows **base -> extension -> composition** progression
- **Verification pattern**: compare custom implementations against Python built-ins
- Every function has a **docstring**
- Integrator reuses **3+ functions** defined earlier
- Natural domains for examples (economics for integrator)

---

## Extending

To modify the generation behavior:
- **Change prompts**: Edit files in `prompts/`. The blueprint prompt controls structure; the part generation prompt controls content quality.
- **Add a new cell role**: Add to `CellRole` enum in `models.py`, reference it in `prompts/blueprint.md`.
- **Change model**: Set `GEMINI_MODEL` env var or edit `config.py`.
- **Add a new generation phase**: Add a function in `generator.py` using `_call_llm()`, add a prompt in `prompts/`, call from `cli.py`.
