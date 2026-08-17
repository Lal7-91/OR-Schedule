# OR Schedule -- Agentic Harness (Learning Project)

A small multi-agent harness, built to practice agentic AI orchestration
ahead of a graduation project on the same topic. It solves a toy Operating
Room (OR) scheduling problem -- deliberately *not* with MILP, the technique
the original research in this repo used, since the point here is to
practice building the harness itself, not to out-optimize a solver.

## The agent graph

Four agents, one supervisor pattern, built on [LangGraph](https://github.com/langchain-ai/langgraph):

```
scheduler -> constraint_checker -> priority_optimizer -> supervisor
                                                              |
                                    (revise) <------------------
                                    (accepted / max_iterations) -> END
```

- **Scheduler** -- the only agent with write access to the schedule. Calls
  `assign_surgery` / `unassign_surgery` to place surgeries into rooms/times.
- **Constraint Checker** -- an LLM agent, but one that relies entirely on a
  deterministic tool (`validate_schedule`) for the actual hard-constraint
  check: no double-booked room, no double-booked surgeon (both date-aware --
  the same room/surgeon on different dates is fine), surgery must fit within
  its room's operating hours, the assigned date must be within the
  scheduling horizon, the required surgeon must actually be available at
  that date/time (if they've declared any availability restriction), and
  every surgery must actually be scheduled. It turns the tool's raw output
  into a critique; it never gets to override what the tool found.
- **Priority Optimizer** -- read-only. Advises on soft objectives (urgent
  cases scheduled earlier, balanced room load) without touching anything.
- **Supervisor** -- reviews the schedule, the violations, and both workers'
  notes, then decides ACCEPT or REVISE. **Violations can never be
  LLM-waived**: if the deterministic check reports any, the supervisor is
  forced to REVISE regardless of what its own LLM call says.

The loop repeats, feeding the supervisor's feedback back to the Scheduler,
until the schedule is accepted or `MAX_SUPERVISOR_ITERATIONS` is hit.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ui]"
cp .env.example .env   # then fill in OLLAMA_BASE_URL etc. below
```

## Running an LLM on your other PC (Ollama)

The harness is designed to talk to a self-hosted model instead of a paid
cloud API.

**On the other PC:**
1. Install [Ollama](https://ollama.com).
2. Pull a tool-calling-capable instruct model, e.g.:
   ```bash
   ollama pull qwen2.5:7b-instruct
   ```
3. Make it reachable on your LAN (not just localhost):
   ```bash
   OLLAMA_HOST=0.0.0.0 ollama serve
   ```
   and make sure the firewall allows inbound connections on port `11434`.
4. Find that PC's LAN IP (`ipconfig getifaddr en0` on macOS, `hostname -I`
   on Linux). A static DHCP reservation on your router keeps it from
   changing later.

**On this machine**, smoke-test connectivity, then set `.env`:
```bash
curl http://<OTHER_PC_IP>:11434/v1/models
```
```
OLLAMA_BASE_URL=http://<OTHER_PC_IP>:11434/v1
OLLAMA_MODEL=qwen2.5:7b-instruct
```

Tool-calling reliability varies by model even among ones that claim
support -- if the harness behaves oddly, try a different pulled model
before assuming there's a harness bug.

**If requests start hanging or timing out for no obvious reason**, restart
the Ollama service on the host PC (`sudo systemctl restart ollama` inside
WSL). A generation that gets cancelled client-side (e.g. hitting
`OLLAMA_REQUEST_TIMEOUT_SECONDS`) can leave the server's inference slot
wedged -- symptoms are requests that never even start processing (no
`slot launch_slot_` line in `journalctl -u ollama`) even for a trivial
prompt. A restart clears it; this is a known class of issue with local
inference servers under GPU passthrough, not a harness bug.

## Running

```bash
python -m harness.main                 # real run against Ollama, pretty CLI report
python -m harness.main --verbose       # + diagnostic output
HARNESS_DRY_RUN=1 python -m harness.main   # trivial scripted model, no network/LLM needed

pytest                                 # unit tests + scripted control-flow tests (no LLM needed)
ruff check harness tests ui            # lint
```

CLI flags: `--problem <path>` (default `data/toy_problem.yaml`),
`--max-iterations <n>`, `--verbose`.

## Dashboard (UI)

```bash
streamlit run ui/app.py
```

Opens a local web dashboard with three tabs:
- **Problem builder** -- assemble a problem interactively instead of hand-
  editing YAML: pick a scheduling horizon (date range), add/edit rooms
  (with a time picker for operating hours), surgeons (with optional
  availability-window restrictions -- leave a surgeon's availability empty
  and they're free any horizon date within room hours), and surgeries
  (duration, required surgeon, priority). Save it as a new problem file and
  it becomes the default in the Live run tab.
- **Live run** -- start a run and watch the 4 agents work in real time: which
  agent is currently active, the schedule filling in, violations
  appearing/clearing, and the supervisor's verdict each iteration.
- **Past runs** -- browse and replay any previous run's full timeline.

The sidebar shows whether your configured Ollama endpoint is currently
reachable, so connectivity problems are obvious immediately.

Under the hood, "Start run" launches `python -m harness.runner` as a
background process, which streams the graph via LangGraph's `.stream()` API
and appends one JSON event per finished agent step to `runs/<run_id>/events.jsonl`.
The UI just polls that file every couple of seconds (`st.fragment(run_every=2)`)
-- the running harness and the UI are two separate processes, so a slow/local
model doesn't block the dashboard. `runs/` is gitignored (local artifacts).

## Project structure

```
harness/
  main.py              CLI entry point (python -m harness.main), pretty report
  runner.py            UI entry point (python -m harness.runner), streams JSONL events
  config.py            env-based Settings
  llm.py               Ollama connection + dry-run/scripted stand-ins
  state.py             HarnessState (the graph's shared blackboard)
  graph.py             StateGraph wiring + revise-loop routing
  agents/              one module per agent, each builds its own node
    tool_loop.py        the actual bounded tool-calling loop every agent uses
  domain/              pure Python, zero LangGraph/LLM dependency
    models.py           pydantic models (Room, Surgeon, Surgery, Assignment)
    store.py             mutable ScheduleStore for one run
    constraints.py         deterministic hard-constraint validation
    tools.py                LangChain tool wrappers around the store
    fixtures.py               loads a problem YAML into a ProblemInstance
  prompts/             one markdown system prompt per agent
ui/
  app.py               Streamlit dashboard (streamlit run ui/app.py)
  problem_builder.py    interactive problem editor (horizon/rooms/surgeons/surgeries)
  components.py         shared rendering pieces (schedule table, violations, ...)
  runs_store.py          reads runs/<run_id>/{meta.json,events.jsonl} off disk
data/toy_problem.yaml  the toy scenario: 2-day horizon, 3 rooms, 3 surgeons, 6 surgeries
tests/
  test_domain_models.py, test_constraints.py   Tier A: no LLM, no network
  test_graph_stub.py                            Tier B: scripted LLM, no network
  test_runner.py                                 event-log format, no LLM, no network
```

`domain/` is deliberately framework-agnostic and fully unit-testable on its
own -- the same split that will matter again when the graduation project
needs a harness reusable across problem domains.

## Configuration reference

| Env var | Purpose | Default |
|---|---|---|
| `OLLAMA_BASE_URL` | OpenAI-compatible endpoint of your Ollama server | `http://localhost:11434/v1` |
| `OLLAMA_MODEL` | Model name to request | `qwen2.5:7b-instruct` |
| `OLLAMA_API_KEY` | Dummy value; Ollama ignores it but the client requires one | `ollama` |
| `MAX_SUPERVISOR_ITERATIONS` | Cap on revise-loop rounds | `5` |
| `HARNESS_DRY_RUN` | `1` to skip the real LLM and run a trivial scripted model | `0` |
| `OLLAMA_REQUEST_TIMEOUT_SECONDS` | Per-request timeout, so a stuck local model can't hang the harness forever | `90` |
| `OLLAMA_MAX_RESPONSE_TOKENS` | Cap on tokens generated per agent reply | `512` |

## Non-goals

Not a production scheduler; no real database (run logs are just JSON files
on disk); no auth or multi-user support; not aiming to beat MILP on
solution quality -- the point is the multi-agent harness mechanics, not the
scheduling result.

## Roadmap

- Try swapping the hand-rolled supervisor routing for the official
  `langgraph-supervisor` package once the manual version is well understood.
- Add LangGraph checkpointing (persist/resume mid-run state).
- Compare tool-calling reliability and speed across a couple of different
  Ollama models on the same toy problem -- the added horizon/availability
  search space makes convergence harder for a small model, worth measuring.
