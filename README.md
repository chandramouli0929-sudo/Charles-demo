# ⚙️ charles-agentic-ai-demo

> **Agentic SDLC Workflow Automation Platform**
>
> Give it a requirement in plain English. It understands, plans, asks for your approval, builds, tests, and validates — automatically.

[![CI](https://github.com/chandramouli0929-sudo/Charles-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/chandramouli0929-sudo/Charles-demo/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What Is charles-agentic-ai-demo?

charles-agentic-ai-demo is an agentic software engineering system that transforms a natural-language software requirement into a reviewable, validated engineering outcome.

**The interaction is simple:**

> *"Add analytics to my URL shortener so I can see clicks per day."*

charles-agentic-ai-demo takes it from there:

1. **Understands** the requirement (intent classification across greenfield, brownfield, bugfix, refactor, ambiguous, out-of-scope)
2. **Clarifies** ambiguous prompts by presenting concrete engineering options rather than guessing or failing
3. **Analyzes** the existing codebase using deterministic tools (AST, directory scanning, git log)
4. **Designs** the architecture and decomposes tasks into a dependency DAG
5. **Asks for your approval** — showing the full plan, risks, and trade-offs before writing a single line of code
6. **Implements** the change with targeted code generation or modification
7. **Tests** the implementation with automated pytest suites
8. **Validates** results with actual execution evidence (syntax check, test run, requirement matching)
9. **Produces** a structured engineering outcome with git diff, test results, and live running web application

**You never select a workflow type manually.** The system figures it out.

---

## Architecture

```mermaid
flowchart TD
    U([User — Natural Language]) --> UI[Streamlit UI]
    UI --> WF[LangGraph Workflow]

    subgraph WF [LangGraph Orchestration]
        A1[Intent Agent] --> A2[Scope Gate]
        A2 --> |in-scope| A3[Requirement Agent]
        A2 --> |out-of-scope| END1[Safe Termination]
        A2 --> |ambiguous| CL[Clarification Options Loop]
        CL --> |User selects option / input| A1
        A3 --> A4{Brownfield / Bugfix / Refactor?}
        A4 --> |yes| A5[Repository Agent]
        A4 --> |no| A6[Architecture Agent]
        A5 --> A6
        A6 --> A7[Planner Agent]
        A7 --> GATE{HUMAN APPROVAL GATE}
        GATE --> |approved| A8[Coding Agent]
        GATE --> |modify / reject| END2[Plan Modified / Restarted]
        A8 --> A9[Test Agent]
        A9 --> A10[Validation Agent]
        A10 --> |pass| A11[Summary Agent]
        A10 --> |fail + retry < max| A12[Remediation Agent]
        A12 --> A9
        A10 --> |max retries| A11
        A11 --> END3([Engineering Outcome & Auto-Launch])
    end
```

---

## Agent Responsibilities

| Agent | Responsibility |
|-------|---------------|
| **Intent Agent** | Classifies user intent: greenfield / brownfield / bugfix / refactor / ambiguous / out-of-scope. Generates 3-4 concrete options when ambiguous. |
| **Requirement Agent** | Normalizes requirement, extracts functional/non-functional requirements, assumptions, acceptance criteria. |
| **Repository Agent** | Inspects existing codebase using deterministic tools (AST, file listing, git log). |
| **Architecture Agent** | Designs solution architecture, API contracts, data model, trade-offs, and risks. |
| **Planner Agent** | Generates dependency-aware task DAG with validation criteria and risk mitigations. |
| **Coding Agent** | Generates new code (greenfield) or modifies existing files (brownfield/bugfix/refactor) and writes to disk. |
| **Test Agent** | Generates and runs pytest test suites with automated failure reporting. |
| **Validation Agent** | Validates outputs with actual execution evidence (syntax check, test results, requirement matching). |
| **Remediation Agent** | Diagnoses test failures and applies automated code repairs. |
| **Summary Agent** | Compiles structured engineering report (tasks, diff, test results, risks). |

---

## LangGraph Orchestration

AgentForge uses **LangGraph** as its orchestration framework. Key features used:

- **Conditional routing** — workflow path determined by structured state, not hard-coded sequences
- **Human-in-the-loop** — `interrupt()` pauses execution at the approval gate
- **Checkpointing** — SQLite-backed state persistence (`SqliteSaver`) allows workflow resumption
- **Retry loops** — failed validation triggers automated remediation (up to 2 attempts)
- **Structured state** — all agents communicate via `EngineeringState` TypedDict
- **Interactive options loop** — ambiguous inputs present suggested options and restart a clean analysis cycle

---

## URL Shortener Reference Application

The reference app is a production-quality FastAPI URL shortener with both API endpoints and a web user interface.

### APIs

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/urls/` | Create a short URL (supports deterministic hash or user-defined `custom_alias`) |
| `POST` | `/api/v1/urls/batch` | Batch create multiple short URLs in a single atomic transaction |
| `GET` | `/{short_code}` | Redirect (HTTP 302) to original URL (cached in Redis/in-memory) |
| `GET` | `/api/v1/urls/{id}` | Get URL details and metadata |
| `GET` | `/api/v1/urls/{id}/analytics` | Click analytics (total clicks, clicks today, recent referral events) |
| `DELETE` | `/api/v1/urls/{id}` | Deactivate URL (returns HTTP 410 Gone on subsequent redirect attempts) |
| `GET` | `/health` | Health check probe (`{"status":"healthy","service":"url-shortener"}`) |
| `GET` | `/docs` | Interactive OpenAPI Swagger documentation |

### Key Design Decisions

**Deterministic Short Codes:** Short codes are generated using SHA-256 hash of the original URL encoded in base62. Same URL always produces the same short code. This eliminates the "different short code after restart" bug.

**Redis Cache:** Redirect lookups check Redis first (cache hit → immediate redirect). On cache miss, query PostgreSQL and populate cache. Reduces database load for popular URLs.

**Redirect Flow:**
```
GET /{short_code}
        ↓
     Redis
        ↓
  ┌────────────┐
  │    HIT     │    MISS
  │            ↓
  │       PostgreSQL
  │            ↓
  │       Set Redis
  │            ↓
  └──────→ 302 Redirect
```

### Data Model

```sql
-- URL table
CREATE TABLE urls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    original_url VARCHAR(2048) NOT NULL,
    short_code   VARCHAR(20) UNIQUE NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at   DATETIME,
    is_active    BOOLEAN DEFAULT TRUE
);

-- Click analytics table
CREATE TABLE clicks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url_id      INTEGER NOT NULL REFERENCES urls(id),
    clicked_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_agent  VARCHAR(512),
    referrer    VARCHAR(2048)
);
```

---

## Setup & Running

### Prerequisites

- Python 3.11+
- pip
- Git
- (Optional) Docker for PostgreSQL + Redis

#### Quick Start — SQLite Mode (Recommended for Demo)

```bash
# 1. Clone the repository
git clone https://github.com/chandramouli0929-sudo/Charles-demo.git
cd agentforge

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Configure environment
copy .env.example .env
# Edit .env — set your LLM_API_KEY

