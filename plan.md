# AI-Agentic Scrum Dashboard

## Rules

### General Principles

1. **Single Source of Truth**: This dashboard is the only place for Scrum artifacts. All agents read from and write to this file.
2. **Git as History**: Do not add timestamps. Git tracks when changes were made.
3. **Order is Priority**: Items higher in lists have higher priority. No separate priority field needed.

### Product Backlog Management

1. **User Story Format**: Every PBI must have a `story` block with `role`, `capability`, and `benefit`.
2. **Ordering**: Product Owner reorders by moving items up/down in the YAML array.
3. **Refinement**: Change status from `draft` -> `refining` -> `ready` as stories mature.

### Definition of Ready (AI-Agentic)

**Ready = AI can complete it without asking humans.**

| Status | Meaning |
|--------|---------|
| `draft` | Initial idea. Needs elaboration. |
| `refining` | Being refined. AI may be able to make it `ready`. |
| `ready` | All information available. AI can execute autonomously. |

**Refinement process**:
1. AI attempts to refine `draft`/`refining` items autonomously (explore codebase, propose acceptance criteria, identify dependencies)
2. If AI can fill in all gaps -> change status to `ready`
3. If story is too big or unclear -> try to split it
4. If unsplittable item still needs human help -> keep as `refining` and document the question

**Prioritization**: Prefer `ready` items. Work on refinement when no `ready` items exist or while waiting for human input.

### Sprint Structure (AI-Agentic)

**1 Sprint = 1 PBI**

Unlike human Scrum where Sprints are time-boxed to amortize event overhead, AI agents have no such constraint. Scrum events are instant for AI, so we maximize iterations by:

- Each Sprint delivers exactly one PBI
- Sprint Planning = select top `ready` item from backlog
- Sprint Review/Retro = run after every PBI completion
- No fixed duration - Sprint ends when PBI is done

**Benefits**: Faster feedback, simpler planning, cleaner increments, easier rollback.

### Sprint Execution (TDD Workflow)

1. **One PBI per Sprint**: Select the top `ready` item. That's the Sprint Backlog.
2. **TDD Subtask Breakdown**: Break the PBI into subtasks. Each subtask produces commits through Red-Green-Refactor:
   - `test`: What behavior to verify (becomes the Red phase test)
   - `implementation`: What to build to make the test pass (Green phase)
   - `type`: `behavioral` (new functionality) or `structural` (refactoring only)
   - `status`: Current TDD phase (`pending` | `red` | `green` | `refactoring` | `completed`)
   - `commits`: Array tracking each commit made for this subtask
3. **TDD Cycle Per Subtask (Commit-Based)**:
   - **Red**: Write a failing test, commit it (`phase: red`), status becomes `red`
   - **Green**: Implement minimum code to pass, commit it (`phase: green`), status becomes `green`
   - **Refactor**: Make structural improvements, commit each one separately (`phase: refactor`), status becomes `refactoring`
   - **Complete**: All refactoring done, status becomes `completed`
4. **Multiple Refactor Commits**: Following Tidy First, make small, frequent structural changes. Each refactor commit should be a single logical improvement (rename, extract method, etc.).
5. **Commit Discipline**: Each commit represents one TDD phase step. Never mix behavioral and structural changes in the same commit.
6. **Full Event Cycle**: After PBI completion, run Review -> Retro -> next Planning.

### Impediment Handling

1. **Log Immediately**: When blocked, add to `impediments.active` right away.
2. **Escalation Path**: Developer -> Scrum Master -> Human.
3. **Resolution**: Move resolved impediments to `impediments.resolved`.

### Definition of Done

1. **All Criteria Must Pass**: Every required DoD criterion must be verified.
2. **Executable Verification**: Run the verification commands, don't just check boxes.
3. **No Partial Done**: An item is either fully Done or still in_progress.

### Status Transitions

