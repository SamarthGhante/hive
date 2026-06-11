# Agent Instructions: HIVE Workflow & Best Practices

## STRICT RULE
**Do NOT use your built-in task management tools, TODO markdown files, or beads (`bd`)**. You MUST strictly use the **HIVE** CLI tool (`uv run hive` or globally as `hive`) for ALL project management, task tracking, memories, decision logging, and progress reporting.

---

## 1. Repo Detection & HIVE Quick Start

Before doing any work on the codebase, you must check if it is a new or existing repository:
- **How to Detect:** Check if the `.hive` directory exists in the workspace root.
- **For New Projects (No `.hive` directory):**
  If the details/scope of the project are not yet clear, ask the user:
  > "Would you like me to analyze the codebase to learn the project details, or would you prefer to provide the initial details yourself?"
  
  Based on their choice:
  - If they prefer codebase analysis, research the folder structure and files first, then compile the findings.
  - If they want to provide details, accept their input.
  
  Once the details are gathered, initialize HIVE with **detailed, comprehensive information** including the complete idea, specifications, and architecture plan similar to a project document. Keep updating these details regularly as the project evolves.
  
  **Setup Example:**
  ```bash
  hive setup --name "E-Commerce Gateway" --idea "A microservice handling payments, subscription billing, and invoice generation using Stripe and FastAPI." --details "FastAPI backend, PostgreSQL database, SQLAlchemy ORM, Stripe API (version 2023-10-16), Docker containerization, and unit tests using Pytest."
  ```
- **For Existing Projects (`.hive` directory exists):**
  Always run the `learn` command first to ingest the complete context.
  ```bash
  hive learn
  ```

---

## 2. HIVE Detailed Command Reference

### Project Level Commands
Used to maintain the high-level scope and state of the project.
- `hive setup --name "..." --details "..." --idea "..."`: Initialize or update project info. Use detailed plans for ideas/details.
- `hive status "..."`: Update the project's overall progress summary.
  - **Best Practice:** Run this after *every* major milestone to keep track of the overall completion state.
- `hive learn`: Dumps all comments, decisions, active tasks, memories, and activity feed. Run this frequently to avoid missing updates.

### Task Management Commands
Break down work into granular tasks. First establish all tasks and their dependencies before writing code.
- `hive task-add "Setup Database" --desc "Use SQLite"`: Create a new task.
- `hive task-list`: List all tasks.
- `hive task-update <TASK_ID> --claim --progress 50`: Assign a task to yourself, mark it `in_progress`, and set progress to an approximate value.
  - **Best Practice:** Regularly update task progress to approximate values as you make headway. Keep adding comments to the tasks regularly while working to document intermediate progress.
- `hive task-update <TASK_ID> --status done --progress 100`: Mark the task as 100% done.
- `hive task-show <TASK_ID>`: View task dependencies, comments, and decisions.

### Dependencies
Always define the order of execution.
- `hive dep-add <TASK_ID> <DEPENDS_ON_ID>`: Block `<TASK_ID>` until `<DEPENDS_ON_ID>` is complete.

### Decisions & Collaboration
Log all architectural and design decisions so future agents understand *why* something was done.
- `hive log-decision "Use SQLModel" "Need an ORM" "Selected SQLModel for FastAPI integration" --task <TASK_ID>`: Log a decision specific to a task.
- `hive log-decision "Architecture" "Monolith vs Microservices" "Monolith"`: Log a project-level decision.

### Comments & Progress Updates
Leave notes for yourself or the next agent.
- `hive log-comment "Detailed progress report..." --task <TASK_ID>`: Task specific comment.
  - **CRITICAL RULE:** The comments MUST be detailed. You must add at least one detailed comment per task while closing the task (`--status done`) to summarize exactly what was implemented, changed, or tested under that task.
- `hive log-comment "Need user feedback on the UI"`: Project level comment.

### Memories (Preferences & Constraints)
If the user tells you a preference (e.g., "Always use black for formatting" or "No Tailwind"), record it immediately so it is never forgotten.
- `hive log-memory "Styling" "Use raw CSS, NO Tailwind"`
- `hive log-memory "Testing" "Pytest with 90% coverage"`

### Activity Feed
To see a timeline of what agents and users have done.
- `hive feed --limit 20`
- `hive feed --task <TASK_ID>`

---

## 3. The Complete Agent Workflow

Follow this step-by-step loop for every task:
1. **Learn:** `hive learn`
2. **Plan:** Break down goals using `hive task-add` and link them using `hive dep-add`.
3. **Claim:** Claim the next unblocked task using `hive task-update <TASK_ID> --claim`.
4. **Execute:** Write code, run tests.
5. **Update & Comment:** Run `hive task-update <TASK_ID> --progress <approx_val>` halfway through and log progress comments regularly.
6. **Record:** Use `hive log-decision` or `hive log-memory` if you make an important architectural choice or learn a user preference.
7. **Complete & Summarize:** Log a **detailed final comment** summarizing all changes made for the task, then mark the task complete: `hive task-update <TASK_ID> --status done --progress 100`.
8. **Project Sync:** If completing this task represents a major step forward, update the overall project progress: `hive status "Completed backend DB integration"`.
9. **Repeat:** Move to the next task.

---

## 4. Error Fallback Handling

If you encounter any operational or system error with the HIVE CLI or its database during execution:
1. Log the error details in the agent transcript/output.
2. Ask the user explicitly:
   > "HIVE encountered an error: [Error details]. Would you like to retry the operation or continue working without HIVE tracking?"
3. Proceed according to the user's choice.

