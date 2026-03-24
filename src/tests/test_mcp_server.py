# /src/tests/test_mcp_server.py, updated 2026-03-23
"""
Unit tests for IndexManager and FileWatcher.

IndexManager is tested with a mock subprocess so no real spack run is needed.
FileWatcher is tested with synthetic filesystem events.

Run with:
    cd src && python -m pytest tests/test_mcp_server.py -v
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

# Bootstrap import path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.index_manager import IndexManager

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_INDEX = {
    "packer_version": "0.6",
    "context_date": "2026-03-23 20:00:00Z",
    "files": [
        "0,/project/src/main.ts,abc123,500,2026-03-23 10:00:00Z",
        "1,/project/src/app.service.ts,def456,300,2026-03-23 11:00:00Z",
    ],
    "entities": [
        "pub,class,,AppService,1,10-50,300",
        "pub,function,,bootstrap,0,5-15,80",
        "prv,method,AppService,getData,1,20-30,120",
    ],
}

SAMPLE_INDEX_JSON = json.dumps(SAMPLE_INDEX)
SAMPLE_INDEX_JSL = SAMPLE_INDEX_JSON + "STRUCTURE: {}"


def _make_manager(tmp_path: Path, index_content: str = "") -> IndexManager:
    """Create an IndexManager pointing at a temp directory."""
    sandwiches_dir = tmp_path / "sandwiches"
    sandwiches_dir.mkdir()

    if index_content:
        (sandwiches_dir / "sandwiches_index.jsl").write_text(index_content, encoding="utf-8")

    script = tmp_path / "spack_sigsys.py"
    script.write_text("# mock script\n")
    return IndexManager(tmp_path, script)


# ── IndexManager tests ────────────────────────────────────────────────────────

class TestIndexManagerCacheWarm(unittest.TestCase):
    """Test cache warming from an existing index file."""

    def test_warm_cache_loads_existing_index(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            manager = _make_manager(tmp, SAMPLE_INDEX_JSL)
            self.assertEqual(len(manager._cache.get("files", [])), 2)
            self.assertEqual(len(manager._cache.get("entities", [])), 3)

    def test_warm_cache_empty_when_no_file(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            manager = _make_manager(tmp, "")  # no index written
            self.assertEqual(manager._cache, {})
            self.assertTrue(manager.stale)

    def test_warm_cache_fresh_index_not_stale(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            # Use _make_manager which creates sandwiches/ itself
            manager = _make_manager(tmp, SAMPLE_INDEX_JSL)
            # Touch the file so mtime is recent, then re-warm
            os.utime(manager._index_file, None)
            manager._warm_cache()
            self.assertFalse(manager.stale)


class TestIndexManagerStatus(unittest.TestCase):
    """Test get_status() output."""

    def test_status_contains_required_keys(self):
        with tempfile.TemporaryDirectory() as td:
            manager = _make_manager(Path(td), SAMPLE_INDEX_JSL)
            status = manager.get_status()
            for key in ("stale", "building", "files", "entities", "last_error"):
                self.assertIn(key, status)

    def test_status_file_entity_counts(self):
        with tempfile.TemporaryDirectory() as td:
            manager = _make_manager(Path(td), SAMPLE_INDEX_JSL)
            status = manager.get_status()
            self.assertEqual(status["files"], 2)
            self.assertEqual(status["entities"], 3)


class TestIndexManagerMarkStale(unittest.TestCase):
    """Test stale flag management."""

    def test_mark_stale_sets_flag(self):
        with tempfile.TemporaryDirectory() as td:
            manager = _make_manager(Path(td), SAMPLE_INDEX_JSL)
            manager._stale = False
            manager.mark_stale("test change")
            self.assertTrue(manager.stale)

    def test_mark_stale_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            manager = _make_manager(Path(td), SAMPLE_INDEX_JSL)
            manager.mark_stale("first")
            manager.mark_stale("second")
            self.assertTrue(manager.stale)


class TestIndexManagerGetEntities(unittest.TestCase):
    """Test entity filtering."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self._manager = _make_manager(Path(self._td.name), SAMPLE_INDEX_JSL)

    def tearDown(self):
        self._td.cleanup()

    def test_get_all_entities(self):
        result = self._manager.get_entities()
        self.assertEqual(result["total"], 3)

    def test_filter_by_filename(self):
        result = self._manager.get_entities("app.service")
        self.assertEqual(result["total"], 2)  # AppService + getData are in file_id 1
        for e in result["entities"]:
            self.assertIn(",1,", e)  # file_id 1

    def test_filter_no_match(self):
        result = self._manager.get_entities("nonexistent_file")
        self.assertEqual(result["total"], 0)


