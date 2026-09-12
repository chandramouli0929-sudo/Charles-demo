"""
AgentForge — Streamlit UI
Agentic SDLC workflow automation platform.

UX Principle: User describes what they want in natural language.
The system figures out everything else.
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

import streamlit as st

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AgentForge",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Main app */
.main { max-width: 1100px; }
.block-container { padding-top: 2rem; }

/* Hero title */
.hero-title {
    font-size: 3rem;
    font-weight: 800;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
.hero-subtitle {
    color: #6b7280;
    font-size: 1.1rem;
    margin-bottom: 2rem;
}

/* Status badges */
.badge-greenfield { background: #d1fae5; color: #065f46; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
.badge-brownfield { background: #dbeafe; color: #1e40af; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
.badge-bugfix { background: #fee2e2; color: #991b1b; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
.badge-refactor { background: #fef3c7; color: #92400e; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
.badge-ambiguous { background: #f3e8ff; color: #6b21a8; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
.badge-out_of_scope { background: #f1f5f9; color: #475569; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }

/* Workflow step indicator */
.step-done { color: #10b981; font-weight: 600; }
.step-running { color: #f59e0b; font-weight: 600; }
.step-pending { color: #d1d5db; }
.step-failed { color: #ef4444; font-weight: 600; }

/* Section headers */
.section-header {
    font-size: 1.1rem;
    font-weight: 700;
    color: #1f2937;
    border-left: 4px solid #667eea;
    padding-left: 0.75rem;
    margin: 1.5rem 0 0.75rem 0;
}

/* Approval panel */
.approval-panel {
    background: #f8faff;
    border: 2px solid #667eea;
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1rem 0;
}
</style>
""", unsafe_allow_html=True)


