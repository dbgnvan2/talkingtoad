import os
import json
import logging
import asyncio
import time
import glob
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()
def get_api_key(name: str) -> Optional[str]:
    """Surgical resolution of API keys across project root and local dir."""
    key = os.getenv(name)
    if not key:
        load_dotenv(Path(__file__).parent.parent / ".env")
        key = os.getenv(name)
    if not key:
        load_dotenv(".env")
        key = os.getenv(name)
    return key

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ── SDLC Constants ───────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
DOCS_CYCLES_DIR = PROJECT_ROOT / 'docs' / 'cycles'
CYCLES_DIR = DOCS_CYCLES_DIR
SUMMARY_FILE = PROJECT_ROOT / "REPOSITORY_SUMMARY.md"
SERVER_START_TIME = time.time()

STATE_FILE = DOCS_CYCLES_DIR / "state.json"
ACTIVE_TASK_FILE = DOCS_CYCLES_DIR / "active_task.md"
TASK_OUTPUT_FILE = DOCS_CYCLES_DIR / "task_output.md"

DOCS_CYCLES_DIR.mkdir(parents=True, exist_ok=True)

# Export for tests
__all__ = ['app', 'SERVER_START_TIME', 'CYCLES_DIR', 'format_size', 'format_uptime', 'is_spec_file', 'get_directory_size']

# ── Grounding Utility ────────────────────────────────────────────────────────

def get_project_context() -> str:
    """Reads REPOSITORY_SUMMARY.md to provide 'Absolute Grounding Truth'."""
    if SUMMARY_FILE.exists():
        try:
            return SUMMARY_FILE.read_text()
        except Exception as e:
            logger.error(f"Failed to read summary file: {e}")
    return "Project: TalkingToad. Stack: Python 3.10+, FastAPI, Uvicorn, Vanilla JS Frontend."

# ── State Models ─────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str
    timestamp: str

class QASentinelContext(BaseModel):
    """Stores empirical evidence from the SDLC cycle."""
    spec_review_results: Dict = {"testability_score": 0.0, "missing_elements": [], "edge_cases": []}
    test_results: Dict = {"passed": 0, "failed": 0, "skipped": 0, "coverage": 0.0, "log": ""}
    git_status: Dict = {"pushed": False, "commit_hash": "", "branch": "main"}

class State(BaseModel):
    phase: str
    goal: str
    spec_path: str
    chat_history: List[Message]
    event_log: List[dict] = []
    provider: str = "gemini"
    qa_context: QASentinelContext = QASentinelContext()
    is_busy: bool = False

def load_state() -> State:
    if not STATE_FILE.exists():
        return State(phase="IDLE", goal="", spec_path="", chat_history=[], event_log=[])
    try:
        data = json.loads(STATE_FILE.read_text())
        return State(**data)
    except Exception as e:
        logger.error(f"State load failed: {e}")
        return State(phase="IDLE", goal="", spec_path="", chat_history=[], event_log=[])

def log_event(state: State, message: str):
    event = {"timestamp": datetime.now().isoformat(), "message": message}
    state.event_log.append(event)
    if len(state.event_log) > 100: state.event_log = state.event_log[-100:]

def save_state(state: State):
    try:
        STATE_FILE.write_text(json.dumps(state.model_dump(), indent=2))
    except Exception as e:
        logger.error(f"State save failed: {e}")

class ChatRequest(BaseModel):
    message: str
    provider: Optional[str] = None

# ── Grounded Roles ──────────────────────────────────────────────────────────

TRUTH_INSTRUCTIONS = f"""
## ABSOLUTE PROJECT TRUTH:
- **Framework**: FastAPI (Strictly use @app.get, @app.post, and return standard dicts).
- **Language**: Python 3.10+.
- **Primary Entry Point**: `orchestrator/app.py`.
- **Primary Test Suite**: `orchestrator/test_app.py`.
- **Handoff Mechanism**: docs/cycles/active_task.md (write only) -> docs/cycles/task_output.md (read only).
- **Prohibited Frameworks**: NO Flask, NO jsonify, NO @app.route.
- **Current Codebase Context**:
{get_project_context()[:500]}
"""

ARCHITECT_PROMPT = TRUTH_INSTRUCTIONS + "\nYou are the Architect. Create surgical spec."
SNR_SPEC_REVIEW_PROMPT = TRUTH_INSTRUCTIONS + "\nYou are the Snr Dev. Reject any Flask code."
QA_SPEC_REVIEW_PROMPT = TRUTH_INSTRUCTIONS + "\nYou are the QA Sentinel. Verify testability."
DEV_SPEC_REVIEW_PROMPT = TRUTH_INSTRUCTIONS + "\nYou are the Developer. AGREE or CHALLENGE."
SNR_IMPL_REVIEW_PROMPT = TRUTH_INSTRUCTIONS + "\nYou are the Snr Dev. Verify code against spec."
QA_VERIFY_PROMPT = TRUTH_INSTRUCTIONS + "\nYou are the QA Sentinel. Verify test logs match the goal."
GIT_PUBLISH_PROMPT = "You are the QA Sentinel. Confirm git publication."

