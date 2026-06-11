import os
import pytest
from pathlib import Path
from sqlmodel import Session

TEST_TUI_DB_FILE = "test_tui_hive.db"

from hive.tui import HiveTUIApp
from hive.database import init_db

@pytest.fixture(autouse=True)
def setup_db():
    os.environ["HIVE_DATABASE_URL"] = f"sqlite:///{TEST_TUI_DB_FILE}"
    if Path(TEST_TUI_DB_FILE).exists():
        Path(TEST_TUI_DB_FILE).unlink()
    init_db()
    yield
    os.environ["HIVE_DATABASE_URL"] = f"sqlite:///{TEST_TUI_DB_FILE}"
    if Path(TEST_TUI_DB_FILE).exists():
        Path(TEST_TUI_DB_FILE).unlink()

@pytest.mark.asyncio
async def test_tui_mount():
    os.environ["HIVE_DATABASE_URL"] = f"sqlite:///{TEST_TUI_DB_FILE}"
    app = HiveTUIApp()
    async with app.run_test() as pilot:
        # Check that top-level widgets exist
        assert app.query_one("#task-table") is not None
        assert app.query_one("#command-input") is not None
        assert app.query_one("#details-view") is not None
        assert app.query_one("#project-command-input") is not None
        
        # Test input command submission to create a task
        command_input = app.query_one("#command-input")
        command_input.focus()
        command_input.value = "/create Test Task from TUI"
        await pilot.press("enter")
        
        # Pause to let the background database worker complete and update table rows
        await pilot.pause(0.2)
        
        # Verify table has updated with the newly created task
        table = app.query_one("#task-table")
        assert table.row_count > 0
