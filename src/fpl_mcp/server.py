"""FPL MCP server entry point."""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from .auth import FPLAuth
from .client import FPLClient
from .tools.registry import ALL_TOOLS, dispatch

# Load .env from the project root (two dirs up from this file)
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def _build_client() -> FPLClient:
    """Construct the FPLClient, attaching auth if credentials are available."""
    email = os.environ.get("FPL_EMAIL", "")
    password = os.environ.get("FPL_PASSWORD", "")
    if email and password:
        auth = FPLAuth.from_env()
        logger.info("Auth configured for %s", email)
    else:
        auth = None
        logger.warning(
            "No FPL_EMAIL/FPL_PASSWORD set. Authenticated endpoints will not work. "
            "Copy .env.example to .env and fill in your credentials."
        )
    return FPLClient(auth=auth)


async def _run() -> None:
    client = _build_client()
    server = Server("fpl-mcp")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return ALL_TOOLS

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        logger.info("Tool call: %s args=%s", name, json.dumps(arguments)[:200])
        try:
            return await dispatch(name, arguments or {}, client)
        except ValueError as exc:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": str(exc)}, indent=2),
                )
            ]
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled error in tool '%s'", name)
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": f"Internal error: {type(exc).__name__}: {exc}"}, indent=2
                    ),
                )
            ]

    logger.info("Starting FPL MCP server with %d tools", len(ALL_TOOLS))
    await client.start()
    try:
        async with stdio_server() as (read_stream, write_stream):
            init_options = server.create_initialization_options()
            await server.run(read_stream, write_stream, init_options)
    finally:
        await client.close()
        logger.info("FPL MCP server stopped")


def main() -> None:
    """Entry point for `fpl-mcp` CLI command."""
    asyncio.run(_run())


if __name__ == "__main__":
    main()