IMPLEMENTATION_PROMPT_TEMPLATE = """You are the Developer implementing this spec:
{spec}
Goal: {goal}
Provide implementation code. Ensure the first line of your output is [IMPLEMENTATION COMPLETE]."""

# ── Utilities ───────────────────────────────────────────────────────────────

def is_approved(content: str) -> bool:
    c = content.upper()
    return any(x in c for x in ["APPROVED", "PASSES", "GREEN LIGHT", "READY"])

def is_agreed(content: str) -> bool:
    c = content.upper()
    return any(x in c for x in ["AGREE", "PROCEED", "IMPLEMENTING", "READY"])

def spool_task(state: State, task_description: str):
    ACTIVE_TASK_FILE.write_text(task_description)
    state.chat_history.append(Message(role="system", content="TASK SPOOLED TO DISK.", timestamp=datetime.now().isoformat()))
    state.chat_history.append(Message(role="dev", content="I have received the task from the Orchestrator and am now implementing.", timestamp=datetime.now().isoformat()))
    log_event(state, "Task handoff to Claude Code successful.")
    save_state(state)

def handle_qa_failure(state: State, phase: str, error: str):
    log_event(state, f"QA FAILURE in {phase}: {error}")
    state.chat_history.append(Message(role="system", content=f"QA ALERT: {error}. Rolling back.", timestamp=datetime.now().isoformat()))
    if phase == "QA_SPEC_REVIEW": state.phase = "ARCHITECT_SPEC"
    elif phase == "QA_VERIFY": state.phase = "IMPLEMENTATION"
    elif phase == "GIT_PUBLISH": state.phase = "QA_VERIFY"
    save_state(state)

# ── AI Router ───────────────────────────────────────────────────────────────

async def call_model(provider: str, role_prompt: str, user_content: str) -> str:
    if provider == "openai":
        key = get_api_key("OPENAI_API_KEY")
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": "gpt-4o", "messages": [{"role":"system","content":role_prompt},{"role":"user","content":user_content}], "temperature": 0.2},
                timeout=120.0)
            return resp.json()["choices"][0]["message"]["content"]
    elif provider == "deepseek":
        key = get_api_key("DEEPSEEK_API_KEY")
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": "deepseek-chat", "messages": [{"role":"system","content":role_prompt},{"role":"user","content":user_content}], "temperature": 0.2},
                timeout=120.0)
            return resp.json()["choices"][0]["message"]["content"]
    else:
        key = get_api_key("GEMINI_API_KEY")
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-3.0-pro")
        chat = model.start_chat(history=[])
        response = await asyncio.to_thread(chat.send_message, f"{role_prompt}\n\n{user_content}")
        return response.text

# ── State Machine Logic ─────────────────────────────────────────────────────

