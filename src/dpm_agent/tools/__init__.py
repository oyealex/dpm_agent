from dpm_agent.core.tools import AgentToolProvider
from dpm_agent.tools.calculator import CalculatorToolProvider, calculator_tool

__all__ = [
    "AgentToolProvider",
    "CalculatorToolProvider",
    "calculator_tool",
    "default_tool_providers",
]


def default_tool_providers() -> tuple[AgentToolProvider, ...]:
    return (CalculatorToolProvider(),)
