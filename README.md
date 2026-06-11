# HIVE 🐝

**HIVE** is an ultra-fast, local-first collaborative execution, coordination, and memory layer explicitly built for both human developers and autonomous AI coding agents. 

HIVE tracks tasks, logs architectural decisions, builds dependency graphs, and stores context memories across the lifecycle of a project—all backed by a blazing-fast local SQLite database and an interactive TUI (Terminal User Interface).

## Installation

HIVE is built as a global developer CLI tool and is distributed perfectly through `uv`:

```bash
uv tool install git+https://github.com/your-username/hive.git
```
*(If you do not have `uv`, you can also use `pipx install git+https://github.com/your-username/hive.git`)*

Once installed, the `hive` command will be securely available in any terminal window.

## Quick Start
To set up HIVE in your current project repository:
```bash
hive setup --name "My Project" --idea "Building an AI assistant"
```

To see the interactive Dashboard:
```bash
hive tui
```

## CLI Usage (Optimized for AI Agents)
HIVE's CLI commands are deliberately flattened and hyphenated to make it as easy as possible for autonomous LLM agents to use without syntax errors.

### Project & Context
- `hive setup --name "..." --details "..." --idea "..."`: Initialize or update project metadata.
- `hive status "..."`: Update the project's overall progress summary.
- `hive learn`: Dumps the **entire** project state (tasks, memories, comments, decisions) so an AI Agent can rapidly ingest the context.

### Task Management
- `hive task-add "Build Database" --desc "Use SQLite"`
- `hive task-list`
- `hive task-update <ID> --status in_progress --progress 50`
- `hive task-update <ID> --status done --progress 100`
- `hive task-show <ID>`

### Dependencies
- `hive dep-add <DEPENDENT_TASK_ID> <BLOCKER_TASK_ID>`: Block one task until another is finished.

### Collaboration & Logging
- `hive log-decision "Architecture" "Need an ORM" "Selected SQLModel"`: Log a project-level decision.
- `hive log-comment "I am stuck on this feature" --task <ID>`: Log a task comment.
- `hive log-memory "Styling" "Use raw CSS, NO Tailwind"`: Store long-term preferences and constraints.

### Activity
- `hive feed`: View the recent timeline of all actions taken by humans and agents.
