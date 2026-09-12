# Architecture Decision Records

## ADR-001: Why LangGraph for Orchestration?

**Decision:** Use LangGraph as the workflow orchestration framework.

**Context:** We need a system that supports conditional routing, human-in-the-loop, checkpointing, and retry loops across multiple AI agents.

**Reasoning:**
- LangGraph provides native support for stateful, cyclical workflows — not just linear chains
- The `interrupt()` mechanism allows clean human approval gates without complex polling
- SQLite checkpointer enables workflow persistence and resumption after UI refresh
- Conditional edges map naturally to our routing decisions (scope gate, approval gate, validation gate)
- Superior to raw LangChain for our use case because we need explicit state management

**Alternatives considered:**
- Raw Python + async queues: More control but requires building all orchestration primitives from scratch
- CrewAI: Better for role-based multi-agent conversation; less suited for stateful SDLC workflows
- Prefect/Airflow: Built for data pipelines, not AI agent workflows

---

## ADR-002: Why Deterministic Repository Tools?

**Decision:** Use Python AST, os.walk, subprocess (git, ripgrep) for codebase analysis — not LLM.

**Reasoning:**
- LLMs hallucinate when asked to reason about large codebases
- Deterministic tools are fast, reliable, and produce structured output
- Lower token usage (only relevant snippets sent to LLM)
- More reproducible results across runs
- git log, ast.parse, and file listing never make things up

**Approach:** Tools produce structured data → LLM receives only relevant context → LLM reasons about impact.

---

## ADR-003: Why SQLite as Default Database?

**Decision:** SQLite as default; PostgreSQL via Docker for full demo.

**Reasoning:**
- SQLite requires zero infrastructure setup — demo starts immediately
- SQLAlchemy async supports SQLite via `aiosqlite`
- For the interview context, demonstrating the agentic workflow is more important than database infrastructure
- PostgreSQL mode is available via `docker-compose up` and a single env variable change

**Trade-off:** SQLite is not suitable for production multi-instance deployments.

---

## ADR-004: Why Not Kafka?

**Decision:** Use PostgreSQL for analytics storage; document Kafka as future work.

**Reasoning:**
- Kafka adds significant operational complexity (brokers, consumers, schema registry)
- For a prototype with SQLite/PostgreSQL, direct click tracking is adequate
- The analytics volume in this demo is negligible
- Kafka would obscure the agentic workflow (the point of this demo) with infrastructure complexity

**Future improvement:** At high scale (>10K redirects/sec), introduce an async event pipeline:
`Redirect API → Kafka → Analytics Consumer → PostgreSQL`

---

## ADR-005: Why Streamlit?

**Decision:** Use Streamlit for the frontend UI.

**Reasoning:**
- Fast to build — keeps focus on agent architecture, not frontend engineering
- Good support for interactive demos with buttons, progress indicators, and expandable sections
- Session state handles workflow state management without a separate backend API
- No build step required

**Trade-off:** Streamlit's execution model (reruns on every interaction) requires careful session state management for the multi-step approval workflow.

**Alternative:** React + FastAPI backend would give more control but adds 2-3 days of development for no additional demo value.

---

## ADR-006: Deterministic Short Code Generation

**Decision:** Generate short codes using SHA-256 hash of the original URL encoded in base62.

**Reasoning:**
- Same URL always produces the same short code (deterministic)
- Eliminates "different short code after restart" bug (random seed issue)
- No collision risk for URLs of reasonable length
- Fast O(1) generation without database lookup for generation

**Implementation:**
```python
import hashlib, string

CHARS = string.digits + string.ascii_letters  # base62

def generate_short_code(url: str, length: int = 7) -> str:
    hash_bytes = hashlib.sha256(url.encode()).digest()
    num = int.from_bytes(hash_bytes[:8], "big")
    code = ""
    while num and len(code) < length:
        code = CHARS[num % 62] + code
        num //= 62
    return code.ljust(length, "0")
```

---

## ADR-007: Why Not a Docker-Based Execution Sandbox?

**Decision:** Write generated code to local workspace directory; no Docker sandbox.

**Reasoning:**
- Docker sandbox adds significant complexity and infrastructure requirement
- The assignment says "not expecting production-grade" — sandbox is a future concern
- For the demo, writing to `./generated_workspace/{request_id}/` is sufficient
- Security note documented: prototype sandbox is NOT a multi-tenant security boundary

**Future improvement:** Docker-based workspace isolation with restricted syscalls, time limits, and network isolation.

---

## ADR-008: Interactive Clarification with Concrete Options vs. Blind Execution

**Decision:** When requirements are ambiguous, the Intent Agent must not fail or build blindly; it must generate concrete engineering options and present them as interactive choices to the user.

**Context:** Users often give underspecified requirements (e.g., *"Make the URL shortener scalable"*). In real-world software engineering, an agent should neither guess blindly (risking building the wrong system) nor abort with a generic error (poor UX).

**Reasoning:**
- Presenting 3–4 concrete engineering options (e.g., Redis redirect caching, batch URL creation, connection pooling, rate limiting) guides the user to a viable architecture.
- Clickable option buttons in the UI reduce user cognitive friction while maintaining strict alignment before code generation.
- The user retains the ability to supply custom freeform text if their intent differs from the suggestions.

**Trade-off:** Requires a two-stage interaction for ambiguous inputs rather than immediate code generation, but prevents wasted token expenditure and erroneous implementations.

---

## ADR-009: Vanity Aliases & Atomic Batch Creation Architecture

**Decision:** Support user-defined custom aliases alongside deterministic hashing, and provide an atomic batch URL creation endpoint.

**Context:** Users require both human-readable vanity links (e.g., `short.ly/marketing-q3`) and the ability to shorten multiple URLs simultaneously.

**Reasoning:**
- **Custom Vanity Aliases:** If `custom_alias` is provided in `POST /api/v1/urls/`, validate against collisions. If already taken, return HTTP 400 Bad Request with a clear message. If omitted, fall back to deterministic SHA-256 base62 hashing.
- **Atomic Batch Creation:** `POST /api/v1/urls/batch` accepts a list of URL definitions. Database writes occur in a single transaction (`session.commit()` on all items or rollback on integrity failure), ensuring no partial batch state.
- **Cache Invalidation / Warmup:** Batch creations immediately register the short codes in the cache for high-throughput redirect resolution.

---

## ADR-010: Re-analysis Cycle vs. Mid-Graph Resume for Ambiguous Requirements

**Decision:** Ambiguous requests that receive clarification restart analysis with an enriched requirement rather than attempting in-flight graph resumption.

**Context:** In LangGraph, pausing at an ambiguous state and attempting to resume via `Command(resume=...)` on an already-terminated thread can cause state desynchronization, empty task graphs (0/0 tasks completed), or false validation failures.

**Reasoning:**
- When the user selects a clarification option, the prompt is updated (e.g., `"{original_request}. Specifically: {selected_option}"`).
- Resetting state and running a clean `run_analysis` pass allows `RequirementAgent`, `RepositoryAgent`, `ArchitectureAgent`, and `PlannerAgent` to execute sequentially with the complete context.
- The generated task DAG, validation criteria, and architecture accurately reflect the chosen direction, cleanly pausing at the `Approval Gate` before any code is generated.
