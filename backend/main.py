"""
SafeOps — API Server
FastAPI application with REST endpoints and WebSocket support.
Now powered by a Multi-Agent Architecture:
  - Field Operator (Robotics-ER 1.6)
  - Auditor (Gemini 2.5 Pro)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from agents import Orchestrator

# ── Logging ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-20s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("safeops.api")


# ── Lifespan ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("  SafeOps — Multi-Agent Industrial Safety Intelligence")
    logger.info("  Agent 1: Field Operator (Robotics-ER 1.6)")
    logger.info("  Agent 2: Auditor (Gemini 2.5 Pro)")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    app.state.orchestrator = Orchestrator()
    app.state.ws_clients: set[WebSocket] = set()

    if not settings.GEMINI_API_KEY:
        logger.warning("⚠️  GEMINI_API_KEY not set — API calls will fail!")

    logger.info(f"Server ready on {settings.HOST}:{settings.PORT}")
    yield
    logger.info("SafeOps shutting down")


# ── App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="SafeOps Multi-Agent API",
    description="Industrial Safety powered by Gemini Robotics-ER 1.6 + Gemini 2.5 Pro",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Policy Configuration ──────────────────────────────────────────────

POLICY_FILE = Path(__file__).parent / "safety_policy.json"

@app.get("/api/policy")
async def get_policy():
    if POLICY_FILE.exists():
        with open(POLICY_FILE, 'r') as f:
            return json.load(f)
    return {"error": "Policy file not found"}

@app.post("/api/policy")
async def update_policy(policy: dict):
    with open(POLICY_FILE, 'w') as f:
        json.dump(policy, f, indent=2)
    return {"status": "success", "message": "Policy updated successfully"}


# ── Health Check ──────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "SafeOps",
        "version": "2.0.0",
        "architecture": "Multi-Agent",
        "agents": [
            {"name": "Field Operator", "model": settings.GEMINI_ROBOTICS_MODEL},
            {"name": "Auditor", "model": settings.GEMINI_PRO_MODEL},
        ],
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "gemini_key_set": bool(settings.GEMINI_API_KEY),
        "agents": ["FIELD_OPERATOR", "AUDITOR"],
    }


# ── Scene Analysis (Full Pipeline) ───────────────────────────────────

@app.post("/api/analyze")
async def analyze_scene(file: UploadFile = File(...)):
    """
    Full multi-agent analysis pipeline.
    Field Operator detects → Auditor validates compliance.
    """
    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"

    orchestrator: Orchestrator = app.state.orchestrator
    result = await orchestrator.analyze(image_bytes, mime_type, task="general")

    await _broadcast({"type": "analysis", "data": result})
    return result


@app.post("/api/analyze/base64")
async def analyze_scene_base64(payload: dict):
    """Analyze a base64-encoded image (webcam frames)."""
    image_b64 = payload.get("image", "")
    mime_type = payload.get("mime_type", "image/jpeg")
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]
    image_bytes = base64.b64decode(image_b64)

    orchestrator: Orchestrator = app.state.orchestrator
    result = await orchestrator.analyze(image_bytes, mime_type, task="general")

    await _broadcast({"type": "analysis", "data": result})
    return result


# ── Trajectory Analysis ──────────────────────────────────────────────

@app.post("/api/trajectory")
async def analyze_trajectory(file: UploadFile = File(...)):
    """Predict movement trajectories and collision risks."""
    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"

    orchestrator: Orchestrator = app.state.orchestrator
    result = await orchestrator.analyze(image_bytes, mime_type, task="trajectory")
    return result


# ── Gauge Reading ─────────────────────────────────────────────────────

@app.post("/api/gauge")
async def read_gauge(file: UploadFile = File(...)):
    """Read an analog gauge/meter from an industrial scene."""
    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"

    orchestrator: Orchestrator = app.state.orchestrator
    result = await orchestrator.analyze(image_bytes, mime_type, task="gauge")
    return result


# ── Robot Response ────────────────────────────────────────────────────

@app.post("/api/robot-response")
async def plan_robot_response(file: UploadFile = File(...)):
    """Simulate robot response using function calling."""
    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"

    orchestrator: Orchestrator = app.state.orchestrator
    result = await orchestrator.analyze(image_bytes, mime_type, task="robot_response")
    return result


# ── Compliance Report ─────────────────────────────────────────────────

@app.post("/api/report")
async def generate_report():
    """Generate compliance report (powered by Auditor agent)."""
    orchestrator: Orchestrator = app.state.orchestrator
    return await orchestrator.generate_report()


# ── Session Stats ─────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    """Get cumulative session statistics across all agents."""
    orchestrator: Orchestrator = app.state.orchestrator
    return orchestrator.get_stats()


# ── WebSocket ─────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    app.state.ws_clients.add(ws)
    logger.info(f"WebSocket connected (total: {len(app.state.ws_clients)})")

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "frame":
                image_b64 = msg.get("image", "")
                if "," in image_b64:
                    image_b64 = image_b64.split(",", 1)[1]
                image_bytes = base64.b64decode(image_b64)
                mime_type = msg.get("mime_type", "image/jpeg")

                orchestrator: Orchestrator = app.state.orchestrator
                result = await orchestrator.analyze(image_bytes, mime_type, task="general")
                await ws.send_json({"type": "analysis", "data": result})

            elif msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        app.state.ws_clients.discard(ws)
        logger.info(f"WebSocket disconnected (total: {len(app.state.ws_clients)})")


# ── Broadcast Helper ──────────────────────────────────────────────────

async def _broadcast(message: dict):
    if not app.state.ws_clients:
        return
    dead = set()
    payload = json.dumps(message, default=str)
    for ws in app.state.ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    app.state.ws_clients -= dead


# ── Entry Point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