async def run_state_machine(state: State):
    if state.is_busy: return
    state.is_busy = True
    save_state(state)
    try:
        while True:
            if state.phase == "ARCHITECT_SPEC":
                log_event(state, "Architect drafting...")
                challenge_context = ""
                dev_msgs = [m.content for m in state.chat_history if m.role == "dev" and "CHALLENGE" in m.content.upper()]
                if dev_msgs: challenge_context = f"\n\nADDRESS CHALLENGE: {dev_msgs[-1]}"
                spec = await call_model(state.provider, ARCHITECT_PROMPT, state.goal + challenge_context)
                spec_path = DOCS_CYCLES_DIR / f"spec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                spec_path.write_text(spec)
                state.spec_path = str(spec_path)
                state.chat_history.append(Message(role="architect", content=spec, timestamp=datetime.now().isoformat()))
                state.phase = "SNR_SPEC_REVIEW"; save_state(state)

            elif state.phase == "SNR_SPEC_REVIEW":
                log_event(state, "Snr Dev reviewing spec...")
                spec = Path(state.spec_path).read_text()
                review = await call_model(state.provider, SNR_SPEC_REVIEW_PROMPT, spec)
                state.chat_history.append(Message(role="snr_dev", content=review, timestamp=datetime.now().isoformat()))
                state.phase = "QA_SPEC_REVIEW" if is_approved(review) else "ARCHITECT_SPEC"
                save_state(state)
                if state.phase == "ARCHITECT_SPEC": continue

            elif state.phase == "QA_SPEC_REVIEW":
                log_event(state, "QA reviewing spec...")
                spec = Path(state.spec_path).read_text()
                review = await call_model(state.provider, QA_SPEC_REVIEW_PROMPT, spec)
                state.chat_history.append(Message(role="qa", content=review, timestamp=datetime.now().isoformat()))
                state.phase = "DEV_SPEC_REVIEW" if is_approved(review) else "ARCHITECT_SPEC"
                save_state(state)
                if state.phase == "ARCHITECT_SPEC": continue

            elif state.phase == "DEV_SPEC_REVIEW":
                log_event(state, "Dev reviewing spec...")
                spec = Path(state.spec_path).read_text()
                snr_review = [m.content for m in state.chat_history if m.role == "snr_dev"][-1]
                response = await call_model(state.provider, DEV_SPEC_REVIEW_PROMPT, f"Spec: {spec}\n\nFeedback: {snr_review}")
                state.chat_history.append(Message(role="dev", content=response, timestamp=datetime.now().isoformat()))
                if is_agreed(response):
                    state.phase = "IMPLEMENTATION"; spool_task(state, IMPLEMENTATION_PROMPT_TEMPLATE.format(spec=spec, goal=state.goal))
                else: state.phase = "ARCHITECT_SPEC"
                save_state(state); break

            elif state.phase == "IMPLEMENTATION":
                if not ACTIVE_TASK_FILE.exists():
                    spec = Path(state.spec_path).read_text()
                    spool_task(state, IMPLEMENTATION_PROMPT_TEMPLATE.format(spec=spec, goal=state.goal))
                save_state(state); break

            elif state.phase == "SNR_IMPL_REVIEW":
                log_event(state, "Snr Dev reviewing code...")
                spec = Path(state.spec_path).read_text()
                code = state.chat_history[-1].content
                review = await call_model(state.provider, SNR_IMPL_REVIEW_PROMPT, f"Spec: {spec}\n\nCode: {code}")
                state.chat_history.append(Message(role="snr_dev", content=review, timestamp=datetime.now().isoformat()))
                if is_approved(review):
                    state.phase = "QA_VERIFY"; spool_task(state, f"TASK: Run pytest and provide logs.\nCODE:\n{code}")
                else:
                    state.phase = "IMPLEMENTATION"; spool_task(state, f"CODE REJECTED.\nFEEDBACK: {review}")
                save_state(state); break

            elif state.phase == "QA_VERIFY":
                log_event(state, "QA verifying logs...")
                spec = Path(state.spec_path).read_text()
                logs = state.chat_history[-1].content
                review = await call_model(state.provider, QA_VERIFY_PROMPT, f"Spec: {spec}\n\nLogs: {logs}")
                state.chat_history.append(Message(role="qa", content=review, timestamp=datetime.now().isoformat()))
                if is_approved(review): state.phase = "ARCHITECT_UPDATE"
                else:
                    state.phase = "IMPLEMENTATION"; spool_task(state, f"VERIFICATION FAILED.\nLOGS: {logs}")
                save_state(state)
                if state.phase == "IMPLEMENTATION": break
                continue

            elif state.phase == "ARCHITECT_UPDATE":
                log_event(state, "Syncing spec...")
                spec = Path(state.spec_path).read_text()
                impl_results = [m.content for m in state.chat_history if m.role == "user" and "COMPLETE" in m.content.upper()]
                impl_result = impl_results[0] if impl_results else "No code found."
                updated_spec = await call_model(state.provider, ARCHITECT_PROMPT, f"Spec: {spec}\n\nFinal Code: {impl_result}")
                Path(state.spec_path).write_text(updated_spec)
                state.chat_history.append(Message(role="architect", content=f"As-Built Spec Updated:\n\n{updated_spec}", timestamp=datetime.now().isoformat()))
                state.phase = "GIT_PUBLISH"; spool_task(state, f"TASK: Commit and push changes.")
                save_state(state); break

            elif state.phase == "GIT_PUBLISH":
                log_event(state, "Finalizing...")
                report = await call_model(state.provider, GIT_PUBLISH_PROMPT, state.chat_history[-1].content)
                state.chat_history.append(Message(role="qa", content=report, timestamp=datetime.now().isoformat()))
                state.phase = "IDLE"; state.goal = ""; save_state(state); break
    except Exception as e:
        logger.exception("Engine Failure"); log_event(state, f"ERROR: {str(e)}"); state.phase = "IDLE"; save_state(state)
    finally:
        state.is_busy = False
        save_state(state)

# ── Background Automation ───────────────────────────────────────────────────

async def poll_for_task_output():
    while True:
        try:
            if TASK_OUTPUT_FILE.exists():
                state = load_state()
                if not state.is_busy:
                    output = TASK_OUTPUT_FILE.read_text()
                    state.chat_history.append(Message(role="user", content=output, timestamp=datetime.now().isoformat()))
                    if state.phase == "IMPLEMENTATION": state.phase = "SNR_IMPL_REVIEW"
                    save_state(state)
                    asyncio.create_task(run_state_machine(state))
                    TASK_OUTPUT_FILE.unlink()
                    if ACTIVE_TASK_FILE.exists(): ACTIVE_TASK_FILE.unlink()
        except Exception as e: logger.error(f"Poller: {e}")
        await asyncio.sleep(2)