class TestIndexManagerReindex(unittest.IsolatedAsyncioTestCase):
    """Test reindex() with a mocked subprocess."""

    async def test_reindex_success(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            manager = _make_manager(tmp, "")
            # Pre-write an index file so reindex can read it back
            index_path = tmp / "sandwiches" / "sandwiches_index.jsl"
            index_path.write_text(SAMPLE_INDEX_JSL, encoding="utf-8")

            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))

            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                result = await manager.reindex()

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["files"], 2)
            self.assertEqual(result["entities"], 3)
            self.assertFalse(manager.stale)
            self.assertFalse(manager.building)

    async def test_reindex_sets_building_false_on_error(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            manager = _make_manager(tmp, "")

            mock_proc = AsyncMock()
            mock_proc.returncode = 2   # fatal error
            mock_proc.communicate = AsyncMock(return_value=(b"", b"fatal error"))

            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                result = await manager.reindex()

            self.assertEqual(result["status"], "error")
            self.assertFalse(manager.building)  # must be cleared even on error

    async def test_concurrent_reindex_returns_already_building(self):
        """Second call while first is running must return immediately."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            manager = _make_manager(tmp, "")
            index_path = tmp / "sandwiches" / "sandwiches_index.jsl"
            index_path.write_text(SAMPLE_INDEX_JSL, encoding="utf-8")

            # Slow subprocess: holds lock for 0.2s
            async def slow_communicate():
                await asyncio.sleep(0.2)
                return b"", b""

            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = slow_communicate

            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                task1 = asyncio.create_task(manager.reindex())
                await asyncio.sleep(0.05)  # let task1 acquire the lock
                result2 = await manager.reindex()
                result1 = await task1

            self.assertEqual(result2["status"], "already_building")
            self.assertEqual(result1["status"], "ok")

    async def test_reindex_clears_stale_flag(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            manager = _make_manager(tmp, "")
            manager._stale = True
            index_path = tmp / "sandwiches" / "sandwiches_index.jsl"
            index_path.write_text(SAMPLE_INDEX_JSL, encoding="utf-8")

            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))

            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                await manager.reindex()

            self.assertFalse(manager.stale)


# ── FileWatcher tests ─────────────────────────────────────────────────────────

class TestFileWatcher(unittest.TestCase):
    """Test FileWatcher event filtering and debounce."""

    def _make_watcher_and_manager(self, tmp_path: Path):
        from mcp_server.file_watcher import FileWatcher, _ChangeHandler
        manager = MagicMock()
        manager.mark_stale = MagicMock()
        watcher = FileWatcher(manager, tmp_path)
        return watcher, manager

    def _fire_event(self, handler, path: str, is_dir: bool = False):
        from watchdog.events import FileModifiedEvent
        event = FileModifiedEvent(path)
        event.is_directory = is_dir
        handler.on_any_event(event)

    def test_ts_file_triggers_mark_after_debounce(self):
        from mcp_server.file_watcher import _ChangeHandler
        manager = MagicMock()
        handler = _ChangeHandler(manager)
        handler.DEBOUNCE_SECONDS = 0.05  # short for test

        self._fire_event(handler, "/project/src/main.ts")
        time.sleep(0.15)
        manager.mark_stale.assert_called_once()

    def test_node_modules_ignored(self):
        from mcp_server.file_watcher import _ChangeHandler
        manager = MagicMock()
        handler = _ChangeHandler(manager)
        handler.DEBOUNCE_SECONDS = 0.05

        self._fire_event(handler, "/project/node_modules/lodash/index.js")
        time.sleep(0.15)
        manager.mark_stale.assert_not_called()

    def test_sandwiches_dir_ignored(self):
        from mcp_server.file_watcher import _ChangeHandler
        manager = MagicMock()
        handler = _ChangeHandler(manager)
        handler.DEBOUNCE_SECONDS = 0.05

        self._fire_event(handler, "/project/sandwiches/sandwich_1.txt")
        time.sleep(0.15)
        manager.mark_stale.assert_not_called()

    def test_unknown_extension_ignored(self):
        from mcp_server.file_watcher import _ChangeHandler
        manager = MagicMock()
        handler = _ChangeHandler(manager)
        handler.DEBOUNCE_SECONDS = 0.05

        self._fire_event(handler, "/project/assets/logo.png")
        time.sleep(0.15)
        manager.mark_stale.assert_not_called()

    def test_multiple_rapid_events_debounced_to_one(self):
        from mcp_server.file_watcher import _ChangeHandler
        manager = MagicMock()
        handler = _ChangeHandler(manager)
        handler.DEBOUNCE_SECONDS = 0.1

        for _ in range(10):
            self._fire_event(handler, "/project/src/main.ts")
            time.sleep(0.01)
        time.sleep(0.25)
        # Should have been called exactly once
        self.assertEqual(manager.mark_stale.call_count, 1)

    def test_watcher_start_stop(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            watcher, manager = self._make_watcher_and_manager(tmp)
            watcher.start()
            self.assertTrue(watcher.running)
            watcher.stop()
            self.assertFalse(watcher.running)

    def test_watcher_start_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            watcher, manager = self._make_watcher_and_manager(tmp)
            watcher.start()
            watcher.start()  # second call must not crash
            self.assertTrue(watcher.running)
            watcher.stop()


if __name__ == "__main__":
    unittest.main()
