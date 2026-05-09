"""Format notebook content into valid .ipynb JSON."""

import json
from typing import List
from .models import NotebookCell, CellType

def create_notebook_json(cells: List[NotebookCell]) -> str:
    """Convert a list of NotebookCells into a Jupyter Notebook JSON string."""
    
    formatted_cells = []
    for cell in cells:
        source_lines = [line + "\n" for line in cell.source.splitlines()]
        # Remove trailing newline from last line if present
        if source_lines and source_lines[-1].endswith("\n"):
             source_lines[-1] = source_lines[-1][:-1]

        formatted_cell = {
            "cell_type": cell.cell_type.value,
            "metadata": cell.metadata,
            "source": source_lines
        }

        if cell.cell_type == CellType.CODE:
            formatted_cell["execution_count"] = None
            formatted_cell["outputs"] = cell.outputs

        formatted_cells.append(formatted_cell)

    notebook = {
        "cells": formatted_cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 3
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.10.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }

    return json.dumps(notebook, indent=1, ensure_ascii=False)
