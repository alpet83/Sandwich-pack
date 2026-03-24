# /src/spack_mcp_server.py, updated 2026-03-23 (v2)
"""
Sandwich-pack MCP server.

Exposes the Sandwich-pack index as a Model Context Protocol (MCP) server,
allowing AI agents (e.g. GitHub Copilot) to query a live, cached entity
index for a project without blocking on regeneration.

Tools provided:
  spack_get_status   — check freshness (stale flag, age, entity count)
  spack_reindex      — trigger full reindex (blocks until done, mutex-guarded)
  spack_get_index    — return full cached index (JSON) with freshness metadata
  spack_get_entities — return entity list, optionally filtered by file path

Usage:
  python spack_mcp_server.py --project <path>

Or with defaults (project = cwd, script = spack_agent.py in this directory):
  python spack_mcp_server.py
"""

import asyncio
import json
import logging
import argparse
import sys
from pathlib import Path

# ── Bootstrap path so mcp_server package is importable ───────────────────────
_SRC_DIR = Path(__file__).parent
sys.path.insert(0, str(_SRC_DIR))

from mcp_server.index_manager import IndexManager
from mcp_server.file_watcher import FileWatcher

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s #%(levelname)s [%(name)s]: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("spack_mcp")

# ── Globals (set in main before serving) ─────────────────────────────────────
_manager: IndexManager | None = None
_watcher: FileWatcher | None = None

# ── MCP server ────────────────────────────────────────────────────────────────
app = Server("spack-index")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="spack_get_status",
            description=(
                "Check Sandwich-pack index freshness. "
                "Returns stale (bool), building (bool), age in seconds, "
                "file/entity counts, and last error if any. "
                "Call this first in a session to decide whether reindex is needed."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="spack_reindex",
            description=(
                "Trigger a full project reindex. "
                "Mutex-guarded: concurrent calls return {status: already_building} immediately. "
                "Blocks until the reindex completes (typically 2-5 seconds). "
                "Returns {status, elapsed_seconds, files, entities} on success."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="spack_get_index",
            description=(
                "Return the full cached index JSON. Instant — never triggers a reindex. "
                "Includes stale/building flags so caller can decide whether to reindex first. "
                "Index format: {files: [id,path,md5,tokens,ts], entities: [vis,type,parent,name,file_id,lines,tokens]}"
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="spack_get_entities",
            description=(
                "Return entities from the cached index, optionally filtered by file path substring. "
                "Example: file_filter='signals.controller' returns only entities from that file. "
                "Each entity: 'vis,type,parent,name,file_id,start-end,tokens'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_filter": {
                        "type": "string",
                        "description": "Optional substring to filter by file path. Empty = all entities.",
                    }
                },
                "required": [],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    assert _manager is not None, "IndexManager not initialized"

    if name == "spack_get_status":
        result = _manager.get_status()

    elif name == "spack_reindex":
        result = await _manager.reindex()

    elif name == "spack_get_index":
        result = _manager.get_index()

    elif name == "spack_get_entities":
        file_filter = arguments.get("file_filter", "")
        result = _manager.get_entities(file_filter)

    else:
        result = {"error": f"Unknown tool: {name}"}

    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


# ── Entry point ───────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sandwich-pack MCP server — live project index for AI agents",
    )
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Root directory of the project to index (default: cwd)",
    )
    parser.add_argument(
        "--script",
        type=Path,
        default=None,
        help="Path to the packer script (default: spack_agent.py beside this server)",
    )
    parser.add_argument(
        "--no-watch",
        action="store_true",
        help="Disable filesystem watcher (stale flag only set via reindex)",
    )
    parser.add_argument(
        "--debounce",
        type=float,
        default=5.0,
        help="Watcher debounce delay in seconds (default: 5)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Path to log file (default: <project>/.vscode/mcp_sandwich_pack.log)",
    )
    return parser.parse_args()


async def serve(args: argparse.Namespace) -> None:
    global _manager, _watcher

    project_root = args.project.resolve()
    script = (args.script or Path(__file__).parent / "spack_agent.py").resolve()

    # ── File logging ─────────────────────────────────────────────────────────
    log_path: Path = (
        args.log_file.resolve()
        if args.log_file
        else project_root / ".vscode" / "mcp_sandwich_pack.log"
    )
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _fh = logging.FileHandler(log_path, encoding="utf-8")
        _fh.setLevel(logging.INFO)
        _fh.setFormatter(logging.Formatter(
            "%(asctime)s #%(levelname)s [%(name)s]: %(message)s"
        ))
        logging.getLogger().addHandler(_fh)
        log.info(f"Log file: {log_path}")
    except Exception as exc:
        log.warning(f"Could not open log file {log_path}: {exc}")

    if not project_root.exists():
        log.error(f"Project root does not exist: {project_root}")
        sys.exit(1)
    if not script.exists():
        log.error(f"Packer script not found: {script}")
        sys.exit(1)

    log.info(f"spack-mcp-server starting")
    log.info(f"  project : {project_root}")
    log.info(f"  script  : {script}")

    _manager = IndexManager(project_root, script)

    if not args.no_watch:
        from mcp_server.file_watcher import _ChangeHandler
        _ChangeHandler.DEBOUNCE_SECONDS = args.debounce
        _watcher = FileWatcher(_manager, project_root)
        _watcher.start()

    try:
        async with stdio_server() as (read_stream, write_stream):
            log.info("MCP stdio server ready")
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )
    finally:
        if _watcher:
            _watcher.stop()


def main() -> None:
    args = parse_args()
    asyncio.run(serve(args))


if __name__ == "__main__":
    main()
