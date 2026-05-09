"""Pydantic data models for the notebook generation pipeline."""

from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from enum import Enum


class Language(str, Enum):
    ENGLISH = "en"
    SPANISH = "es"


class CellType(str, Enum):
    MARKDOWN = "markdown"
    CODE = "code"


class NotebookCell(BaseModel):
    """A single cell in a Jupyter notebook."""
    cell_type: CellType
    source: str
    outputs: List[Dict[str, Any]] = Field(default_factory=list)
    execution_count: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CellRole(str, Enum):
    HEADER = "header"
    INTRODUCTION = "introduction"
    CONCEPT_DEEP = "concept_deep"
    EXAMPLE_BASE = "example_base"
    EXAMPLE_EXTENSION = "example_extension"
    EXAMPLE_COMPOSITION = "example_composition"
    DISTINCTION = "distinction"
    ALGORITHM_STEPS = "algorithm_steps"
    VISUAL_TRACE = "visual_trace"
    VERIFICATION = "verification"
    INTEGRATOR_SETUP = "integrator_setup"
    INTEGRATOR_CODE = "integrator_code"
    SUMMARY = "summary"


class CellSpec(BaseModel):
    """Specification for a single cell in the blueprint."""
    cell_id: int
    cell_type: CellType
    role: CellRole
    content_brief: str
    pedagogical_elements: List[str] = Field(default_factory=list)
    defines: List[str] = Field(default_factory=list)
    uses: List[str] = Field(default_factory=list)


class PartSpec(BaseModel):
    """Specification for a logical part of the notebook."""
    part_number: int
    part_title: str
    narrative_arc: str
    cells: List[CellSpec]


class Blueprint(BaseModel):
    """Cell-by-cell structural blueprint for the entire notebook."""
    title: str
    language: Language
    introduction_connects_to: str
    parts: List[PartSpec]


class InterviewResult(BaseModel):
    """Collected answers from the interactive interview."""
    goal: str
    context_text: str
    answers: Dict[str, str] = Field(default_factory=dict)
    language: Language
