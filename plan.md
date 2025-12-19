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
  number: 2
  pbi: PBI-002
  status: done
  subtasks_completed: 7
  subtasks_total: 7
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
  - id: PBI-002
    story:
      role: "recruiter"
      capability: "see real-time generation progress in the HTMX UI"
      benefit: "I understand what the system is doing and can see intermediate results"
    acceptance_criteria:
      - criterion: "Base template loads HTMX SSE extension from CDN"
        verification: "uv run pytest tests/ui/test_sse_streaming.py::test_htmx_sse_extension_loaded -v"
      - criterion: "Form uses SSE connection for streaming generation"
        verification: "uv run pytest tests/ui/test_sse_streaming.py::test_form_uses_sse_connection -v"
      - criterion: "Progress bar shows current generation step (1-6)"
        verification: "uv run pytest tests/ui/test_sse_streaming.py::test_progress_bar_updates -v"
      - criterion: "Current step name displays in Japanese"
        verification: "uv run pytest tests/ui/test_sse_streaming.py::test_step_name_display -v"
      - criterion: "Generated result displays after completion"
        verification: "uv run pytest tests/ui/test_sse_streaming.py::test_result_displays_on_complete -v"
      - criterion: "Error message displays on generation failure"
        verification: "uv run pytest tests/ui/test_sse_streaming.py::test_error_message_display -v"
    dependencies:
      - PBI-001
    status: ready
    notes: |
      ## Technical Analysis (Refinement)

      ### Existing Infrastructure
      - /generate/stream endpoint already exists with SSE support
      - sse_models.py defines ProgressEvent, CompleteEvent, ErrorEvent
      - 6 generation steps with Japanese names and percentages defined

      ### Implementation Approach
      1. Add HTMX SSE extension to base.html (htmx.org/extensions/sse)
      2. Create new POST /ui/generate/stream endpoint that returns initial progress UI
      3. Add progress.html partial with progress bar and step indicator
      4. Use hx-ext="sse" with sse-connect to /generate/stream
      5. Use sse-swap to update progress bar on "progress" events
      6. Display result partial on "complete" event

      ### Key Decisions
      - Use htmx sse extension (not vanilla EventSource) for consistency
      - POST form data to /ui/generate/stream, which returns SSE-enabled HTML
      - Progress bar uses CSS width transition for smooth animation

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
  number: 2
  pbi_id: PBI-002
  story: "As a recruiter, I can see real-time generation progress in the HTMX UI so that I understand what the system is doing and can see intermediate results"
  status: done

  sprint_goal:
    statement: "Add real-time SSE streaming progress to the HTMX UI"
    success_criteria:
      - "HTMX SSE extension loaded and functional"
      - "Progress bar shows 6 generation steps"
      - "Generated result displays on completion"
    stakeholder_value: "Recruiters understand generation progress and can see intermediate results"
    alignment_with_product_goal: "Improves UX by providing transparency during article generation"

  subtasks:
    - test: "Base template includes HTMX SSE extension script from CDN"
      implementation: "Add htmx sse extension script tag to base.html after htmx.org"
      type: behavioral
      status: completed
      commits:
        - phase: red
          message: "test: add failing test for HTMX SSE extension (Red phase)"
        - phase: green
          message: "feat: add HTMX SSE extension for real-time progress streaming"

    - test: "Index page form submits to /ui/generate/stream and connects to SSE"
      implementation: "Update form to use hx-ext='sse' and return progress partial with SSE connection"
      type: behavioral
      status: completed
      commits:
        - phase: red
          message: "test: add test for form SSE connection endpoint (Red phase)"
        - phase: green
          message: "feat: update form to use SSE streaming endpoint"

    - test: "Progress partial displays progress bar with percentage and step name"
      implementation: "Create partials/progress.html with progress bar and step indicator"
      type: behavioral
      status: completed
      commits:
        - phase: red
          message: "test: add test for progress partial with SSE (Red phase)"
        - phase: green
          message: "feat: add /ui/generate/stream endpoint with progress partial"

    - test: "POST /ui/generate/stream endpoint returns progress partial and starts SSE"
      implementation: "Add endpoint that returns initial HTML with SSE connection, then streams events"
      type: behavioral
      status: completed
      commits:
        - phase: green
          message: "Already implemented in Subtask 3 (progress partial with SSE connection)"

    - test: "SSE progress events update progress bar width and step name"
      implementation: "Add sse-swap targets for progress bar and step name updates"
      type: behavioral
      status: completed
      commits:
        - phase: red
          message: "test: add test for step name display in progress partial"
        - phase: green
          message: "Already implemented in Subtask 3 (sse-swap='progress' attribute)"

    - test: "SSE complete event displays result partial with generated article"
      implementation: "Handle complete event to swap result content into container"
      type: behavioral
      status: completed
      commits:
        - phase: red
          message: "test: add test for SSE complete event handling (Red phase)"
        - phase: green
          message: "feat: add SSE complete event swap to progress partial"

    - test: "SSE error event displays error message"
      implementation: "Handle error event to display error message to user"
      type: behavioral
      status: completed
      commits:
        - phase: red
          message: "test: add test for SSE error event handling (Red phase)"
        - phase: green
          message: "feat: add SSE error event swap to progress partial"
        - phase: refactor
          message: "refactor: format test_sse_streaming.py"

  notes: |
    ## Sprint 2 Planning Notes

    ### Sprint Goal
    Add real-time SSE streaming progress to the HTMX UI.

    ### Capacity
    - AI Agent: Full availability
    - Dependencies: PBI-001 completed

    ### Technical Decisions
    - HTMX SSE extension 2.0.x from CDN
    - Progress bar with CSS transition
    - 6 steps matching existing STEP_METADATA

    ### Definition of Done Verification
    1. All 7 subtasks completed through TDD cycle
    2. All acceptance criteria tests pass
    3. uv run pytest tests/ -v --tb=short
    4. uv run ruff check . && uv run ruff format --check .
    5. uv run mypy src/

  # Sprint 1 subtasks moved to completed section
  completed_subtasks:
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
completed:
  - sprint: 1
    pbi: PBI-001
    story: "As a recruiter, I can use the article generation system through an HTMX-based web UI instead of Streamlit, so that I get a more responsive, lightweight UI that integrates seamlessly with the FastAPI backend"
    verification: passed
    review_summary:
      increment_delivered:
        - "Jinja2Templates configuration in FastAPI (src/api/main.py)"
        - "Base HTML template with HTMX 2.0.4 CDN (src/templates/base.html)"
        - "Index page with article generation form (src/templates/index.html)"
        - "Result partial for HTMX updates (src/templates/partials/result.html)"
        - "/ui/generate endpoint for form submission"
        - "Static CSS file (src/static/css/style.css)"
        - "17 UI-specific tests (tests/ui/)"
      acceptance_criteria_verification:
        - criterion: "GET / returns base HTML page with HTMX script loaded from CDN"
          test: "test_htmx_base.py::test_index_returns_html, test_htmx_script_from_cdn"
          status: passed
        - criterion: "Base template includes proper HTML5 structure with Japanese lang attribute"
          test: "test_htmx_base.py::test_html_structure"
          status: passed
        - criterion: "Article type dropdown renders with 5 options (auto + 4 types)"
          test: "test_htmx_form.py::test_article_type_options"
          status: passed
        - criterion: "Input textarea renders with placeholder example text"
          test: "test_htmx_form.py::test_input_textarea"
          status: passed
        - criterion: "Generate button posts form data to /generate endpoint via HTMX"
          test: "test_htmx_form.py::test_generate_button_htmx_attrs"
          status: passed
        - criterion: "Generation result displays in result container without full page reload"
          test: "test_htmx_form.py::test_partial_update_result"
          status: passed
      definition_of_done:
        tests: "69 tests passed"
        lint: "ruff check passed"
        types: "mypy passed"
      product_goal_progress: "HTMX UI foundation delivered - recruiters can use lightweight alternative to Streamlit"
    notes: "Clean implementation with TDD. All 10 subtasks completed."