```
PBI Status (in Product Backlog):
  draft -> refining -> ready

Sprint Status (1 PBI per Sprint):
  in_progress -> done
       |
    blocked

Subtask Status (TDD Cycle with Commits):
  pending ─┬─> red ─────> green ─┬─> refactoring ─┬─> completed
           │   (commit)  (commit) │    (commit)    │
           │                      │       ↓        │
           │                      │   (more refactor commits)
           │                      │       ↓        │
           │                      └───────┴────────┘
           │
           └─> (skip to completed if no test needed, e.g., pure structural)

Each status transition produces a commit:
  pending -> red:        commit(test: ...)
  red -> green:          commit(feat: ... or fix: ...)
  green -> refactoring:  commit(refactor: ...)
  refactoring -> refactoring: commit(refactor: ...) [multiple allowed]
  refactoring -> completed:   (no commit, just status update)
  green -> completed:    (no commit, skip refactor if not needed)

Sprint Cycle:
  Planning -> Execution -> Review -> Retro -> (next Planning)
```

### Agent Responsibilities

| Agent | Reads | Writes |
|-------|-------|--------|
| Product Owner | Full dashboard | Product Backlog, Product Goal, Sprint acceptance |
| Scrum Master | Full dashboard | Sprint config, Impediments, Retrospective, Metrics |
| Developer | Sprint Backlog, DoD | Subtask status, Progress, Notes, Impediments |
| Event Agents | Relevant sections | Event-specific outputs |

---

## Quick Status

```yaml
sprint:
  number: 1
  pbi: PBI-001
  status: in_progress
  subtasks_completed: 10
  subtasks_total: 10
  impediments: 0
```

---

## 1. Product Backlog

### Product Goal

```yaml
product_goal:
  statement: "Enable recruiters to generate high-quality recruiting articles efficiently"
  success_metrics:
    - metric: "Article generation time"
      target: "< 60 seconds for complete article"
    - metric: "User satisfaction"
      target: "> 80% approval rate on generated drafts"
    - metric: "Retrieval accuracy"
      target: "> 90% relevance in retrieved reference articles"
  owner: "@scrum-team-product-owner"
```

### Backlog Items

