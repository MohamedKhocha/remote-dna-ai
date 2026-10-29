"""The DNA model as an MCP server, so any agent (Claude, Cursor, Codex, a
LangChain agent) can look up TV remotes. Read-only: nothing here sends a code.

    python -m agent.mcp_server        # stdio transport
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import tools as dna_tools

mcp = FastMCP("remote-dna")


@mcp.tool()
def find_model(label_text: str, brand: str = "") -> list[dict]:
    """Find a TV from the model number on its label: brand, model, and the
    infrared protocol and address it listens on (or its Wi-Fi platform)."""
    return dna_tools.find_model(label_text, brand or None)


@mcp.tool()
def brand_addresses(brand: str) -> dict:
    """Infrared addresses a TV brand's remotes use, most common first."""
    return dna_tools.brand_addresses(brand)


@mcp.tool()
def predict_buttons(protocol: str, address: int, confirmed: dict[str, int]) -> dict[str, int]:
    """Guess the remaining buttons of a remote from the ones confirmed on the TV."""
    return dna_tools.predict_buttons(protocol, address, confirmed)


if __name__ == "__main__":
    mcp.run()
