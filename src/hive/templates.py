AGENTS_TEMPLATE = """# Agent Instructions: HIVE Workflow & Best Practices

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
- `hive task-add "Setup Database" --desc "Use SQLite" --type [feature|bug|issue|chore]`: Create a new task.
  * **Guidelines and Examples for Task Types:**
    * `feature`: For implementing new functional capabilities, user interfaces, endpoints, or modules.
      * *Example:* `hive task-add "Add email verification flow" --desc "Send magic link via Resend API and verify token on redirect" --type feature`
    * `bug`: For resolving unintended behaviors, crashes, validation failures, or incorrect state transitions.
      * *Example:* `hive task-add "Fix DataTable cursor jumps on refresh" --desc "Ensure row highlight doesn't jump to row 0 during poll interval" --type bug`
    * `issue`: For tracking user feedback, semantic issues, research tasks, security vulnerabilities, or performance investigations.
      * *Example:* `hive task-add "Investigate API latency spikes" --desc "Analyze database queries and index coverage under load" --type issue`
    * `chore`: For refactorings, updating dependency versions, adding/fixing tests, cleanup, or documentation updates.
      * *Example:* `hive task-add "Migrate Pytest fixtures to conftest.py" --desc "Move reusable DB and CLI test configurations" --type chore`
- `hive task-list`: List all tasks.
- `hive task-update <TASK_ID> --claim --progress 50`: **(ALWAYS claim first before starting work)** Assign a task to yourself, mark it `in_progress`, and set progress to an approximate value.
  - **Best Practice for Large Tasks:** If the task is too large, keep updating the task progress regularly (e.g. at 25%, 50%, 75%) while still working on it, adding comments to document intermediate progress.
- `hive task-update <TASK_ID> --status done --progress 100`: Mark the task as 100% done (only for absolute, self-contained setups).
- `hive task-show <TASK_ID>`: View task dependencies, comments, and decisions.

### Dependencies
Always define the order of execution.
- `hive dep-add <TASK_ID> <DEPENDS_ON_ID>`: Block `<TASK_ID>` until `<DEPENDS_ON_ID>` is complete.

### Decisions & Collaboration
Log all architectural and design decisions so future agents understand *why* something was done.
- `hive log-decision "Use SQLModel" "Need an ORM" "Selected SQLModel for FastAPI integration" --task <TASK_ID>`: Log a decision specific to a task.
- `hive log-decision "Architecture" "Monolith vs Microservices" "Monolith"`: Log a project-level decision.
- `hive edit-decision <DECISION_ID> [--title "..."] [--context "..."] [--decision "..."]`: Edit or update an existing decision by its ID.

### Comments & Progress Updates
Leave notes for yourself or the next agent.
- `hive log-comment "Detailed progress report..." --task <TASK_ID>`: Task-specific comment.
  - **CRITICAL RULE:** Task-related comments must only be logged as task-level comments (using `--task <TASK_ID>`).
  - **CRITICAL RULE:** The comments MUST be detailed. You must add at least one detailed comment per task while closing the task (`--status done`) to summarize exactly what was implemented, changed, or tested under that task.
- `hive log-comment "Need user feedback on the UI"`: Project-level comment.

### Memories (Preferences & Constraints)
If the user tells you a preference (e.g., "Always use black for formatting" or "No Tailwind"), record it immediately so it is never forgotten.
- `hive log-memory "Styling" "Use raw CSS, NO Tailwind"`
- `hive log-memory "Testing" "Pytest with 90% coverage"`

### Activity Feed
To see a timeline of what agents and users have done.
- `hive feed --limit 20`
- `hive feed --task <TASK_ID>`

---

## 3. The Complete Agent Workflow & Claiming Rules

Follow this step-by-step loop for every task:
1. **Learn:** `hive learn`
2. **Plan:** Break down goals using `hive task-add` and link them using `hive dep-add`.
3. **Claim First:** **ALWAYS claim the task first** before making any modifications or writing code. Run `hive task-update <TASK_ID> --claim`.
4. **Execute:** Write code, run tests.
5. **Update Frequently:** If a task is large, keep updating the task progress to approximate values and add comments regularly.
6. **Record Decisions:** Use `hive log-decision` (or `hive edit-decision` to modify) if you make an important architectural choice.
7. **Submit for Review & Summarize (Do NOT directly close tasks):**
   When work for a task is complete:
   - **Except for absolute, self-contained tasks** that require no human testing or verification (such as initial project setup, database schema migration that you verified, or basic config file generation), you **MUST NOT** directly mark the task as `done`.
   - Instead, update the status to `review` and set the progress to `90%` (indicating it is ready for review).
     * *Example:* `hive task-update <TASK_ID> --status review --progress 90`
   - Ask the user to verify/test the changes and wait for their feedback.
   - For absolute tasks, mark them complete: `hive task-update <TASK_ID> --status done --progress 100`.
   - In both cases, **always log a detailed final comment** summarizing exactly what was implemented, changed, or tested under that task.
8. **Project Sync:** On task completion, **always check if project metadata needs updating**. If it is a major change, update the project details, decisions, memories, or progress status (`hive status`), or at least add a project-level progress comment.
9. **Refixing / Reclaiming / Reopening Rules:**
   - If the user reports that a completed or review task is still not fixed/implemented correctly:
     - **Reopen/reclaim the task:** Transition the task's status back to `reopened` and progress to `0%` or `<100%`.
       * *Example:* `hive task-update <TASK_ID> --status reopened --progress 0`
     - Claim it to assign it to yourself and start work: `hive task-update <TASK_ID> --claim`
   - If the user reports a new, unrelated problem, **always open a new task** with the correct type (`bug`, `issue`, etc.) and define its dependencies.
10. **Repeat:** Move to the next task.

---

## 4. Error Fallback Handling

If you encounter any operational or system error with the HIVE CLI or its database during execution:
1. Log the error details in the agent transcript/output.
2. Ask the user explicitly:
   > "HIVE encountered an error: [Error details]. Would you like to retry the operation or continue working without HIVE tracking?"
3. Proceed according to the user's choice.

---

## 5. Summary of Workflow & Guidelines

| Step | Action | Status | Progress | Command Example |
| :--- | :--- | :--- | :--- | :--- |
| **1. Ingest** | Load latest project context | - | - | `hive learn` |
| **2. Plan** | Add tasks with types/dependencies | `todo` | `0%` | `hive task-add "..." --type bug` |
| **3. Claim** | Claim task before editing code | `in_progress` | `0%` | `hive task-update <TASK_ID> --claim` |
| **4. Execute**| Implement code changes and tests | `in_progress` | `10%` - `80%` | `hive task-update <TASK_ID> --progress 50` |
| **5. Review** | Submit for user testing (except setups) | `review` | `90%` | `hive task-update <TASK_ID> --status review --progress 90` |
| **6. Finish** | Final completion (when verified) | `done` | `100%` | `hive task-update <TASK_ID> --status done --progress 100` |
| **7. Reopen** | If verification fails or is rejected | `reopened` | `0%` | `hive task-update <TASK_ID> --status reopened --progress 0` |
"""
