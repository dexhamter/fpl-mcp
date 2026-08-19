"""Tool registry — collects all tool definitions and dispatches calls."""

from ..client import FPLClient
from . import bootstrap, chips, fixtures, leagues, live, news, picks, players, prices, squad, transfers
import mcp.types as types

_MODULES = [
    bootstrap,
    chips,
    fixtures,
    leagues,
    live,
    news,
    picks,
    players,
    prices,
    squad,
    transfers,
]

ALL_TOOLS: list[types.Tool] = []
for _mod in _MODULES:
    ALL_TOOLS.extend(_mod.TOOLS)


async def dispatch(
    name: str, arguments: dict, client: FPLClient
) -> list[types.TextContent]:
    """Dispatch a tool call to the appropriate module handler."""
    for module in _MODULES:
        result = await module.handle(name, arguments, client)
        if result is not None:
            return result
    raise ValueError(f"Unknown tool: '{name}'")
