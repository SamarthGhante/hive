from datetime import datetime
from typing import Optional

from sqlmodel import Session, select
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header, Footer, Static, DataTable, TabbedContent, TabPane,
    Button, Input, Label, RichLog, ContentSwitcher, Tabs, Tab
)
from textual.reactive import reactive
from textual.events import Resize
from rich.panel import Panel
from rich.text import Text
from rich.console import Group
from rich.table import Table
from rich.rule import Rule

from hive.database import get_session
import hive.crud as crud
from hive.models import Task, Project
from hive.utils import get_current_actor, format_priority, format_status, format_datetime

class HiveTUIApp(App):
    TITLE = "Hive"
    SUBTITLE = None
    theme = "catppuccin-mocha"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh All"),
        ("c", "claim_selected", "Claim Task"),
        ("s", "cycle_status", "Cycle Status"),
        ("n", "focus_new_task", "New Task Input"),
        ("t", "switch_to_tasks", "Task Board"),
        ("p", "switch_to_project", "Project Hub"),
    ]

    CSS = """
    Screen {
        background: $background;
        color: $text;
    }

    Header {
        background: $surface;
        color: $text;
        dock: top;
    }

    Footer {
        background: $surface;
        color: $text-muted;
    }

    Static {
        color: $text;
    }

    Label {
        color: $text;
    }

    DataTable {
        color: $text;
    }

    RichLog {
        color: $text;
    }

    #app-container {
        layout: vertical;
        height: 1fr;
        width: 100%;
    }

    #nav-tabs {
        width: 100%;
        height: auto;
        background: $surface;
        dock: top;
    }

    #nav-tabs Tab {
        color: $text-muted;
        padding: 0 3;
        background: transparent;
    }

    #nav-tabs Tab:hover {
        color: $text;
        background: $panel;
    }

    #nav-tabs Tab.-active {
        color: $primary;
        text-style: bold;
        background: transparent;
    }

    #nav-stats {
        height: 1;
        color: $text-muted;
        content-align: right middle;
        width: 100%;
        padding: 0 1;
        background: $surface;
    }

    #main-content {
        width: 100%;
        height: 1fr;
        background: $background;
        padding: 1;
    }

    ContentSwitcher {
        height: 1fr;
        width: 100%;
    }

    .page-container {
        layout: horizontal;
        height: 100%;
        width: 100%;
        padding: 0;
        margin: 0;
    }

    .left-column {
        width: 45%;
        height: 100%;
        border: tall $panel;
        padding: 0 1;
        margin-right: 1;
        background: $surface;
    }

    .right-column {
        width: 55%;
        height: 100%;
        border: tall $panel;
        padding: 0 1;
        background: $surface;
    }

    .section-title {
        text-style: bold;
        color: $text-muted;
        padding: 0 0 1 0;
    }

    #task-table {
        height: 1fr;
        background: $background;
        border: tall $panel;
    }

    DataTable > .datatable--header {
        background: $surface;
        color: $text-muted;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: $primary 30%;
        color: $text;
        text-style: bold;
    }

    DataTable > .datatable--hover {
        background: $panel;
    }

    .form-container {
        height: auto;
        border-top: solid $panel;
        margin-top: 0;
        layout: vertical;
        background: $surface;
        padding: 1 0 0 0;
    }

    Input {
        background: $background;
        border: tall $panel;
        color: $text;
        margin: 0 0 1 0;
    }

    Input:focus {
        border: tall $primary;
    }

    TabbedContent {
        background: $surface;
        height: 1fr;
    }

    TabbedContent > Tabs {
        background: $surface;
        border-bottom: solid $panel;
    }

    TabbedContent > Tabs > Tab {
        color: $text-muted;
        background: transparent;
    }

    TabbedContent > Tabs > Tab:hover {
        background: $panel;
        color: $text;
    }

    TabbedContent > Tabs > Tab.--active {
        color: $primary;
        background: transparent;
        text-style: bold;
    }

    .scrollable-pane {
        height: 1fr;
        padding: 1;
        background: $background;
        border: tall $panel;
        margin: 0 0 1 0;
    }

    .scrollable-pane > Static {
        height: auto;
    }

    #details-view, #project-info-view {
        padding: 0;
        border: none;
        height: auto;
    }

    #details-actions {
        layout: horizontal;
        height: 3;
        align: center middle;
        margin-top: 0;
    }

    .action-btn {
        margin: 0 1;
        min-width: 14;
        height: 3;
    }

    .input-box-pane {
        height: auto;
        border-top: solid $panel;
        background: $surface;
        padding: 1 0 0 0;
    }

    #task-feed-log, #project-feed-log {
        height: 1fr;
        background: $background;
        border: tall $panel;
        padding: 0 1;
    }

    Button {
        background: $panel;
        color: $text;
        border: none;
        height: 3;
    }

    Button:hover {
        background: $primary 30%;
        color: $text;
    }

    Button.-active {
        background: $primary;
        color: $background;
    }

    #btn-claim {
        background: $panel;
        color: $text-muted;
    }

    #btn-claim:hover {
        background: $primary 30%;
        color: $text;
    }

    #btn-status {
        background: $panel;
        color: $text-muted;
    }

    #btn-status:hover {
        background: $primary 30%;
        color: $text;
    }

    #btn-complete {
        background: $success 30%;
        color: $text;
    }

    #btn-complete:hover {
        background: $success 50%;
        color: $text;
    }
    """

    selected_task_id = reactive(None)

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="app-container"):
            # Native Tabs navigation bar
            yield Tabs(
                Tab("Task Board", id="tab-tasks"),
                Tab("Project Hub", id="tab-project"),
                id="nav-tabs"
            )
            yield Static(id="nav-stats")

            # Bottom Main Content area
            with Vertical(id="main-content"):
                with ContentSwitcher(initial="pane-tasks", id="content-switcher"):
                    # Task Board pane
                    with Horizontal(id="pane-tasks", classes="page-container"):
                        # Left Column
                        with Vertical(id="left-pane", classes="left-column"):
                            yield Label("Tasks", classes="section-title")
                            yield DataTable(id="task-table")
                            with Vertical(id="new-task-form", classes="form-container"):
                                yield Label("Quick Create")
                                yield Input(placeholder="Task title...", id="new-task-title")
                                yield Input(placeholder="Description (Enter to save)", id="new-task-desc")

                        
                        # Right Column
                        with Vertical(id="right-pane", classes="right-column"):
                            with TabbedContent(id="task-tabs"):
                                with TabPane("Task Details"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="details-view")
                                    with Horizontal(id="details-actions"):
                                        yield Button("Claim (c)", id="btn-claim", classes="action-btn")
                                        yield Button("Status (s)", id="btn-status", classes="action-btn")
                                        yield Button("Complete", id="btn-complete", classes="action-btn")
                                
                                with TabPane("Task Comments"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="task-comments-list")
                                    with Vertical(classes="input-box-pane"):
                                        yield Label("Add Comment")
                                        yield Input(placeholder="Type comment, press Enter...", id="new-task-comment-input")
                                
                                with TabPane("Task Decisions"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="task-decisions-list")
                                    with Vertical(classes="input-box-pane"):
                                        yield Label("Record Decision")
                                        yield Input(placeholder="Title...", id="task-dec-title")
                                        yield Input(placeholder="Context...", id="task-dec-context")
                                        yield Input(placeholder="Decision (Enter to save)", id="task-dec-text")
                                
                                with TabPane("Task Activity"):
                                    yield RichLog(id="task-feed-log", highlight=True, markup=True)
                                    
                    # Project Hub pane
                    with Horizontal(id="pane-project", classes="page-container"):
                        # Left Column
                        with Vertical(id="project-left-pane", classes="left-column"):
                            yield Label("Project Info", classes="section-title")
                            with VerticalScroll(classes="scrollable-pane"):
                                yield Static(id="project-info-view")
                            with Vertical(id="project-update-form", classes="form-container"):
                                yield Label("Update Project")
                                yield Input(placeholder="Name...", id="project-name-input")
                                yield Input(placeholder="Details...", id="project-details-input")
                                yield Input(placeholder="Idea (Enter to update)", id="project-idea-input")
                        
                        # Right Column
                        with Vertical(id="project-right-pane", classes="right-column"):
                            with TabbedContent(id="project-tabs"):
                                with TabPane("Project Comments"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="project-comments-list")
                                    with Vertical(classes="input-box-pane"):
                                        yield Label("Add Comment")
                                        yield Input(placeholder="Type comment, press Enter...", id="new-project-comment-input")
                                
                                with TabPane("Project Decisions"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="project-decisions-list")
                                    with Vertical(classes="input-box-pane"):
                                        yield Label("Record Decision")
                                        yield Input(placeholder="Title...", id="project-dec-title")
                                        yield Input(placeholder="Context...", id="project-dec-context")
                                        yield Input(placeholder="Decision (Enter to save)", id="project-dec-text")
                                
                                with TabPane("Project Memories"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="project-memories-list")
                                    with Vertical(classes="input-box-pane"):
                                        yield Label("Add Memory")
                                        yield Input(placeholder="Key...", id="project-mem-key")
                                        yield Input(placeholder="Value (Enter to save)", id="project-mem-val")
                                        
                                with TabPane("Project Activity"):
                                    yield RichLog(id="project-feed-log", highlight=True, markup=True)
        yield Footer()

    def on_resize(self, event: Resize) -> None:
        is_narrow = event.size.width < 90
        
        # 1. Update page container layouts
        for pane_id in ("#pane-tasks", "#pane-project"):
            try:
                pane = self.query_one(pane_id)
                pane.styles.layout = "vertical" if is_narrow else "horizontal"
            except Exception:
                pass
                
        # 2. Update column dimensions
        for col in self.query(".left-column"):
            col.styles.width = "100%" if is_narrow else "45%"
            col.styles.height = "1fr" if is_narrow else "100%"
            col.styles.margin_right = 0 if is_narrow else 1
            col.styles.margin_bottom = 1 if is_narrow else 0
            
        for col in self.query(".right-column"):
            col.styles.width = "100%" if is_narrow else "55%"
            col.styles.height = "1fr" if is_narrow else "100%"
            col.styles.margin_left = 0 if is_narrow else 1
            
        # 3. Toggle nav stats visibility based on width 70 threshold
        try:
            stats = self.query_one("#nav-stats")
            stats.styles.display = "none" if event.size.width < 70 else "block"
        except Exception:
            pass

    def on_mount(self) -> None:
        self.theme = "catppuccin-mocha"
        table = self.query_one("#task-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(
            "[#a1a1aa]ID[/#a1a1aa]",
            "[#a1a1aa]Title[/#a1a1aa]",
            "[#a1a1aa]Status[/#a1a1aa]",
            "[#a1a1aa]Priority[/#a1a1aa]",
            "[#a1a1aa]Progress[/#a1a1aa]",
            "[#a1a1aa]Assignee[/#a1a1aa]"
        )
        self.refresh_tasks()
        self.update_project_view()
        self.refresh_feed()
        self.update_nav_stats()

    def refresh_tasks(self) -> None:
        table = self.query_one("#task-table", DataTable)
        table.clear()
        
        prev_selected_id = self.selected_task_id
        tasks = []
        
        with get_session() as session:
            tasks = crud.list_tasks(session)
            for t in tasks:
                status_color = {"todo": "#a1a1aa", "in_progress": "#60a5fa", "review": "#fbbf24", "done": "#34d399"}.get(t.status.lower(), "#e4e4e7")
                status_str = f"[{status_color}]{format_status(t.status)}[/{status_color}]"
                
                prio_color = {0: "#fca5a5", 1: "#fca5a5", 2: "#fde047", 3: "#93c5fd", 4: "#a1a1aa"}.get(t.priority, "#e4e4e7")
                priority_str = f"[{prio_color}]{format_priority(t.priority)}[/{prio_color}]"
                
                assignee_str = f"[#22d3ee]@{t.assignee}[/#22d3ee]" if t.assignee else "[#71717a]-[/#71717a]"
                id_str = f"[bold #f4f4f5]#{t.id}[/bold #f4f4f5]"
                title_str = f"[strike][#71717a]{t.title}[/#71717a][/strike]" if t.status.lower() == "done" else f"[#e4e4e7]{t.title}[/#e4e4e7]"
                
                progress_color = "#34d399" if t.progress == 100 else "#60a5fa" if t.progress > 0 else "#a1a1aa"
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
        self.update_nav_stats()

    def update_nav_stats(self) -> None:
        stats_box = self.query_one("#nav-stats", Static)
        with get_session() as session:
            tasks = crud.list_tasks(session)
            total_tasks = len(tasks)
            done_count = sum(1 for t in tasks if t.status == "done")
            in_progress_count = sum(1 for t in tasks if t.status == "in_progress")
            
            stats_text = Text.assemble(
                ("Tasks: ", "bold #a1a1aa"), (f"{total_tasks}  |  ", "#e4e4e7"),
                ("Active: ", "bold #a1a1aa"), (f"{in_progress_count}  |  ", "#e4e4e7"),
                ("Completed: ", "bold #a1a1aa"), (f"{done_count}  ", "#e4e4e7")
            )
            stats_box.update(stats_text)

    def refresh_feed(self) -> None:
        # 1. Update Project Feed Log (unfiltered)
        project_log = self.query_one("#project-feed-log", RichLog)
        project_log.clear()
        with get_session() as session:
            project_events = crud.get_events(session, limit=50)
            for e in reversed(project_events):
                time_str = format_datetime(e.created_at)
                task_part = f" [#60a5fa]#{e.task_id}[/#60a5fa]" if e.task_id else ""
                project_log.write(f"[#71717a][{time_str}][/#71717a] [#22d3ee]@{e.actor}[/#22d3ee] [bold #34d399]{e.event_type.upper()}[/bold #34d399]{task_part}: [#e4e4e7]{e.details}[/#e4e4e7]")
                
        # 2. Update Task Feed Log (filtered by selected task)
        task_log = self.query_one("#task-feed-log", RichLog)
        task_log.clear()
        if self.selected_task_id:
            with get_session() as session:
                task_events = crud.get_events(session, task_id=self.selected_task_id, limit=50)
                for e in reversed(task_events):
                    time_str = format_datetime(e.created_at)
                    task_log.write(f"[#71717a][{time_str}][/#71717a] [#22d3ee]@{e.actor}[/#22d3ee] [bold #34d399]{e.event_type.upper()}[/bold #34d399]: [#e4e4e7]{e.details}[/#e4e4e7]")
        else:
            task_log.write("[italic #71717a]No task selected.[/italic #71717a]")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value
        if row_key:
            new_id = int(row_key)
            if new_id != self.selected_task_id:
                self.selected_task_id = new_id
                self.update_details_view()
                self.refresh_feed()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        row_key = event.row_key.value
        if row_key:
            new_id = int(row_key)
            if new_id != self.selected_task_id:
                self.selected_task_id = new_id
                self.update_details_view()
                self.refresh_feed()

    def update_details_view(self) -> None:
        details_box = self.query_one("#details-view", Static)
        comments_box = self.query_one("#task-comments-list", Static)
        decisions_box = self.query_one("#task-decisions-list", Static)
        
        with get_session() as session:
            if not self.selected_task_id:
                panel_text = Text("No tasks found. Use the quick create input on the left to create a task.", style="#e4e4e7")
                details_box.update(Panel(panel_text, title=Text("Details", style="bold #a1a1aa"), border_style="#3f3f46"))
                comments_box.update("[italic #71717a]Create a task to view comments.[/italic #71717a]")
                decisions_box.update("[italic #71717a]No task selected.[/italic #71717a]")
                
                self.query_one("#btn-claim", Button).disabled = True
                self.query_one("#btn-status", Button).disabled = True
                self.query_one("#btn-complete", Button).disabled = True
            else:
                task = crud.get_task(session, self.selected_task_id)
                if not task:
                    panel_text = Text("Selected task not found.", style="#e4e4e7")
                    details_box.update(Panel(panel_text, title=Text("Error", style="bold #ef4444"), border_style="#ef4444"))
                    return
                    
                status_theme = {"todo": "#a1a1aa", "in_progress": "#60a5fa", "review": "#fbbf24", "done": "#34d399"}.get(task.status, "#e4e4e7")
                prio_theme = {0: "#fca5a5", 1: "#fca5a5", 2: "#fde047", 3: "#93c5fd", 4: "#a1a1aa"}.get(task.priority, "#e4e4e7")
                
                details_text = Text.assemble(
                    ("Task Title:  ", "bold #a1a1aa"), (f"{task.title}\n", "#e4e4e7"),
                    ("Description: ", "bold #a1a1aa"), (f"{task.description or 'No description'}\n\n", "#e4e4e7"),
                    ("Status:      ", "bold #a1a1aa"), (format_status(task.status), status_theme), ("  |  ", "#a1a1aa"),
                    ("Priority:    ", "bold #a1a1aa"), (format_priority(task.priority), prio_theme), ("  |  ", "#a1a1aa"),
                    ("Progress:    ", "bold #a1a1aa"), (f"{task.progress}%\n", "#e4e4e7"),
                    ("Assignee:    ", "bold #a1a1aa"), ("@" + task.assignee if task.assignee else "Unassigned", "#34d399"), ("\n", "#a1a1aa"),
                    ("Created:     ", "bold #a1a1aa"), (f"{format_datetime(task.created_at)}\n", "#e4e4e7"),
                    ("Updated:     ", "bold #a1a1aa"), (f"{format_datetime(task.updated_at)}", "#e4e4e7")
                )
                details_box.update(Panel(details_text, title=Text(f"Task #{task.id}", style="bold #a1a1aa"), border_style="#3f3f46"))
                
                # Comments
                comments = crud.get_comments(session, self.selected_task_id)
                comment_content = []
                for c in comments:
                    comment_content.append(f"[bold #60a5fa]@{c.author}[/bold #60a5fa] [#71717a]({format_datetime(c.created_at)})[/#71717a]\n[#e4e4e7]{c.content}[/#e4e4e7]\n[#2e2e33]──────────────────────────────────────────────────[/#2e2e33]")
                if not comment_content:
                    comment_content.append("[italic #71717a]No comments yet. Type below and press Enter to add one.[/italic #71717a]")
                comments_box.update("\n".join(comment_content))
                
                # Decisions: Task-level decisions only
                task_decisions = crud.get_decisions(session, self.selected_task_id)
                decision_content = []
                if task_decisions:
                    decision_content.append("[bold underline #34d399]Task Decisions:[/bold underline #34d399]")
                    for d in task_decisions:
                        decision_content.append(
                            f"[bold #f4f4f5]{d.title}[/bold #f4f4f5] [#71717a]by @{d.author} ({format_datetime(d.created_at)})[/#71717a]\n"
                            f"[italic #a1a1aa]Context:[/italic #a1a1aa] [#e4e4e7]{d.context}[/#e4e4e7]\n"
                            f"[bold #34d399]Decision:[/bold #34d399] [#e4e4e7]{d.decision}[/#e4e4e7]\n"
                            f"[#2e2e33]──────────────────────────────────────────────────[/#2e2e33]"
                        )
                if not decision_content:
                    decision_content.append("[italic #71717a]No decisions recorded for this task yet.[/italic #71717a]")
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
            
            # Build project overview details
            # Project Profile Info Grid
            info_table = Table.grid(padding=(0, 2))
            info_table.add_column(style="bold #a1a1aa", width=16)
            info_table.add_column(style="#e4e4e7")
            
            info_table.add_row("Project Name:", f"[bold #f4f4f5]{project.name}[/bold #f4f4f5]")
            info_table.add_row("Last Updated:", format_datetime(project.updated_at))
            
            details_content = project.details or "No details provided."
            idea_content = project.overall_idea or "No overall idea recorded."
            
            # Create a beautiful grid for task stats
            stats_table = Table.grid(padding=(0, 2))
            stats_table.add_column(style="bold #a1a1aa") # Label
            stats_table.add_column(style="bold #f4f4f5") # Value
            
            stats_table.add_row("Total Tasks:", f"[#f4f4f5]{total_tasks}[/#f4f4f5]")
            stats_table.add_row("Todo Tasks:", f"[#a1a1aa]{todo_count}[/#a1a1aa]")
            stats_table.add_row("In Progress:", f"[#60a5fa]{in_progress_count}[/#60a5fa]")
            stats_table.add_row("In Review:", f"[#fde047]{review_count}[/#fde047]")
            stats_table.add_row("Completed:", f"[#34d399]{done_count}[/#34d399]")
            
            progress_bar = f"[#34d399]{'█' * (avg_progress // 10)}{'░' * (10 - avg_progress // 10)}[/#34d399] [#e4e4e7]{avg_progress}%[/#e4e4e7]"
            stats_table.add_row("Avg Progress:", progress_bar)
            stats_table.add_row("Team Size:", f"[#e4e4e7]{len(assignees)} active member(s)[/#e4e4e7]")
            
            group = Group(
                Text("\n"),
                info_table,
                Text("\n"),
                Rule("Description", style="#2e2e33"),
                Text(f"\n{details_content}\n", style="#e4e4e7"),
                Rule("Overall Idea", style="#2e2e33"),
                Text(f"\n{idea_content}\n", style="#e4e4e7"),
                Rule("Metrics", style="#2e2e33"),
                Text("\n"),
                Panel(stats_table, title="Task Statistics", border_style="#2e2e33")
            )
            info_box.update(Panel(group, title=Text("Project Profile", style="bold #a1a1aa"), border_style="#3f3f46"))
            
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
                comment_content.append(f"[bold #60a5fa]@{c.author}[/bold #60a5fa] [#71717a]({format_datetime(c.created_at)})[/#71717a]\n[#e4e4e7]{c.content}[/#e4e4e7]\n[#2e2e33]──────────────────────────────────────────────────[/#2e2e33]")
            if not comment_content:
                comment_content.append("[italic #71717a]No project comments yet. Type below to add one.[/italic #71717a]")
            comments_box.update("\n".join(comment_content))
            
            # Project decisions
            decisions = crud.get_decisions(session, project_only=True)
            decision_content = []
            for d in decisions:
                decision_content.append(
                    f"[bold #f4f4f5]{d.title}[/bold #f4f4f5] [#71717a]by @{d.author} ({format_datetime(d.created_at)})[/#71717a]\n"
                    f"[italic #a1a1aa]Context:[/italic #a1a1aa] [#e4e4e7]{d.context}[/#e4e4e7]\n"
                    f"[bold #34d399]Decision:[/bold #34d399] [#e4e4e7]{d.decision}[/#e4e4e7]\n"
                    f"[#2e2e33]──────────────────────────────────────────────────[/#2e2e33]"
                )
            if not decision_content:
                decision_content.append("[italic #71717a]No project decisions recorded yet. Record one below.[/italic #71717a]")
            decisions_box.update("\n".join(decision_content))
            
            # Project memories
            memories = crud.list_memories(session)
            memory_lines = []
            for m in memories:
                memory_lines.append(f"[bold #fbbf24]{m.key}[/bold #fbbf24] = [#e4e4e7]{m.value}[/#e4e4e7] [#71717a]({format_datetime(m.updated_at)})[/#71717a]\n[#2e2e33]──────────────────────────────────────────────────[/#2e2e33]")
            if not memory_lines:
                memory_lines.append("[italic #71717a]No project memories stored yet. Add one below.[/italic #71717a]")
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

    def action_switch_to_tasks(self) -> None:
        self.query_one("#content-switcher", ContentSwitcher).current = "pane-tasks"
        self.query_one("#nav-tabs", Tabs).active = "tab-tasks"

    def action_switch_to_project(self) -> None:
        self.query_one("#content-switcher", ContentSwitcher).current = "pane-project"
        self.query_one("#nav-tabs", Tabs).active = "tab-project"

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Handle native Tabs navigation switching."""
        if event.tabs.id != "nav-tabs":
            return  # Only handle our top-level nav tabs
        tab_id = event.tab.id if event.tab else None
        switcher = self.query_one("#content-switcher", ContentSwitcher)
        if tab_id == "tab-tasks":
            switcher.current = "pane-tasks"
        elif tab_id == "tab-project":
            switcher.current = "pane-project"

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
