import os
import sys
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.tree import Tree
from rich import print as rprint
from sqlmodel import select
from hive.database import get_engine, init_db, get_db_path, get_session
from hive.models import Task, Dependency, Comment, Decision, Memory, Event, Project
import hive.crud as crud
from hive.utils import get_current_actor, format_priority, format_status, format_datetime

app = typer.Typer(
    help="Hive: Collaborative execution, coordination, memory, and project management layer for humans and agents.",
    no_args_is_help=True
)

task_app = typer.Typer(help="Manage tasks", no_args_is_help=True)
dep_app = typer.Typer(help="Manage task dependencies", no_args_is_help=True)
comment_app = typer.Typer(help="Manage task comments", no_args_is_help=True)
decision_app = typer.Typer(help="Manage decisions", no_args_is_help=True)
memory_app = typer.Typer(help="Manage project memories", no_args_is_help=True)
project_app = typer.Typer(help="Manage project metadata", no_args_is_help=True)

app.add_typer(task_app, name="task")
app.add_typer(dep_app, name="dep")
app.add_typer(comment_app, name="comment")
app.add_typer(decision_app, name="decision")
app.add_typer(memory_app, name="memory")
app.add_typer(project_app, name="project")

console = Console()

# --- Top Level Commands ---

@app.command("init")
def init():
    """Initialize Hive database in the current project root."""
    db_path = get_db_path()
    if db_path.exists():
        console.print(f"[yellow]Hive database already exists at {db_path}[/yellow]")
    else:
        init_db()
        console.print(f"[green]Initialized Hive database at {db_path}[/green]")

