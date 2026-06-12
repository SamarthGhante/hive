import os
from typer.testing import CliRunner
import pytest

from pathlib import Path

from hive.main import app
from hive.database import init_db

TEST_CLI_DB_FILE = "test_cli_hive.db"

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

def test_cli_setup():
    result = runner.invoke(app, ["setup", "--name", "My Hive Project"])
    assert result.exit_code == 0
    assert "Project updated successfully" in result.stdout or "Initialized Hive database" in result.stdout

def test_cli_task_flow():
    # 1. Create a task
    result = runner.invoke(app, ["task-add", "CLI Task", "--desc", "From command line"])
    assert result.exit_code == 0
    assert "Successfully created task" in result.stdout
    
    # 2. List tasks
    result = runner.invoke(app, ["task-list"])
    assert result.exit_code == 0
    assert "CLI Task" in result.stdout
    
    # 3. Claim the task and update
    result = runner.invoke(app, ["task-update", "1", "--claim", "--progress", "75"])
    assert result.exit_code == 0
    assert "Successfully updated task" in result.stdout
    
    # 4. Complete task
    result = runner.invoke(app, ["task-update", "1", "--status", "done", "--progress", "100"])
    assert result.exit_code == 0
    assert "Successfully updated task" in result.stdout

def test_cli_dependencies():
    runner.invoke(app, ["task-add", "Task A"])
    runner.invoke(app, ["task-add", "Task B"])
    
    # Add dependency: B depends on A
    result = runner.invoke(app, ["dep-add", "2", "1"])
    assert result.exit_code == 0
    assert "depends on Task" in result.stdout

def test_cli_comments_and_decisions():
    runner.invoke(app, ["task-add", "Task C"])
    
    # Comment
    result = runner.invoke(app, ["log-comment", "Nice task", "--task", "1"])
    assert result.exit_code == 0
    assert "comment to task" in result.stdout
    
    # Decision
    result = runner.invoke(app, ["log-decision", "Architecture", "Need auth", "Use JWT", "--task", "1"])
    assert result.exit_code == 0
    assert "Recorded decision" in result.stdout

def test_cli_memories():
    result = runner.invoke(app, ["log-memory", "my_key", "my_value"])
    assert result.exit_code == 0
    assert "stored successfully" in result.stdout
    
    result = runner.invoke(app, ["learn"])
    assert result.exit_code == 0
    assert "my_key" in result.stdout
    assert "my_value" in result.stdout

def test_cli_feed():
    runner.invoke(app, ["task-add", "Feed Task"])
    result = runner.invoke(app, ["feed"])
    assert result.exit_code == 0
    assert "TASK_CREATED" in result.stdout

def test_cli_project():
    # Update
    result = runner.invoke(app, ["setup", "--name", "New Project CLI", "--details", "Cli details", "--idea", "Cli idea"])
    assert result.exit_code == 0
    assert "Project updated successfully" in result.stdout
    
    # Show updated
    result = runner.invoke(app, ["learn"])
    assert result.exit_code == 0
    assert "New Project CLI" in result.stdout
    assert "Cli details" in result.stdout
    assert "Cli idea" in result.stdout

def test_cli_comment_project():
    result = runner.invoke(app, ["log-comment", "CLI Project Comment"])
    assert result.exit_code == 0
    assert "Successfully added comment to project" in result.stdout

def test_cli_feed_filtering():
    runner.invoke(app, ["task-add", "Filter Task"])
    result = runner.invoke(app, ["feed", "--task", "1"])
    assert result.exit_code == 0
    assert "TASK_CREATED" in result.stdout

def test_cli_init_agents():
    import pathlib
    agents_path = pathlib.Path("AGENTS.md")
    backup_path = pathlib.Path("AGENTS.md.bak")
    has_agents = agents_path.exists()
    if has_agents:
        agents_path.rename(backup_path)
    
    try:
        result = runner.invoke(app, ["init-agents"])
        assert result.exit_code == 0
        assert "Successfully generated AGENTS.md" in result.stdout
        assert agents_path.exists()
        
        result = runner.invoke(app, ["init-agents"])
        assert "already exists" in result.stdout
        
        result = runner.invoke(app, ["init-agents", "--force"])
        assert result.exit_code == 0
        assert "Successfully generated AGENTS.md" in result.stdout
    finally:
        if agents_path.exists():
            agents_path.unlink()
        if has_agents and backup_path.exists():
            backup_path.rename(agents_path)

def test_cli_setup_auto_agents():
    import pathlib
    agents_path = pathlib.Path("AGENTS.md")
    backup_path = pathlib.Path("AGENTS.md.bak")
    has_agents = agents_path.exists()
    if has_agents:
        agents_path.rename(backup_path)
        
    try:
        result = runner.invoke(app, ["setup", "--name", "Auto Agents Project"])
        assert result.exit_code == 0
        assert "Generated AGENTS.md template" in result.stdout
        assert agents_path.exists()
    finally:
        if agents_path.exists():
            agents_path.unlink()
        if has_agents and backup_path.exists():
            backup_path.rename(agents_path)

def test_cli_task_type_and_unassign():
    result = runner.invoke(app, ["task-add", "Bug Task", "--type", "bug"])
    assert result.exit_code == 0
    assert "Successfully created task" in result.stdout
    
    result = runner.invoke(app, ["task-update", "1", "--status", "done", "--progress", "100"])
    assert result.exit_code == 0
    assert "Task completed!" in result.stdout
    
    result = runner.invoke(app, ["task-update", "1", "--assignee", "none", "--status", "todo", "--progress", "0"])
    assert result.exit_code == 0
    assert "Successfully updated task" in result.stdout
    
    result = runner.invoke(app, ["task-show", "1"])
    assert "Unassigned" in result.stdout

def test_cli_edit_decision():
    runner.invoke(app, ["task-add", "Decision Task"])
    runner.invoke(app, ["log-decision", "Dec Title", "Dec Context", "Dec Details", "--task", "1"])
    
    result = runner.invoke(app, ["edit-decision", "1", "--title", "Updated Title", "--decision", "Updated Details"])
    assert result.exit_code == 0
    assert "Successfully updated decision" in result.stdout

def test_cli_reopened_status():
    runner.invoke(app, ["task-add", "Reopen Task"])
    
    # Update to reopened
    result = runner.invoke(app, ["task-update", "1", "--status", "reopened"])
    assert result.exit_code == 0
    assert "Successfully updated task #1" in result.stdout
    
    # Verify status in task-show
    result = runner.invoke(app, ["task-show", "1"])
    assert result.exit_code == 0
    assert "Status:    bold red Reopened" in result.stdout or "Status:" in result.stdout