# ─── Session State Init ───────────────────────────────────────────────────────
def init_session():
    defaults = {
        "phase": "input",           # input | analyzing | clarifying | planning | approval | executing | complete | error
        "request_id": None,
        "user_request": "",
        "state": {},
        "workflow": None,
        "config": None,
        "clarification_answer": "",
        "error": None,
        "trace": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_session()


# ─── Workflow Step Display ────────────────────────────────────────────────────
WORKFLOW_STEPS = [
    ("intent", "🔍 Understanding Requirement"),
    ("requirement", "📋 Requirement Analysis"),
    ("repository", "🗂️ Repository Analysis"),
    ("architecture", "🏗️ Architecture Design"),
    ("planning", "📊 Task Planning"),
    ("approval", "👤 Human Approval"),
    ("coding", "⚙️ Code Generation"),
    ("testing", "🧪 Testing"),
    ("validation", "✅ Validation"),
    ("summary", "📄 Engineering Outcome"),
]


def get_step_status(step_key: str, current_phase: str) -> str:
    phase_order = [s[0] for s in WORKFLOW_STEPS]
    step_idx = phase_order.index(step_key) if step_key in phase_order else -1
    current_idx = phase_order.index(current_phase) if current_phase in phase_order else -1

    if current_phase == "complete":
        return "done"
    if step_idx < current_idx:
        return "done"
    if step_idx == current_idx:
        return "running"
    return "pending"


def render_workflow_trace():
    """Show workflow progress sidebar."""
    st.sidebar.markdown("## 🔄 Workflow Progress")
    phase = st.session_state.get("phase", "input")

    for step_key, step_label in WORKFLOW_STEPS:
        status = get_step_status(step_key, phase)
        if status == "done":
            st.sidebar.markdown(f"<span class='step-done'>✓ {step_label}</span>", unsafe_allow_html=True)
        elif status == "running":
            st.sidebar.markdown(f"<span class='step-running'>⏳ {step_label}</span>", unsafe_allow_html=True)
        else:
            st.sidebar.markdown(f"<span class='step-pending'>○ {step_label}</span>", unsafe_allow_html=True)

    # Show request type badge if known
    state = st.session_state.get("state", {})
    if state.get("request_type"):
        rt = state["request_type"]
        st.sidebar.markdown("---")
        st.sidebar.markdown("**Detected Intent:**")
        st.sidebar.markdown(f"<span class='badge-{rt}'>{rt.replace('_', ' ').title()}</span>", unsafe_allow_html=True)
        if state.get("confidence"):
            st.sidebar.markdown(f"Confidence: `{state['confidence']:.0%}`")

    if st.session_state.get("request_id"):
        st.sidebar.markdown("---")
        st.sidebar.caption(f"Request ID: `{st.session_state['request_id'][:8]}...`")


# ─── Helper: Run Analysis Pipeline ───────────────────────────────────────────
def run_analysis(user_request: str):
    """Run the pre-approval analysis pipeline."""
    from app.graph.workflow import create_workflow
    from app.config import settings

    request_id = str(uuid.uuid4())
    st.session_state["request_id"] = request_id
    st.session_state["user_request"] = user_request

    initial_state = {
        "request_id": request_id,
        "user_request": user_request,
        "workflow_status": "running",
        "retry_count": 0,
        "approval_status": "pending",
        "approval_required": True,
        "clarification_answered": False,
        "clarification_answer": "",
        "generated_files": [],
        "workflow_trace": [],
    }

    # Checkpointer: prefer SqliteSaver, fallback to MemorySaver
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        import sqlite3
        db_path = settings.workflow_db_path
        conn = sqlite3.connect(db_path, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()

    graph = create_workflow(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": request_id}}
    st.session_state["config"] = config
    st.session_state["workflow"] = graph

    # Run until interrupt (human approval) or completion
    result = graph.invoke(initial_state, config=config)

    return result


def resume_workflow(approval_status: str, modification_notes: str = ""):
    """Resume workflow after human approval/rejection."""
    from langgraph.types import Command

    graph = st.session_state["workflow"]
    config = st.session_state["config"]

    update = {
        "approval_status": approval_status,
        "modification_notes": modification_notes,
        "workflow_status": "executing" if approval_status == "approved" else "failed",
    }

    result = graph.invoke(Command(resume=update), config=config)
    return result


def resume_with_clarification(answer: str):
    """Resume workflow after user provides clarification."""
    from langgraph.types import Command

    graph = st.session_state["workflow"]
    config = st.session_state["config"]

    update = {
        "clarification_answer": answer,
        "clarification_answered": True,
        "workflow_status": "running",
    }
    result = graph.invoke(Command(resume=update), config=config)
    return result


# ─── Render Functions ─────────────────────────────────────────────────────────

def render_input_phase():
    """Initial screen — natural language input only."""
    st.markdown('<div class="hero-title">⚙️ AgentForge</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">Agentic Software Engineering · Understand → Plan → Approve → Build</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### Describe what you want to build or change")
        st.caption("The system will understand your requirement, design a solution, and ask for your approval before writing any code.")

        user_request = st.text_area(
            label="Requirement",
            label_visibility="collapsed",
            height=120,
            placeholder='Example: "Add analytics to my URL shortener so I can see clicks per day."',
            key="input_request",
        )

        col_btn, col_spacer = st.columns([1, 3])
        with col_btn:
            analyze_clicked = st.button(
                "🔍 Analyze Requirement",
                type="primary",
                disabled=not user_request.strip(),
                use_container_width=True,
            )

        if analyze_clicked and user_request.strip():
            st.session_state["phase"] = "analyzing"
            st.session_state["user_request"] = user_request.strip()
            st.rerun()

    with col2:
        st.markdown("### Demo Scenarios")
        st.caption("Click to try:")
        demos = [
            ("🆕 Greenfield", "Build a scalable URL shortener with APIs, persistence and analytics."),
            ("🔧 Brownfield", "Add rate limiting to the URL creation endpoint."),
            ("🐛 Bug Fix", "Sometimes the same URL gets a different short code after restarting the application. Fix it."),
            ("♻️ Refactor", "Refactor the URL service because it is becoming difficult to maintain."),
            ("❓ Ambiguous", "Make the URL shortener scalable."),
            ("🚫 Out of Scope", "Build me a payroll management system."),
        ]
        for label, demo_text in demos:
            if st.button(label, use_container_width=True, key=f"demo_{label}"):
                st.session_state["phase"] = "analyzing"
                st.session_state["user_request"] = demo_text
                st.rerun()


def render_analyzing_phase():
    """Show analysis in progress."""
    st.markdown('<div class="hero-title">⚙️ AgentForge</div>', unsafe_allow_html=True)
    st.markdown("---")

    user_request = st.session_state["user_request"]
    st.info(f'**Analyzing:** "{user_request}"')

    with st.spinner("🤖 AgentForge is analyzing your requirement..."):
        try:
            result = run_analysis(user_request)
            st.session_state["state"] = result

            wf_status = result.get("workflow_status", "")

            if wf_status == "waiting_approval":
                st.session_state["phase"] = "approval"
            elif wf_status == "waiting_clarification":
                st.session_state["phase"] = "clarifying"
            elif wf_status == "out_of_scope":
                st.session_state["phase"] = "out_of_scope"
            elif wf_status == "complete":
                st.session_state["phase"] = "complete"
            else:
                st.session_state["phase"] = "complete"

            st.rerun()
        except Exception as e:
            st.session_state["error"] = str(e)
            st.session_state["phase"] = "error"
            st.rerun()


def render_clarifying_phase():
    """Ask the user for clarification on ambiguous requirements."""
    state = st.session_state["state"]
    st.markdown('<div class="hero-title">⚙️ AgentForge</div>', unsafe_allow_html=True)
    st.markdown("---")

    st.warning("⚠️ **Clarification Needed**")
    st.markdown(f"**Your request:** `{state.get('user_request', '')}`")
    st.markdown("---")

    st.markdown(f"**{state.get('clarification_question', 'Could you please clarify your requirement?')}**")

    answer = st.text_area(
        "Your clarification:",
        height=100,
        placeholder="Please describe what you mean...",
        key="clarification_input",
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("✅ Submit Clarification", type="primary", disabled=not answer.strip()):
            with st.spinner("Re-analyzing with your clarification..."):
                try:
                    result = resume_with_clarification(answer.strip())
                    st.session_state["state"] = result
                    wf_status = result.get("workflow_status", "")
                    if wf_status == "waiting_approval":
                        st.session_state["phase"] = "approval"
                    else:
                        st.session_state["phase"] = "complete"
                    st.rerun()
                except Exception as e:
                    st.session_state["error"] = str(e)
                    st.session_state["phase"] = "error"
                    st.rerun()
    with col2:
        if st.button("↩️ Start Over"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


def render_out_of_scope_phase():
    """Gracefully handle out-of-scope requests."""
    state = st.session_state["state"]
    st.markdown('<div class="hero-title">⚙️ AgentForge</div>', unsafe_allow_html=True)
    st.markdown("---")

    st.warning("🚫 **Request Outside Demo Scope**")

    st.markdown(f"""
> "{state.get('user_request', '')}"

**AgentForge Assessment:**

{state.get('intent_reason', 'This request does not appear to be related to the URL shortener application.')}

This demo is currently scoped around the **URL shortener engineering workflow**.
""")

    st.markdown("**Are you perhaps referring to a URL shortener requirement?**")
    st.caption("Try rephrasing as a URL shortener requirement, or use one of the demo scenarios.")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("↩️ Try Again", type="primary"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


def render_approval_phase():
    """Human approval gate — show full plan before any code generation."""
    state = st.session_state["state"]
    st.markdown('<div class="hero-title">⚙️ AgentForge</div>', unsafe_allow_html=True)
    st.markdown("---")

    rt = state.get("request_type", "unknown")
    conf = state.get("confidence", 0)

    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("## 📋 Engineering Plan — Awaiting Your Approval")
        st.caption("Review the plan below. No code will be generated until you approve.")
    with col2:
        st.markdown(f"<br><span class='badge-{rt}'>{rt.replace('_', ' ').title()}</span> `{conf:.0%}` confidence", unsafe_allow_html=True)

    st.markdown("---")

    # Requirement Understanding
    st.markdown('<div class="section-header">✅ Requirement Understood</div>', unsafe_allow_html=True)
    st.markdown(f"> {state.get('normalized_requirement', state.get('user_request', ''))}")

    col1, col2 = st.columns(2)

    with col1:
        # Functional Requirements
        if state.get("functional_requirements"):
            st.markdown('<div class="section-header">📌 Functional Requirements</div>', unsafe_allow_html=True)
            for req in state["functional_requirements"]:
                st.markdown(f"- {req}")

        # Assumptions
        if state.get("assumptions"):
            st.markdown('<div class="section-header">💡 Assumptions</div>', unsafe_allow_html=True)
            for a in state["assumptions"]:
                st.markdown(f"- {a}")

        # Architecture
        if state.get("architecture_summary"):
            st.markdown('<div class="section-header">🏗️ Architecture</div>', unsafe_allow_html=True)
            st.markdown(state["architecture_summary"])

        if state.get("technology_stack"):
            st.markdown("**Technology Stack:**")
            st.markdown(" · ".join([f"`{t}`" for t in state["technology_stack"]]))

    with col2:
        # Non-functional Requirements
        if state.get("non_functional_requirements"):
            st.markdown('<div class="section-header">⚡ Non-Functional Requirements</div>', unsafe_allow_html=True)
            for req in state["non_functional_requirements"]:
                st.markdown(f"- {req}")

        # Impacted Components (brownfield)
        if state.get("impacted_components"):
            st.markdown('<div class="section-header">🎯 Impacted Components</div>', unsafe_allow_html=True)
            for comp in state["impacted_components"]:
                st.markdown(f"- `{comp}`")

        # API Contract
        if state.get("api_contract") and state["api_contract"].get("endpoints"):
            st.markdown('<div class="section-header">🔌 API Contract</div>', unsafe_allow_html=True)
            for ep in state["api_contract"]["endpoints"]:
                st.markdown(f"- `{ep.get('method', 'GET')} {ep.get('path', '')}` — {ep.get('description', '')}")

    # Task Breakdown
    if state.get("task_graph"):
        st.markdown('<div class="section-header">📊 Task Breakdown</div>', unsafe_allow_html=True)
        for task in state["task_graph"]:
            with st.expander(f"**{task.get('task_id', '')}** — {task.get('description', '')}", expanded=False):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"**Agent:** `{task.get('agent', '')}`")
                    if task.get("dependencies"):
                        st.markdown(f"**Depends on:** {', '.join(task['dependencies'])}")
                    if task.get("expected_outputs"):
                        st.markdown("**Outputs:**")
                        for o in task["expected_outputs"]:
                            st.markdown(f"  - {o}")
                with col_b:
                    if task.get("validation_criteria"):
                        st.markdown("**Validation:**")
                        for v in task["validation_criteria"]:
                            st.markdown(f"  - {v}")
                    if task.get("risks"):
                        st.markdown("**Risks:**")
                        for r in task["risks"]:
                            st.markdown(f"  - ⚠️ {r}")

    col_risk, col_valid = st.columns(2)

    with col_risk:
        # Risks
        if state.get("risks"):
            st.markdown('<div class="section-header">⚠️ Risks</div>', unsafe_allow_html=True)
            for risk in state["risks"]:
                st.markdown(f"- {risk}")

        # Trade-offs
        if state.get("tradeoffs"):
            st.markdown('<div class="section-header">⚖️ Trade-offs</div>', unsafe_allow_html=True)
            for to in state["tradeoffs"]:
                st.markdown(f"- {to}")

    with col_valid:
        # Validation Strategy
        if state.get("validation_strategy"):
            st.markdown('<div class="section-header">🧪 Validation Strategy</div>', unsafe_allow_html=True)
            st.markdown(state["validation_strategy"])

    # Repository Findings (brownfield)
    if state.get("codebase_summary"):
        st.markdown('<div class="section-header">🗂️ Repository Analysis</div>', unsafe_allow_html=True)
        st.markdown(state["codebase_summary"])
        if state.get("impacted_files"):
            st.markdown("**Files to be modified:**")
            for f in state["impacted_files"]:
                st.markdown(f"- `{f}`")

    # ── Approval Buttons ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🚀 Ready to proceed?")

    col_approve, col_modify, col_reject = st.columns([2, 2, 1])

    with col_approve:
        if st.button("✅ Approve & Build", type="primary", use_container_width=True):
            st.session_state["phase"] = "executing"
            st.rerun()

    with col_modify:
        modification = st.text_input(
            "Request changes (optional):",
            placeholder="e.g., Also add URL expiration...",
            key="modification_input",
            label_visibility="collapsed",
        )
        if st.button("✏️ Modify Plan", use_container_width=True, disabled=not modification.strip()):
            st.session_state["phase"] = "analyzing"
            # Add modification to request
            st.session_state["user_request"] = (
                st.session_state["user_request"] + f"\n\nAdditional requirement: {modification}"
            )
            for k in ["state", "workflow", "config", "request_id"]:
                st.session_state[k] = {} if k == "state" else None
            st.rerun()

    with col_reject:
        if st.button("❌ Cancel", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


def render_executing_phase():
    """Execute the approved plan."""
    state = st.session_state["state"]
    st.markdown('<div class="hero-title">⚙️ AgentForge</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("## ⚙️ Executing Approved Plan")

    progress_placeholder = st.empty()
    status_placeholder = st.empty()

    with progress_placeholder.container():
        steps = [
            "💻 Generating code...",
            "🧪 Running tests...",
            "✅ Validating outputs...",
            "📄 Compiling engineering summary...",
        ]
        progress_bar = st.progress(0)
        status_text = st.empty()
        for i, step in enumerate(steps):
            status_text.markdown(f"**{step}**")
            progress_bar.progress((i + 1) / len(steps))
            time.sleep(0.5)  # Visual feedback

    with st.spinner("🤖 Agents working..."):
        try:
            result = resume_workflow("approved")
            st.session_state["state"] = result
            st.session_state["phase"] = "complete"

            # Automatically launch the generated workspace application on port 8001
            ws_path = result.get("workspace_path")
            if ws_path and Path(ws_path, "main.py").exists():
                try:
                    import subprocess, sys, time
                    # Free up port 8001 if an older run was holding it
                    if sys.platform == "win32":
                        subprocess.run(
                            'powershell -Command "Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"',
                            shell=True,
                            timeout=5,
                        )
                    time.sleep(0.5)
                    subprocess.Popen(
                        [sys.executable, "-m", "uvicorn", "main:app", "--port", "8001", "--host", "127.0.0.1"],
                        cwd=ws_path,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass

            progress_placeholder.empty()
            st.rerun()
        except Exception as e:
            st.session_state["error"] = str(e)
            st.session_state["phase"] = "error"
            st.rerun()


def render_complete_phase():
    """Show the final engineering outcome."""
    state = st.session_state["state"]
    st.markdown('<div class="hero-title">⚙️ AgentForge</div>', unsafe_allow_html=True)
    st.markdown("---")

    final = state.get("final_summary", {})
    validation = state.get("validation_results", {})
    test_results = state.get("test_results", {})
    wf_status = state.get("workflow_status", "complete")

    # Overall status
    if wf_status == "complete" or validation.get("passed"):
        st.success("## 🎉 IMPLEMENTATION VALIDATED")
    else:
        st.error("## ❌ IMPLEMENTATION FAILED — See details below")

    # Summary header
    col1, col2, col3 = st.columns(3)
    rt = state.get("request_type", "unknown")
    with col1:
        st.metric("Intent", rt.replace("_", " ").title())
    with col2:
        tasks = state.get("task_graph", [])
        st.metric("Tasks Completed", f"{len([t for t in tasks if t.get('status') == 'done'])}/{len(tasks)}")
    with col3:
        retries = state.get("retry_count", 0)
        st.metric("Remediation Attempts", retries)

    # ── Quick Access Banner ──────────────────────────────────────────────────
    ws_path = state.get("workspace_path", "")
    st.info(
        f"""
**🚀 Launch Your Built Application:**
* **🌐 Web Application UI:** 👉 [http://127.0.0.1:8001/](http://127.0.0.1:8001/) *(or [http://127.0.0.1:8000/](http://127.0.0.1:8000/))*
* **📖 Interactive API Docs (Swagger):** [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)
* **📂 Workspace Directory on Disk:** `{ws_path}`
        """
    )

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Summary",
        "🎮 Test Playground",
        "📁 Generated Files",
        "🧪 Test Results",
        "⚖️ Risks & Trade-offs",
    ])

    with tab1:
        st.markdown("### Requirement")
        st.markdown(f"> {state.get('normalized_requirement', state.get('user_request', ''))}")

        if state.get("assumptions"):
            st.markdown("**Assumptions:**")
            for a in state["assumptions"]:
                st.markdown(f"- {a}")

        if state.get("architecture_summary"):
            st.markdown("### Architecture")
            st.markdown(state["architecture_summary"])

        if validation.get("checks"):
            st.markdown("### Validation Evidence")
            for check in validation["checks"]:
                icon = "✅" if check.get("passed") else "❌"
                st.markdown(f"{icon} **{check.get('name', '')}** — {check.get('evidence', '')}")

    with tab2:
        st.markdown("### 🎮 Interactive URL Shortener Playground")
        st.caption("Test the live FastAPI application generated by AgentForge directly from this UI!")

        target_port = st.selectbox(
            "Service Port",
            options=["8001 (Generated Workspace)", "8000 (Reference App)"],
            index=0,
            help="Select which running instance of the URL Shortener you want to interact with."
        )
        base_api_url = "http://127.0.0.1:8001" if "8001" in target_port else "http://127.0.0.1:8000"

        # Check connectivity
        import urllib.request
        import json as pyjson

        try:
            with urllib.request.urlopen(f"{base_api_url}/health", timeout=2) as r:
                h_data = pyjson.loads(r.read().decode())
                st.success(f"🟢 Connected to {base_api_url} — Service Status: `{h_data.get('status', 'unknown')}`")
        except Exception as err:
            st.warning(f"🟡 Connection check to {base_api_url}: {err}. Make sure the server is up.")

        st.markdown("#### 1️⃣ Create a Short URL")
        with st.form("create_url_form"):
            user_url_input = st.text_input("Destination URL", value="https://www.google.com")
            user_alias_input = st.text_input("Custom Short Code / Alias (Optional)", value="", placeholder="e.g. my-custom-link")
            submitted = st.form_submit_button("⚡ Shorten URL", use_container_width=True)

            if submitted:
                if not user_url_input.strip():
                    st.error("Please enter a valid URL.")
                else:
                    try:
                        payload = {"url": user_url_input.strip()}
                        if user_alias_input.strip():
                            payload["custom_alias"] = user_alias_input.strip()
                        req_data = pyjson.dumps(payload).encode("utf-8")
                        req = urllib.request.Request(
                            f"{base_api_url}/api/v1/urls/",
                            data=req_data,
                            headers={"Content-Type": "application/json"}
                        )
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            res = pyjson.loads(resp.read().decode())
                            st.session_state["last_short_code"] = res.get("short_code")
                            st.session_state["last_url_id"] = res.get("id")
                            st.session_state["last_short_url"] = res.get("short_url")

                            st.success("🎉 Short URL Created Successfully!")
                            c1, c2 = st.columns(2)
                            with c1:
                                st.text_input("Short Code", value=res.get("short_code", ""), disabled=True)
                                st.text_input("URL ID", value=str(res.get("id", "")), disabled=True)
                            with c2:
                                st.markdown(f"**Clickable Short URL:** [{res.get('short_url')}]({res.get('short_url')})")
                                st.code(pyjson.dumps(res, indent=2), language="json")
                    except Exception as e:
                        st.error(f"Error creating short URL: {e}")

        st.markdown("---")
        st.markdown("#### 2️⃣ Test Redirect & Record Clicks")
        col_red1, col_red2 = st.columns([3, 1])
        with col_red1:
            code_to_test = st.text_input(
                "Short Code to Redirect",
                value=st.session_state.get("last_short_code", "8e5db1a")
            )
        with col_red2:
            st.write("")
            st.write("")
            test_redirect_btn = st.button("🚀 Test Redirect", use_container_width=True)

        if test_redirect_btn:
            try:
                redirect_url = f"{base_api_url}/{code_to_test.strip()}"
                req = urllib.request.Request(redirect_url, headers={"User-Agent": "AgentForgePlayground/1.0"})
                # Prevent auto-following so we can inspect the 302
                class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
                    def http_error_302(self, req, fp, code, msg, headers):
                        return fp

                opener = urllib.request.build_opener(NoRedirectHandler)
                resp = opener.open(req, timeout=5)
                loc = resp.headers.get("Location") or resp.headers.get("location")
                if loc:
                    st.success(f"✅ HTTP 302 Found! Redirects destination: [{loc}]({loc})")
                else:
                    st.info(f"Response status: {resp.status}. Click recorded.")
            except Exception as e:
                st.error(f"Redirect error: {e}")

        st.markdown("---")
        st.markdown("#### 3️⃣ View Click Analytics")
        col_an1, col_an2 = st.columns([3, 1])
        with col_an1:
            url_id_to_check = st.number_input(
                "URL ID",
                min_value=1,
                value=int(st.session_state.get("last_url_id", 1)),
                step=1
            )
        with col_an2:
            st.write("")
            st.write("")
            get_analytics_btn = st.button("📊 Fetch Analytics", use_container_width=True)

        if get_analytics_btn:
            try:
                with urllib.request.urlopen(f"{base_api_url}/api/v1/urls/{url_id_to_check}/analytics", timeout=5) as resp:
                    an_data = pyjson.loads(resp.read().decode())
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Clicks", an_data.get("total_clicks", 0))
                    m2.metric("Clicks Today", an_data.get("clicks_today", 0))
                    m3.metric("Short Code", an_data.get("short_code", ""))

                    recent = an_data.get("recent_clicks", [])
                    if recent:
                        st.markdown("**Recent Click Events:**")
                        st.dataframe(recent)
                    else:
                        st.info("No clicks recorded yet for this URL.")
            except Exception as e:
                st.error(f"Error fetching analytics: {e}")

    with tab3:
        generated = state.get("generated_files", [])
        if generated:
            for gf in generated:
                with st.expander(f"`{gf.get('path', 'unknown')}` ({gf.get('action', 'create')})", expanded=False):
                    st.code(gf.get("content", ""), language="python")
        else:
            st.info("No files were generated in this run.")

        if state.get("git_diff"):
            st.markdown("### Git Diff")
            st.code(state["git_diff"], language="diff")

    with tab4:
        if test_results:
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Total Tests", test_results.get("total", 0))
            col_b.metric("Passed", test_results.get("passed_count", 0))
            col_c.metric("Failed", test_results.get("failed_count", 0))

            if test_results.get("output"):
                st.markdown("**Test Output:**")
                st.code(test_results["output"], language="text")

            if test_results.get("failed_tests"):
                st.markdown("**Failed Tests:**")
                for ft in test_results["failed_tests"]:
                    st.markdown(f"- ❌ `{ft}`")
        else:
            st.info("No test results available.")

    with tab5:
        col_r, col_t = st.columns(2)
        with col_r:
            st.markdown("### ⚠️ Risks")
            for risk in state.get("risks", []):
                st.markdown(f"- {risk}")

        with col_t:
            st.markdown("### ⚖️ Trade-offs")
            for to in state.get("tradeoffs", []):
                st.markdown(f"- {to}")

        if state.get("error_message"):
            st.markdown("### ❌ Error Details")
            st.error(state["error_message"])

    # Start over
    st.markdown("---")
    if st.button("↩️ New Requirement", type="secondary"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


def render_error_phase():
    """Show error state."""
    st.markdown('<div class="hero-title">⚙️ AgentForge</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.error("## ❌ An Error Occurred")
    st.exception(st.session_state.get("error", "Unknown error"))
    if st.button("↩️ Start Over"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ─── Main Router ─────────────────────────────────────────────────────────────
def main():
    # Always render workflow trace in sidebar (if past input phase)
    if st.session_state.get("phase", "input") != "input":
        render_workflow_trace()

    phase = st.session_state.get("phase", "input")

    phase_map = {
        "input": render_input_phase,
        "analyzing": render_analyzing_phase,
        "clarifying": render_clarifying_phase,
        "out_of_scope": render_out_of_scope_phase,
        "approval": render_approval_phase,
        "executing": render_executing_phase,
        "complete": render_complete_phase,
        "error": render_error_phase,
    }

    renderer = phase_map.get(phase, render_input_phase)
    renderer()


if __name__ == "__main__":
    main()