@app.command("feed")
def feed(
    limit: int = typer.Option(30, help="Number of activity events to display"),
    task_id: Optional[int] = typer.Option(None, "--task-id", "-t", help="Filter events by Task ID")
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

# --- Task Commands ---

@task_app.command("create")
def task_create(
    title: str = typer.Option(..., "--title", "-t", help="Task title"),
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

@task_app.command("claim")
def task_claim(
    task_id: int = typer.Argument(..., help="Task ID to claim"),
    assignee: Optional[str] = typer.Option(None, "--assignee", "-a", help="Claimant name (defaults to current actor)")
):
    """Claim a task for yourself or a specific agent."""
    if not assignee:
        assignee = get_current_actor()
        
    with get_session() as session:
        task = crud.claim_task(session, task_id, assignee)
        if not task:
            console.print(f"[red]Error: Task #{task_id} not found.[/red]")
            raise typer.Exit(1)
        console.print(f"[green]Task #{task.id} claimed by [bold]{assignee}[/bold] (Status set to In Progress)[/green]")

@task_app.command("update")
def task_update(
    task_id: int = typer.Argument(..., help="Task ID to update"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Update title"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Update description"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Update status (todo, in_progress, review, done)"),
    priority: Optional[int] = typer.Option(None, "--priority", "-p", help="Update priority (0-4)"),
    progress: Optional[int] = typer.Option(None, "--progress", "-g", help="Update progress percentage (0-100)"),
    assignee: Optional[str] = typer.Option(None, "--assignee", "-a", help="Update assignee name")
):
    """Update an existing task's fields."""
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

@task_app.command("complete")
def task_complete(task_id: int = typer.Argument(..., help="Task ID to mark complete")):
    """Mark a task as complete."""
    with get_session() as session:
        task = crud.complete_task(session, task_id)
        if not task:
            console.print(f"[red]Error: Task #{task_id} not found.[/red]")
            raise typer.Exit(1)
        console.print(f"[green]Task #{task.id} marked as complete (status: done, progress: 100%)[/green]")

@task_app.command("list")
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

@task_app.command("show")
def task_show(task_id: int = typer.Argument(..., help="Task ID to show")):
    """Show detailed view of a task including comments, dependencies, and decisions."""
    with get_session() as session:
        task = crud.get_task(session, task_id)
        if not task:
            console.print(f"[red]Error: Task #{task_id} not found.[/red]")
            raise typer.Exit(1)
            
        # Get extra information
        blockers = crud.get_dependencies(session, task_id)
        dependents = crud.get_dependents(session, task_id)
        comments = crud.get_comments(session, task_id)
        decisions = crud.get_decisions(session, task_id)
        
        # Priority and status representation
        priority_style = {0: "bold red", 1: "red", 2: "orange3", 3: "blue", 4: "dim white"}.get(task.priority, "white")
        status_style = {"todo": "dim white", "in_progress": "bold blue", "review": "bold yellow", "done": "bold green"}.get(task.status, "white")
        
        # Details Panel
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
        
        # Dependencies Columns
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
        
        # Decisions Panel
        dec_lines = []
        if decisions:
            for dec in decisions:
                dec_lines.append(f"[bold]{dec.title}[/bold] by [cyan]{dec.author}[/cyan] ({format_datetime(dec.created_at)})\nContext: {dec.context}\nDecision: {dec.decision}\n---")
        else:
            dec_lines.append("No decisions recorded for this task.")
        console.print(Panel("\n".join(dec_lines), title="Decisions", border_style="magenta"))
        
        # Comments Panel
        comm_lines = []
        if comments:
            for c in comments:
                comm_lines.append(f"[bold][cyan]{c.author}[/cyan][/bold] ({format_datetime(c.created_at)}):\n{c.content}\n---")
        else:
            comm_lines.append("No comments yet.")
        console.print(Panel("\n".join(comm_lines), title="Comments", border_style="green"))

# --- Dependency Commands ---

@dep_app.command("add")
def dep_add(
    task_id: int = typer.Argument(..., help="Dependent task ID"),
    depends_on: int = typer.Argument(..., help="Task ID that is blocking it")
):
    """Add a dependency (task depends_on becomes blocking for task_id)."""
    with get_session() as session:
        success = crud.add_dependency(session, task_id, depends_on)
        if not success:
            console.print(f"[red]Error: Failed to add dependency. Make sure both tasks exist and adding it does not create a cycle.[/red]")
            raise typer.Exit(1)
        console.print(f"[green]Successfully added dependency: Task #{task_id} now depends on Task #{depends_on}[/green]")

@dep_app.command("remove")
def dep_remove(
    task_id: int = typer.Argument(..., help="Dependent task ID"),
    depends_on: int = typer.Argument(..., help="Task ID to remove dependency from")
):
    """Remove a dependency."""
    with get_session() as session:
        success = crud.remove_dependency(session, task_id, depends_on)
        if not success:
            console.print(f"[red]Error: Dependency not found between Task #{task_id} and Task #{depends_on}[/red]")
            raise typer.Exit(1)
        console.print(f"[green]Successfully removed dependency: Task #{task_id} no longer depends on Task #{depends_on}[/green]")

@dep_app.command("graph")
def dep_graph():
    """Print dependency tree of the project."""
    with get_session() as session:
        tasks = session.exec(select(Task)).all()
        if not tasks:
            console.print("[yellow]No tasks found.[/yellow]")
            return
            
        task_map = {t.id: t for t in tasks}
        deps = session.exec(select(Dependency)).all()
        
        blockers = {t.id: [] for t in tasks}
        dependents = {t.id: [] for t in tasks}
        
        for dep in deps:
            if dep.task_id in blockers:
                blockers[dep.task_id].append(dep.depends_on_id)
            if dep.depends_on_id in dependents:
                dependents[dep.depends_on_id].append(dep.task_id)
                
        # Root tasks are those with no blockers
        roots = [t for t in tasks if not blockers[t.id]]
        if not roots:
            roots = tasks # fallback
            
        tree = Tree("🔗 [bold]Hive Task Dependency Tree (Blocked by -> Blocks)[/bold]")
        
        def add_node(parent_tree_node, t_id, visited=None):
            if visited is None:
                visited = set()
            if t_id in visited:
                parent_tree_node.add(f"[red]🔄 Cycle detected at task #{t_id}[/red]")
                return
            visited.add(t_id)
            
            t = task_map.get(t_id)
            if not t:
                return
                
            status_colors = {
                "todo": "dim white",
                "in_progress": "bold blue",
                "review": "bold yellow",
                "done": "bold green"
            }
            c = status_colors.get(t.status, "white")
            node_label = f"[bold]#{t.id}[/bold] {t.title} [[{c}]{format_status(t.status)}[/{c}]]"
            
            node = parent_tree_node.add(node_label)
            for child_id in dependents[t_id]:
                add_node(node, child_id, visited.copy())
                
        for root in roots:
            add_node(tree, root.id)
            
        rprint(tree)

# --- Comment Commands ---

@comment_app.command("add")
def comment_add(
    task_id: Optional[int] = typer.Argument(None, help="Task ID to comment on (leave empty if --project is set)"),
    content: str = typer.Option(..., "--content", "-c", prompt="Enter comment content", help="Comment body"),
    project: bool = typer.Option(False, "--project", "-p", help="Add comment to the project level rather than a specific task")
):
    """Add a comment to a task or project."""
    if not project and task_id is None:
        console.print("[red]Error: Must specify Task ID or pass --project flag.[/red]")
        raise typer.Exit(1)
    if project and task_id is not None:
        console.print("[red]Error: Cannot specify both a Task ID and the --project flag.[/red]")
        raise typer.Exit(1)
        
    author = get_current_actor()
    with get_session() as session:
        comment = crud.add_comment(session, task_id if not project else None, author, content)
        if not project and not comment:
            console.print(f"[red]Error: Task #{task_id} not found.[/red]")
            raise typer.Exit(1)
        if project:
            console.print("[green]Successfully added comment to project[/green]")
        else:
            console.print(f"[green]Successfully added comment to task #{task_id}[/green]")

# --- Decision Commands ---

@decision_app.command("add")
def decision_add(
    title: str = typer.Option(..., "--title", "-t", help="Title of the decision"),
    context: str = typer.Option(..., "--context", "-x", help="Context or problem being addressed"),
    decision_text: str = typer.Option(..., "--decision", "-d", help="The decision details"),
    task_id: Optional[int] = typer.Option(None, "--task-id", "-k", help="Associated Task ID (optional)")
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

@decision_app.command("list")
def decision_list(
    task_id: Optional[int] = typer.Option(None, "--task-id", "-k", help="Filter by Task ID"),
    project_only: bool = typer.Option(False, "--project-only", "-p", help="Filter for project-level decisions only")
):
    """List decisions."""
    with get_session() as session:
        decisions = crud.get_decisions(session, task_id=task_id, project_only=project_only)
        if not decisions:
            console.print("[yellow]No decisions found.[/yellow]")
            return
            
        for d in decisions:
            t_str = f"Task #{d.task_id}" if d.task_id else "Project Level"
            panel_content = (
                f"[bold]Title:[/bold] {d.title}\n"
                f"[bold]Author:[/bold] {d.author}  |  [bold]Date:[/bold] {format_datetime(d.created_at)}\n"
                f"[bold]Context:[/bold] {d.context}\n"
                f"[bold]Decision:[/bold] {d.decision}"
            )
            console.print(Panel(panel_content, title=t_str, border_style="magenta"))

# --- Memory Commands ---

@memory_app.command("add")
def memory_add(
    key: str = typer.Argument(..., help="Key for the memory"),
    value: str = typer.Argument(..., help="Value / content of the memory")
):
    """Store or update a project memory."""
    with get_session() as session:
        crud.add_memory(session, key, value)
        console.print(f"[green]Memory [bold]{key}[/bold] stored successfully.[/green]")

@memory_app.command("list")
def memory_list():
    """List all project memories."""
    with get_session() as session:
        memories = crud.list_memories(session)
        if not memories:
            console.print("[yellow]No memories stored yet.[/yellow]")
            return
            
        table = Table(title="Hive Project Memories", show_header=True, header_style="bold magenta")
        table.add_column("Key", style="bold cyan")
        table.add_column("Value", style="white")
        table.add_column("Updated At", style="dim", width=20)
        
        for m in memories:
            table.add_row(m.key, m.value, format_datetime(m.updated_at))
        console.print(table)

# --- Project Commands ---

@project_app.command("show")
def project_show():
    """Show project metadata and general statistics."""
    with get_session() as session:
        project = crud.get_project(session)
        tasks = crud.list_tasks(session)
        
        # Calculate stats
        total_tasks = len(tasks)
        todo_count = sum(1 for t in tasks if t.status == "todo")
        in_progress_count = sum(1 for t in tasks if t.status == "in_progress")
        review_count = sum(1 for t in tasks if t.status == "review")
        done_count = sum(1 for t in tasks if t.status == "done")
        
        avg_progress = 0
        if total_tasks > 0:
            avg_progress = int(sum(t.progress for t in tasks) / total_tasks)
            
        assignees = {t.assignee for t in tasks if t.assignee}
        
        # Print Project Info
        console.print(Panel(
            f"[bold cyan]Name:[/bold cyan] {project.name}\n"
            f"[bold cyan]Details:[/bold cyan] {project.details or 'No details.'}\n"
            f"[bold cyan]Overall Idea:[/bold cyan] {project.overall_idea or 'No overall idea.'}\n"
            f"[bold cyan]Last Updated:[/bold cyan] {format_datetime(project.updated_at)}",
            title="Hive Project Metadata",
            border_style="magenta"
        ))
        
        # Print Stats Info
        stats_table = Table(title="Task Statistics", show_header=True, header_style="bold green")
        stats_table.add_column("Metric", style="bold")
        stats_table.add_column("Value", style="white")
        
        stats_table.add_row("Total Tasks", str(total_tasks))
        stats_table.add_row("Todo", str(todo_count))
        stats_table.add_row("In Progress", str(in_progress_count))
        stats_table.add_row("Review", str(review_count))
        stats_table.add_row("Done", str(done_count))
        stats_table.add_row("Average Progress", f"{avg_progress}%")
        stats_table.add_row("Active Team Members", str(len(assignees)))
        
        console.print(stats_table)

@project_app.command("update")
def project_update(
    name: Optional[str] = typer.Option(None, "--name", help="Project name"),
    details: Optional[str] = typer.Option(None, "--details", help="Project details / description"),
    overall_idea: Optional[str] = typer.Option(None, "--idea", help="Project overall goal or idea")
):
    """Update project metadata."""
    if name is None and details is None and overall_idea is None:
        console.print("[yellow]No updates specified. Use --name, --details, or --idea.[/yellow]")
        return
        
    with get_session() as session:
        crud.update_project(session, name=name, details=details, overall_idea=overall_idea)
        console.print("[green]Project updated successfully.[/green]")

# --- Interactive TUI Launcher ---

@app.command("tui")
def launch_tui():
    """Launch the interactive TUI dashboard."""
    from hive.tui import HiveTUIApp
    # Ensure db path exists before launching TUI
    db_path = get_db_path()
    if not db_path.exists():
        init_db()
    
    # We run the Textual App
    app_tui = HiveTUIApp()
    app_tui.run()

if __name__ == "__main__":
    app()
