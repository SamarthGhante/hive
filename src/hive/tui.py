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

from hive.database import get_engine, get_session
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
        height: 70%;
        border: solid #2d2d2d;
        padding: 1;
        background: #1e1e1e;
        overflow-y: scroll;
    }
    
    .comment-input-box {
        height: 25%;
        margin-top: 1;
    }
    
    .decision-list {
        height: 60%;
        border: solid #2d2d2d;
        padding: 1;
        background: #1e1e1e;
        overflow-y: scroll;
    }
    
    .decision-form {
        height: 38%;
        margin-top: 1;
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
        yield Container(
            # Left Column
            Vertical(
                Label("📋 Tasks", classes="section-title"),
                DataTable(id="task-table"),
                Vertical(
                    Label("[bold]Quick Create Task[/bold] (Enter Title)"),
                    Input(placeholder="Type task title and press Enter...", id="new-task-title"),
                    id="new-task-form"
                ),
                id="left-pane"
            ),
            # Right Column
            Vertical(
                TabbedContent(
                    TabPane("Details", 
                        Vertical(
                            Static(id="details-view"),
                            Horizontal(
                                Button("Claim Task (c)", id="btn-claim", variant="primary", classes="action-btn"),
                                Button("Cycle Status (s)", id="btn-status", variant="secondary", classes="action-btn"),
                                Button("Complete Task", id="btn-complete", variant="success", classes="action-btn"),
                                id="details-actions"
                            )
                        )
                    ),
                    TabPane("Comments", 
                        Vertical(
                            Static(id="comments-list", classes="comment-list"),
                            Vertical(
                                Label("Add Comment:"),
                                Input(placeholder="Type comment and press Enter...", id="new-comment-input"),
                                classes="comment-input-box"
                            )
                        )
                    ),
                    TabPane("Decisions", 
                        Vertical(
                            Static(id="decisions-list", classes="decision-list"),
                            Vertical(
                                Label("[bold]Record Decision[/bold]"),
                                Input(placeholder="Decision Title...", id="dec-title"),
                                Input(placeholder="Context/Reasoning...", id="dec-context"),
                                Input(placeholder="Resolution/Decision details... (Press Enter to save)", id="dec-text"),
                                classes="decision-form"
                            )
                        )
                    ),
                    TabPane("Activity Feed", 
                        RichLog(id="feed-log", highlight=True, markup=True)
                    ),
                    id="tabs"
                ),
                id="right-pane"
            ),
            id="main-container"
        )
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
        
        # Save cursor position or selected row if possible
        prev_selected_id = self.selected_task_id
        
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
        
        # Reselect previous if still exists
        if prev_selected_id:
            try:
                table.move_cursor(row=table.find_row(str(prev_selected_id)))
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
        
        if not self.selected_task_id:
            details_box.update(Panel("No task selected. Select a task on the left or create a new one.", title="Details"))
            comments_box.update("Select a task to view comments.")
            decisions_box.update("Select a task to view decisions.")
            return

        with get_session() as session:
            task = crud.get_task(session, self.selected_task_id)
            if not task:
                details_box.update(Panel("Selected task not found.", title="Error"))
                return
                
            # Details panel
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
            
            # Decisions
            decisions = crud.get_decisions(session, self.selected_task_id)
            decision_content = []
            for d in decisions:
                decision_content.append(f"[bold magenta]{d.title}[/bold magenta] by @{d.author} ({format_datetime(d.created_at)})\n[italic]Context:[/italic] {d.context}\n[bold]Decision:[/bold] {d.decision}\n---")
            if not decision_content:
                decision_content.append("No decisions recorded for this task.")
            decisions_box.update("\n".join(decision_content))

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
            if not self.selected_task_id:
                self.notify("No task selected.")
                return
            title = self.query_one("#dec-title", Input).value.strip()
            context = self.query_one("#dec-context", Input).value.strip()
            decision = event.value.strip()
            
            if not title or not decision:
                self.notify("Decision Title and Details are required.")
                return
                
            actor = get_current_actor()
            with get_session() as session:
                crud.add_decision(session, self.selected_task_id, title, context, decision, actor)
                
            self.query_one("#dec-title", Input).value = ""
            self.query_one("#dec-context", Input).value = ""
            event.input.value = ""
            self.update_details_view()
            self.refresh_feed()
            self.notify("Recorded decision.")

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
