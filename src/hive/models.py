from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel

class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    status: str = Field(default="todo")  # todo, in_progress, review, done
    priority: int = Field(default=2)    # 0=Critical, 1=High, 2=Medium, 3=Low, 4=Backlog
    progress: int = Field(default=0)    # 0 to 100
    assignee: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Dependency(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="task.id", index=True)
    depends_on_id: int = Field(foreign_key="task.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="My Hive Project")
    details: Optional[str] = Field(default=None)
    overall_idea: Optional[str] = Field(default=None)
    progress: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Comment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: Optional[int] = Field(default=None, foreign_key="task.id", nullable=True, index=True)
    author: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Decision(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: Optional[int] = Field(default=None, foreign_key="task.id", nullable=True, index=True)
    title: str
    context: str
    decision: str
    author: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Memory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    value: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: Optional[int] = Field(default=None, foreign_key="task.id", nullable=True, index=True)
    event_type: str  # task_created, task_claimed, task_updated, task_completed, comment_added, decision_added, memory_added, dependency_added
    actor: str
    details: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
