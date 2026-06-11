from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich import print as rprint
from sqlmodel import select
from hive.database import init_db, get_db_path, get_session
from hive.models import Task, Dependency
import hive.crud as crud
from hive.utils import get_current_actor, format_priority, format_status, format_datetime

app = typer.Typer(
    help="Hive: Collaborative execution, coordination, memory, and project management layer for humans and agents.",
    no_args_is_help=True
)

console = Console()

# --- Project Initialization & Learning ---

@app.command("setup")
def setup(
    name: Optional[str] = typer.Option(None, "--name", help="Project name"),
    details: Optional[str] = typer.Option(None, "--details", help="Project details / description"),
    overall_idea: Optional[str] = typer.Option(None, "--idea", help="Project overall goal or idea")
):
    """Initialize Hive and set project metadata."""
    db_path = get_db_path()
    if not db_path.exists():
        init_db()
        console.print(f"[green]Initialized Hive database at {db_path}[/green]")
    
    if name or details or overall_idea:
        with get_session() as session:
            crud.update_project(session, name=name, details=details, overall_idea=overall_idea)
            console.print("[green]Project updated successfully.[/green]")

    # Auto-generate AGENTS.md if it doesn't exist
    import pathlib
    agents_path = pathlib.Path("AGENTS.md")
    if not agents_path.exists():
        from hive.templates import AGENTS_TEMPLATE
        agents_path.write_text(AGENTS_TEMPLATE, encoding="utf-8")
        console.print("[green]Generated AGENTS.md template for agent guidelines.[/green]")

@app.command("init-agents")
def init_agents(
    force: bool = typer.Option(False, "--force", "-f", help="Force overwrite AGENTS.md if it exists")
):
    """Generate the AGENTS.md workflow and instruction manual in the current directory."""
    import pathlib
    from hive.templates import AGENTS_TEMPLATE
    agents_path = pathlib.Path("AGENTS.md")
    if agents_path.exists() and not force:
        console.print("[yellow]AGENTS.md already exists in the current directory. Use --force to overwrite it.[/yellow]")
        raise typer.Exit()
    
    agents_path.write_text(AGENTS_TEMPLATE, encoding="utf-8")
    console.print("[green]Successfully generated AGENTS.md in the current directory.[/green]")

@app.command("status")
def status(progress: str = typer.Argument(..., help="Project progress summary")):
    """Quickly update the project's overall progress string."""
    with get_session() as session:
        crud.update_project(session, progress=progress)
        console.print("[green]Project progress updated successfully.[/green]")

@app.command("learn")
def learn():
    """Print the complete project context for agent learning."""
    with get_session() as session:
        project = crud.get_project(session)
        tasks = crud.list_tasks(session)
        memories = crud.list_memories(session)
        decisions = crud.get_decisions(session, project_only=True)
        comments = crud.get_comments(session, project_only=True)
        events = crud.get_events(session, limit=100)
        
        console.print(f"\n=== PROJECT: {project.name} ===")
        console.print(f"Details: {project.details or 'None'}")
        console.print(f"Overall Idea: {project.overall_idea or 'None'}")
        console.print(f"Progress Summary: {project.progress or 'None'}")
        
        console.print("\n=== MEMORIES (PREFERENCES & GUIDELINES) ===")
        if not memories: console.print("None")
        for m in memories: console.print(f"- {m.key}: {m.value}")
            
        console.print("\n=== PROJECT DECISIONS ===")
        if not decisions: console.print("None")
        for d in decisions: console.print(f"- {d.title}: {d.decision} (Context: {d.context})")
            
        console.print("\n=== PROJECT COMMENTS ===")
        if not comments: console.print("None")
        for c in comments: console.print(f"- {c.author}: {c.content}")
            
        console.print("\n=== TASKS ===")
        open_tasks = [t for t in tasks if t.status != "done"]
        closed_tasks = [t for t in tasks if t.status == "done"]
        console.print(f"Open Tasks ({len(open_tasks)}):")
        for t in open_tasks:
            console.print(f"  [{t.id}] {t.title} (Status: {t.status}, Progress: {t.progress}%)")
        console.print(f"\nClosed Tasks ({len(closed_tasks)}):")
        for t in closed_tasks:
            console.print(f"  [{t.id}] {t.title}")
            
        console.print("\n=== RECENT ACTIVITY FEED ===")
        if not events: console.print("None")
        for e in events: console.print(f"- {format_datetime(e.created_at)} | {e.actor} | {e.event_type} | {e.details}")

