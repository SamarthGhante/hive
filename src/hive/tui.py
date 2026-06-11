import asyncio
from datetime import datetime
from typing import Optional, List, Tuple

from sqlmodel import Session, select
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header, Footer, Static, DataTable, TabbedContent, TabPane,
    Button, Input, Label, RichLog, ContentSwitcher, Tabs, Tab
)
from textual.reactive import reactive
from rich.panel import Panel
from rich.text import Text
from rich.console import Group
from rich.table import Table
from rich.rule import Rule

from hive.database import get_session
import hive.crud as crud
from hive.models import Task, Project, Event, Comment, Decision, Memory
from hive.utils import get_current_actor, format_priority, format_status, format_datetime

class HiveTUIApp(App):
    TITLE = "Hive"
    SUBTITLE = "Collaborative Project Coordination Engine"
    HORIZONTAL_BREAKPOINTS = [(0, "narrow"), (95, "wide")]
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh All"),
        ("c", "claim_selected", "Claim Task"),
        ("s", "cycle_status", "Cycle Status"),
        ("n", "focus_command", "Focus Console"),
        ("t", "switch_to_tasks", "Task Board"),
        ("p", "switch_to_project", "Project Hub"),
    ]

    CSS = """
    /* OpenCode CLI Inspired TUI Stylesheet */

    /* Color system tokens */
    $background: #212121;
    $surface: #2b2b2b;
    $panel: #323232;
    $primary: #fab283;       /* Gold/Orange */
    $secondary: #5c9cf5;     /* Accent Blue */
    $text: #e4e4e7;
    $text-muted: #a1a1aa;
    $success: #34d399;
    $warning: #fbbf24;
    $error: #f87171;
    $border: #444444;

    Screen {
        background: $background;
        color: $text;
    }

    Header {
        background: $surface;
        color: $primary;
        text-style: bold;
        dock: top;
        height: 1;
    }

    Footer {
        background: $surface;
        color: $text-muted;
        dock: bottom;
        height: 1;
    }

    /* Tab navigation styling */
    #nav-tabs {
        width: 100%;
        height: 3;
        background: $surface;
        border-bottom: solid $border;
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
        border-bottom: tall $primary;
    }

    #nav-stats {
        height: 1;
        color: $text-muted;
        content-align: right middle;
        width: 100%;
        padding: 0 2;
        background: $background;
    }

    #main-content {
        width: 100%;
        height: 1fr;
        background: $background;
        padding: 1 1 0 1;
    }

    ContentSwitcher {
        height: 1fr;
        width: 100%;
    }

    /* Responsive layouts via class-based rules (updated by HORIZONTAL_BREAKPOINTS) */
    .page-container {
        layout: vertical;
        height: 100%;
        width: 100%;
    }

    .left-column {
        width: 100%;
        height: 1fr;
        border: solid $border;
        background: $surface;
        padding: 1;
        margin-bottom: 1;
    }

    .right-column {
        width: 100%;
        height: 1fr;
        border: solid $border;
        background: $surface;
        padding: 1;
        margin-left: 0;
    }

    /* Wide layout adjustments */
    .wide .page-container {
        layout: horizontal;
    }

    .wide .left-column {
        width: 45%;
        height: 100%;
        margin-bottom: 0;
    }

    .wide .right-column {
        width: 55%;
        height: 100%;
        margin-left: 1;
    }

    .section-title {
        text-style: bold;
        color: $primary;
        padding: 0 0 1 0;
    }

    /* DataTable styling */
    #task-table {
        height: 1fr;
        background: $background;
        border: none;
    }

    DataTable > .datatable--header {
        background: $panel;
        color: $primary;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: $secondary 25%;
        color: $text;
        text-style: bold;
    }

    DataTable > .datatable--hover {
        background: $panel;
    }

    /* Unified command console at the bottom of the left column */
    #console-pane, #project-console-pane {
        height: auto;
        border-top: solid $border;
        padding-top: 1;
        margin-top: 1;
        layout: vertical;
    }

    #command-input, #project-command-input {
        background: $background;
        border: tall $border;
        color: $text;
        margin-bottom: 0;
    }

    #command-input:focus, #project-command-input:focus {
        border: tall $primary;
    }

    #command-hint, #project-command-hint {
        color: $text-muted;
        margin-left: 1;
        margin-top: 0;
    }

    /* Tabbed content inside detail column */
    TabbedContent {
        background: $surface;
        height: 1fr;
    }

    TabbedContent > Tabs {
        background: $surface;
        border-bottom: solid $border;
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
        color: $secondary;
        background: transparent;
        text-style: bold;
    }

    .scrollable-pane {
        height: 1fr;
        padding: 1;
        background: $background;
        border: solid $border;
        margin-bottom: 1;
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
    }

    .action-btn {
        margin: 0 1;
        min-width: 14;
        height: 3;
        background: $panel;
        color: $text;
        border: none;
    }

    .action-btn:hover {
        background: $secondary 30%;
        color: $text;
    }

    #btn-claim {
        background: $panel;
        color: $text;
    }

    #btn-claim:hover {
        background: $secondary 30%;
    }

    #btn-status {
        background: $panel;
        color: $text;
    }

    #btn-status:hover {
        background: $secondary 30%;
    }

    #btn-complete {
        background: $panel;
        color: $text;
    }

    #btn-complete:hover {
        background: $success 30%;
    }

    /* Feed rich logs */
    #task-feed-log, #project-feed-log {
        height: 1fr;
        background: $background;
        border: solid $border;
        padding: 0 1;
    }
    """

    selected_task_id = reactive(None)

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="app-container"):
            yield Tabs(
                Tab("Task Board", id="tab-tasks"),
                Tab("Project Hub", id="tab-project"),
                id="nav-tabs"
            )
            yield Static(id="nav-stats")

            with Vertical(id="main-content"):
                with ContentSwitcher(initial="pane-tasks", id="content-switcher"):
                    # Task Board Pane
                    with Horizontal(id="pane-tasks", classes="page-container"):
                        # Left Column
                        with Vertical(id="left-pane", classes="left-column"):
                            yield Label("Tasks", classes="section-title")
                            yield DataTable(id="task-table")
                            with Vertical(id="console-pane"):
                                yield Label("Interactive Console", classes="section-title")
                                yield Input(placeholder="Type command (e.g. /help) or comment...", id="command-input")
                                yield Static("💡 Tip: Type a comment directly, or use /create, /claim, /complete, /status, /decision", id="command-hint")
                        
                        # Right Column
                        with Vertical(id="right-pane", classes="right-column"):
                            with TabbedContent(id="task-tabs"):
                                with TabPane("Task Details", id="pane-task-details"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="details-view")
                                    with Horizontal(id="details-actions"):
                                        yield Button("Claim (c)", id="btn-claim", classes="action-btn")
                                        yield Button("Status (s)", id="btn-status", classes="action-btn")
                                        yield Button("Complete", id="btn-complete", classes="action-btn")
                                
                                with TabPane("Task Comments", id="pane-task-comments"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="task-comments-list")
                                
                                with TabPane("Task Decisions", id="pane-task-decisions"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="task-decisions-list")
                                
                                with TabPane("Task Activity", id="pane-task-activity"):
                                    yield RichLog(id="task-feed-log", highlight=True, markup=True)
                                    
                    # Project Hub Pane
                    with Horizontal(id="pane-project", classes="page-container"):
                        # Left Column
                        with Vertical(id="project-left-pane", classes="left-column"):
                            yield Label("Project Info", classes="section-title")
                            with VerticalScroll(classes="scrollable-pane"):
                                yield Static(id="project-info-view")
                            with Vertical(id="project-console-pane"):
                                yield Label("Interactive Project Console", classes="section-title")
                                yield Input(placeholder="Type project command (e.g. /help) or comment...", id="project-command-input")
                                yield Static("💡 Tip: Type project comment directly, or use /update-project, /memory, /decision", id="project-command-hint")
                        
                        # Right Column
                        with Vertical(id="project-right-pane", classes="right-column"):
                            with TabbedContent(id="project-tabs"):
                                with TabPane("Project Comments", id="pane-project-comments"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="project-comments-list")
                                
                                with TabPane("Project Decisions", id="pane-project-decisions"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="project-decisions-list")
                                
                                with TabPane("Project Memories", id="pane-project-memories"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="project-memories-list")
                                        
                                with TabPane("Project Activity", id="pane-project-activity"):
                                    yield RichLog(id="project-feed-log", highlight=True, markup=True)
        yield Footer()

    # --- Threaded DB operations ---

    def _db_list_tasks(self) -> List[Task]:
        with get_session() as session:
            return crud.list_tasks(session)

    def _db_get_project(self) -> Project:
        with get_session() as session:
            return crud.get_project(session)

    def _db_get_events(self, task_id: Optional[int]) -> List[Event]:
        with get_session() as session:
            return crud.get_events(session, task_id=task_id, limit=50)

    def _db_get_task_details(self, task_id: int) -> Tuple[Optional[Task], List[Comment], List[Decision], List[Event]]:
        with get_session() as session:
            task = crud.get_task(session, task_id)
            if not task:
                return None, [], [], []
            comments = crud.get_comments(session, task_id)
            decisions = crud.get_decisions(session, task_id)
            events = crud.get_events(session, task_id=task_id, limit=50)
            return task, comments, decisions, events

    def _db_get_project_details(self) -> Tuple[Project, List[Task], List[Comment], List[Decision], List[Memory], List[Event]]:
        with get_session() as session:
            project = crud.get_project(session)
            tasks = crud.list_tasks(session)
            comments = crud.get_comments(session, task_id=None)
            decisions = crud.get_decisions(session, project_only=True)
            memories = crud.list_memories(session)
            events = crud.get_events(session, limit=50)
            return project, tasks, comments, decisions, memories, events

    def _db_claim_task(self, task_id: int, assignee: str) -> None:
        with get_session() as session:
            crud.claim_task(session, task_id, assignee)

    def _db_complete_task(self, task_id: int) -> None:
        with get_session() as session:
            crud.complete_task(session, task_id)

    def _db_update_task(self, task_id: int, **kwargs) -> None:
        with get_session() as session:
            crud.update_task(session, task_id, **kwargs)

    def _db_create_task(self, title: str, description: Optional[str]) -> None:
        with get_session() as session:
            crud.create_task(session, title=title, description=description)

    def _db_add_comment(self, task_id: Optional[int], author: str, content: str) -> None:
        with get_session() as session:
            crud.add_comment(session, task_id, author, content)

    def _db_add_decision(self, task_id: Optional[int], title: str, context: str, decision: str, author: str) -> None:
        with get_session() as session:
            crud.add_decision(session, task_id, title, context, decision, author)

    def _db_add_memory(self, key: str, value: str) -> None:
        with get_session() as session:
            crud.add_memory(session, key, value)

    def _db_update_project(self, name: Optional[str], details: Optional[str], overall_idea: Optional[str]) -> None:
        with get_session() as session:
            crud.update_project(session, name=name, details=details, overall_idea=overall_idea)

    # --- UI rendering / Reactive sync ---

    def on_mount(self) -> None:
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
        self.run_worker(self.async_refresh_all(), group="db_sync")

    async def async_refresh_all(self) -> None:
        """Refresh all TUI data asynchronously from the database."""
        # 1. Fetch tasks
        tasks = await asyncio.to_thread(self._db_list_tasks)
        
        # 2. Update tasks table
        table = self.query_one("#task-table", DataTable)
        table.clear()
        
        prev_selected_id = self.selected_task_id
        
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
            
        if prev_selected_id and any(t.id == prev_selected_id for t in tasks):
            try:
                table.move_cursor(row=table.find_row(str(prev_selected_id)))
            except Exception:
                pass
        elif tasks:
            try:
                table.move_cursor(row=0)
                self.selected_task_id = tasks[0].id
            except Exception:
                pass
        else:
            self.selected_task_id = None

        # 3. Fetch project details
        project, all_tasks, project_comments, project_decisions, project_memories, project_events = await asyncio.to_thread(self._db_get_project_details)
        
        # 4. Update nav stats
        stats_box = self.query_one("#nav-stats", Static)
        total_tasks = len(all_tasks)
        done_count = sum(1 for t in all_tasks if t.status == "done")
        in_progress_count = sum(1 for t in all_tasks if t.status == "in_progress")
        stats_text = Text.assemble(
            ("Tasks: ", "bold #a1a1aa"), (f"{total_tasks}  |  ", "#e4e4e7"),
            ("Active: ", "bold #a1a1aa"), (f"{in_progress_count}  |  ", "#e4e4e7"),
            ("Completed: ", "bold #a1a1aa"), (f"{done_count}  ", "#e4e4e7")
        )
        stats_box.update(stats_text)
        
        # 5. Update Project Hub panels
        self._update_project_hub_ui(project, all_tasks, project_comments, project_decisions, project_memories, project_events)
        
        # 6. Update Task Details
        await self.async_refresh_task_details()

    def _update_project_hub_ui(self, project: Project, tasks: List[Task], comments: List[Comment], decisions: List[Decision], memories: List[Memory], events: List[Event]) -> None:
        info_box = self.query_one("#project-info-view", Static)
        comments_box = self.query_one("#project-comments-list", Static)
        decisions_box = self.query_one("#project-decisions-list", Static)
        memories_box = self.query_one("#project-memories-list", Static)
        project_log = self.query_one("#project-feed-log", RichLog)

        # Stats calculations
        total_tasks = len(tasks)
        todo_count = sum(1 for t in tasks if t.status == "todo")
        in_progress_count = sum(1 for t in tasks if t.status == "in_progress")
        review_count = sum(1 for t in tasks if t.status == "review")
        done_count = sum(1 for t in tasks if t.status == "done")
        avg_progress = 0
        if total_tasks > 0:
            avg_progress = int(sum(t.progress for t in tasks) / total_tasks)
        assignees = {t.assignee for t in tasks if t.assignee}

        # Project Info Grid
        info_table = Table.grid(padding=(0, 2))
        info_table.add_column(style="bold #a1a1aa", width=16)
        info_table.add_column(style="#e4e4e7")
        info_table.add_row("Project Name:", f"[bold #f4f4f5]{project.name}[/bold #f4f4f5]")
        info_table.add_row("Last Updated:", format_datetime(project.updated_at))

        details_content = project.details or "No details provided."
        idea_content = project.overall_idea or "No overall idea recorded."

        # Stats Grid
        stats_table = Table.grid(padding=(0, 2))
        stats_table.add_column(style="bold #a1a1aa")
        stats_table.add_column(style="bold #f4f4f5")
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
            Rule("Description", style="#444444"),
            Text(f"\n{details_content}\n", style="#e4e4e7"),
            Rule("Overall Idea", style="#444444"),
            Text(f"\n{idea_content}\n", style="#e4e4e7"),
            Rule("Metrics", style="#444444"),
            Text("\n"),
            Panel(stats_table, title="Task Statistics", border_style="#444444")
        )
        info_box.update(Panel(group, title=Text("Project Profile", style="bold #a1a1aa"), border_style="#444444"))

        # Project Comments
        comment_content = []
        for c in comments:
            comment_content.append(f"[bold #60a5fa]@{c.author}[/bold #60a5fa] [#71717a]({format_datetime(c.created_at)})[/#71717a]\n[#e4e4e7]{c.content}[/#e4e4e7]\n[#323232]──────────────────────────────────────────────────[/#323232]")
        if not comment_content:
            comment_content.append("[italic #71717a]No project comments yet. Type in the project console to add one.[/italic #71717a]")
        comments_box.update("\n".join(comment_content))

        # Project Decisions
        decision_content = []
        for d in decisions:
            decision_content.append(
                f"[bold #f4f4f5]{d.title}[/bold #f4f4f5] [#71717a]by @{d.author} ({format_datetime(d.created_at)})[/#71717a]\n"
                f"[italic #a1a1aa]Context:[/italic #a1a1aa] [#e4e4e7]{d.context}[/#e4e4e7]\n"
                f"[bold #34d399]Decision:[/bold #34d399] [#e4e4e7]{d.decision}[/#e4e4e7]\n"
                f"[#323232]──────────────────────────────────────────────────[/#323232]"
            )
        if not decision_content:
            decision_content.append("[italic #71717a]No project decisions recorded yet. Record one using /decision.[/italic #71717a]")
        decisions_box.update("\n".join(decision_content))

        # Project Memories
        memory_lines = []
        for m in memories:
            memory_lines.append(f"[bold #fbbf24]{m.key}[/bold #fbbf24] = [#e4e4e7]{m.value}[/#e4e4e7] [#71717a]({format_datetime(m.updated_at)})[/#71717a]\n[#323232]──────────────────────────────────────────────────[/#323232]")
        if not memory_lines:
            memory_lines.append("[italic #71717a]No project memories stored yet. Add one using /memory.[/italic #71717a]")
        memories_box.update("\n".join(memory_lines))

        # Project Feed
        project_log.clear()
        for e in reversed(events):
            time_str = format_datetime(e.created_at)
            task_part = f" [#60a5fa]#{e.task_id}[/bold #60a5fa]" if e.task_id else ""
            project_log.write(f"[#71717a][{time_str}][/#71717a] [#22d3ee]@{e.actor}[/#22d3ee] [bold #34d399]{e.event_type.upper()}[/bold #34d399]{task_part}: [#e4e4e7]{e.details}[/#e4e4e7]")

    async def async_refresh_task_details(self) -> None:
        """Refresh only the task details view asynchronously."""
        details_box = self.query_one("#details-view", Static)
        comments_box = self.query_one("#task-comments-list", Static)
        decisions_box = self.query_one("#task-decisions-list", Static)
        task_log = self.query_one("#task-feed-log", RichLog)

        if not self.selected_task_id:
            self._update_empty_details_ui()
            return

        task, comments, decisions, events = await asyncio.to_thread(self._db_get_task_details, self.selected_task_id)

        if not task:
            panel_text = Text("Selected task not found.", style="#e4e4e7")
            details_box.update(Panel(panel_text, title=Text("Error", style="bold #ef4444"), border_style="#ef4444"))
            return

        status_theme = {"todo": "#a1a1aa", "in_progress": "#60a5fa", "review": "#fbbf24", "done": "#34d399"}.get(task.status.lower(), "#e4e4e7")
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
        details_box.update(Panel(details_text, title=Text(f"Task #{task.id}", style="bold #a1a1aa"), border_style="#444444"))

        # Comments
        comment_content = []
        for c in comments:
            comment_content.append(f"[bold #60a5fa]@{c.author}[/bold #60a5fa] [#71717a]({format_datetime(c.created_at)})[/#71717a]\n[#e4e4e7]{c.content}[/#e4e4e7]\n[#323232]──────────────────────────────────────────────────[/#323232]")
        if not comment_content:
            comment_content.append("[italic #71717a]No comments yet. Type in the task console to add one.[/italic #71717a]")
        comments_box.update("\n".join(comment_content))

        # Decisions
        decision_content = []
        if decisions:
            decision_content.append("[bold underline #34d399]Task Decisions:[/bold underline #34d399]")
            for d in decisions:
                decision_content.append(
                    f"[bold #f4f4f5]{d.title}[/bold #f4f4f5] [#71717a]by @{d.author} ({format_datetime(d.created_at)})[/#71717a]\n"
                    f"[italic #a1a1aa]Context:[/italic #a1a1aa] [#e4e4e7]{d.context}[/#e4e4e7]\n"
                    f"[bold #34d399]Decision:[/bold #34d399] [#e4e4e7]{d.decision}[/#e4e4e7]\n"
                    f"[#323232]──────────────────────────────────────────────────[/#323232]"
                )
        if not decision_content:
            decision_content.append("[italic #71717a]No decisions recorded for this task yet. Record one using /decision.[/italic #71717a]")
        decisions_box.update("\n".join(decision_content))

        # Feed
        task_log.clear()
        for e in reversed(events):
            time_str = format_datetime(e.created_at)
            task_log.write(f"[#71717a][{time_str}][/#71717a] [#22d3ee]@{e.actor}[/#22d3ee] [bold #34d399]{e.event_type.upper()}[/bold #34d399]: [#e4e4e7]{e.details}[/#e4e4e7]")

        # Enable buttons
        self.query_one("#btn-claim", Button).disabled = False
        self.query_one("#btn-status", Button).disabled = False
        self.query_one("#btn-complete", Button).disabled = False

    def _update_empty_details_ui(self) -> None:
        details_box = self.query_one("#details-view", Static)
        comments_box = self.query_one("#task-comments-list", Static)
        decisions_box = self.query_one("#task-decisions-list", Static)
        task_log = self.query_one("#task-feed-log", RichLog)

        panel_text = Text("No tasks found. Use the Interactive Console to create a task via:\n/create <title> [| <description>]", style="#e4e4e7")
        details_box.update(Panel(panel_text, title=Text("Details", style="bold #a1a1aa"), border_style="#444444"))
        comments_box.update("[italic #71717a]Create a task to view comments.[/italic #71717a]")
        decisions_box.update("[italic #71717a]No task selected.[/italic #71717a]")
        task_log.clear()
        task_log.write("[italic #71717a]No task selected.[/italic #71717a]")

        self.query_one("#btn-claim", Button).disabled = True
        self.query_one("#btn-status", Button).disabled = True
        self.query_one("#btn-complete", Button).disabled = True

    # --- Interactive Event Handlers ---

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value
        if row_key:
            new_id = int(row_key)
            if new_id != self.selected_task_id:
                self.selected_task_id = new_id
                self.run_worker(self.async_refresh_task_details(), group="db_sync")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        row_key = event.row_key.value
        if row_key:
            new_id = int(row_key)
            if new_id != self.selected_task_id:
                self.selected_task_id = new_id
                self.run_worker(self.async_refresh_task_details(), group="db_sync")

    # --- Actions / Keyboard Shortcuts ---

    def action_refresh(self) -> None:
        self.run_worker(self.async_refresh_all(), group="db_sync")
        self.notify("Refreshed all data.")

    def action_claim_selected(self) -> None:
        if not self.selected_task_id:
            self.notify("No task selected to claim.", severity="warning")
            return
        actor = get_current_actor()
        self.run_worker(self.async_claim_task(self.selected_task_id, actor), group="db_sync")

    async def async_claim_task(self, task_id: int, actor: str) -> None:
        await asyncio.to_thread(self._db_claim_task, task_id, actor)
        self.notify(f"Claimed task #{task_id}")
        await self.async_refresh_all()

    def action_cycle_status(self) -> None:
        if not self.selected_task_id:
            self.notify("No task selected.", severity="warning")
            return
        self.run_worker(self.async_cycle_task_status(self.selected_task_id), group="db_sync")

    async def async_cycle_task_status(self, task_id: int) -> None:
        status_flow = ["todo", "in_progress", "review", "done"]
        with get_session() as session:
            task = crud.get_task(session, task_id)
            if not task:
                return
            next_index = (status_flow.index(task.status.lower()) + 1) % len(status_flow)
            next_status = status_flow[next_index]
            progress = task.progress
            if next_status == "done":
                progress = 100
            elif next_status == "todo":
                progress = 0
        
        await asyncio.to_thread(self._db_update_task, task_id, status=next_status, progress=progress)
        self.notify(f"Updated status of task #{task_id}")
        await self.async_refresh_all()

    def action_focus_command(self) -> None:
        current_tab = self.query_one("#nav-tabs", Tabs).active
        input_id = "#command-input" if current_tab == "tab-tasks" else "#project-command-input"
        try:
            self.query_one(input_id, Input).focus()
        except Exception:
            pass

    def action_switch_to_tasks(self) -> None:
        self.query_one("#content-switcher", ContentSwitcher).current = "pane-tasks"
        self.query_one("#nav-tabs", Tabs).active = "tab-tasks"

    def action_switch_to_project(self) -> None:
        self.query_one("#content-switcher", ContentSwitcher).current = "pane-project"
        self.query_one("#nav-tabs", Tabs).active = "tab-project"

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        if event.tabs.id != "nav-tabs":
            return
        tab_id = event.tab.id if event.tab else None
        switcher = self.query_one("#content-switcher", ContentSwitcher)
        if tab_id == "tab-tasks":
            switcher.current = "pane-tasks"
        elif tab_id == "tab-project":
            switcher.current = "pane-project"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-claim":
            self.action_claim_selected()
        elif btn_id == "btn-status":
            self.action_cycle_status()
        elif btn_id == "btn-complete":
            if not self.selected_task_id:
                self.notify("No task selected.", severity="warning")
                return
            self.run_worker(self.async_complete_task(self.selected_task_id), group="db_sync")

    async def async_complete_task(self, task_id: int) -> None:
        await asyncio.to_thread(self._db_complete_task, task_id)
        self.notify(f"Completed task #{task_id}")
        await self.async_refresh_all()

    # --- Unified Console Command Line Parser ---

    def on_input_submitted(self, event: Input.Submitted) -> None:
        input_id = event.input.id
        if input_id in ("command-input", "project-command-input"):
            cmd_text = event.value.strip()
            if not cmd_text:
                return
            event.input.value = ""
            self.run_worker(self.handle_command(cmd_text), group="db_sync")

    async def handle_command(self, cmd_text: str) -> None:
        actor = get_current_actor()
        
        if cmd_text.startswith("/"):
            parts = cmd_text[1:].split(" ", 1)
            cmd = parts[0].lower().strip()
            args = parts[1].strip() if len(parts) > 1 else ""
            
            if cmd == "help":
                self._show_help_info()
            elif cmd == "refresh":
                self.notify("Refreshing data...")
                await self.async_refresh_all()
            elif cmd == "quit":
                self.exit()
            elif cmd == "claim":
                task_id = self.selected_task_id
                if args:
                    try:
                        task_id = int(args)
                    except ValueError:
                        self.notify("Invalid task ID. Use /claim or /claim <id>", severity="error")
                        return
                if not task_id:
                    self.notify("No task selected or ID provided.", severity="warning")
                    return
                await asyncio.to_thread(self._db_claim_task, task_id, actor)
                self.notify(f"Claimed task #{task_id}")
                await self.async_refresh_all()
                
            elif cmd == "complete":
                task_id = self.selected_task_id
                if args:
                    try:
                        task_id = int(args)
                    except ValueError:
                        self.notify("Invalid task ID. Use /complete or /complete <id>", severity="error")
                        return
                if not task_id:
                    self.notify("No task selected or ID provided.", severity="warning")
                    return
                await asyncio.to_thread(self._db_complete_task, task_id)
                self.notify(f"Completed task #{task_id}")
                await self.async_refresh_all()
                
            elif cmd == "status":
                if not self.selected_task_id:
                    self.notify("No task selected.", severity="warning")
                    return
                status_val = args.lower().strip()
                if status_val not in ["todo", "in_progress", "review", "done"]:
                    self.notify("Invalid status. Use /status <todo|in_progress|review|done>", severity="error")
                    return
                progress = None
                if status_val == "done":
                    progress = 100
                elif status_val == "todo":
                    progress = 0
                await asyncio.to_thread(self._db_update_task, self.selected_task_id, status=status_val, progress=progress)
                self.notify(f"Updated status of task #{self.selected_task_id} to {status_val}")
                await self.async_refresh_all()
                
            elif cmd == "create":
                if not args:
                    self.notify("Usage: /create <title> [| <description>]", severity="error")
                    return
                title = args
                desc = None
                if "|" in args:
                    title, desc = args.split("|", 1)
                    title = title.strip()
                    desc = desc.strip()
                await asyncio.to_thread(self._db_create_task, title, desc)
                self.notify(f"Created task: {title}")
                await self.async_refresh_all()
                
            elif cmd == "decision":
                if not args or "|" not in args:
                    self.notify("Usage: /decision <title> | <context> | <decision>", severity="error")
                    return
                parts = args.split("|")
                if len(parts) < 2:
                    self.notify("Usage: /decision <title> | <context> | <decision>", severity="error")
                    return
                dec_title = parts[0].strip()
                dec_context = parts[1].strip()
                dec_text = parts[2].strip() if len(parts) > 2 else ""
                
                current_tab = self.query_one("#nav-tabs", Tabs).active
                task_id = self.selected_task_id if current_tab == "tab-tasks" else None
                
                await asyncio.to_thread(self._db_add_decision, task_id, dec_title, dec_context, dec_text, actor)
                self.notify("Recorded decision successfully.")
                await self.async_refresh_all()
                
            elif cmd == "memory":
                if not args or "=" not in args:
                    self.notify("Usage: /memory <key> = <value>", severity="error")
                    return
                m_key, m_val = args.split("=", 1)
                m_key = m_key.strip()
                m_val = m_val.strip()
                await asyncio.to_thread(self._db_add_memory, m_key, m_val)
                self.notify(f"Memory '{m_key}' saved.")
                await self.async_refresh_all()
                
            elif cmd == "update-project":
                if not args:
                    self.notify("Usage: /update-project <name> [| <details> [| <idea>]]", severity="error")
                    return
                parts = args.split("|")
                name = parts[0].strip() or None
                details = parts[1].strip() if len(parts) > 1 else None
                idea = parts[2].strip() if len(parts) > 2 else None
                await asyncio.to_thread(self._db_update_project, name, details, idea)
                self.notify("Project metadata updated.")
                await self.async_refresh_all()
            else:
                self.notify(f"Unknown command: /{cmd}. Type /help for assistance.", severity="error")
        else:
            current_tab = self.query_one("#nav-tabs", Tabs).active
            if current_tab == "tab-tasks":
                if not self.selected_task_id:
                    self.notify("No task selected to add comment.", severity="warning")
                    return
                await asyncio.to_thread(self._db_add_comment, self.selected_task_id, actor, cmd_text)
                self.notify("Comment added to task.")
            else:
                await asyncio.to_thread(self._db_add_comment, None, actor, cmd_text)
                self.notify("Comment added to project.")
            await self.async_refresh_all()

    def _show_help_info(self) -> None:
        current_tab = self.query_one("#nav-tabs", Tabs).active
        feed_log_id = "#task-feed-log" if current_tab == "tab-tasks" else "#project-feed-log"
        try:
            feed_log = self.query_one(feed_log_id, RichLog)
            feed_log.write("\n[bold #fab283]═══ Hive Console Command Help ═══[/bold #fab283]")
            if current_tab == "tab-tasks":
                feed_log.write("  [bold #5c9cf5]/create <title> [| <desc>][/bold #5c9cf5] - Create a new task")
                feed_log.write("  [bold #5c9cf5]/claim [id][/bold #5c9cf5]            - Claim task (defaults to selected)")
                feed_log.write("  [bold #5c9cf5]/complete [id][/bold #5c9cf5]         - Complete task (defaults to selected)")
                feed_log.write("  [bold #5c9cf5]/status <todo|in_progress|review|done>[/bold #5c9cf5] - Change status of selected task")
                feed_log.write("  [bold #5c9cf5]/decision <title> | <ctx> | <dec>[/bold #5c9cf5] - Record task decision")
                feed_log.write("  [bold #5c9cf5]<any other text>[/bold #5c9cf5]         - Add comment to selected task")
            else:
                feed_log.write("  [bold #5c9cf5]/update-project <name> [| <desc> [| <idea>]][/bold #5c9cf5] - Update project details")
                feed_log.write("  [bold #5c9cf5]/memory <key> = <val>[/bold #5c9cf5]   - Record project memory")
                feed_log.write("  [bold #5c9cf5]/decision <title> | <ctx> | <dec>[/bold #5c9cf5] - Record project decision")
                feed_log.write("  [bold #5c9cf5]<any other text>[/bold #5c9cf5]         - Add comment to project")
            feed_log.write("  [bold #5c9cf5]/refresh[/bold #5c9cf5]              - Refresh database views")
            feed_log.write("  [bold #5c9cf5]/quit[/bold #5c9cf5]                 - Exit the TUI")
            feed_log.write("[bold #fab283]═══════════════════════════════[/bold #fab283]\n")
            
            # Focus the activity feed tab so the user sees the help text immediately
            if current_tab == "tab-tasks":
                self.query_one("#task-tabs").active = "pane-task-activity"
            else:
                self.query_one("#project-tabs").active = "pane-project-activity"
        except Exception as e:
            self.notify(f"Help written to console feed.")
