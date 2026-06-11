import asyncio
from typing import Optional, List, Tuple

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
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
    TITLE = "HIVE"
    SUBTITLE = "Collaborative Project Coordination Engine"
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("tab", "switch_focus", "Focus Tab"),
        ("c", "claim_selected", "Claim"),
        ("s", "cycle_status", "Cycle Status"),
        ("t", "switch_to_tasks", "Tasks"),
        ("p", "switch_to_project", "Project"),
    ]

    CSS = """
    /* Premium Minimalist Stylesheet */
    $background: #000000;   /* Black background */
    $surface: #121212;      /* Dark gray card surface */
    $panel: #1e1e1e;        /* Elevated elements / inputs */
    $primary: #ffffff;      /* Primary text - white */
    $secondary: #8e8e93;    /* Secondary muted text */
    $accent: #60a5fa;       /* Blue accent */
    $border: #2c2c2e;       /* Clean border tone */
    
    $success: #34d399;      /* Emerald */
    $warning: #fbbf24;      /* Amber */
    $error: #f87171;        /* Rose */

    Screen {
        background: $background;
        color: $primary;
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
        content-align: center middle;
        width: 100%;
        padding: 0 2;
        background: $background;
        text-style: italic;
    }

    #app-container {
        height: 1fr;
        width: 100%;
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
        background: #fbbf24 25%; /* Yellow highlight color */
        color: $primary;
        text-style: bold;
    }

    DataTable > .datatable--hover {
        background: $panel;
    }

    /* Form and Input styling */
    .form-container {
        height: auto;
        border-top: solid $border;
        margin-top: 1;
        layout: vertical;
        background: $surface;
        padding: 1 0 0 0;
    }

    .form-label {
        color: $secondary;
        text-style: italic;
        margin-bottom: 0;
    }

    Input {
        background: $panel;
        border: tall $border;
        color: $primary;
        margin: 0 0 1 0;
    }

    Input:focus {
        border: tall $accent;
    }

    /* Input box pane inside tab scrolls */
    .input-box-pane {
        height: auto;
        border-top: solid $border;
        background: $surface;
        padding: 1 0 0 0;
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

    /* Styles for centered placeholder texts */
    .placeholder-style {
        background: #1c1c1e;
        color: #ffffff;
        content-align: center middle;
        height: 100%;
        text-align: center;
        text-style: italic;
        padding: 2;
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
        yield Header(show_clock=True)
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
                            with Vertical(id="new-task-form", classes="form-container"):
                                yield Label("Quick Create Task", classes="form-label")
                                yield Input(placeholder="Task title (Enter to description)...", id="new-task-title")
                                yield Input(placeholder="Description (Enter to type)...", id="new-task-desc")
                                yield Input(placeholder="Type: feature, bug, issue, chore (Enter to create)...", id="new-task-type", value="feature")
                        
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
                                        yield Button("Unclaim", id="btn-unclaim", classes="action-btn")
                                        yield Button("Reopen", id="btn-reopen", classes="action-btn")
                                
                                with TabPane("Comments", id="pane-task-comments"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="task-comments-list")
                                    with Vertical(classes="input-box-pane"):
                                        yield Label("Add Comment", classes="form-label")
                                        yield Input(placeholder="Type comment, press Enter...", id="new-task-comment-input")
                                
                                with TabPane("Decisions", id="pane-task-decisions"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="task-decisions-list")
                                    with Vertical(classes="input-box-pane"):
                                        yield Label("Record Decision", classes="form-label")
                                        yield Input(placeholder="Title (Enter to context)...", id="task-dec-title")
                                        yield Input(placeholder="Context (Enter to decision)...", id="task-dec-context")
                                        yield Input(placeholder="Decision (Enter to record)...", id="task-dec-text")
                                
                                with TabPane("Activity Feed", id="pane-task-activity"):
                                    yield RichLog(id="task-feed-log", highlight=True, markup=True)
                                    
                    # Project Hub Pane
                    with Horizontal(id="pane-project", classes="page-container"):
                        # Left Column
                        with Vertical(id="project-left-pane", classes="left-column"):
                            yield Label("Project Profile", classes="section-title")
                            with VerticalScroll(classes="scrollable-pane"):
                                yield Static(id="project-info-view")
                            with Vertical(id="project-update-form", classes="form-container"):
                                yield Label("Update Project Info", classes="form-label")
                                yield Input(placeholder="Project Name (Enter to details)...", id="project-name-input")
                                yield Input(placeholder="Details (Enter to overall idea)...", id="project-details-input")
                                yield Input(placeholder="Overall Idea (Enter to progress)...", id="project-idea-input")
                                yield Input(placeholder="Progress Summary (Enter to save)...", id="project-progress-input")
                        
                        # Right Column
                        with Vertical(id="project-right-pane", classes="right-column"):
                            with TabbedContent(id="project-tabs"):
                                with TabPane("Comments", id="pane-project-comments"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="project-comments-list")
                                    with Vertical(classes="input-box-pane"):
                                        yield Label("Add Project Comment", classes="form-label")
                                        yield Input(placeholder="Type comment, press Enter...", id="new-project-comment-input")
                                
                                with TabPane("Decisions", id="pane-project-decisions"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="project-decisions-list")
                                    with Vertical(classes="input-box-pane"):
                                        yield Label("Record Project Decision", classes="form-label")
                                        yield Input(placeholder="Title (Enter to context)...", id="project-dec-title")
                                        yield Input(placeholder="Context (Enter to decision)...", id="project-dec-context")
                                        yield Input(placeholder="Decision (Enter to record)...", id="project-dec-text")
                                
                                with TabPane("Memories", id="pane-project-memories"):
                                    with VerticalScroll(classes="scrollable-pane"):
                                        yield Static(id="project-memories-list")
                                    with Vertical(classes="input-box-pane"):
                                        yield Label("Record Project Memory", classes="form-label")
                                        yield Input(placeholder="Key (Enter to value)...", id="project-mem-key")
                                        yield Input(placeholder="Value (Enter to save)...", id="project-mem-val")
                                        
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

    def _db_unclaim_task(self, task_id: int) -> None:
        with get_session() as session:
            crud.update_task(session, task_id, assignee="unassigned", status="todo", progress=0)

    def _db_reopen_task(self, task_id: int) -> None:
        with get_session() as session:
            crud.update_task(session, task_id, status="todo", progress=0)

    def _db_create_task(self, title: str, description: Optional[str], task_type: str = "feature") -> None:
        with get_session() as session:
            crud.create_task(session, title=title, description=description, task_type=task_type)

    def _db_add_comment(self, task_id: Optional[int], author: str, content: str) -> None:
        with get_session() as session:
            crud.add_comment(session, task_id, author, content)

    def _db_add_decision(self, task_id: Optional[int], title: str, context: str, decision: str, author: str) -> None:
        with get_session() as session:
            crud.add_decision(session, task_id, title, context, decision, author)

    def _db_add_memory(self, key: str, value: str) -> None:
        with get_session() as session:
            crud.add_memory(session, key, value)

    def _db_update_project(self, name: Optional[str], details: Optional[str], overall_idea: Optional[str], progress: Optional[str]) -> None:
        with get_session() as session:
            crud.update_project(session, name=name, details=details, overall_idea=overall_idea, progress=progress)

    # --- UI rendering / Reactive sync ---

    def on_mount(self) -> None:
        self.dark = True
        self.is_refreshing = False
        table = self.query_one("#task-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(
            "[#a1a1aa]ID[/#a1a1aa]",
            "[#a1a1aa]Title[/#a1a1aa]",
            "[#a1a1aa]Type[/#a1a1aa]",
            "[#a1a1aa]Status[/#a1a1aa]",
            "[#a1a1aa]Priority[/#a1a1aa]",
            "[#a1a1aa]Progress[/#a1a1aa]",
            "[#a1a1aa]Assignee[/#a1a1aa]"
        )
        
        self.query_one("#task-tabs", TabbedContent).active = "pane-task-details"
        self.query_one("#project-tabs", TabbedContent).active = "pane-project-comments"
        
        table.focus()
        self.run_worker(self.async_refresh_all(), group="db_sync")
        
        # Set up polling interval to auto update TUI when things change
        self.set_interval(3.0, self.auto_refresh)

    def auto_refresh(self) -> None:
        self.run_worker(self.async_refresh_all(), group="db_sync")

    async def async_refresh_all(self) -> None:
        """Refresh all TUI data asynchronously from the database."""
        self.is_refreshing = True
        try:
            tasks = await asyncio.to_thread(self._db_list_tasks)
            
            table = self.query_one("#task-table", DataTable)
            table.clear()
            
            prev_selected_id = self.selected_task_id
            
            for t in tasks:
                status_color = {"todo": "#a1a1aa", "in_progress": "#60a5fa", "review": "#fbbf24", "done": "#34d399"}.get(t.status.lower(), "#e4e4e7")
                status_str = f"[{status_color}]{format_status(t.status)}[/{status_color}]"
                
                prio_color = {0: "#fca5a5", 1: "#fca5a5", 2: "#fde047", 3: "#93c5fd", 4: "#a1a1aa"}.get(t.priority, "#e4e4e7")
                priority_str = f"[{prio_color}]{format_priority(t.priority)}[/{prio_color}]"
                
                type_color = {"feature": "#a7f3d0", "bug": "#f87171", "issue": "#fbbf24", "chore": "#e4e4e7"}.get(t.task_type.lower(), "#e4e4e7")
                type_str = f"[{type_color}]{t.task_type.upper()}[/{type_color}]"
                
                assignee_str = f"[#22d3ee]@{t.assignee}[/#22d3ee]" if t.assignee else "[#71717a]-[/#71717a]"
                id_str = f"[bold #f4f4f5]#{t.id}[/bold #f4f4f5]"
                title_str = f"[strike][#71717a]{t.title}[/#71717a][/strike]" if t.status.lower() == "done" else f"[#e4e4e7]{t.title}[/#e4e4e7]"
                
                progress_color = "#34d399" if t.progress == 100 else "#60a5fa" if t.progress > 0 else "#a1a1aa"
                progress_str = f"[{progress_color}]{t.progress}%[/{progress_color}]"
                
                table.add_row(
                    id_str,
                    title_str,
                    type_str,
                    status_str,
                    priority_str,
                    progress_str,
                    assignee_str,
                    key=str(t.id)
                )
                
            if prev_selected_id and any(t.id == prev_selected_id for t in tasks):
                try:
                    table.move_cursor(row=table.find_row(str(prev_selected_id)))
                    self.selected_task_id = prev_selected_id
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
        finally:
            self.is_refreshing = False

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
        progress_content = project.progress or "No progress recorded yet."

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
            Rule("Description", style="#2c2c2e"),
            Text(f"\n{details_content}\n", style="#e4e4e7"),
            Rule("Overall Idea", style="#2c2c2e"),
            Text(f"\n{idea_content}\n", style="#e4e4e7"),
            Rule("Progress", style="#2c2c2e"),
            Text(f"\n{progress_content}\n", style="#e4e4e7"),
            Rule("Metrics", style="#2c2c2e"),
            Text("\n"),
            Panel(stats_table, title="Task Statistics", border_style="#2c2c2e")
        )
        info_box.update(Panel(group, title=Text("Project Profile", style="bold #a1a1aa"), border_style="#2c2c2e"))

        # Populate forms metadata if empty
        name_input = self.query_one("#project-name-input", Input)
        details_input = self.query_one("#project-details-input", Input)
        idea_input = self.query_one("#project-idea-input", Input)
        if not name_input.value:
            name_input.value = project.name
        if not details_input.value:
            details_input.value = project.details or ""
        progress_input = self.query_one("#project-progress-input", Input)
        if not idea_input.value:
            idea_input.value = project.overall_idea or ""
        if not progress_input.value:
            progress_input.value = project.progress or ""

        comment_content = []
        for c in comments:
            comment_content.append(f"[bold #60a5fa]@{c.author}[/] [#71717a]({format_datetime(c.created_at)})[/#71717a]\n[#e4e4e7]{c.content}[/#e4e4e7]\n[#323232]──────────────────────────────────────────────────[/#323232]")
        if not comment_content:
            comment_content.append("[italic #71717a]No project comments yet. Type in the form below to add one.[/italic #71717a]")
        
        # Centerized placeholder logic if no comments
        if not comments:
            comments_box.update(Text("\n\nNo project comments yet.\n\nType in the form below to add one.", style="white"))
            comments_box.set_class(True, "placeholder-style")
        else:
            comments_box.update("\n".join(comment_content))
            comments_box.set_class(False, "placeholder-style")

        decision_content = []
        for d in decisions:
            decision_content.append(
                f"[bold #f4f4f5]{d.title}[/bold #f4f4f5] [#71717a]by @{d.author} ({format_datetime(d.created_at)})[/#71717a]\n"
                f"[italic #a1a1aa]Context:[/italic #a1a1aa] [#e4e4e7]{d.context}[/#e4e4e7]\n"
                f"[bold #34d399]Decision:[/bold #34d399] [#e4e4e7]{d.decision}[/#e4e4e7]\n"
                f"[#323232]──────────────────────────────────────────────────[/#323232]"
            )
        
        if not decisions:
            decisions_box.update(Text("\n\nNo project decisions recorded yet.\n\nRecord one using the form below.", style="white"))
            decisions_box.set_class(True, "placeholder-style")
        else:
            decisions_box.update("\n".join(decision_content))
            decisions_box.set_class(False, "placeholder-style")

        memory_lines = []
        for m in memories:
            memory_lines.append(f"[bold #fbbf24]{m.key}[/bold #fbbf24] = [#e4e4e7]{m.value}[/#e4e4e7] [#71717a]({format_datetime(m.updated_at)})[/#71717a]\n[#323232]──────────────────────────────────────────────────[/#323232]")
        
        if not memories:
            memories_box.update(Text("\n\nNo project memories stored yet.\n\nAdd one using the form below.", style="white"))
            memories_box.set_class(True, "placeholder-style")
        else:
            memories_box.update("\n".join(memory_lines))
            memories_box.set_class(False, "placeholder-style")

        project_log.clear()
        for e in reversed(events):
            time_str = format_datetime(e.created_at)
            task_part = f" [#60a5fa]#{e.task_id}[/] " if e.task_id else ""
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
        type_color = {"feature": "#a7f3d0", "bug": "#f87171", "issue": "#fbbf24", "chore": "#e4e4e7"}.get(task.task_type.lower(), "#e4e4e7")

        details_text = Text.assemble(
            ("Task Title:  ", "bold #a1a1aa"), (f"{task.title}\n", "#e4e4e7"),
            ("Description: ", "bold #a1a1aa"), (f"{task.description or 'No description'}\n\n", "#e4e4e7"),
            ("Type:        ", "bold #a1a1aa"), (task.task_type.upper(), type_color), ("  |  ", "#a1a1aa"),
            ("Status:      ", "bold #a1a1aa"), (format_status(task.status), status_theme), ("  |  ", "#a1a1aa"),
            ("Priority:    ", "bold #a1a1aa"), (format_priority(task.priority), prio_theme), ("\n", "#a1a1aa"),
            ("Progress:    ", "bold #a1a1aa"), (f"{task.progress}%\n", "#e4e4e7"),
            ("Assignee:    ", "bold #a1a1aa"), ("@" + task.assignee if task.assignee else "Unassigned", "#34d399"), ("\n", "#a1a1aa"),
            ("Created:     ", "bold #a1a1aa"), (f"{format_datetime(task.created_at)}\n", "#e4e4e7"),
            ("Updated:     ", "bold #a1a1aa"), (f"{format_datetime(task.updated_at)}", "#e4e4e7")
        )
        details_box.update(Panel(details_text, title=Text(f"Task #{task.id}", style="bold #a1a1aa"), border_style="#2c2c2e"))

        # Comments
        comment_content = []
        for c in comments:
            comment_content.append(f"[bold #60a5fa]@{c.author}[/] [#71717a]({format_datetime(c.created_at)})[/#71717a]\n[#e4e4e7]{c.content}[/#e4e4e7]\n[#323232]──────────────────────────────────────────────────[/#323232]")
        
        if not comments:
            comments_box.update(Text("\n\nNo comments yet.\n\nType in the form below to add one.", style="white"))
            comments_box.set_class(True, "placeholder-style")
        else:
            comments_box.update("\n".join(comment_content))
            comments_box.set_class(False, "placeholder-style")

        # Decisions
        decision_content = []
        if decisions:
            decision_content.append("[bold underline #34d399]Task Decisions:[/bold underline #34d399]")
            for d in decisions:
                decision_content.append(
                    f"[bold #f4f4f5][{d.id}] {d.title}[/bold #f4f4f5] [#71717a]by @{d.author} ({format_datetime(d.created_at)})[/#71717a]\n"
                    f"[italic #a1a1aa]Context:[/italic #a1a1aa] [#e4e4e7]{d.context}[/#e4e4e7]\n"
                    f"[bold #34d399]Decision:[/bold #34d399] [#e4e4e7]{d.decision}[/#e4e4e7]\n"
                    f"[#323232]──────────────────────────────────────────────────[/#323232]"
                )
        
        if not decisions:
            decisions_box.update(Text("\n\nNo decisions recorded for this task yet.\n\nRecord one using the form below.", style="white"))
            decisions_box.set_class(True, "placeholder-style")
        else:
            decisions_box.update("\n".join(decision_content))
            decisions_box.set_class(False, "placeholder-style")

        # Feed
        task_log.clear()
        for e in reversed(events):
            time_str = format_datetime(e.created_at)
            task_log.write(f"[#71717a][{time_str}][/#71717a] [#22d3ee]@{e.actor}[/#22d3ee] [bold #34d399]{e.event_type.upper()}[/bold #34d399]: [#e4e4e7]{e.details}[/#e4e4e7]")

        is_done = task.status.lower() == "done"
        has_assignee = task.assignee is not None
        self.query_one("#btn-claim", Button).disabled = is_done
        self.query_one("#btn-status", Button).disabled = is_done
        self.query_one("#btn-complete", Button).disabled = is_done
        self.query_one("#btn-unclaim", Button).disabled = is_done or not has_assignee
        self.query_one("#btn-reopen", Button).disabled = not is_done

    def _update_empty_details_ui(self) -> None:
        details_box = self.query_one("#details-view", Static)
        comments_box = self.query_one("#task-comments-list", Static)
        decisions_box = self.query_one("#task-decisions-list", Static)
        task_log = self.query_one("#task-feed-log", RichLog)

        details_box.update(Text("\n\nNo tasks found.\n\nUse the Quick Create form on the left to create a task.", style="white"))
        details_box.set_class(True, "placeholder-style")

        comments_box.update(Text("\n\nNo task selected.", style="white"))
        comments_box.set_class(True, "placeholder-style")

        decisions_box.update(Text("\n\nNo task selected.", style="white"))
        decisions_box.set_class(True, "placeholder-style")

        task_log.clear()
        task_log.write("[italic #71717a]No task selected.[/italic #71717a]")

        self.query_one("#btn-claim", Button).disabled = True
        self.query_one("#btn-status", Button).disabled = True
        self.query_one("#btn-complete", Button).disabled = True
        self.query_one("#btn-unclaim", Button).disabled = True
        self.query_one("#btn-reopen", Button).disabled = True

    # --- Interactive Event Handlers ---

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if getattr(self, "is_refreshing", False):
            return
        row_key = event.row_key.value
        if row_key:
            new_id = int(row_key)
            if new_id != self.selected_task_id:
                self.selected_task_id = new_id
                self.run_worker(self.async_refresh_task_details(), group="db_sync")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if getattr(self, "is_refreshing", False):
            return
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
        # Toggle focus between main panels & inputs
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
        elif btn_id == "btn-unclaim":
            if not self.selected_task_id:
                self.notify("No task selected.", severity="warning")
                return
            self.run_worker(self.async_unclaim_task(self.selected_task_id), group="db_sync")
        elif btn_id == "btn-reopen":
            if not self.selected_task_id:
                self.notify("No task selected.", severity="warning")
                return
            self.run_worker(self.async_reopen_task(self.selected_task_id), group="db_sync")

    async def async_complete_task(self, task_id: int) -> None:
        await asyncio.to_thread(self._db_complete_task, task_id)
        self.notify(f"Completed task #{task_id}")
        await self.async_refresh_all()

    async def async_unclaim_task(self, task_id: int) -> None:
        await asyncio.to_thread(self._db_unclaim_task, task_id)
        self.notify(f"Unclaimed/reopened task #{task_id}")
        await self.async_refresh_all()

    async def async_reopen_task(self, task_id: int) -> None:
        await asyncio.to_thread(self._db_reopen_task, task_id)
        self.notify(f"Reopened task #{task_id}")
        await self.async_refresh_all()

    # --- Interactive Form Event Handlers ---

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        input_id = event.input.id
        val = event.value.strip()
        
        # 1. Quick Task Create Form
        if input_id == "new-task-title":
            if val:
                self.query_one("#new-task-desc", Input).focus()
        elif input_id == "new-task-desc":
            self.query_one("#new-task-type", Input).focus()
        elif input_id == "new-task-type":
            title = self.query_one("#new-task-title", Input).value.strip()
            desc = self.query_one("#new-task-desc", Input).value.strip()
            task_type = val or "feature"
            if not title:
                self.notify("Task title is required.", severity="error")
                return
            if task_type.lower() not in ["feature", "bug", "issue", "chore"]:
                self.notify("Type must be: feature, bug, issue, or chore.", severity="error")
                return
            self.query_one("#new-task-title", Input).value = ""
            self.query_one("#new-task-desc", Input).value = ""
            event.input.value = "feature"
            self.query_one("#new-task-title", Input).focus()
            self.run_worker(self.async_create_task(title, desc, task_type), group="db_sync")
            
        # 2. Add Task Comment Form
        elif input_id == "new-task-comment-input":
            if not val:
                return
            if not self.selected_task_id:
                self.notify("No task selected.", severity="warning")
                return
            event.input.value = ""
            self.run_worker(self.async_add_comment(self.selected_task_id, val), group="db_sync")
            
        # 3. Add Task Decision Form
        elif input_id == "task-dec-title":
            if val:
                self.query_one("#task-dec-context", Input).focus()
        elif input_id == "task-dec-context":
            if val:
                self.query_one("#task-dec-text", Input).focus()
        elif input_id == "task-dec-text":
            title = self.query_one("#task-dec-title", Input).value.strip()
            context = self.query_one("#task-dec-context", Input).value.strip()
            if not title or not val:
                self.notify("Decision title and details are required.", severity="error")
                return
            self.query_one("#task-dec-title", Input).value = ""
            self.query_one("#task-dec-context", Input).value = ""
            event.input.value = ""
            self.query_one("#task-dec-title", Input).focus()
            self.run_worker(self.async_add_decision(self.selected_task_id, title, context, val), group="db_sync")
            
        # 4. Project Update Metadata Form
        elif input_id == "project-name-input":
            if val:
                self.query_one("#project-details-input", Input).focus()
        elif input_id == "project-details-input":
            if val:
                self.query_one("#project-idea-input", Input).focus()
        elif input_id == "project-idea-input":
            if val:
                self.query_one("#project-progress-input", Input).focus()
        elif input_id == "project-progress-input":
            name = self.query_one("#project-name-input", Input).value.strip()
            details = self.query_one("#project-details-input", Input).value.strip()
            idea = self.query_one("#project-idea-input", Input).value.strip()
            self.run_worker(self.async_update_project(name, details, idea, val), group="db_sync")
            self.query_one("#project-name-input", Input).focus()
            
        # 5. Add Project Comment Form
        elif input_id == "new-project-comment-input":
            if not val:
                return
            event.input.value = ""
            self.run_worker(self.async_add_comment(None, val), group="db_sync")
            
        # 6. Add Project Decision Form
        elif input_id == "project-dec-title":
            if val:
                self.query_one("#project-dec-context", Input).focus()
        elif input_id == "project-dec-context":
            if val:
                self.query_one("#project-dec-text", Input).focus()
        elif input_id == "project-dec-text":
            title = self.query_one("#project-dec-title", Input).value.strip()
            context = self.query_one("#project-dec-context", Input).value.strip()
            if not title or not val:
                self.notify("Decision title and details are required.", severity="error")
                return
            self.query_one("#project-dec-title", Input).value = ""
            self.query_one("#project-dec-context", Input).value = ""
            event.input.value = ""
            self.query_one("#project-dec-title", Input).focus()
            self.run_worker(self.async_add_decision(None, title, context, val), group="db_sync")
            
        # 7. Add Project Memory Form
        elif input_id == "project-mem-key":
            if val:
                self.query_one("#project-mem-val", Input).focus()
        elif input_id == "project-mem-val":
            key = self.query_one("#project-mem-key", Input).value.strip()
            if not key or not val:
                self.notify("Memory key and value are required.", severity="error")
                return
            self.query_one("#project-mem-key", Input).value = ""
            event.input.value = ""
            self.query_one("#project-mem-key", Input).focus()
            self.run_worker(self.async_add_memory(key, val), group="db_sync")

    # --- Async operations connected to database helper threads ---

    async def async_create_task(self, title: str, description: Optional[str], task_type: str = "feature") -> None:
        await asyncio.to_thread(self._db_create_task, title, description, task_type)
        self.notify(f"Created task: {title}")
        await self.async_refresh_all()

    async def async_add_comment(self, task_id: Optional[int], content: str) -> None:
        actor = get_current_actor()
        await asyncio.to_thread(self._db_add_comment, task_id, actor, content)
        self.notify("Added comment successfully.")
        await self.async_refresh_all()

    async def async_add_decision(self, task_id: Optional[int], title: str, context: str, decision: str) -> None:
        actor = get_current_actor()
        await asyncio.to_thread(self._db_add_decision, task_id, title, context, decision, actor)
        self.notify("Decision recorded successfully.")
        await self.async_refresh_all()

    async def async_update_project(self, name: str, details: str, overall_idea: str, progress: str) -> None:
        await asyncio.to_thread(self._db_update_project, name, details, overall_idea, progress)
        self.notify("Project info updated successfully.")
        await self.async_refresh_all()

    async def async_add_memory(self, key: str, value: str) -> None:
        await asyncio.to_thread(self._db_add_memory, key, value)
        self.notify(f"Memory '{key}' saved.")
        await self.async_refresh_all()

if __name__ == "__main__":
    app = HiveTUIApp()
    app.run()
