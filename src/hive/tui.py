from datetime import datetime
from typing import Optional

from sqlmodel import Session, select
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header, Footer, Static, DataTable, TabbedContent, TabPane, 
    Button, Input, Label, RichLog
)
from textual.reactive import reactive
from rich.panel import Panel
from rich.text import Text

from hive.database import get_session
import hive.crud as crud
from hive.models import Task, Project
from hive.utils import get_current_actor, format_priority, format_status, format_datetime

class HiveTUIApp(App):
    TITLE = "Hive Coordination Dashboard"
    SUBTITLE = "Collaborative Execution Layer"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh All"),
        ("c", "claim_selected", "Claim Task"),
        ("s", "cycle_status", "Cycle Status"),
        ("n", "focus_new_task", "New Task Input"),
    ]

    CSS = """
    Screen {
        background: #020617;
        color: #f8fafc;
    }
    
    TabbedContent {
        background: #020617;
    }
    
    Tabs {
        background: #0b0f19;
        border-bottom: solid #1e293b;
    }
    
    Tab {
        color: #64748b;
        font-weight: bold;
    }
    
    Tab:hover {
        background: #1e293b;
        color: #38bdf8;
    }
    
    Tab.--active {
        color: #38bdf8;
        background: #0f172a;
        border-bottom: solid #38bdf8 2;
    }
    
    .pane-container {
        layout: grid;
        grid-size: 2;
        grid-columns: 40% 60%;
        height: 100%;
        padding: 0;
        margin: 0;
    }
    
    .tui-column {
        border: solid #1e293b;
        padding: 1;
        margin: 1;
        background: #0b0f19;
        border-radius: 4;
    }
    
    .section-title {
        text-style: bold;
        color: #38bdf8;
        margin-bottom: 1;
        border-bottom: double #334155;
    }
    
    #task-table {
        height: 1fr;
        border: solid #1e293b;
        background: #020617;
    }
    
    DataTable > .datatable--header {
        background: #0f172a;
        color: #38bdf8;
        text-style: bold;
    }
    
    DataTable > .datatable--cursor {
        background: #2563eb;
        color: #ffffff;
    }
    
    #new-task-form, #project-update-form {
        height: auto;
        border-top: solid #1e293b;
        padding-top: 1;
        margin-top: 1;
        layout: vertical;
        background: #0f172a;
        border-radius: 4;
        padding: 1;
    }
    
    .input-field {
        margin-bottom: 1;
    }
    
    Input {
        background: #020617;
        border: tall #334155;
        color: #f8fafc;
        margin-bottom: 1;
    }
    
    Input:focus {
        border: tall #38bdf8;
    }
    
    .scrollable-pane {
        height: 1fr;
        border: solid #1e293b;
        padding: 1;
        background: #020617;
        margin-bottom: 1;
        border-radius: 4;
    }
    
    .scrollable-pane > Static {
        height: auto;
    }
    
    #details-view, #project-info-view {
        padding: 1;
        background: #020617;
        border: none;
        height: auto;
    }
    
    #details-actions {
        layout: horizontal;
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    
    .action-btn {
        margin: 0 1;
        min-width: 16;
    }
    
    .input-box-pane {
        height: auto;
        border-top: solid #1e293b;
        padding-top: 1;
        background: #0f172a;
        padding: 1;
        border-radius: 4;
    }
    
    #task-feed-log, #project-feed-log {
        height: 1fr;
        background: #020617;
        border: solid #1e293b;
        border-radius: 4;
        padding: 1;
    }
    
    Button {
        background: #1e293b;
        color: #e2e8f0;
        border: none;
        height: 3;
    }
    
    Button:hover {
        background: #334155;
    }
    
    Button.-active {
        background: #2563eb;
    }
    
    #btn-claim {
        background: #0f766e;
        color: #ffffff;
    }
    
    #btn-claim:hover {
        background: #0d9488;
    }
    
    #btn-status {
        background: #1e293b;
        color: #e2e8f0;
    }
    
    #btn-status:hover {
        background: #334155;
    }
    
    #btn-complete {
        background: #166534;
        color: #ffffff;
    }
    
    #btn-complete:hover {
        background: #15803d;
    }
    """

    selected_task_id = reactive(None)

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(id="top-tabs"):
            with TabPane("Task Board", id="tab-task-board"):
                with Container(classes="pane-container"):
                    # Left Column
                    with Vertical(id="left-pane", classes="tui-column"):
                        yield Label("📋 Tasks", classes="section-title")
                        yield DataTable(id="task-table")
                        with Vertical(id="new-task-form"):
                            yield Label("[bold cyan]Quick Create Task[/bold cyan]")
                            yield Input(placeholder="Task Title...", id="new-task-title")
                            yield Input(placeholder="Task Description... (Press Enter to save)", id="new-task-desc")
                    
                    # Right Column
                    with Vertical(id="right-pane", classes="tui-column"):
                        with TabbedContent(id="task-tabs"):
                            with TabPane("Task Details"):
                                with VerticalScroll(classes="scrollable-pane"):
                                    yield Static(id="details-view")
                                with Horizontal(id="details-actions"):
                                    yield Button("Claim Task (c)", id="btn-claim", variant="primary", classes="action-btn")
                                    yield Button("Cycle Status (s)", id="btn-status", variant="default", classes="action-btn")
                                    yield Button("Complete Task", id="btn-complete", variant="success", classes="action-btn")
                            
                            with TabPane("Task Comments"):
                                with VerticalScroll(classes="scrollable-pane"):
                                    yield Static(id="task-comments-list")
                                with Vertical(classes="input-box-pane"):
                                    yield Label("[bold cyan]Add Task Comment:[/bold cyan]")
                                    yield Input(placeholder="Type comment and press Enter...", id="new-task-comment-input")
                            
                            with TabPane("Task Decisions"):
                                with VerticalScroll(classes="scrollable-pane"):
                                    yield Static(id="task-decisions-list")
                                with Vertical(classes="input-box-pane"):
                                    yield Label("[bold cyan]Record Task Decision[/bold cyan]")
                                    yield Input(placeholder="Decision Title...", id="task-dec-title")
                                    yield Input(placeholder="Context/Reasoning...", id="task-dec-context")
                                    yield Input(placeholder="Resolution/Decision details... (Press Enter to save)", id="task-dec-text")
                            
                            with TabPane("Task Activity"):
                                yield RichLog(id="task-feed-log", highlight=True, markup=True)
                                
            with TabPane("Project Hub", id="tab-project-hub"):
                with Container(classes="pane-container"):
                    # Left Column
                    with Vertical(id="project-left-pane", classes="tui-column"):
                        yield Label("🏢 Project Info", classes="section-title")
                        with VerticalScroll(classes="scrollable-pane"):
                            yield Static(id="project-info-view")
                        with Vertical(id="project-update-form"):
                            yield Label("[bold cyan]Update Project Info[/bold cyan]")
                            yield Input(placeholder="Project Name...", id="project-name-input")
                            yield Input(placeholder="Project Details...", id="project-details-input")
                            yield Input(placeholder="Overall Idea... (Press Enter to update)", id="project-idea-input")
                    
                    # Right Column
                    with Vertical(id="project-right-pane", classes="tui-column"):
                        with TabbedContent(id="project-tabs"):
                            with TabPane("Project Comments"):
                                with VerticalScroll(classes="scrollable-pane"):
                                    yield Static(id="project-comments-list")
                                with Vertical(classes="input-box-pane"):
                                    yield Label("[bold cyan]Add Project Comment:[/bold cyan]")
                                    yield Input(placeholder="Type comment and press Enter...", id="new-project-comment-input")
                            
                            with TabPane("Project Decisions"):
                                with VerticalScroll(classes="scrollable-pane"):
                                    yield Static(id="project-decisions-list")
                                with Vertical(classes="input-box-pane"):
                                    yield Label("[bold cyan]Record Project Decision[/bold cyan]")
                                    yield Input(placeholder="Decision Title...", id="project-dec-title")
                                    yield Input(placeholder="Context/Reasoning...", id="project-dec-context")
                                    yield Input(placeholder="Resolution/Decision details... (Press Enter to save)", id="project-dec-text")
                            
                            with TabPane("Project Memories"):
                                with VerticalScroll(classes="scrollable-pane"):
                                    yield Static(id="project-memories-list")
                                with Vertical(classes="input-box-pane"):
                                    yield Label("[bold cyan]Add/Update Project Memory[/bold cyan]")
                                    yield Input(placeholder="Memory Key...", id="project-mem-key")
                                    yield Input(placeholder="Memory Value... (Press Enter to save)", id="project-mem-val")
                                    
                            with TabPane("Project Activity"):
                                yield RichLog(id="project-feed-log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#task-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Title", "Status", "Priority", "Progress", "Assignee")
        self.refresh_tasks()
        self.update_project_view()
        self.refresh_feed()

    def refresh_tasks(self) -> None:
        table = self.query_one("#task-table", DataTable)
        table.clear()
        
        prev_selected_id = self.selected_task_id
        tasks = []
        
        with get_session() as session:
            tasks = crud.list_tasks(session)
            for t in tasks:
                status_color = {"todo": "gray", "in_progress": "blue", "review": "yellow", "done": "green"}.get(t.status.lower(), "white")
                status_str = f"[{status_color}]{format_status(t.status)}[/{status_color}]"
                
                prio_color = {0: "bold red", 1: "red", 2: "yellow", 3: "blue", 4: "gray"}.get(t.priority, "white")
                priority_str = f"[{prio_color}]{format_priority(t.priority)}[/{prio_color}]"
                
                assignee_str = f"[cyan]@{t.assignee}[/cyan]" if t.assignee else "[dim]-[/dim]"
                id_str = f"[bold white]#{t.id}[/bold white]"
                title_str = f"[strike dim]{t.title}[/strike dim]" if t.status.lower() == "done" else t.title
                
                progress_color = "green" if t.progress == 100 else "blue" if t.progress > 0 else "gray"
                progress_str = f"[{progress_color}]{t.progress}%[/{progress_color}]"
                
                table.add_row(
                    id_str,
                    title_str,
                    status_str,
                    priority_str,
                    progress_str,
                    assignee_str,
                    key=str(t.id)
                )
        
        # Reselect previous if still exists, otherwise default to first task
        if prev_selected_id:
            try:
                table.move_cursor(row=table.find_row(str(prev_selected_id)))
            except Exception:
                pass
        else:
            if tasks:
                try:
                    table.move_cursor(row=0)
                    self.selected_task_id = tasks[0].id
                except Exception:
                    pass
        
        # Trigger details refresh
        self.update_details_view()
        self.update_project_view()

    def refresh_feed(self) -> None:
        # 1. Update Project Feed Log (unfiltered)
        project_log = self.query_one("#project-feed-log", RichLog)
        project_log.clear()
        with get_session() as session:
            project_events = crud.get_events(session, limit=50)
            for e in reversed(project_events):
                time_str = format_datetime(e.created_at)
                task_part = f" [blue]#{e.task_id}[/blue]" if e.task_id else ""
                project_log.write(f"[{time_str}] [cyan]{e.actor}[/cyan] [bold green]{e.event_type.upper()}[/bold green]{task_part}: {e.details}")
                
        # 2. Update Task Feed Log (filtered by selected task)
        task_log = self.query_one("#task-feed-log", RichLog)
        task_log.clear()
        if self.selected_task_id:
            with get_session() as session:
                task_events = crud.get_events(session, task_id=self.selected_task_id, limit=50)
                for e in reversed(task_events):
                    time_str = format_datetime(e.created_at)
                    task_log.write(f"[{time_str}] [cyan]{e.actor}[/cyan] [bold green]{e.event_type.upper()}[/bold green]: {e.details}")
        else:
            task_log.write("No task selected.")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value
        if row_key:
            self.selected_task_id = int(row_key)
            self.update_details_view()
            self.refresh_feed()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        row_key = event.row_key.value
        if row_key:
            self.selected_task_id = int(row_key)
            self.update_details_view()
            self.refresh_feed()

    def update_details_view(self) -> None:
        details_box = self.query_one("#details-view", Static)
        comments_box = self.query_one("#task-comments-list", Static)
        decisions_box = self.query_one("#task-decisions-list", Static)
        
        with get_session() as session:
            if not self.selected_task_id:
                details_box.update(Panel("No tasks found. Use the quick create input on the left to create a task.", title="Details"))
                comments_box.update("[italic dim]Create a task to view comments.[/italic dim]")
                decisions_box.update("[italic dim]No task selected.[/italic dim]")
                
                self.query_one("#btn-claim", Button).disabled = True
                self.query_one("#btn-status", Button).disabled = True
                self.query_one("#btn-complete", Button).disabled = True
            else:
                task = crud.get_task(session, self.selected_task_id)
                if not task:
                    details_box.update(Panel("Selected task not found.", title="Error"))
                    return
                    
                status_theme = {"todo": "gray", "in_progress": "blue", "review": "yellow", "done": "green"}.get(task.status, "white")
                prio_theme = {0: "bold red", 1: "red", 2: "yellow", 3: "blue", 4: "gray"}.get(task.priority, "white")
                
                details_text = Text.assemble(
                    ("Title: ", "bold cyan"), f"{task.title}\n",
                    ("Description: ", "bold cyan"), f"{task.description or 'No description'}\n\n",
                    ("Status: ", "bold cyan"), (format_status(task.status), status_theme), "  |  ",
                    ("Priority: ", "bold cyan"), (format_priority(task.priority), prio_theme), "  |  ",
                    ("Progress: ", "bold cyan"), f"{task.progress}%\n",
                    ("Assignee: ", "bold cyan"), ("@" + task.assignee if task.assignee else "Unassigned", "green"), "\n",
                    ("Created: ", "bold cyan"), f"{format_datetime(task.created_at)}\n",
                    ("Updated: ", "bold cyan"), f"{format_datetime(task.updated_at)}"
                )
                details_box.update(Panel(details_text, title=f"Task #{task.id}", border_style="cyan"))
                
                # Comments
                comments = crud.get_comments(session, self.selected_task_id)
                comment_content = []
                for c in comments:
                    comment_content.append(f"[bold cyan]@{c.author}[/bold cyan] [dim]({format_datetime(c.created_at)})[/dim]\n{c.content}\n[dim]──────────────────────────────────────────────────[/dim]")
                if not comment_content:
                    comment_content.append("[italic dim]No comments yet. Type below and press Enter to add one.[/italic dim]")
                comments_box.update("\n".join(comment_content))
                
                # Decisions: Task-level decisions only
                task_decisions = crud.get_decisions(session, self.selected_task_id)
                decision_content = []
                if task_decisions:
                    decision_content.append("[bold underline green]Task Decisions:[/bold underline green]")
                    for d in task_decisions:
                        decision_content.append(
                            f"[bold magenta]⚡ {d.title}[/bold magenta] [dim]by @{d.author} ({format_datetime(d.created_at)})[/dim]\n"
                            f"[italic cyan]Context:[/italic cyan] {d.context}\n"
                            f"[bold green]Decision:[/bold green] {d.decision}\n"
                            f"[dim]──────────────────────────────────────────────────[/dim]"
                        )
                if not decision_content:
                    decision_content.append("[italic dim]No decisions recorded for this task yet.[/italic dim]")
                decisions_box.update("\n".join(decision_content))
                
                # Enable action buttons
                self.query_one("#btn-claim", Button).disabled = False
                self.query_one("#btn-status", Button).disabled = False
                self.query_one("#btn-complete", Button).disabled = False

    def update_project_view(self) -> None:
        info_box = self.query_one("#project-info-view", Static)
        comments_box = self.query_one("#project-comments-list", Static)
        decisions_box = self.query_one("#project-decisions-list", Static)
        memories_box = self.query_one("#project-memories-list", Static)
        
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
            
            info_text = Text.assemble(
                ("Project Name: ", "bold yellow"), f"{project.name}\n\n",
                ("Details: ", "bold yellow"), f"{project.details or 'No details.'}\n\n",
                ("Overall Idea: ", "bold yellow"), f"{project.overall_idea or 'No overall idea.'}\n\n",
                ("Last Updated: ", "bold yellow"), f"{format_datetime(project.updated_at)}\n\n",
                ("┌" + "─" * 40 + "┐\n", "bold magenta"),
                ("│            TASK STATISTICS             │\n", "bold magenta"),
                ("├" + "─" * 40 + "┤\n", "bold magenta"),
                ("│  Total Tasks: ", "bold"), f"{total_tasks:<25}│\n",
                ("│  Todo: ", "bold"), f"{todo_count:<32}│\n",
                ("│  In Progress: ", "bold"), f"{in_progress_count:<25}│\n",
                ("│  Review: ", "bold"), f"{review_count:<30}│\n",
                ("│  Done: ", "bold"), f"{done_count:<32}│\n",
                ("│  Average Progress: ", "bold"), f"{f'{avg_progress}%':<20}│\n",
                ("│  Active Team Members: ", "bold"), f"{len(assignees):<17}│\n",
                ("└" + "─" * 40 + "┘", "bold magenta")
            )
            info_box.update(Panel(info_text, title="Project Hub Status", border_style="yellow"))
            
            # Populate form inputs with current values if they are empty
            name_input = self.query_one("#project-name-input", Input)
            details_input = self.query_one("#project-details-input", Input)
            idea_input = self.query_one("#project-idea-input", Input)
            if not name_input.value:
                name_input.value = project.name
            if not details_input.value:
                details_input.value = project.details or ""
            if not idea_input.value:
                idea_input.value = project.overall_idea or ""
            
            # Project comments
            comments = crud.get_comments(session, task_id=None)
            comment_content = []
            for c in comments:
                comment_content.append(f"[bold cyan]@{c.author}[/bold cyan] [dim]({format_datetime(c.created_at)})[/dim]\n{c.content}\n[dim]──────────────────────────────────────────────────[/dim]")
            if not comment_content:
                comment_content.append("[italic dim]No project comments yet. Type below to add one.[/italic dim]")
            comments_box.update("\n".join(comment_content))
            
            # Project decisions
            decisions = crud.get_decisions(session, project_only=True)
            decision_content = []
            for d in decisions:
                decision_content.append(
                    f"[bold magenta]⚡ {d.title}[/bold magenta] [dim]by @{d.author} ({format_datetime(d.created_at)})[/dim]\n"
                    f"[italic cyan]Context:[/italic cyan] {d.context}\n"
                    f"[bold green]Decision:[/bold green] {d.decision}\n"
                    f"[dim]──────────────────────────────────────────────────[/dim]"
                )
            if not decision_content:
                decision_content.append("[italic dim]No project decisions recorded yet. Record one below.[/italic dim]")
            decisions_box.update("\n".join(decision_content))
            
            # Project memories
            memories = crud.list_memories(session)
            memory_lines = []
            for m in memories:
                memory_lines.append(f"[bold yellow]🧠 {m.key}[/bold yellow] = {m.value} [dim]({format_datetime(m.updated_at)})[/dim]\n[dim]──────────────────────────────────────────────────[/dim]")
            if not memory_lines:
                memory_lines.append("[italic dim]No project memories stored yet. Add one below.[/italic dim]")
            memories_box.update("\n".join(memory_lines))

    # --- Actions / Keyboard Event Handlers ---

    def action_refresh(self) -> None:
        self.refresh_tasks()
        self.update_project_view()
        self.refresh_feed()
        self.notify("Refreshed all data.")

    def action_claim_selected(self) -> None:
        if not self.selected_task_id:
            self.notify("No task selected to claim.")
            return
        actor = get_current_actor()
        with get_session() as session:
            crud.claim_task(session, self.selected_task_id, actor)
        self.refresh_tasks()
        self.refresh_feed()
        self.notify(f"Claimed task #{self.selected_task_id}")

    def action_cycle_status(self) -> None:
        if not self.selected_task_id:
            self.notify("No task selected.")
            return
            
        status_flow = ["todo", "in_progress", "review", "done"]
        with get_session() as session:
            task = crud.get_task(session, self.selected_task_id)
            if task:
                next_index = (status_flow.index(task.status.lower()) + 1) % len(status_flow)
                next_status = status_flow[next_index]
                progress = task.progress
                if next_status == "done":
                    progress = 100
                elif next_status == "todo":
                    progress = 0
                crud.update_task(session, self.selected_task_id, status=next_status, progress=progress)
        self.refresh_tasks()
        self.refresh_feed()
        self.notify(f"Updated status of task #{self.selected_task_id}")

    def action_focus_new_task(self) -> None:
        self.query_one("#new-task-title", Input).focus()

    # --- Widget Event Handlers ---

    def on_input_submitted(self, event: Input.Submitted) -> None:
        input_id = event.input.id
        
        if input_id == "new-task-title":
            title = event.value.strip()
            if not title:
                return
            self.query_one("#new-task-desc", Input).focus()
            
        elif input_id == "new-task-desc":
            title = self.query_one("#new-task-title", Input).value.strip()
            desc = event.value.strip()
            if not title:
                self.notify("Task Title is required.")
                return
            with get_session() as session:
                crud.create_task(session, title=title, description=desc if desc else None)
            
            self.query_one("#new-task-title", Input).value = ""
            event.input.value = ""
            self.refresh_tasks()
            self.refresh_feed()
            self.notify("Created task successfully.")
            
        elif input_id == "new-task-comment-input":
            if not self.selected_task_id:
                self.notify("No task selected.")
                return
            content = event.value.strip()
            if not content:
                return
            actor = get_current_actor()
            with get_session() as session:
                crud.add_comment(session, self.selected_task_id, actor, content)
            event.input.value = ""
            self.update_details_view()
            self.refresh_feed()
            self.notify("Added task comment.")
            
        elif input_id == "task-dec-text":
            title = self.query_one("#task-dec-title", Input).value.strip()
            context = self.query_one("#task-dec-context", Input).value.strip()
            decision = event.value.strip()
            
            if not title or not decision:
                self.notify("Decision Title and Details are required.")
                return
                
            actor = get_current_actor()
            with get_session() as session:
                crud.add_decision(session, self.selected_task_id, title, context, decision, actor)
                
            self.query_one("#task-dec-title", Input).value = ""
            self.query_one("#task-dec-context", Input).value = ""
            event.input.value = ""
            self.update_details_view()
            self.refresh_feed()
            self.notify("Recorded task decision.")
            
        elif input_id == "new-project-comment-input":
            content = event.value.strip()
            if not content:
                return
            actor = get_current_actor()
            with get_session() as session:
                crud.add_comment(session, None, actor, content)
            event.input.value = ""
            self.update_project_view()
            self.refresh_feed()
            self.notify("Added project comment.")
            
        elif input_id == "project-dec-text":
            title = self.query_one("#project-dec-title", Input).value.strip()
            context = self.query_one("#project-dec-context", Input).value.strip()
            decision = event.value.strip()
            
            if not title or not decision:
                self.notify("Decision Title and Details are required.")
                return
                
            actor = get_current_actor()
            with get_session() as session:
                crud.add_decision(session, None, title, context, decision, actor)
                
            self.query_one("#project-dec-title", Input).value = ""
            self.query_one("#project-dec-context", Input).value = ""
            event.input.value = ""
            self.update_project_view()
            self.refresh_feed()
            self.notify("Recorded project decision.")
            
        elif input_id == "project-mem-val":
            key = self.query_one("#project-mem-key", Input).value.strip()
            value = event.value.strip()
            
            if not key or not value:
                self.notify("Memory Key and Value are required.")
                return
                
            with get_session() as session:
                crud.add_memory(session, key, value)
                
            self.query_one("#project-mem-key", Input).value = ""
            event.input.value = ""
            self.update_project_view()
            self.refresh_feed()
            self.notify(f"Memory '{key}' saved successfully.")
            
        elif input_id in ("project-name-input", "project-details-input", "project-idea-input"):
            name = self.query_one("#project-name-input", Input).value.strip()
            details = self.query_one("#project-details-input", Input).value.strip()
            idea = self.query_one("#project-idea-input", Input).value.strip()
            
            with get_session() as session:
                crud.update_project(
                    session,
                    name=name if name else None,
                    details=details if details else None,
                    overall_idea=idea if idea else None
                )
            
            self.update_project_view()
            self.refresh_feed()
            self.notify("Updated project metadata.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        
        if btn_id == "btn-claim":
            self.action_claim_selected()
        elif btn_id == "btn-status":
            self.action_cycle_status()
        elif btn_id == "btn-complete":
            if not self.selected_task_id:
                self.notify("No task selected.")
                return
            with get_session() as session:
                crud.complete_task(session, self.selected_task_id)
            self.refresh_tasks()
            self.refresh_feed()
            self.notify(f"Completed task #{self.selected_task_id}")
