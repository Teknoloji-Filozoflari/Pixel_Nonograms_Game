"""Constraint-based Nonogram solving and logical hints."""

from .hint_engine import HintPlan, HintStep, create_hint_plan, get_hint
from .possibilities import generate_line_possibilities
from .solver import (
    LogicalMove,
    SolveResult,
    SolveStatus,
    ValidationResult,
    explain_next_logical_move,
    get_next_logical_move,
    solve,
    validate,
    validate_unique_solution,
)

__all__ = [
    "LogicalMove",
    "HintPlan",
    "HintStep",
    "SolveResult",
    "SolveStatus",
    "ValidationResult",
    "explain_next_logical_move",
    "generate_line_possibilities",
    "get_next_logical_move",
    "create_hint_plan",
    "get_hint",
    "solve",
    "validate",
    "validate_unique_solution",
]
