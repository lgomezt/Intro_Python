"""Parse source material for the notebook generator."""

import json
from pathlib import Path


def parse_notebook(path: str) -> str:
    """Extract markdown + code cells from a Jupyter notebook as context text."""
    with open(path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    parts = []
    for cell in nb.get("cells", []):
        cell_type = cell.get("cell_type", "")
        source = "".join(cell.get("source", []))

        if cell_type == "markdown":
            parts.append(f"Markdown:\n{source}")
        elif cell_type == "code":
            parts.append(f"Code:\n```python\n{source}\n```")

    return "\n\n".join(parts)


def parse_text(path: str) -> str:
    """Read a plain text or markdown file."""
    return Path(path).read_text(encoding="utf-8")


def parse_input(path: str) -> str:
    """Dispatch to the appropriate parser based on file extension."""
    p = Path(path)

    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    ext = p.suffix.lower()

    if ext == ".ipynb":
        return parse_notebook(path)
    elif ext in (".txt", ".md", ".markdown"):
        return parse_text(path)
    else:
        # Try reading as text
        return parse_text(path)