# 5. Run the AgentForge Control Center UI
streamlit run ui/streamlit_app.py --server.port 8501
# Open: http://localhost:8501
```

### Run the URL Shortener Application Directly

```bash
# SQLite mode (no Docker required)
cd reference_app/url_shortener
python -m uvicorn main:app --port 8001 --host 127.0.0.1

# Visit Web App UI: http://127.0.0.1:8001/
# Interactive API Docs: http://127.0.0.1:8001/docs
```

> **Note on Automatic Execution:** When you approve an engineering plan inside AgentForge, the system automatically launches the generated application on port `8001` and provides direct links inside the UI.

### With Docker (PostgreSQL + Redis)

```bash
# Start infrastructure
docker-compose up -d

# URL shortener will be at http://localhost:8000
```

---

## ☁️ Free Cloud Deployment (Share with End Users)

You can deploy `charles-agentic-ai-demo` to free cloud platforms so evaluators and end users can interact with it directly in their browsers:

### Option 1: Streamlit Community Cloud (Recommended — 100% Free Forever)
1. Fork or push this repository to GitHub: [`https://github.com/chandramouli0929-sudo/Charles-demo`](https://github.com/chandramouli0929-sudo/Charles-demo)
2. Go to **[share.streamlit.io](https://share.streamlit.io/)** and sign in with GitHub.
3. Click **"New app"** and configure:
   - **Repository:** `chandramouli0929-sudo/Charles-demo`
   - **Branch:** `master`
   - **Main file path:** `ui/streamlit_app.py`
   - **App URL:** `charles-agentic-ai-demo.streamlit.app`
4. Under **Advanced settings** → **Secrets**, add your API key:
   ```toml
   LLM_API_KEY = "your-gemini-or-openai-key"
   LLM_PROVIDER = "gemini"
   LLM_MODEL = "gemini-1.5-flash"
   ```
5. Click **"Deploy!"** — Streamlit automatically installs from `requirements.txt` and serves the app with a public HTTPS URL.

### Option 2: Instant Public Tunnel (Share Local Run Instantly)
To share your active local session with end users without deploying to cloud:
```bash
# Expose local Streamlit UI (port 8501) via localtunnel
npx localtunnel --port 8501

# Or expose via SSH localhost.run (no npm needed):
ssh -R 80:localhost:8501 localhost.run
```

---

## Demo Instructions

### Demo 1 — Greenfield
Enter: `"Build a scalable URL shortener with APIs, persistence and analytics."`

Watch AgentForge:
- Classify as GREENFIELD (new build)
- Design FastAPI + SQLite + Redis architecture
- Create 6-task dependency DAG
- Wait for your approval at the Human Approval Gate
- Generate complete working application with vanity alias and batch endpoints
- Automatically launch on port 8001, run tests, and show live links

### Demo 2 — Brownfield Enhancement
Enter: `"Add rate limiting to the URL creation endpoint."`

Watch AgentForge:
- Classify as BROWNFIELD
- Inspect existing `reference_app/url_shortener/` codebase
- Identify impacted API routes and middleware
- Show proposed changes
- After approval: modify files, show git diff

### Demo 3 — Bug Fix
Enter: `"Sometimes the same URL gets a different short code after restarting the application. Fix it."`

Watch AgentForge:
- Classify as BUG FIX
- Locate short-code generation code
- Identify root cause (random vs. deterministic)
- Propose fix: SHA-256 hash → base62 encoding
- Add regression test
- After approval: implement and validate

### Demo 4 — Refactoring
Enter: `"Refactor the URL service because it is becoming difficult to maintain."`

Watch AgentForge:
- Classify as REFACTOR
- Establish test baseline
- Identify code organization issues
- Propose safe refactoring (extract analytics service)
- After approval: refactor + verify behavior unchanged

### Demo 5 — Ambiguous Requirement (Options & Clarification)
Enter: `"Make the URL shortener scalable."`

Watch AgentForge:
- Detect AMBIGUITY
- Instead of building blindly or crashing, present concrete architectural options:
  - *Optimize redirect throughput using Redis caching*
  - *Add high-volume batch URL creation with bulk insert*
  - *Add rate limiting to protect system endpoints*
  - *Implement PostgreSQL connection pooling & read replica support*
- Click any suggested option (or type custom input)
- Observe AgentForge re-analyzing with the chosen direction and cleanly pausing at the Approval Gate

### Demo 6 — Out of Scope
Enter: `"Build me a payroll management system."`

Watch AgentForge:
- Detect OUT_OF_SCOPE
- Respond gracefully without starting expensive agents
- Ask if this might be a URL shortener requirement

---

## Running Tests

```bash
# URL shortener tests (16 comprehensive tests)
cd reference_app/url_shortener
python -m pytest tests/ -v

# All unit tests (no API key required)
pytest tests/unit/ -v

# All tests with coverage
pytest tests/ --cov=app --cov-report=html
```

---

## LLM Configuration

Configure in `.env`:

```env
LLM_PROVIDER=gemini          # gemini | openai | anthropic | openai_compatible
LLM_MODEL=gemini-1.5-flash   # model name
LLM_API_KEY=your-key-here
LLM_PLANNER_MODEL=gemini-1.5-pro  # smarter model for planning
```

For OpenAI-compatible servers (vLLM, LM Studio, Ollama):
```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=not-needed
```

---

## Known Limitations & Trade-offs

| Limitation | Reason | Future Improvement |
|------------|--------|-------------------|
| Gemini API key needed | LLM calls required for agents | Support local models via Ollama |
| SQLite by default | Simpler setup for zero-dependency demo | Full PostgreSQL mode via Docker |
| No real sandbox isolation | Prototype scope | Docker-based workspace isolation |
| Brownfield changes written to disk | Demo simplicity | Git branch + PR workflow |
| In-memory fallback for Redis | Zero Docker dependency for demo | Full Redis cluster in production |
| Analytics stored in DB | Prototype simplicity | Kafka + async click stream pipeline at scale |

---

## Architecture Decision Records

See [docs/decisions.md](docs/decisions.md) for detailed ADRs covering:
- **ADR-001:** Why LangGraph for Orchestration
- **ADR-002:** Why Deterministic Repository Tools (AST, git log, ripgrep)
- **ADR-003:** Why SQLite as Default Database
- **ADR-004:** Why Not Kafka for Prototype
- **ADR-005:** Why Streamlit for UI
- **ADR-006:** Deterministic Short Code Generation (SHA-256 + base62)
- **ADR-007:** Workspace Directories vs Docker Sandbox
- **ADR-008:** Interactive Clarification with Concrete Options vs Blind Execution
- **ADR-009:** Vanity Aliases & Atomic Batch Creation Architecture
- **ADR-010:** Re-analysis Cycle vs Mid-Graph Resume for Ambiguous Requirements

---

## Project Structure

```
agentforge/
├── app/
│   ├── agents/          # All AI agents
│   ├── graph/           # LangGraph state + workflow
│   ├── llm/             # LLM provider abstraction
│   └── tools/           # Deterministic repo tools
├── ui/
│   └── streamlit_app.py # Full Streamlit frontend
├── reference_app/
│   └── url_shortener/   # Runnable FastAPI URL shortener
├── demo/                # Demo scenario inputs
├── docs/                # Architecture docs
├── tests/               # Unit + Integration tests
└── .github/workflows/   # CI pipeline
```

---

## License

MIT License — see [LICENSE](LICENSE)
