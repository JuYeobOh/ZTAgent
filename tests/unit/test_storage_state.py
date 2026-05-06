import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock
from employee_agent.browser.session import SessionManager


def test_load_returns_none_when_no_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SessionManager(tmpdir)
        assert mgr.load() is None


def test_load_returns_dict_when_file_exists():
    with tempfile.TemporaryDirectory() as tmpdir:
        state = {"cookies": [{"name": "session", "value": "abc123"}], "origins": []}
        path = Path(tmpdir) / "storage_state.json"
        path.write_text(json.dumps(state))

        mgr = SessionManager(tmpdir)
        result = mgr.load()
        assert result == state


@pytest.mark.asyncio
async def test_save_writes_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SessionManager(tmpdir)
        mock_context = AsyncMock()
        mock_context.storage_state = AsyncMock(return_value={"cookies": [], "origins": []})

        await mgr.save(mock_context)

        path = Path(tmpdir) / "storage_state.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert "cookies" in data


def test_exists_false_when_no_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SessionManager(tmpdir)
        assert mgr.exists() is False


def test_exists_true_when_file_present():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "storage_state.json"
        path.write_text('{"cookies": [], "origins": []}')
        mgr = SessionManager(tmpdir)
        assert mgr.exists() is True