# --- Task Management ---

@app.command("task-add")
def task_add(
    title: str = typer.Argument(..., help="Task title"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Task description"),
    priority: int = typer.Option(2, "--priority", "-p", help="Priority: 0(Critical)-4(Backlog)"),
    assignee: Optional[str] = typer.Option(None, "--assignee", "-a", help="Assignee name")
):
    """Create a new task."""
    if priority < 0 or priority > 4:
        console.print("[red]Error: Priority must be between 0 (Critical) and 4 (Backlog)[/red]")
        raise typer.Exit(1)
        
    with get_session() as session:
        task = crud.create_task(session, title, description, priority, assignee)
        console.print(f"[green]Successfully created task #{task.id}: [bold]{task.title}[/bold][/green]")

@app.command("task-list")
def task_list(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
    assignee: Optional[str] = typer.Option(None, "--assignee", "-a", help="Filter by assignee")
):
    """List tasks in the project."""
    with get_session() as session:
        tasks = crud.list_tasks(session, status, assignee)
        if not tasks:
            console.print("[yellow]No tasks found.[/yellow]")
            return
            
        table = Table(title="Hive Tasks", show_header=True, header_style="bold blue")
        table.add_column("ID", style="bold blue", width=6)
        table.add_column("Title", style="bold white", width=30)
        table.add_column("Status", width=15)
        table.add_column("Priority", width=12)
        table.add_column("Progress", width=10)
        table.add_column("Assignee", style="cyan", width=15)
        table.add_column("Updated At", style="dim", width=20)
        
        status_colors = {
            "todo": "dim white",
            "in_progress": "bold blue",
            "review": "bold yellow",
            "done": "bold green"
        }
        
        priority_colors = {
            0: "bold red",
            1: "red",
            2: "orange3",
            3: "blue",
            4: "dim white"
        }
        
        for t in tasks:
            status_style = status_colors.get(t.status, "white")
            priority_style = priority_colors.get(t.priority, "white")
            p_bar = f"{t.progress}%"
            
            table.add_row(
                f"#{t.id}",
                t.title,
                f"[{status_style}]{format_status(t.status)}[/{status_style}]",
                f"[{priority_style}]{format_priority(t.priority)}[/{priority_style}]",
                p_bar,
                t.assignee or "-",
                format_datetime(t.updated_at)
            )
        console.print(table)

@app.command("task-update")
def task_update(
    task_id: int = typer.Argument(..., help="Task ID to update"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Update title"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Update description"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Update status (todo, in_progress, review, done)"),
    priority: Optional[int] = typer.Option(None, "--priority", "-p", help="Update priority (0-4)"),
    progress: Optional[int] = typer.Option(None, "--progress", "-g", help="Update progress percentage (0-100)"),
    assignee: Optional[str] = typer.Option(None, "--assignee", "-a", help="Update assignee name"),
    claim: bool = typer.Option(False, "--claim", help="Claim this task for yourself (sets status to in_progress)")
):
    """Update an existing task's fields, or claim/complete it."""
    if priority is not None and (priority < 0 or priority > 4):
        console.print("[red]Error: Priority must be between 0 and 4[/red]")
        raise typer.Exit(1)
    if progress is not None and (progress < 0 or progress > 100):
        console.print("[red]Error: Progress must be between 0 and 100[/red]")
        raise typer.Exit(1)
    if status is not None and status.lower() not in ["todo", "in_progress", "review", "done"]:
        console.print("[red]Error: Status must be one of: todo, in_progress, review, done[/red]")
        raise typer.Exit(1)
        
    with get_session() as session:
        if claim:
            assignee = assignee or get_current_actor()
            status = "in_progress"
            
        task = crud.update_task(
            session=session,
            task_id=task_id,
            title=title,
            description=description,
            status=status.lower() if status else None,
            priority=priority,
            progress=progress,
            assignee=assignee
        )
        if not task:
            console.print(f"[red]Error: Task #{task_id} not found.[/red]")
            raise typer.Exit(1)
        console.print(f"[green]Successfully updated task #{task.id}[/green]")

@app.command("task-show")
def task_show(task_id: int = typer.Argument(..., help="Task ID to show")):
    """Show detailed view of a task including comments, dependencies, and decisions."""
    with get_session() as session:
        task = crud.get_task(session, task_id)
        if not task:
            console.print(f"[red]Error: Task #{task_id} not found.[/red]")
            raise typer.Exit(1)
            
        blockers = crud.get_dependencies(session, task_id)
        dependents = crud.get_dependents(session, task_id)
        comments = crud.get_comments(session, task_id)
        decisions = crud.get_decisions(session, task_id)
        
        priority_style = {0: "bold red", 1: "red", 2: "orange3", 3: "blue", 4: "dim white"}.get(task.priority, "white")
        status_style = {"todo": "dim white", "in_progress": "bold blue", "review": "bold yellow", "done": "bold green"}.get(task.status, "white")
        
        details_text = (
            f"[bold]Title:[/bold] {task.title}\n"
            f"[bold]Description:[/bold] {task.description or 'No description'}\n\n"
            f"[bold]Status:[/bold] [{status_style}]{format_status(task.status)}[/{status_style}]  |  "
            f"[bold]Priority:[/bold] [{priority_style}]{format_priority(task.priority)}[/{priority_style}]  |  "
            f"[bold]Progress:[/bold] {task.progress}%\n"
            f"[bold]Assignee:[/bold] [cyan]{task.assignee or 'Unassigned'}[/cyan]\n"
            f"[bold]Created:[/bold] {format_datetime(task.created_at)}  |  "
            f"[bold]Updated:[/bold] {format_datetime(task.updated_at)}"
        )
        console.print(Panel(details_text, title=f"Task #{task.id}", border_style="blue"))
        
        dep_lines = []
        dep_lines.append("[bold]Depends On (Blockers):[/bold]")
        if blockers:
            for b in blockers:
                dep_lines.append(f"  - #{b.id}: {b.title} ({format_status(b.status)})")
        else:
            dep_lines.append("  - None")
            
        dep_lines.append("\n[bold]Blocked Tasks (Dependents):[/bold]")
        if dependents:
            for d in dependents:
                dep_lines.append(f"  - #{d.id}: {d.title} ({format_status(d.status)})")
        else:
            dep_lines.append("  - None")
            
        console.print(Panel("\n".join(dep_lines), title="Dependencies", border_style="cyan"))
        
        dec_lines = []
        if decisions:
            for dec in decisions:
                dec_lines.append(f"[bold]{dec.title}[/bold] by [cyan]{dec.author}[/cyan] ({format_datetime(dec.created_at)})\nContext: {dec.context}\nDecision: {dec.decision}\n---")
        else:
            dec_lines.append("No decisions recorded for this task.")
        console.print(Panel("\n".join(dec_lines), title="Decisions", border_style="magenta"))
        
        comm_lines = []
        if comments:
            for c in comments:
                comm_lines.append(f"[bold][cyan]{c.author}[/cyan][/bold] ({format_datetime(c.created_at)}):\n{c.content}\n---")
        else:
            comm_lines.append("No comments yet.")
        console.print(Panel("\n".join(comm_lines), title="Comments", border_style="green"))

# --- Logging (Decisions, Comments, Memories) ---

@app.command("log-decision")
def log_decision(
    title: str = typer.Argument(..., help="Title of the decision"),
    context: str = typer.Argument(..., help="Context or problem being addressed"),
    decision_text: str = typer.Argument(..., help="The decision details"),
    task_id: Optional[int] = typer.Option(None, "--task", "-t", help="Associated Task ID (optional)")
):
    """Record an architectural or project decision."""
    author = get_current_actor()
    with get_session() as session:
        if task_id is not None:
            task = crud.get_task(session, task_id)
            if not task:
                console.print(f"[red]Error: Task #{task_id} not found.[/red]")
                raise typer.Exit(1)
        crud.add_decision(session, task_id, title, context, decision_text, author)
        console.print(f"[green]Recorded decision: [bold]{title}[/bold][/green]")

@app.command("log-comment")
def log_comment(
    content: str = typer.Argument(..., help="Comment body"),
    task_id: Optional[int] = typer.Option(None, "--task", "-t", help="Task ID to comment on (leave empty for project-level)")
):
    """Add a comment to a task or the project."""
    author = get_current_actor()
    with get_session() as session:
        comment = crud.add_comment(session, task_id, author, content)
        if task_id is not None and not comment:
            console.print(f"[red]Error: Task #{task_id} not found.[/red]")
            raise typer.Exit(1)
        if task_id is None:
            console.print("[green]Successfully added comment to project[/green]")
        else:
            console.print(f"[green]Successfully added comment to task #{task_id}[/green]")

@app.command("log-memory")
def log_memory(
    key: str = typer.Argument(..., help="Key for the memory"),
    value: str = typer.Argument(..., help="Value / content of the memory")
):
    """Store or update a project memory (preferences, rules)."""
    with get_session() as session:
        crud.add_memory(session, key, value)
        console.print(f"[green]Memory [bold]{key}[/bold] stored successfully.[/green]")

# --- Dependencies & Tracking ---

@app.command("dep-add")
def dep_add(
    task_id: int = typer.Argument(..., help="Dependent task ID"),
    depends_on: int = typer.Argument(..., help="Task ID that is blocking it")
):
    """Add a dependency (task depends_on becomes blocking for task_id)."""
    with get_session() as session:
        success = crud.add_dependency(session, task_id, depends_on)
        if not success:
            console.print("[red]Error: Failed to add dependency. Make sure both tasks exist and adding it does not create a cycle.[/red]")
            raise typer.Exit(1)
        console.print(f"[green]Successfully added dependency: Task #{task_id} now depends on Task #{depends_on}[/green]")

@app.command("feed")
def feed(
    limit: int = typer.Option(30, help="Number of activity events to display"),
    task_id: Optional[int] = typer.Option(None, "--task", "-t", help="Filter events by Task ID")
):
    """Show recent activity feed / event log."""
    with get_session() as session:
        events = crud.get_events(session, task_id=task_id, limit=limit)
        if not events:
            console.print("[yellow]No activity events found.[/yellow]")
            return
            
        table = Table(title="Hive Activity Feed", show_header=True, header_style="bold magenta")
        table.add_column("Time", style="dim", width=20)
        table.add_column("Actor", style="cyan")
        table.add_column("Event Type", style="green")
        table.add_column("Details", style="white")
        table.add_column("Task ID", style="blue")
        
        for e in events:
            task_str = f"#{e.task_id}" if e.task_id else "-"
            table.add_row(
                format_datetime(e.created_at),
                e.actor,
                e.event_type.upper(),
                e.details,
                task_str
            )
        console.print(table)

@app.command("tui")
def launch_tui():
    """Launch the interactive TUI dashboard."""
    from hive.tui import HiveTUIApp
    db_path = get_db_path()
    if not db_path.exists():
        init_db()
    app_tui = HiveTUIApp()
    app_tui.run()

if __name__ == "__main__":
    app()
