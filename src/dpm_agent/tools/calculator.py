from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from dpm_agent.sanitize import sanitize_text

try:
    from langchain_core.tools import tool
except ModuleNotFoundError:

    def tool(func: Any) -> Any:
        return func


Operation = Literal["add", "subtract", "multiply", "divide"]


def calculate(operation: Operation, left: float, right: float) -> float:
    if operation == "add":
        return left + right
    if operation == "subtract":
        return left - right
    if operation == "multiply":
        return left * right
    if operation == "divide":
        if right == 0:
            raise ValueError("division by zero")
        return left / right
    raise ValueError(f"unsupported operation: {operation}")


@tool
def calculator_tool(operation: Operation, left: float, right: float) -> str:
    """Perform basic arithmetic: add, subtract, multiply, or divide two numbers."""
    try:
        result = calculate(operation=operation, left=left, right=right)
    except ValueError as exc:
        return sanitize_text(f"error: {exc}")
    return sanitize_text(str(result))


class CalculatorToolProvider:
    """Registers the example calculator tool for every thread."""

    def tools_for_thread(self, thread_id: str) -> Iterable[Any]:
        return (calculator_tool,)