```yaml
product_backlog:
  - id: PBI-001
    story:
      role: "recruiter"
      capability: "use the article generation system through an HTMX-based web UI instead of Streamlit"
      benefit: "I get a more responsive, lightweight UI that integrates seamlessly with the FastAPI backend"
    acceptance_criteria:
      - criterion: "GET / returns base HTML page with HTMX script loaded from CDN"
        verification: "uv run pytest tests/ui/test_htmx_base.py::test_index_returns_html -v"
      - criterion: "Base template includes proper HTML5 structure with Japanese lang attribute"
        verification: "uv run pytest tests/ui/test_htmx_base.py::test_html_structure -v"
      - criterion: "Article type dropdown renders with 5 options (auto + 4 types)"
        verification: "uv run pytest tests/ui/test_htmx_form.py::test_article_type_options -v"
      - criterion: "Input textarea renders with placeholder example text"
        verification: "uv run pytest tests/ui/test_htmx_form.py::test_input_textarea -v"
      - criterion: "Generate button posts form data to /generate endpoint via HTMX"
        verification: "uv run pytest tests/ui/test_htmx_form.py::test_generate_button_htmx_attrs -v"
      - criterion: "Generation result displays in result container without full page reload"
        verification: "uv run pytest tests/ui/test_htmx_form.py::test_partial_update_result -v"
    dependencies: []
    status: ready
    technical_decisions:
      template_location: "src/templates/"
      static_location: "src/static/"
      css_framework: "Minimal custom CSS (no heavy framework)"
      htmx_version: "2.0.x (CDN)"
      template_engine: "Jinja2"
      new_dependencies:
        - "jinja2"
        - "python-multipart"
    notes: |
      ## Refinement Summary (2025-12-19)

      ### Scope
      This PBI covers the foundational HTMX UI setup. It does NOT include:
      - Streaming progress display (PBI-002)
      - Verification features (future PBI)
      - History/saved articles (PBI-003)

      ### Technical Approach
      1. Add Jinja2Templates to FastAPI app
      2. Create base template with HTMX script from CDN
      3. Create form partial for article generation input
      4. Create result partial for displaying generated article
      5. Add endpoint to serve main page (GET /)
      6. Add endpoint to return result partial (POST /generate returns HTML partial)

      ### File Structure
      ```
      src/
        templates/
          base.html          # Base layout with HTMX
          index.html         # Main page extending base
          partials/
            form.html        # Input form partial
            result.html      # Generation result partial
        static/
          css/
            style.css        # Minimal styling
      ```

      ### INVEST Validation
      - Independent: No dependencies, self-contained UI foundation
      - Negotiable: CSS styling, exact layout can be adjusted
      - Valuable: Enables lightweight UI as alternative to Streamlit
      - Estimable: Clear scope with defined endpoints and templates
      - Small: Focused on basic form and result display only
      - Testable: 6 specific acceptance criteria with pytest verification

      ### TDD Subtasks (Sprint Execution Plan)
      When this PBI is selected for sprint, use these subtasks:

      1. **Setup Jinja2 templates in FastAPI**
         - test: "FastAPI app has Jinja2Templates configured with src/templates directory"
         - implementation: "Add Jinja2Templates to main.py, mount static files"
         - type: behavioral

      2. **Create base HTML template with HTMX**
         - test: "GET / returns HTML with HTMX script tag from unpkg CDN"
         - implementation: "Create base.html with HTML5 structure, HTMX CDN link, Japanese lang"
         - type: behavioral

      3. **Create index page extending base**
         - test: "GET / returns page with title 'Note記事ドラフト生成' and main content area"
         - implementation: "Create index.html extending base.html with header and content sections"
         - type: behavioral

      4. **Add article type selection dropdown**
         - test: "Index page contains select element with 5 options for article types"
         - implementation: "Add select with options: 自動判定, お知らせ, イベントレポート, インタビュー, カルチャー"
         - type: behavioral

      5. **Add input textarea for material**
         - test: "Index page contains textarea with name='input_material' and placeholder"
         - implementation: "Add textarea with Japanese placeholder showing example input format"
         - type: behavioral

      6. **Add generate button with HTMX attributes**
         - test: "Form has button with hx-post='/ui/generate', hx-target='#result', hx-swap='innerHTML'"
         - implementation: "Add button element with HTMX attributes for partial page update"
         - type: behavioral

      7. **Create result partial template**
         - test: "POST /ui/generate returns HTML partial with article sections"
         - implementation: "Create result.html partial with tabs for titles, lead, body, closing, markdown"
         - type: behavioral

      8. **Add /ui/generate endpoint**
         - test: "POST /ui/generate with form data calls pipeline and returns result partial"
         - implementation: "Add endpoint that parses form, calls ArticleGenerationPipeline, renders partial"
         - type: behavioral

      9. **Add minimal CSS styling**
         - test: "Static CSS file is served at /static/css/style.css"
         - implementation: "Create style.css with basic layout, form styling, result container styles"
         - type: behavioral

      10. **Integration test: Full form submission flow**
          - test: "Submitting form updates result container without page reload"
          - implementation: "Verify HTMX attributes work together for seamless UX"
          - type: behavioral

  - id: PBI-002
    story:
      role: "recruiter"
      capability: "see real-time generation progress in the HTMX UI"
      benefit: "I understand what the system is doing and can see intermediate results"
    acceptance_criteria:
      - criterion: "SSE endpoint streams generation progress to HTMX"
        verification: "uv run pytest tests/ui/test_sse_streaming.py -v"
      - criterion: "Progress indicators show current generation stage"
        verification: "uv run pytest tests/ui/test_progress_indicators.py -v"
      - criterion: "Generated content appears incrementally"
        verification: "uv run pytest tests/ui/test_incremental_content.py -v"
    dependencies:
      - PBI-001
    status: draft
    notes: |
      Leverage existing /generate/stream SSE endpoint.
      Use HTMX sse extension for real-time updates.

  - id: PBI-003
    story:
      role: "recruiter"
      capability: "view and manage previously generated articles"
      benefit: "I can review past work, reuse successful articles, and track my generation history"
    acceptance_criteria:
      - criterion: "Article history list displays past generations"
        verification: "uv run pytest tests/ui/test_history_list.py -v"
      - criterion: "Individual article view shows full content"
        verification: "uv run pytest tests/ui/test_article_view.py -v"
      - criterion: "Articles can be deleted from history"
        verification: "uv run pytest tests/ui/test_article_delete.py -v"
    dependencies:
      - PBI-001
    status: draft
    notes: |
      Requires new database table or storage mechanism for generated articles.
      Consider: pagination, search/filter, export options.
```

