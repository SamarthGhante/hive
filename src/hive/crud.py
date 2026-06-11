import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlmodel import Session, select, or_
from hive.models import Task, Dependency, Comment, Decision, Memory, Event
from hive.utils import get_current_actor

def log_event(
    session: Session,
    event_type: str,
    details: str,
    task_id: Optional[int] = None,
    actor: Optional[str] = None
) -> Event:
    """Helper to write to the event log / activity feed."""
    if not actor:
        actor = get_current_actor()
    event = Event(
        task_id=task_id,
        event_type=event_type,
        actor=actor,
        details=details
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event

# --- Task Operations ---

def create_task(
    session: Session,
    title: str,
    description: Optional[str] = None,
    priority: int = 2,
    assignee: Optional[str] = None
) -> Task:
    task = Task(
        title=title,
        description=description,
        priority=priority,
        assignee=assignee,
        status="todo",
        progress=0
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    
    log_event(
        session=session,
        event_type="task_created",
        details=f"Created task: '{title}' (Priority: P{priority})",
        task_id=task.id
    )
    return task

def get_task(session: Session, task_id: int) -> Optional[Task]:
    return session.get(Task, task_id)

def claim_task(session: Session, task_id: int, assignee: str) -> Optional[Task]:
    task = get_task(session, task_id)
    if not task:
        return None
    
    old_assignee = task.assignee
    task.assignee = assignee
    # If a task is claimed and was 'todo', it often transitions to 'in_progress'
    if task.status == "todo":
        task.status = "in_progress"
    task.updated_at = datetime.now(timezone.utc)
    
    session.add(task)
    session.commit()
    session.refresh(task)
    
    details = f"Claimed task. Assignee updated from '{old_assignee}' to '{assignee}'."
    log_event(session=session, event_type="task_claimed", details=details, task_id=task.id)
    return task

def update_task(
    session: Session,
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[int] = None,
    progress: Optional[int] = None,
    assignee: Optional[str] = None
) -> Optional[Task]:
    task = get_task(session, task_id)
    if not task:
        return None
    
    changes = []
    if title is not None and title != task.title:
        changes.append(f"title: '{task.title}' -> '{title}'")
        task.title = title
    if description is not None and description != task.description:
        changes.append(f"description changed")
        task.description = description
    if status is not None and status != task.status:
        changes.append(f"status: '{task.status}' -> '{status}'")
        task.status = status
    if priority is not None and priority != task.priority:
        changes.append(f"priority: P{task.priority} -> P{priority}")
        task.priority = priority
    if progress is not None and progress != task.progress:
        changes.append(f"progress: {task.progress}% -> {progress}%")
        task.progress = progress
    if assignee is not None and assignee != task.assignee:
        changes.append(f"assignee: '{task.assignee}' -> '{assignee}'")
        task.assignee = assignee
        
    if changes:
        task.updated_at = datetime.now(timezone.utc)
        session.add(task)
        session.commit()
        session.refresh(task)
        
        details = f"Updated task: {', '.join(changes)}"
        log_event(session=session, event_type="task_updated", details=details, task_id=task.id)
        
    return task

def complete_task(session: Session, task_id: int) -> Optional[Task]:
    task = get_task(session, task_id)
    if not task:
        return None
        
    if task.status != "done" or task.progress != 100:
        task.status = "done"
        task.progress = 100
        task.updated_at = datetime.now(timezone.utc)
        session.add(task)
        session.commit()
        session.refresh(task)
        
        log_event(
            session=session,
            event_type="task_completed",
            details="Completed task (status set to done, progress 100%).",
            task_id=task.id
        )
    return task

def list_tasks(
    session: Session,
    status: Optional[str] = None,
    assignee: Optional[str] = None
) -> List[Task]:
    statement = select(Task)
    if status:
        statement = statement.where(Task.status == status.lower())
    if assignee:
        statement = statement.where(Task.assignee == assignee)
    return session.exec(statement).all()

# --- Dependency Operations ---

def check_cycle(session: Session, start_task_id: int, target_depends_on_id: int) -> bool:
    """Returns True if making start_task_id depend on target_depends_on_id creates a cycle."""
    visited = set()
    queue = [target_depends_on_id]
    
    while queue:
        current = queue.pop(0)
        if current == start_task_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        
        # Get things that `current` depends on
        statement = select(Dependency).where(Dependency.task_id == current)
        deps = session.exec(statement).all()
        for dep in deps:
            queue.append(dep.depends_on_id)
            
    return False

def add_dependency(session: Session, task_id: int, depends_on_id: int) -> bool:
    """Adds a dependency. Returns False if cycle detected or task doesn't exist."""
    task = get_task(session, task_id)
    dep_task = get_task(session, depends_on_id)
    if not task or not dep_task:
        return False
        
    # Check if duplicate dependency already exists
    statement = select(Dependency).where(
        Dependency.task_id == task_id,
        Dependency.depends_on_id == depends_on_id
    )
    existing = session.exec(statement).first()
    if existing:
        return True # already exists
        
    # Cycle check
    if check_cycle(session, task_id, depends_on_id):
        return False
        
    dep = Dependency(task_id=task_id, depends_on_id=depends_on_id)
    session.add(dep)
    session.commit()
    
    log_event(
        session=session,
        event_type="dependency_added",
        details=f"Added dependency: Task {task_id} now depends on Task {depends_on_id}.",
        task_id=task_id
    )
    return True

def remove_dependency(session: Session, task_id: int, depends_on_id: int) -> bool:
    statement = select(Dependency).where(
        Dependency.task_id == task_id,
        Dependency.depends_on_id == depends_on_id
    )
    dep = session.exec(statement).first()
    if not dep:
        return False
        
    session.delete(dep)
    session.commit()
    
    log_event(
        session=session,
        event_type="dependency_removed",
        details=f"Removed dependency: Task {task_id} no longer depends on Task {depends_on_id}.",
        task_id=task_id
    )
    return True

def get_dependencies(session: Session, task_id: int) -> List[Task]:
    """Get tasks that task_id depends on (its blockers)."""
    statement = select(Task).join(
        Dependency,
        Dependency.depends_on_id == Task.id
    ).where(Dependency.task_id == task_id)
    return session.exec(statement).all()

def get_dependents(session: Session, task_id: int) -> List[Task]:
    """Get tasks that depend on task_id (tasks blocked by it)."""
    statement = select(Task).join(
        Dependency,
        Dependency.task_id == Task.id
    ).where(Dependency.depends_on_id == task_id)
    return session.exec(statement).all()

# --- Comments ---

def add_comment(session: Session, task_id: int, author: str, content: str) -> Optional[Comment]:
    task = get_task(session, task_id)
    if not task:
        return None
        
    comment = Comment(task_id=task_id, author=author, content=content)
    session.add(comment)
    session.commit()
    session.refresh(comment)
    
    log_event(
        session=session,
        event_type="comment_added",
        details=f"Added comment by {author}: '{content[:30]}...'",
        task_id=task_id,
        actor=author
    )
    return comment

def get_comments(session: Session, task_id: int) -> List[Comment]:
    statement = select(Comment).where(Comment.task_id == task_id).order_by(Comment.created_at.asc())
    return session.exec(statement).all()

# --- Decisions ---

def add_decision(
    session: Session,
    task_id: Optional[int],
    title: str,
    context: str,
    decision_text: str,
    author: str
) -> Decision:
    decision = Decision(
        task_id=task_id,
        title=title,
        context=context,
        decision=decision_text,
        author=author
    )
    session.add(decision)
    session.commit()
    session.refresh(decision)
    
    t_msg = f" for Task {task_id}" if task_id else ""
    log_event(
        session=session,
        event_type="decision_added",
        details=f"Recorded decision{t_msg}: '{title}'",
        task_id=task_id,
        actor=author
    )
    return decision

def get_decisions(session: Session, task_id: Optional[int] = None) -> List[Decision]:
    statement = select(Decision)
    if task_id is not None:
        statement = statement.where(Decision.task_id == task_id)
    statement = statement.order_by(Decision.created_at.desc())
    return session.exec(statement).all()

# --- Memory ---

def add_memory(session: Session, key: str, value: str) -> Memory:
    statement = select(Memory).where(Memory.key == key)
    memory = session.exec(statement).first()
    
    actor = get_current_actor()
    if memory:
        old_value = memory.value
        memory.value = value
        memory.updated_at = datetime.now(timezone.utc)
        session.add(memory)
        session.commit()
        session.refresh(memory)
        log_event(
            session=session,
            event_type="memory_updated",
            details=f"Updated memory '{key}'",
            actor=actor
        )
    else:
        memory = Memory(key=key, value=value)
        session.add(memory)
        session.commit()
        session.refresh(memory)
        log_event(
            session=session,
            event_type="memory_added",
            details=f"Added memory '{key}'",
            actor=actor
        )
    return memory

def list_memories(session: Session) -> List[Memory]:
    statement = select(Memory).order_by(Memory.key.asc())
    return session.exec(statement).all()

# --- Activity Feed ---

def get_events(session: Session, limit: int = 50) -> List[Event]:
    statement = select(Event).order_by(Event.created_at.desc()).limit(limit)
    return session.exec(statement).all()
