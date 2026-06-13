import os
import pytest
from pathlib import Path
from sqlmodel import Session

from hive.database import get_engine, init_db
import hive.crud as crud

TEST_DB_FILE = "test_hive.db"

@pytest.fixture(name="session")
def session_fixture():
    # Setup
    os.environ["HIVE_DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
    if Path(TEST_DB_FILE).exists():
        Path(TEST_DB_FILE).unlink()
    init_db()
    engine = get_engine()
    with Session(engine) as session:
        yield session
    # Teardown
    os.environ["HIVE_DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE}"
    if Path(TEST_DB_FILE).exists():
        Path(TEST_DB_FILE).unlink()

def test_create_and_get_task(session: Session):
    task = crud.create_task(
        session=session,
        title="Test Task",
        description="Test description",
        priority=1,
        assignee="test_agent"
    )
    
    assert task.id is not None
    assert task.title == "Test Task"
    assert task.description == "Test description"
    assert task.priority == 1
    assert task.status == "todo"
    assert task.progress == 0
    assert task.assignee == "test_agent"
    
    fetched = crud.get_task(session, task.id)
    assert fetched is not None
    assert fetched.id == task.id

def test_claim_and_complete_task(session: Session):
    task = crud.create_task(session, title="Claimable Task")
    assert task.assignee is None
    
    claimed = crud.claim_task(session, task.id, "claimant_agent")
    assert claimed.assignee == "claimant_agent"
    assert claimed.status == "in_progress"
    
    completed = crud.complete_task(session, task.id)
    assert completed.status == "done"
    assert completed.progress == 100

def test_update_task(session: Session):
    task = crud.create_task(session, title="Update Task")
    
    updated = crud.update_task(
        session=session,
        task_id=task.id,
        title="New Title",
        progress=50,
        status="review"
    )
    
    assert updated.title == "New Title"
    assert updated.progress == 50
    assert updated.status == "review"

def test_dependencies_and_cycle_checking(session: Session):
    t1 = crud.create_task(session, title="Task 1")
    t2 = crud.create_task(session, title="Task 2")
    t3 = crud.create_task(session, title="Task 3")
    
    # Add dependency t2 depends on t1 (t1 blocks t2)
    success = crud.add_dependency(session, t2.id, t1.id)
    assert success is True
    
    # Add dependency t3 depends on t2 (t2 blocks t3)
    success = crud.add_dependency(session, t3.id, t2.id)
    assert success is True
    
    # Verify blockers and dependents
    blockers = crud.get_dependencies(session, t2.id)
    assert len(blockers) == 1
    assert blockers[0].id == t1.id
    
    dependents = crud.get_dependents(session, t2.id)
    assert len(dependents) == 1
    assert dependents[0].id == t3.id
    
    # Check cycle detection: try to make t1 depend on t3 (which would create t1 -> t3 -> t2 -> t1)
    success = crud.add_dependency(session, t1.id, t3.id)
    assert success is False # cycle detected!

def test_comments(session: Session):
    task = crud.create_task(session, title="Comment Task")
    
    comment = crud.add_comment(session, task.id, "author_agent", "This is a comment.")
    assert comment is not None
    assert comment.author == "author_agent"
    assert comment.content == "This is a comment."
    
    comments = crud.get_comments(session, task.id)
    assert len(comments) == 1
    assert comments[0].content == "This is a comment."

def test_decisions(session: Session):
    task = crud.create_task(session, title="Decision Task")
    
    decision = crud.add_decision(
        session=session,
        task_id=task.id,
        title="Auth Decision",
        context="We need authentication",
        decision_text="Use OAuth2",
        author="decision_agent"
    )
    
    assert decision.title == "Auth Decision"
    assert decision.decision == "Use OAuth2"
    
    decisions = crud.get_decisions(session, task.id)
    assert len(decisions) == 1

def test_memories(session: Session):
    crud.add_memory(session, "key1", "value1")
    crud.add_memory(session, "key1", "value2") # overwrite
    
    memories = crud.list_memories(session)
    assert len(memories) == 1
    assert memories[0].key == "key1"
    assert memories[0].value == "value2"

def test_project_metadata(session: Session):
    # Test auto-create defaults
    project = crud.get_project(session)
    assert project.name == "My Hive Project"
    assert project.details == "No project details yet."
    assert project.overall_idea == "No overall idea yet."
    
    # Test update
    updated = crud.update_project(
        session,
        name="New Project Name",
        details="Brand new details",
        overall_idea="Brand new idea"
    )
    assert updated.name == "New Project Name"
    assert updated.details == "Brand new details"
    assert updated.overall_idea == "Brand new idea"

def test_project_comments(session: Session):
    # Comment without task_id
    comment = crud.add_comment(session, task_id=None, author="project_agent", content="Project level comment.")
    assert comment is not None
    assert comment.task_id is None
    assert comment.content == "Project level comment."
    
    comments = crud.get_comments(session, task_id=None)
    assert len(comments) == 1
    assert comments[0].content == "Project level comment."

def test_reopen_task(session: Session):
    task = crud.create_task(session, title="Reopen Test Task")
    assert task.status == "todo"
    
    # Claim transitions to in_progress
    crud.claim_task(session, task.id, "agent1")
    assert task.status == "in_progress"
    
    # Reopen transitions to reopened and resets progress
    crud.update_task(session, task.id, status="reopened", progress=0)
    assert task.status == "reopened"
    assert task.progress == 0
    
    # Re-claim from reopened transitions to in_progress
    crud.claim_task(session, task.id, "agent2")
    assert task.status == "in_progress"

def test_project_progress_appending(session: Session):
    p = crud.get_project(session)
    # Check default progress
    assert p.progress == "No progress recorded yet." or p.progress is None
    
    # Update progress
    p = crud.update_project(session, progress="Initial setup")
    assert "Initial setup" in p.progress
    
    # Append progress
    p = crud.update_project(session, progress="Phase 2")
    assert "Initial setup" in p.progress
    assert "Phase 2" in p.progress
    
    # Try updating with identical text (should do nothing)
    old_prog = p.progress
    p = crud.update_project(session, progress=old_prog)
    assert p.progress == old_prog
