import os
from typer.testing import CliRunner
import pytest
from sqlmodel import SQLModel

from pathlib import Path
from sqlmodel import SQLModel

TEST_CLI_DB_FILE = "test_cli_hive.db"

from hive.main import app
from hive.database import get_engine, init_db

runner = CliRunner()

@pytest.fixture(autouse=True)
def setup_db():
    # Setup
    os.environ["HIVE_DATABASE_URL"] = f"sqlite:///{TEST_CLI_DB_FILE}"
    if Path(TEST_CLI_DB_FILE).exists():
        Path(TEST_CLI_DB_FILE).unlink()
    init_db()
    yield
    # Teardown
    os.environ["HIVE_DATABASE_URL"] = f"sqlite:///{TEST_CLI_DB_FILE}"
    if Path(TEST_CLI_DB_FILE).exists():
        Path(TEST_CLI_DB_FILE).unlink()

def test_cli_init():
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "Hive database" in result.stdout

def test_cli_task_flow():
    # 1. Create a task
    result = runner.invoke(app, ["task", "create", "--title", "CLI Task", "--desc", "From command line"])
    assert result.exit_code == 0
    assert "Successfully created task" in result.stdout
    
    # 2. List tasks
    result = runner.invoke(app, ["task", "list"])
    assert result.exit_code == 0
    assert "CLI Task" in result.stdout
    
    # 3. Claim the task
    result = runner.invoke(app, ["task", "claim", "1", "--assignee", "cli_agent"])
    assert result.exit_code == 0
    assert "claimed by" in result.stdout
    
    # 4. Update progress
    result = runner.invoke(app, ["task", "update", "1", "--progress", "75", "--status", "review"])
    assert result.exit_code == 0
    assert "Successfully updated task" in result.stdout
    
    # 5. Complete task
    result = runner.invoke(app, ["task", "complete", "1"])
    assert result.exit_code == 0
    assert "marked as complete" in result.stdout

def test_cli_dependencies():
    runner.invoke(app, ["task", "create", "--title", "Task A"])
    runner.invoke(app, ["task", "create", "--title", "Task B"])
    
    # Add dependency: B depends on A
    result = runner.invoke(app, ["dep", "add", "2", "1"])
    assert result.exit_code == 0
    assert "depends on Task" in result.stdout
    
    # Print graph
    result = runner.invoke(app, ["dep", "graph"])
    assert result.exit_code == 0
    assert "Task A" in result.stdout
    assert "Task B" in result.stdout

def test_cli_comments_and_decisions():
    runner.invoke(app, ["task", "create", "--title", "Task C"])
    
    # Comment
    result = runner.invoke(app, ["comment", "add", "1", "--content", "Nice task"])
    assert result.exit_code == 0
    assert "comment to task" in result.stdout
    
    # Decision
    result = runner.invoke(app, ["decision", "add", "-t", "Architecture", "-x", "Need auth", "-d", "Use JWT", "-k", "1"])
    assert result.exit_code == 0
    assert "Recorded decision" in result.stdout

def test_cli_memories():
    result = runner.invoke(app, ["memory", "add", "my_key", "my_value"])
    assert result.exit_code == 0
    assert "stored successfully" in result.stdout
    
    result = runner.invoke(app, ["memory", "list"])
    assert result.exit_code == 0
    assert "my_key" in result.stdout
    assert "my_value" in result.stdout

def test_cli_feed():
    runner.invoke(app, ["task", "create", "--title", "Feed Task"])
    result = runner.invoke(app, ["feed"])
    assert result.exit_code == 0
    assert "TASK_CREATED" in result.stdout

def test_cli_project():
    # Show initial
    result = runner.invoke(app, ["project", "show"])
    assert result.exit_code == 0
    assert "My Hive Project" in result.stdout
    
    # Update
    result = runner.invoke(app, ["project", "update", "--name", "New Project CLI", "--details", "Cli details", "--idea", "Cli idea"])
    assert result.exit_code == 0
    assert "Project updated successfully" in result.stdout
    
    # Show updated
    result = runner.invoke(app, ["project", "show"])
    assert result.exit_code == 0
    assert "New Project CLI" in result.stdout
    assert "Cli details" in result.stdout
    assert "Cli idea" in result.stdout

def test_cli_comment_project():
    result = runner.invoke(app, ["comment", "add", "--project", "--content", "CLI Project Comment"])
    assert result.exit_code == 0
    assert "Successfully added comment to project" in result.stdout

def test_cli_feed_filtering():
    runner.invoke(app, ["task", "create", "--title", "Filter Task"])
    result = runner.invoke(app, ["feed", "--task-id", "1"])
    assert result.exit_code == 0
    assert "TASK_CREATED" in result.stdout