@app.on_event("startup")
async def startup_event(): asyncio.create_task(poll_for_task_output())

# ── API ─────────────────────────────────────────────────────────────────────

@app.get("/api/state")
async def get_state(): return load_state()

@app.post("/api/chat")
async def chat(request: ChatRequest):
    state = load_state()
    if state.phase != "IDLE": return {"status": "error", "message": "Machine busy."}
    state.goal = request.message; state.provider = request.provider or state.provider
    state.phase = "ARCHITECT_SPEC"; asyncio.create_task(run_state_machine(state)); return {"status": "ok"}

@app.post("/api/reset")
async def reset():
    state = State(phase="IDLE", goal="", spec_path="", chat_history=[], event_log=[], provider="gemini")
    save_state(state); return {"status": "ok"}

@app.post("/api/rerun")
async def rerun():
    state = load_state()
    goal, provider = state.goal, state.provider
    if not goal: return {"status": "error"}
    for f in DOCS_CYCLES_DIR.glob("spec_*.md"): f.unlink()
    if ACTIVE_TASK_FILE.exists(): ACTIVE_TASK_FILE.unlink()
    if TASK_OUTPUT_FILE.exists(): TASK_OUTPUT_FILE.unlink()
    new_state = State(phase="ARCHITECT_SPEC", goal=goal, provider=provider, chat_history=[], event_log=[])
    log_event(new_state, "🔄 ATOMIC RE-RUN START.")
    save_state(new_state)
    asyncio.create_task(run_state_machine(new_state)); return {"status": "ok"}

# ── Health & Diagnostics Helpers ─────────────────────────────────────────────

def get_directory_size(path: str) -> int:
    """Calculate total size of all files in a directory recursively."""
    dir_path = Path(path)
    if not dir_path.exists() or not dir_path.is_dir():
        return 0
    total_size = 0
    try:
        for file_path in dir_path.rglob("*"):
            if file_path.is_file():
                try:
                    total_size += file_path.stat().st_size
                except (OSError, PermissionError): continue
    except PermissionError: return 0
    return total_size

def format_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format."""
    value = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if value < 1024: return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"

def format_uptime(seconds: int) -> str:
    """Format seconds into human-readable uptime string."""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)

def is_spec_file(file_path: Path) -> bool:
    """Determine if a file is a spec file based on naming conventions."""
    spec_patterns = ["spec", "specification", "requirements", "design_doc", "architecture", "api_spec"]
    name_lower = file_path.stem.lower()
    return any(pattern in name_lower for pattern in spec_patterns)

# ── Health & Diagnostics Endpoints ───────────────────────────────────────────

@app.get("/health")
async def health():
    """Returns server uptime and docs/cycles/ directory size."""
    uptime_seconds = time.time() - SERVER_START_TIME
    size_bytes = get_directory_size(str(DOCS_CYCLES_DIR))
    return {
        "status": "healthy",
        "uptime_seconds": uptime_seconds,
        "uptime_formatted": format_uptime(int(uptime_seconds)),
        "cycles_directory_size_bytes": size_bytes,
        "cycles_directory_size_human": format_size(size_bytes),
        "start_time": datetime.fromtimestamp(SERVER_START_TIME, tz=timezone.utc).isoformat(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/api/diagnostics")
async def diagnostics():
    """Returns metadata-rich list of all spec files on disk."""
    spec_files = []
    search_paths = [Path("docs"), Path("specs"), Path(".")]
    for base_path in search_paths:
        if base_path.exists() and base_path.is_dir():
            for file_path in base_path.rglob("*"):
                if file_path.is_file() and is_spec_file(file_path):
                    stat = file_path.stat()
                    spec_files.append({
                        "path": str(file_path),
                        "filename": file_path.name,
                        "extension": file_path.suffix,
                        "size_bytes": stat.st_size,
                        "size_human": format_size(stat.st_size),
                        "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                        "created": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
                        "directory": str(file_path.parent),
                        "is_spec": True,
                    })
    spec_files.sort(key=lambda x: x["path"])
    total_size = sum(f["size_bytes"] for f in spec_files)
    return {
        "total_spec_files": len(spec_files),
        "spec_files": spec_files,
        "total_size_bytes": total_size,
        "total_size_human": format_size(total_size),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

app.mount("/static", StaticFiles(directory="orchestrator/static"), name="static")
@app.get("/")
async def read_index(): return FileResponse("orchestrator/static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