### Definition of Ready

```yaml
definition_of_ready:
  criteria:
    - criterion: "AI can complete this story without human input"
      required: true
      note: "If human input needed, split or keep as refining"
    - criterion: "User story has role, capability, and benefit"
      required: true
    - criterion: "At least 3 acceptance criteria with verification commands"
      required: true
    - criterion: "Dependencies are resolved or not blocking"
      required: true
```

---

## 2. Current Sprint

```yaml
sprint:
  number: 1
  pbi_id: PBI-001
  story: "As a recruiter, I can use the article generation system through an HTMX-based web UI instead of Streamlit, so that I get a more responsive, lightweight UI that integrates seamlessly with the FastAPI backend"
  status: in_progress

  sprint_goal:
    statement: "Deliver a functional HTMX-based web UI foundation for article generation"
    success_criteria:
      - "Base HTML page loads with HTMX from CDN"
      - "Article generation form is fully functional"
      - "Generated articles display without page reload"
    stakeholder_value: "Recruiters can start using a lightweight, responsive alternative to Streamlit UI"
    alignment_with_product_goal: "Enables efficient article generation through improved UX"

  subtasks:
    - test: "FastAPI app has Jinja2Templates configured with src/templates directory"
      implementation: "Add Jinja2Templates to main.py, mount static files"
      type: behavioral
      status: completed
      commits:
        - phase: red
          message: "test: add failing test for Jinja2Templates configuration"
        - phase: green
          message: "feat: add Jinja2Templates and static files configuration"
        - phase: refactor
          message: "refactor: use new TemplateResponse signature"

    - test: "GET / returns HTML with HTMX script tag from unpkg CDN"
      implementation: "Create base.html with HTML5 structure, HTMX CDN link, Japanese lang"
      type: behavioral
      status: completed
      commits:
        - phase: green
          message: "test: add HTMX CDN script verification test (already implemented in Subtask 1)"

    - test: "GET / returns page with title 'Note記事ドラフト生成' and main content area"
      implementation: "Create index.html extending base.html with header and content sections"
      type: behavioral
      status: completed
      commits:
        - phase: green
          message: "Already implemented in Subtask 1"

    - test: "Index page contains select element with 5 options for article types"
      implementation: "Add select with options: 自動判定, お知らせ, イベントレポート, インタビュー, カルチャー"
      type: behavioral
      status: completed
      commits:
        - phase: red
          message: "test: add form component tests (Red phase for Subtask 4-6)"
        - phase: green
          message: "feat: add article generation form with HTMX"

    - test: "Index page contains textarea with name='input_material' and placeholder"
      implementation: "Add textarea with Japanese placeholder showing example input format"
      type: behavioral
      status: completed
      commits:
        - phase: red
          message: "test: add form component tests (Red phase for Subtask 4-6)"
        - phase: green
          message: "feat: add article generation form with HTMX"

    - test: "Form has button with hx-post='/ui/generate', hx-target='#result', hx-swap='innerHTML'"
      implementation: "Add button element with HTMX attributes for partial page update"
      type: behavioral
      status: completed
      commits:
        - phase: red
          message: "test: add form component tests (Red phase for Subtask 4-6)"
        - phase: green
          message: "feat: add article generation form with HTMX"

    - test: "POST /ui/generate returns HTML partial with article sections"
      implementation: "Create result.html partial with tabs for titles, lead, body, closing, markdown"
      type: behavioral
      status: completed
      commits:
        - phase: red
          message: "test: add /ui/generate endpoint tests (Red phase)"
        - phase: green
          message: "feat: add /ui/generate endpoint for HTMX"

    - test: "POST /ui/generate with form data calls pipeline and returns result partial"
      implementation: "Add endpoint that parses form, calls ArticleGenerationPipeline, renders partial"
      type: behavioral
      status: completed
      commits:
        - phase: red
          message: "test: add /ui/generate endpoint tests (Red phase)"
        - phase: green
          message: "feat: add /ui/generate endpoint for HTMX"

    - test: "Static CSS file is served at /static/css/style.css"
      implementation: "Create style.css with basic layout, form styling, result container styles"
      type: behavioral
      status: completed
      commits:
        - phase: green
          message: "test: add CSS serving and integration tests"

    - test: "Submitting form updates result container without page reload"
      implementation: "Verify HTMX attributes work together for seamless UX"
      type: behavioral
      status: completed
      commits:
        - phase: green
          message: "test: add CSS serving and integration tests"

  notes: |
    ## Sprint 1 Planning Notes

    ### Sprint Goal
    Deliver a functional HTMX-based web UI foundation for article generation.

    ### Capacity
    - AI Agent: Full availability
    - No blocking dependencies

    ### Technical Decisions (from PBI-001)
    - Template location: src/templates/
    - Static files: src/static/
    - CSS framework: Minimal custom CSS
    - HTMX version: 2.0.x from CDN
    - Template engine: Jinja2
    - New dependencies: jinja2, python-multipart

    ### Definition of Done Verification
    1. All 10 subtasks completed through TDD cycle
    2. All acceptance criteria tests pass
    3. uv run pytest tests/ -v --tb=short
    4. uv run ruff check . && uv run ruff format --check .
    5. uv run mypy src/
```

