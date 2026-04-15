from agents.core.tools import AgentToolProvider
from agents.tools.calculator import CalculatorToolProvider, calculator_tool

__all__ = [
    "AgentToolProvider",
    "CalculatorToolProvider",
    "calculator_tool",
    "default_tool_providers",
]


def default_tool_providers() -> tuple[AgentToolProvider, ...]:
    return (CalculatorToolProvider(),)
