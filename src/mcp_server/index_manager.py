# /src/mcp_server/index_manager.py
import asyncio
import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)


class IndexManager:
    """
    Thread-safe async manager for the Sandwich-pack index.

    Responsibilities:
    - Hold an in-memory cache of the last successful index JSON.
    - Guard reindex runs with asyncio.Lock so concurrent tool calls
      never produce a half-written index.
    - Expose a stale flag that FileWatcher raises without touching files.

    The lock is intentionally coarse: only one reindex can run at a time.
    Callers that race get {"status": "already_building"} instantly and
    can retry after polling get_status().
    """

    def __init__(self, project_root: Path, spack_script: Path):
        """
        Args:
            project_root:  Root of the project to index (where spack_sigsys.py lives).
            spack_script:  Path to the packer script (e.g. spack_agent.py or spack.py).
        """
        self._root = project_root
        self._script = spack_script
        self._index_file = project_root / "sandwiches" / "sandwiches_index.jsl"

        self._cache: dict = {}          # last successfully parsed index
        self._raw_index: str = ""       # raw JSON string (for get_raw_index)
        self._lock = asyncio.Lock()
        self._stale: bool = True        # True until first successful reindex
        self._building: bool = False
        self._last_build_time: float = 0.0
        self._last_error: str = ""

        # Try to warm cache from existing file on startup (no lock needed yet)
        self._warm_cache()

    # ── Public state queries ──────────────────────────────────────────────────

    @property
    def stale(self) -> bool:
        return self._stale

    @property
    def building(self) -> bool:
        return self._building

    @property
    def last_build_time(self) -> float:
        return self._last_build_time

    def mark_stale(self, reason: str = "file changed") -> None:
        """Called by FileWatcher — only sets flag, never touches files."""
        if not self._stale:
            log.info(f"Index marked stale: {reason}")
        self._stale = True

    def get_status(self) -> dict:
        age = time.time() - self._last_build_time if self._last_build_time else None
        return {
            "stale": self._stale,
            "building": self._building,
            "last_build_age_seconds": round(age, 1) if age is not None else None,
            "files": len(self._cache.get("files", [])),
            "entities": len(self._cache.get("entities", [])),
            "last_error": self._last_error or None,
        }

    def get_index(self) -> dict:
        """Return cached index immediately. Annotate with freshness metadata."""
        return {
            "stale": self._stale,
            "building": self._building,
            "index": self._cache,
        }

    def get_entities(self, file_filter: str = "") -> dict:
        """Return entity list, optionally filtered by file path substring."""
        entities = self._cache.get("entities", [])
        files = self._cache.get("files", [])

        if file_filter:
            # Build set of matching file ids
            matching_fids: set[int] = set()
            for entry in files:
                parts = entry.split(",")
                if len(parts) >= 2 and file_filter in parts[1]:
                    try:
                        matching_fids.add(int(parts[0]))
                    except ValueError:
                        pass
            filtered = []
            for e in entities:
                parts = e.split(",")
                if len(parts) >= 5:
                    try:
                        if int(parts[4]) in matching_fids:
                            filtered.append(e)
                    except ValueError:
                        pass
            return {"entities": filtered, "total": len(filtered), "filter": file_filter}

        return {"entities": entities, "total": len(entities)}

    # ── Reindex ───────────────────────────────────────────────────────────────

    async def reindex(self) -> dict:
        """
        Run a full reindex.  Acquires lock — concurrent calls return immediately
        with status='already_building'.  Returns status dict when complete.
        """
        if self._lock.locked():
            log.debug("reindex() called while already building, skipping")
            return {"status": "already_building"}

        async with self._lock:
            self._building = True
            self._last_error = ""
            log.info(f"Starting reindex: {self._script}")
            t0 = time.monotonic()

            try:
                proc = await asyncio.create_subprocess_exec(
                    "python", str(self._script), "--pack-only",
                    cwd=str(self._root),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()

                elapsed = round(time.monotonic() - t0, 2)

                if proc.returncode not in (0, 1):  # spack exits 1 on verbose log
                    err = stderr.decode(errors="replace")[-800:]
                    self._last_error = err
                    log.error(f"Reindex failed (rc={proc.returncode}): {err}")
                    return {"status": "error", "returncode": proc.returncode,
                            "stderr": err, "elapsed_seconds": elapsed}

                # Atomically replace cache only after success
                new_cache, raw = self._parse_index_file()
                self._cache = new_cache     # GIL makes this atomic in CPython
                self._raw_index = raw
                self._stale = False
                self._last_build_time = time.time()

                summary = {
                    "status": "ok",
                    "elapsed_seconds": elapsed,
                    "files": len(new_cache.get("files", [])),
                    "entities": len(new_cache.get("entities", [])),
                    "sandwiches": len(new_cache.get("sandwiches_map", [])),
                }
                log.info(f"Reindex complete: {summary}")
                return summary

            except Exception as exc:
                self._last_error = str(exc)
                log.exception("Unexpected error during reindex")
                return {"status": "error", "exception": str(exc)}
            finally:
                self._building = False

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _parse_index_file(self) -> tuple[dict, str]:
        """Read sandwiches_index.jsl and return (parsed_dict, raw_json_str)."""
        raw_full = self._index_file.read_text(encoding="utf-8")
        raw_json = raw_full.split("STRUCTURE:")[0].strip()
        return json.loads(raw_json), raw_json

    def _warm_cache(self) -> None:
        """Load existing index on startup if available. Does not acquire lock."""
        if not self._index_file.exists():
            log.debug("No existing index file found, cache empty")
            return
        try:
            parsed, raw = self._parse_index_file()
            self._cache = parsed
            self._raw_index = raw
            mtime = os.path.getmtime(self._index_file)
            self._last_build_time = mtime
            age = round(time.time() - mtime)
            log.info(
                f"Warmed cache from {self._index_file} "
                f"({len(parsed.get('files', []))} files, "
                f"{len(parsed.get('entities', []))} entities, "
                f"age {age}s)"
            )
            # Consider stale if index is older than 30 minutes
            self._stale = age > 1800
        except Exception as exc:
            log.warning(f"Could not warm cache: {exc}")
