from datetime import datetime
from typing import Optional

from sqlmodel import Session, select
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header, Footer, Static, DataTable, TabbedContent, TabPane, 
    Button, Input, Label, RichLog
)
from textual.reactive import reactive
from textual.message import Message
from rich.panel import Panel
from rich.text import Text

from hive.database import get_engine, get_session, find_project_root
import hive.crud as crud
from hive.models import Task
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
        background: #1e1e1e;
        color: #d4d4d4;
    }
    
    #main-container {
        layout: grid;
        grid-size: 2;
        grid-columns: 45% 55%;
        height: 100%;
        padding: 1;
    }
    
    #left-pane {
        border: solid #3c3c3c;
        padding: 1;
        height: 100%;
    }
    
    #right-pane {
        border: solid #3c3c3c;
        padding: 1;
        height: 100%;
    }
    
    .section-title {
        text-style: bold;
        color: #007acc;
        margin-bottom: 1;
    }
    
    #task-table {
        height: 70%;
        border: tall #2d2d2d;
    }
    
    #new-task-form {
        height: 25%;
        border-top: solid #3c3c3c;
        padding-top: 1;
        margin-top: 1;
        layout: vertical;
    }
    
    .input-field {
        margin-bottom: 1;
    }
    
    #details-view {
        padding: 1;
        background: #252526;
        border: solid #3c3c3c;
        height: 70%;
        margin-bottom: 1;
    }
    
    #details-actions {
        layout: horizontal;
        height: 20%;
        align: center middle;
    }
    
    .action-btn {
        margin: 0 1;
    }
    
    .comment-list {
        height: 1fr;
        border: solid #2d2d2d;
        padding: 1;
        background: #1e1e1e;
        overflow-y: scroll;
        margin-bottom: 1;
    }
    
    .comment-input-box {
        height: 6;
        border-top: solid #3c3c3c;
        padding-top: 1;
    }
    
    .decision-list {
        height: 1fr;
        border: solid #2d2d2d;
        padding: 1;
        background: #1e1e1e;
        overflow-y: scroll;
        margin-bottom: 1;
    }
    
    .decision-form {
        height: 11;
        border-top: solid #3c3c3c;
        padding-top: 1;
    }
    
    .memory-list {
        height: 1fr;
        border: solid #2d2d2d;
        padding: 1;
        background: #1e1e1e;
        overflow-y: scroll;
        margin-bottom: 1;
    }
    
    .memory-form {
        height: 8;
        border-top: solid #3c3c3c;
        padding-top: 1;
    }
    
    #feed-log {
        height: 100%;
        background: #1e1e1e;
        border: solid #2d2d2d;
    }
    """

    selected_task_id = reactive(None)

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            # Left Column
            with Vertical(id="left-pane"):
                yield Label("📋 Tasks", classes="section-title")
                yield DataTable(id="task-table")
                with Vertical(id="new-task-form"):
                    yield Label("[bold]Quick Create Task[/bold] (Enter Title)")
                    yield Input(placeholder="Type task title and press Enter...", id="new-task-title")
            
            # Right Column
            with Vertical(id="right-pane"):
                with TabbedContent(id="tabs"):
                    with TabPane("Details"):
                        yield Static(id="details-view")
                        with Horizontal(id="details-actions"):
                            yield Button("Claim Task (c)", id="btn-claim", variant="primary", classes="action-btn")
                            yield Button("Cycle Status (s)", id="btn-status", variant="default", classes="action-btn")
                            yield Button("Complete Task", id="btn-complete", variant="success", classes="action-btn")
                    
                    with TabPane("Comments"):
                        yield Static(id="comments-list", classes="comment-list")
                        with Vertical(classes="comment-input-box"):
                            yield Label("Add Comment:")
                            yield Input(placeholder="Type comment and press Enter...", id="new-comment-input")
                    
                    with TabPane("Decisions"):
                        yield Static(id="decisions-list", classes="decision-list")
                        with Vertical(classes="decision-form"):
                            yield Label("[bold]Record Decision[/bold]")
                            yield Input(placeholder="Decision Title...", id="dec-title")
                            yield Input(placeholder="Context/Reasoning...", id="dec-context")
                            yield Input(placeholder="Resolution/Decision details... (Press Enter to save)", id="dec-text")
                    
                    with TabPane("Memories"):
                        yield Static(id="memories-list", classes="memory-list")
                        with Vertical(classes="memory-form"):
                            yield Label("[bold]Add/Update Project Memory[/bold]")
                            yield Input(placeholder="Memory Key...", id="mem-key")
                            yield Input(placeholder="Memory Value... (Press Enter to save)", id="mem-val")
                    
                    with TabPane("Activity Feed"):
                        yield RichLog(id="feed-log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#task-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Title", "Status", "Priority", "Progress", "Assignee")
        self.refresh_tasks()
        self.refresh_feed()

    def refresh_tasks(self) -> None:
        table = self.query_one("#task-table", DataTable)
        table.clear()
        
        prev_selected_id = self.selected_task_id
        tasks = []
        
        with get_session() as session:
            tasks = crud.list_tasks(session)
            for t in tasks:
                status_str = format_status(t.status)
                priority_str = format_priority(t.priority)
                table.add_row(
                    f"#{t.id}",
                    t.title,
                    status_str,
                    priority_str,
                    f"{t.progress}%",
                    t.assignee or "-",
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

    def refresh_feed(self) -> None:
        log = self.query_one("#feed-log", RichLog)
        log.clear()
        with get_session() as session:
            events = crud.get_events(session, limit=50)
            for e in reversed(events):
                time_str = format_datetime(e.created_at)
                task_part = f" [blue]#{e.task_id}[/blue]" if e.task_id else ""
                log.write(f"[{time_str}] [cyan]{e.actor}[/cyan] [bold green]{e.event_type.upper()}[/bold green]{task_part}: {e.details}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value
        if row_key:
            self.selected_task_id = int(row_key)
            self.update_details_view()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        row_key = event.row_key.value
        if row_key:
            self.selected_task_id = int(row_key)
            self.update_details_view()

    def update_details_view(self) -> None:
        details_box = self.query_one("#details-view", Static)
        comments_box = self.query_one("#comments-list", Static)
        decisions_box = self.query_one("#decisions-list", Static)
        memories_box = self.query_one("#memories-list", Static)
        
        # Always update memories (project-level)
        with get_session() as session:
            memories = crud.list_memories(session)
            memory_lines = []
            for m in memories:
                memory_lines.append(f"[bold cyan]{m.key}[/bold cyan]: {m.value} [dim]({format_datetime(m.updated_at)})[/dim]\n---")
            if not memory_lines:
                memory_lines.append("No project memories stored yet. Add one below.")
            memories_box.update("\n".join(memory_lines))
            
            if not self.selected_task_id:
                # If there are no tasks in the project at all
                details_box.update(Panel("No tasks found. Use the quick create input on the left to create a task.", title="Details"))
                comments_box.update("Create a task to view comments.")
                
                # Show project decisions
                decisions = crud.get_decisions(session, task_id=None)
                decision_content = []
                for d in decisions:
                    decision_content.append(f"[bold magenta]{d.title}[/bold magenta] by @{d.author} ({format_datetime(d.created_at)})\n[italic]Context:[/italic] {d.context}\n[bold]Decision:[/bold] {d.decision}\n---")
                if not decision_content:
                    decision_content.append("No decisions recorded yet.")
                decisions_box.update("\n".join(decision_content))
                
                # Disable buttons
                self.query_one("#btn-claim", Button).disabled = True
                self.query_one("#btn-status", Button).disabled = True
                self.query_one("#btn-complete", Button).disabled = True
                
            else:
                # Task selected -> show Task Details
                task = crud.get_task(session, self.selected_task_id)
                if not task:
                    details_box.update(Panel("Selected task not found.", title="Error"))
                    return
                    
                status_theme = {"todo": "grey", "in_progress": "blue", "review": "yellow", "done": "green"}.get(task.status, "white")
                prio_theme = {0: "red bold", 1: "red", 2: "yellow", 3: "blue", 4: "grey"}.get(task.priority, "white")
                
                details_text = Text.assemble(
                    ("Title: ", "bold"), f"{task.title}\n",
                    ("Description: ", "bold"), f"{task.description or 'No description'}\n\n",
                    ("Status: ", "bold"), (format_status(task.status), status_theme), "  |  ",
                    ("Priority: ", "bold"), (format_priority(task.priority), prio_theme), "  |  ",
                    ("Progress: ", "bold"), f"{task.progress}%\n",
                    ("Assignee: ", "bold"), ("@" + task.assignee if task.assignee else "Unassigned", "cyan"), "\n",
                    ("Created: ", "bold"), f"{format_datetime(task.created_at)}\n",
                    ("Updated: ", "bold"), f"{format_datetime(task.updated_at)}"
                )
                details_box.update(Panel(details_text, title=f"Task #{task.id}"))
                
                # Comments
                comments = crud.get_comments(session, self.selected_task_id)
                comment_content = []
                for c in comments:
                    comment_content.append(f"[bold cyan]@{c.author}[/bold cyan] ({format_datetime(c.created_at)}):\n{c.content}\n---")
                if not comment_content:
                    comment_content.append("No comments yet. Type below to add one.")
                comments_box.update("\n".join(comment_content))
                
                # Decisions: Task-level + Project-level (clearly labeled)
                task_decisions = crud.get_decisions(session, self.selected_task_id)
                project_decisions = crud.get_decisions(session, task_id=None)
                
                decision_content = []
                if task_decisions:
                    decision_content.append("[bold underline green]Task Decisions:[/bold underline green]")
                    for d in task_decisions:
                        decision_content.append(f"[bold magenta]{d.title}[/bold magenta] by @{d.author} ({format_datetime(d.created_at)})\n[italic]Context:[/italic] {d.context}\n[bold]Decision:[/bold] {d.decision}\n---")
                    decision_content.append("")
                
                if project_decisions:
                    decision_content.append("[bold underline blue]Project Level Decisions:[/bold underline blue]")
                    for d in project_decisions:
                        decision_content.append(f"[bold magenta]{d.title}[/bold magenta] by @{d.author} ({format_datetime(d.created_at)})\n[italic]Context:[/italic] {d.context}\n[bold]Decision:[/bold] {d.decision}\n---")
                        
                if not decision_content:
                    decision_content.append("No decisions recorded yet.")
                decisions_box.update("\n".join(decision_content))
                
                # Enable action buttons
                self.query_one("#btn-claim", Button).disabled = False
                self.query_one("#btn-status", Button).disabled = False
                self.query_one("#btn-complete", Button).disabled = False

    # --- Actions / Keyboard Event Handlers ---

    def action_refresh(self) -> None:
        self.refresh_tasks()
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
            with get_session() as session:
                crud.create_task(session, title=title)
            event.input.value = ""
            self.refresh_tasks()
            self.refresh_feed()
            self.notify("Created task successfully.")
            
        elif input_id == "new-comment-input":
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
            self.notify("Added comment.")
            
        elif input_id == "dec-text":
            title = self.query_one("#dec-title", Input).value.strip()
            context = self.query_one("#dec-context", Input).value.strip()
            decision = event.value.strip()
            
            if not title or not decision:
                self.notify("Decision Title and Details are required.")
                return
                
            actor = get_current_actor()
            with get_session() as session:
                task_id = self.selected_task_id if self.selected_task_id else None
                crud.add_decision(session, task_id, title, context, decision, actor)
                
            self.query_one("#dec-title", Input).value = ""
            self.query_one("#dec-context", Input).value = ""
            event.input.value = ""
            self.update_details_view()
            self.refresh_feed()
            self.notify("Recorded decision.")
            
        elif input_id == "mem-val":
            key = self.query_one("#mem-key", Input).value.strip()
            value = event.value.strip()
            
            if not key or not value:
                self.notify("Memory Key and Value are required.")
                return
                
            with get_session() as session:
                crud.add_memory(session, key, value)
                
            self.query_one("#mem-key", Input).value = ""
            event.input.value = ""
            self.update_details_view()
            self.refresh_feed()
            self.notify(f"Memory '{key}' saved successfully.")

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
