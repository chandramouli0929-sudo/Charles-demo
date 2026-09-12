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
