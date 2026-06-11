import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from sqlmodel import SQLModel, create_engine, Session

def find_project_root() -> Path:
    """Find the root of the project, looking for .git or pyproject.toml."""
    current = Path.cwd().resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists() or (parent / ".hive").exists():
            return parent
    return current

def get_db_path() -> Path:
    """Get the path to the SQLite database file."""
    # Allow overriding database path via env var
    env_db = os.environ.get("HIVE_DATABASE_URL")
    if env_db:
        # If it's a sqlite path, extract the file path
        if env_db.startswith("sqlite:///"):
            return Path(env_db.replace("sqlite:///", ""))
        return Path(env_db) # Non-sqlite URLs handled separately in get_engine
    
    root = find_project_root()
    hive_dir = root / ".hive"
    return hive_dir / "hive.db"

def get_database_url() -> str:
    """Get the SQLAlchemy database connection URL."""
    env_url = os.environ.get("HIVE_DATABASE_URL")
    if env_url:
        return env_url
    
    db_path = get_db_path()
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"

def get_engine():
    url = get_database_url()
    connect_args = {}
    if url.startswith("sqlite:"):
        connect_args = {"check_same_thread": False}
    return create_engine(url, connect_args=connect_args)

def init_db() -> None:
    """Create all database tables and apply schema updates if needed."""
    # Ensure models are imported so SQLModel knows about them
    from hive.models import Task, Project, Comment, Decision, Memory, Event
    
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    
    # Run migrations for existing sqlite databases
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    
    # Check project table columns
    if "project" in inspector.get_table_names():
        proj_cols = [c["name"] for c in inspector.get_columns("project")]
        if "progress" not in proj_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE project ADD COLUMN progress VARCHAR"))
                
    # Check task table columns
    if "task" in inspector.get_table_names():
        task_cols = [c["name"] for c in inspector.get_columns("task")]
        if "task_type" not in task_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE task ADD COLUMN task_type VARCHAR DEFAULT 'feature'"))

@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager for database sessions."""
    init_db()
    engine = get_engine()
    with Session(engine) as session:
        yield session
