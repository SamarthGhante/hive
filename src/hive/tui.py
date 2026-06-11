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
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("tab", "switch_focus", "Focus Tab"),
        ("c", "claim_selected", "Claim"),
        ("s", "cycle_status", "Cycle Status"),
        ("n", "focus_command", "Console Input"),
        ("t", "switch_to_tasks", "Tasks"),
        ("p", "switch_to_project", "Project"),
    ]

    CSS = """
    /* Premium Minimalist Stylesheet */
    $background: #09090b;   /* Almost black background */
    $surface: #18181b;      /* Dark gray card surface */
    $panel: #27272a;        /* Elevated elements / inputs */
    $primary: #f4f4f5;      /* Primary text - white */
    $secondary: #a1a1aa;    /* Secondary muted text */
    $accent: #60a5fa;       /* Dynamic blue accent */
    $border: #3f3f46;       /* Clean border tone */
    
    $success: #34d399;      /* Emerald */
    $warning: #fbbf24;      /* Amber */
    $error: #f87171;        /* Rose */

    Screen {
        background: $background;
        color: $primary;
    }

    Header {
        background: $surface;
        color: $primary;
        text-style: bold;
        height: 1;
        border-bottom: solid $border;
    }

    Footer {
        background: $surface;
        color: $secondary;
        height: 1;
        border-top: solid $border;
    }

    #nav-tabs {
        width: 100%;
        height: 3;
        background: $surface;
        border-bottom: solid $border;
        padding: 0 1;
    }

    #nav-stats {
        height: 1;
        color: $secondary;
        content-align: right middle;
        width: 100%;
        padding: 0 2;
        background: $background;
        text-style: italic;
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

    /* Grid layout configurations */
    .page-container {
        layout: horizontal;
        height: 100%;
        width: 100%;
    }

    .left-column {
        width: 45%;
        height: 100%;
        border: round $border;
        background: $surface;
        padding: 1;
    }

    .right-column {
        width: 55%;
        height: 100%;
        border: round $border;
        background: $surface;
        padding: 1;
        margin-left: 1;
    }

    .section-title {
        text-style: bold;
        color: $accent;
        padding: 0 0 1 0;
    }

    /* DataTable styles */
    #task-table {
        height: 1fr;
        background: $background;
        border: none;
    }

    DataTable > .datatable--header {
        background: $panel;
        color: $accent;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: $accent 25%;
        color: $primary;
        text-style: bold;
    }

    DataTable > .datatable--hover {
        background: $panel;
    }

    /* Quick Console Command Bar */
    .console-container {
        height: auto;
        border-top: solid $border;
        margin-top: 1;
        background: $surface;
        padding: 1 0 0 0;
    }

    .console-label {
        color: $secondary;
        text-style: bold;
        margin-bottom: 0;
    }

    #console-input {
        background: $panel;
        border: tall $border;
        color: $primary;
        margin: 0;
    }

    #console-input:focus {
        border: tall $accent;
    }

    /* Tabbed content details */
    TabbedContent {
        background: $surface;
        height: 1fr;
    }

    TabbedContent > Tabs {
        background: $surface;
        border-bottom: solid $border;
    }

    TabbedContent > Tabs > Tab {
        color: $secondary;
        background: transparent;
    }

    TabbedContent > Tabs > Tab:hover {
        background: $panel;
        color: $primary;
    }

    TabbedContent > Tabs > Tab.--active {
        color: $accent;
        background: transparent;
        text-style: bold;
    }

    .scrollable-pane {
        height: 1fr;
        padding: 1;
        background: $background;
        border: round $border;
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
        color: $primary;
        border: none;
    }

    .action-btn:hover {
        background: $accent 30%;
        color: $primary;
    }

    #btn-complete:hover {
        background: $success 30%;
    }

    /* Log logs */
    #task-feed-log, #project-feed-log {
        height: 1fr;
        background: $background;
        border: round $border;
        padding: 0 1;
    }
    """

    selected_task_id = reactive(None)

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="app-container"):
            yield Tabs(
                Tab("Workspace Board", id="tab-tasks"),
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
                            yield Label("Tasks Overview", classes="section-title")
                            yield DataTable(id="task-table")
                            with Vertical(id="task-console-container", classes="console-container"):
                                yield Label("Workspace Console (/help for commands, enter comment directly)", classes="console-label")
                                yield Input(placeholder="Type command or comment, then press Enter...", id="new-task-title")
                        
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
                                
                                with TabPane("Comments", id="pane-task-comments"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="task-comments-list")
                                
                                with TabPane("Decisions", id="pane-task-decisions"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="task-decisions-list")
                                
                                with TabPane("Activity Feed", id="pane-task-activity"):
                                    yield RichLog(id="task-feed-log", highlight=True, markup=True)
                                    
                    # Project Hub Pane
                    with Horizontal(id="pane-project", classes="page-container"):
                        # Left Column
                        with Vertical(id="project-left-pane", classes="left-column"):
                            yield Label("Project Profile", classes="section-title")
                            with VerticalScroll(classes="scrollable-pane"):
                                yield Static(id="project-info-view")
                            with Vertical(id="project-console-container", classes="console-container"):
                                yield Label("Project Console (/help for commands, enter comment directly)", classes="console-label")
                                yield Input(placeholder="Type command or project comment...", id="project-name-input")
                        
                        # Right Column
                        with Vertical(id="project-right-pane", classes="right-column"):
                            with TabbedContent(id="project-tabs"):
                                with TabPane("Comments", id="pane-project-comments"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="project-comments-list")
                                
                                with TabPane("Decisions", id="pane-project-decisions"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="project-decisions-list")
                                
                                with TabPane("Memories", id="pane-project-memories"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="project-memories-list")
                                        
                                with TabPane("Activity Feed", id="pane-project-activity"):
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
        
        self.query_one("#task-tabs", TabbedContent).active = "pane-task-details"
        self.query_one("#project-tabs", TabbedContent).active = "pane-project-comments"
        
        table.focus()
        self.run_worker(self.async_refresh_all(), group="db_sync")

    async def async_refresh_all(self) -> None:
        """Refresh all TUI data asynchronously from the database."""
        tasks = await asyncio.to_thread(self._db_list_tasks)
        
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

        project, all_tasks, project_comments, project_decisions, project_memories, project_events = await asyncio.to_thread(self._db_get_project_details)
        
        # Update Nav Stats
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
        
        self._update_project_hub_ui(project, all_tasks, project_comments, project_decisions, project_memories, project_events)
        await self.async_refresh_task_details()

    def _update_project_hub_ui(self, project: Project, tasks: List[Task], comments: List[Comment], decisions: List[Decision], memories: List[Memory], events: List[Event]) -> None:
        info_box = self.query_one("#project-info-view", Static)
        comments_box = self.query_one("#project-comments-list", Static)
        decisions_box = self.query_one("#project-decisions-list", Static)
        memories_box = self.query_one("#project-memories-list", Static)
        project_log = self.query_one("#project-feed-log", RichLog)

        total_tasks = len(tasks)
        todo_count = sum(1 for t in tasks if t.status == "todo")
        in_progress_count = sum(1 for t in tasks if t.status == "in_progress")
        review_count = sum(1 for t in tasks if t.status == "review")
        done_count = sum(1 for t in tasks if t.status == "done")
        avg_progress = 0
        if total_tasks > 0:
            avg_progress = int(sum(t.progress for t in tasks) / total_tasks)
        assignees = {t.assignee for t in tasks if t.assignee}

        info_table = Table.grid(padding=(0, 2))
        info_table.add_column(style="bold #a1a1aa", width=16)
        info_table.add_column(style="#e4e4e7")
        info_table.add_row("Project Name:", f"[bold #f4f4f5]{project.name}[/bold #f4f4f5]")
        info_table.add_row("Last Updated:", format_datetime(project.updated_at))

        details_content = project.details or "No details provided."
        idea_content = project.overall_idea or "No overall idea recorded."

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
            Rule("Description", style="#3f3f46"),
            Text(f"\n{details_content}\n", style="#e4e4e7"),
            Rule("Overall Idea", style="#3f3f46"),
            Text(f"\n{idea_content}\n", style="#e4e4e7"),
            Rule("Metrics", style="#3f3f46"),
            Text("\n"),
            Panel(stats_table, title="Task Statistics", border_style="#3f3f46")
        )
        info_box.update(Panel(group, title=Text("Project Profile", style="bold #a1a1aa"), border_style="#3f3f46"))

        comment_content = []
        for c in comments:
            comment_content.append(f"[bold #60a5fa]@{c.author}[/bold #60a5fa] [#71717a]({format_datetime(c.created_at)})[/#71717a]\n[#e4e4e7]{c.content}[/#e4e4e7]\n[#323232]──────────────────────────────────────────────────[/#323232]")
        if not comment_content:
            comment_content.append("[italic #71717a]No project comments yet. Type comment directly in the Project Console.[/italic #71717a]")
        comments_box.update("\n".join(comment_content))

        decision_content = []
        for d in decisions:
            decision_content.append(
                f"[bold #f4f4f5]{d.title}[/bold #f4f4f5] [#71717a]by @{d.author} ({format_datetime(d.created_at)})[/#71717a]\n"
                f"[italic #a1a1aa]Context:[/italic #a1a1aa] [#e4e4e7]{d.context}[/#e4e4e7]\n"
                f"[bold #34d399]Decision:[/bold #34d399] [#e4e4e7]{d.decision}[/#e4e4e7]\n"
                f"[#323232]──────────────────────────────────────────────────[/#323232]"
            )
        if not decision_content:
            decision_content.append("[italic #71717a]No project decisions recorded yet. Type `/decision <title> | <ctx> | <dec>` in the console.[/italic #71717a]")
        decisions_box.update("\n".join(decision_content))

        memory_lines = []
        for m in memories:
            memory_lines.append(f"[bold #fbbf24]{m.key}[/bold #fbbf24] = [#e4e4e7]{m.value}[/#e4e4e7] [#71717a]({format_datetime(m.updated_at)})[/#71717a]\n[#323232]──────────────────────────────────────────────────[/#323232]")
        if not memory_lines:
            memory_lines.append("[italic #71717a]No project memories stored yet. Type `/memory <key> = <val>` in the console.[/italic #71717a]")
        memories_box.update("\n".join(memory_lines))

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
        details_box.update(Panel(details_text, title=Text(f"Task #{task.id}", style="bold #a1a1aa"), border_style="#3f3f46"))

        comment_content = []
        for c in comments:
            comment_content.append(f"[bold #60a5fa]@{c.author}[/bold #60a5fa] [#71717a]({format_datetime(c.created_at)})[/#71717a]\n[#e4e4e7]{c.content}[/#e4e4e7]\n[#323232]──────────────────────────────────────────────────[/#323232]")
        if not comment_content:
            comment_content.append("[italic #71717a]No comments yet. Type comments directly in the Workspace Console below.[/italic #71717a]")
        comments_box.update("\n".join(comment_content))

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
            decision_content.append("[italic #71717a]No decisions recorded. Type `/decision <title> | <ctx> | <dec>` in the console.[/italic #71717a]")
        decisions_box.update("\n".join(decision_content))

        task_log.clear()
        for e in reversed(events):
            time_str = format_datetime(e.created_at)
            task_log.write(f"[#71717a][{time_str}][/#71717a] [#22d3ee]@{e.actor}[/#22d3ee] [bold #34d399]{e.event_type.upper()}[/bold #34d399]: [#e4e4e7]{e.details}[/#e4e4e7]")

        self.query_one("#btn-claim", Button).disabled = False
        self.query_one("#btn-status", Button).disabled = False
        self.query_one("#btn-complete", Button).disabled = False

    def _update_empty_details_ui(self) -> None:
        details_box = self.query_one("#details-view", Static)
        comments_box = self.query_one("#task-comments-list", Static)
        decisions_box = self.query_one("#task-decisions-list", Static)
        task_log = self.query_one("#task-feed-log", RichLog)

        panel_text = Text("No tasks found. Use `/create <title> | <desc>` in the console input below.", style="#e4e4e7")
        details_box.update(Panel(panel_text, title=Text("Details", style="bold #a1a1aa"), border_style="#3f3f46"))
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
        if current_tab == "tab-tasks":
            self.query_one("#new-task-title", Input).focus()
        else:
            self.query_one("#project-name-input", Input).focus()

    def action_switch_to_tasks(self) -> None:
        self.query_one("#content-switcher", ContentSwitcher).current = "pane-tasks"
        self.query_one("#nav-tabs", Tabs).active = "tab-tasks"

    def action_switch_to_project(self) -> None:
        self.query_one("#content-switcher", ContentSwitcher).current = "pane-project"
        self.query_one("#nav-tabs", Tabs).active = "tab-project"

    def action_switch_focus(self) -> None:
        # Toggle focus between main panels & console
        focused = self.focused
        if isinstance(focused, DataTable):
            self.action_focus_command()
        else:
            self.query_one("#task-table", DataTable).focus()

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

    # --- Integrated Console Command Handler ---

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        input_id = event.input.id
        val = event.value.strip()
        if not val:
            return

        actor = get_current_actor()
        event.input.value = ""

        # Help menu
        if val == "/help":
            self._show_help_info()
            return
        elif val == "/quit":
            self.exit()
            return
        elif val == "/refresh":
            await self.async_refresh_all()
            self.notify("Database view refreshed.")
            return

        # Commands processing
        if val.startswith("/"):
            parts = val[1:].split(" ", 1)
            cmd = parts[0].lower()
            args = parts[1].strip() if len(parts) > 1 else ""

            if cmd == "create":
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
                
            elif cmd == "claim":
                target_id = self.selected_task_id
                if args:
                    try:
                        target_id = int(args)
                    except ValueError:
                        self.notify("Task ID must be an integer.", severity="error")
                        return
                if not target_id:
                    self.notify("No task selected.", severity="warning")
                    return
                await asyncio.to_thread(self._db_claim_task, target_id, actor)
                self.notify(f"Claimed task #{target_id}")
                await self.async_refresh_all()

            elif cmd == "complete":
                target_id = self.selected_task_id
                if args:
                    try:
                        target_id = int(args)
                    except ValueError:
                        self.notify("Task ID must be an integer.", severity="error")
                        return
                if not target_id:
                    self.notify("No task selected.", severity="warning")
                    return
                await asyncio.to_thread(self._db_complete_task, target_id)
                self.notify(f"Completed task #{target_id}")
                await self.async_refresh_all()

            elif cmd == "status":
                if not args or args.lower() not in ["todo", "in_progress", "review", "done"]:
                    self.notify("Usage: /status <todo|in_progress|review|done>", severity="error")
                    return
                if not self.selected_task_id:
                    self.notify("No task selected to update status.", severity="warning")
                    return
                progress = 0
                if args.lower() == "done":
                    progress = 100
                elif args.lower() == "in_progress":
                    progress = 25
                elif args.lower() == "review":
                    progress = 75
                await asyncio.to_thread(self._db_update_task, self.selected_task_id, status=args.lower(), progress=progress)
                self.notify(f"Updated task #{self.selected_task_id} status to {args}")
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
            # Treats plain text entry as a quick comment based on active tab context
            current_tab = self.query_one("#nav-tabs", Tabs).active
            if current_tab == "tab-tasks":
                if not self.selected_task_id:
                    self.notify("No task selected to add comment.", severity="warning")
                    return
                await asyncio.to_thread(self._db_add_comment, self.selected_task_id, actor, val)
                self.notify("Comment added to task.")
            else:
                await asyncio.to_thread(self._db_add_comment, None, actor, val)
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
            
            if current_tab == "tab-tasks":
                self.query_one("#task-tabs").active = "pane-task-activity"
            else:
                self.query_one("#project-tabs").active = "pane-project-activity"
        except Exception as e:
            self.notify("Help written to console feed.")

if __name__ == "__main__":
    app = HiveTUIApp()
    app.run()