### Impediment Registry

```yaml
impediments:
  active: []
  # Example impediment format:
  # - id: IMP-001
  #   reporter: "@scrum-team-developer"
  #   description: "Redis connection timeout in test environment"
  #   impact: "Blocks rate limiting tests"
  #   severity: high  # low | medium | high | critical
  #   affected_items:
  #     - PBI-003
  #   resolution_attempts:
  #     - attempt: "Increased connection timeout to 30s"
  #       result: "Still failing"
  #   status: investigating  # new | investigating | escalated | resolved
  #   escalated_to: null
  #   resolution: null

  resolved: []
```

---

## 3. Definition of Done

```yaml
definition_of_done:
  # Run all verification commands from the PBI's acceptance_criteria
  # Plus these baseline checks:
  checks:
    - name: "Tests pass"
      run: "uv run pytest tests/ -v --tb=short"
    - name: "Lint clean"
      run: "uv run ruff check . && uv run ruff format --check ."
    - name: "Types valid"
      run: "uv run mypy src/"
```

---

## 4. Completed Sprints

```yaml
# Log of completed PBIs (one per sprint)
completed: []
# Example completed sprint format:
# - sprint: 1
#   pbi: PBI-001
#   story: "As registered user, I can log in..."
#   verification: passed
#   notes: "Clean implementation"
```

---

## 5. Retrospective Log

```yaml
# After each sprint, record what to improve
retrospectives: []
# Example retrospective format:
# - sprint: 1
#   worked_well:
#     - "Clear acceptance criteria"
#   to_improve:
#     - "Better subtask breakdown"
#   actions:
#     - "Add more specific verification commands"
```

---

## 6. Agents

```yaml
agents:
  product_owner: "@scrum-team-product-owner"
  scrum_master: "@scrum-team-scrum-master"
  developer: "@scrum-team-developer"

events:
  planning: "@scrum-event-sprint-planning"
  review: "@scrum-event-sprint-review"
  retrospective: "@scrum-event-sprint-retrospective"
  refinement: "@scrum-event-backlog-refinement"
```