```

---

## 5. Retrospective Log

```yaml
# After each sprint, record what to improve
retrospectives:
  - sprint: 1
    pbi: PBI-001
    outcome: success
    worked_well:
      - "TDDサイクルが明確に機能（Red→Green→Refactor）"
      - "サブタスクの事前定義がスムーズな実装を可能にした"
      - "依存関係（python-multipart）の問題を即座に解決"
      - "DeprecationWarningをRefactorフェーズで適切に修正"
      - "全10サブタスクが計画通り完了"
    to_improve:
      - "Subtask 1-3が1つの実装で完了（base.htmlで複数テストがまとめて実装）"
      - "Subtask 4-6も同様に1コミットで完了（フォーム要素が論理的に1つ）"
      - "CSSスタイリングが最小限のまま（機能優先で見た目は後回し）"
    root_cause_analysis:
      problem: "サブタスク分割がテスト観点で細かすぎた"
      insight: "テンプレート/HTMLの最小単位はファイル/コンポーネントであり、個別要素ではない"
      pattern: "実装の最小単位とサブタスク粒度を合わせるべき"
    actions:
      - action: "サブタスク分割を「実装の最小単位」に合わせる"
        why: "1つの実装で複数サブタスクが完了する非効率を防ぐ"
        success_criteria: "次のSprintで1サブタスク=1実装コミットが達成される"
        backlog: Sprint Backlog
      - action: "テンプレート作業はファイル/コンポーネント単位でサブタスク化"
        why: "HTML/CSSはファイルが最小デプロイ単位"
        success_criteria: "テンプレート関連PBIで適切な粒度が維持される"
        backlog: Sprint Backlog
      - action: "CSSスタイリング改善は機能PBIとは別に計画を検討"
        why: "機能とスタイルは異なるスコープ"
        success_criteria: "見た目改善が必要な場合は明確に別PBIとして定義される"
        backlog: Product Backlog
    happiness_score: 4
    happiness_trend: stable
    notes: |
      Sprint 1は成功裏に完了。TDDプロセスが機能した良いスタート。
      サブタスク粒度の改善は次Sprint以降で適用する。
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
