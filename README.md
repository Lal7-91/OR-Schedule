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
  check (no double-booked room, no double-booked surgeon, surgery must fit
  within its room's operating hours). It turns the tool's raw output into a
  critique; it never gets to override what the tool found.
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
pip install -e ".[dev]"
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

## Running

```bash
python -m harness.main                 # real run against Ollama
python -m harness.main --verbose       # + diagnostic output
HARNESS_DRY_RUN=1 python -m harness.main   # trivial scripted model, no network/LLM needed

pytest                                 # unit tests + scripted control-flow tests (no LLM needed)
ruff check harness tests               # lint
```

CLI flags: `--problem <path>` (default `data/toy_problem.yaml`),
`--max-iterations <n>`, `--verbose`.

## Project structure

```
harness/
  main.py              entry point (python -m harness.main)
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
data/toy_problem.yaml  the toy scenario: 3 rooms, 3 surgeons, 6 surgeries
tests/
  test_domain_models.py, test_constraints.py   Tier A: no LLM, no network
  test_graph_stub.py                            Tier B: scripted LLM, no network
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

## Non-goals

Not a production scheduler; no persistence/database; single-run CLI, no
auth or multi-user support; not aiming to beat MILP on solution quality --
the point is the multi-agent harness mechanics, not the scheduling result.

## Roadmap

- Add a surgeon-availability-window hard constraint (4th constraint type).
- Try swapping the hand-rolled supervisor routing for the official
  `langgraph-supervisor` package once the manual version is well understood.
- Add streaming and LangGraph checkpointing.
- Compare tool-calling reliability across a couple of different Ollama
  models on the same toy problem.
