"""
SafeOps -- API Server v3.0
FastAPI application with REST endpoints and WebSocket support.
Multi-Agent Architecture powered by Gemini:
- Field Operator (Robotics-ER 1.6) -- Visual perception + instrument reading
- Response Agent (Robotics-ER 1.6) -- Robot function calling
- Auditor (Gemini 2.5 Pro) -- OSHA compliance + financial impact
- Supervisor (Gemini 2.5 Pro) -- AI workflow orchestration
- VEEA Guard (Lobster Trap) -- Prompt security inspection

New endpoints for Track 3 (Robotics & Simulation):
- /api/analyze/instrument -- Specialized instrument reading
- /api/analyze/trajectory -- Video trajectory prediction
- /api/analyze/multiview -- Multi-camera spatial fusion
- /api/agents/supervisor -- Supervisor decisions and memory
- /api/security/stats -- VEEA Lobster Trap security stats
- /api/security/audit -- Full security audit trail
- /api/digital-twin -- 3D scene state for digital twin
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
from pydantic import BaseModel
from config import settings
from agents import Orchestrator

# -- Logging --------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("safeops.api")

# -- Lifespan -------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("  SafeOps v3.0 -- Multi-Agent Industrial Safety")
    logger.info("  Field Operator : %s", settings.GEMINI_ROBOTICS_MODEL)
    logger.info("  Response Agent : %s", settings.GEMINI_ROBOTICS_MODEL)
    logger.info("  Auditor        : %s", settings.GEMINI_PRO_MODEL)
    logger.info("  Supervisor     : %s", settings.GEMINI_PRO_MODEL)
    logger.info("  VEEA Guard     : %s", "ENABLED" if settings.LOBSTER_TRAP_ENABLED else "standby")
    logger.info("  X402 Payments  : %s", "ENABLED" if settings.X402_ENABLED else "disabled")
    logger.info("  Agentic Vision : %s", "ON" if settings.AGENTIC_VISION_ENABLED else "OFF")
    logger.info("  Multi-view     : %s", "ON" if settings.MULTIVIEW_FUSION_ENABLED else "OFF")
    logger.info("=" * 60)

    app.state.orchestrator = Orchestrator()
    app.state.ws_clients: set[WebSocket] = set()

    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set -- API calls will fail!")

    logger.info("Server ready on %s:%d", settings.HOST, settings.PORT)
    yield
    logger.info("SafeOps shutting down")

# -- App ------------------------------------------------------------------

app = FastAPI(
    title="SafeOps Multi-Agent API v3.0",
    description="Industrial Safety powered by Gemini Robotics-ER 1.6 + Gemini 2.5 Pro + VEEA Lobster Trap",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Request Models -------------------------------------------------------

class InstrumentRequest(BaseModel):
    instrument_type: str = "gauge"
    mime_type: str = "image/jpeg"

class MultiviewRequest(BaseModel):
    mime_types: list[str] = ["image/jpeg", "image/jpeg", "image/jpeg", "image/jpeg"]

class PolicyUpdateRequest(BaseModel):
    policy: dict

class LobsterTrapConfigRequest(BaseModel):
    enabled: bool
    url: str = "http://localhost:8080"

# -- Helper: broadcast to WebSockets --------------------------------------

async def broadcast(ws_clients: set[WebSocket], message: dict):
    """Broadcast a message to all connected WebSocket clients."""
    dead = set()
    for ws in ws_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)
    for ws in dead:
        ws_clients.discard(ws)

# -- Endpoints ------------------------------------------------------------

@app.get("/")
async def root():
    """Service status and feature overview."""
    return {
        "service": "SafeOps v3.0",
        "track": "Track 3: Robotics & Simulation",
        "hackathon": "TechEx Intelligent Enterprise Solutions",
        "models": {
            "field_operator": settings.GEMINI_ROBOTICS_MODEL,
            "response_agent": settings.GEMINI_ROBOTICS_MODEL,
            "auditor": settings.GEMINI_PRO_MODEL,
            "supervisor": settings.GEMINI_PRO_MODEL,
        },
        "features": {
            "agentic_vision": settings.AGENTIC_VISION_ENABLED,
            "multiview_fusion": settings.MULTIVIEW_FUSION_ENABLED,
            "instrument_reading": True,
            "trajectory_prediction": True,
            "function_calling": True,
            "veea_lobster_trap": settings.LOBSTER_TRAP_ENABLED,
            "x402_payments": settings.X402_ENABLED,
            "digital_twin": settings.DIGITAL_TWIN_ENABLED,
        },
        "agents": [
            {
                "name": "Field Operator",
                "model": settings.GEMINI_ROBOTICS_MODEL,
                "role": "Visual perception, spatial reasoning, instrument reading",
            },
            {
                "name": "Response Agent",
                "model": settings.GEMINI_ROBOTICS_MODEL,
                "role": "Robot action planning via function calling",
            },
            {
                "name": "Auditor",
                "model": settings.GEMINI_PRO_MODEL,
                "role": "OSHA compliance, financial impact, audit reports",
            },
            {
                "name": "Supervisor",
                "model": settings.GEMINI_PRO_MODEL,
                "role": "AI workflow orchestration and memory",
            },
            {
                "name": "VEEA Guard",
                "model": "Lobster Trap DPI",
                "role": "Prompt security inspection and audit trail",
            },
        ],
    }

# -- Standard analysis endpoint -------------------------------------------

@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
):
    """
    Standard scene analysis -- single image.
    Returns full multi-agent pipeline result with field operator + auditor.
    """
    orchestrator: Orchestrator = app.state.orchestrator
    image_data = await file.read()

    result = await orchestrator.run_pipeline(
        [{"data": image_data, "mime_type": file.content_type or "image/jpeg"}],
        operation_type="standard",
    )

    await broadcast(app.state.ws_clients, {
        "type": "analysis_complete",
        "operation_id": result.get("operation_id"),
        "risk_level": result.get("agents", {}).get("field_operator", {}).get("overall_risk_level"),
        "timestamp": datetime.utcnow().isoformat(),
    })

    return result

# -- Instrument reading endpoint (KILLER FEATURE) -------------------------

@app.post("/api/analyze/instrument")
async def analyze_instrument(
    file: UploadFile = File(...),
    instrument_type: str = "gauge",
):
    """
    Specialized instrument reading with agentic vision.
    Uses code execution for 93% accuracy on analog gauges, sight glasses, digital displays.
    This is the feature validated by Boston Dynamics Spot.
    """
    orchestrator: Orchestrator = app.state.orchestrator
    image_data = await file.read()

    result = await orchestrator.run_instrument_reading(
        image_data,
        instrument_type=instrument_type,
        mime_type=file.content_type or "image/jpeg",
    )

    await broadcast(app.state.ws_clients, {
        "type": "instrument_reading",
        "operation_id": result.get("operation_id"),
        "instrument_type": instrument_type,
        "timestamp": datetime.utcnow().isoformat(),
    })

    return result

# -- Trajectory prediction endpoint ---------------------------------------

@app.post("/api/analyze/trajectory")
async def analyze_trajectory(
    file: UploadFile = File(...),
):
    """
    Video trajectory prediction.
    Analyzes video frames to track objects and predict collision trajectories.
    Returns predicted paths and imminent collision alerts.
    """
    orchestrator: Orchestrator = app.state.orchestrator
    video_data = await file.read()

    result = await orchestrator.run_trajectory_analysis(
        video_data,
        mime_type=file.content_type or "video/mp4",
    )

    await broadcast(app.state.ws_clients, {
        "type": "trajectory_analysis",
        "operation_id": result.get("operation_id"),
        "timestamp": datetime.utcnow().isoformat(),
    })

    return result

# -- Multi-view fusion endpoint -------------------------------------------

@app.post("/api/analyze/multiview")
async def analyze_multiview(
    files: list[UploadFile] = File(...),
):
    """
    Multi-camera spatial fusion analysis.
    Fuses up to 4 camera views into a single coherent scene understanding.
    ER 1.6 performs cross-view tracking and 3D spatial reasoning.
    """
    if len(files) < 2:
        return {"error": "At least 2 camera views required for multi-view fusion"}
    if len(files) > 4:
        files = files[:4]

    orchestrator: Orchestrator = app.state.orchestrator
    media_list = []
    for f in files:
        media_list.append({
            "data": await f.read(),
            "mime_type": f.content_type or "image/jpeg",
        })

    result = await orchestrator.run_multiview_analysis(media_list)

    await broadcast(app.state.ws_clients, {
        "type": "multiview_fusion",
        "operation_id": result.get("operation_id"),
        "num_views": len(files),
        "timestamp": datetime.utcnow().isoformat(),
    })

    return result

# -- Supervisor endpoint --------------------------------------------------

@app.get("/api/agents/supervisor")
async def get_supervisor_state():
    """
    Get supervisor decisions, memory, and active alarms.
    Shows AI-driven workflow orchestration in action.
    """
    orchestrator: Orchestrator = app.state.orchestrator
    return {
        "supervisor": orchestrator.supervisor.get_memory_summary(),
        "workflow_decisions": list(orchestrator.supervisor.memory)[-10:],
        "active_alarms": orchestrator.supervisor.active_alarms,
        "total_operations": orchestrator.stats["total_operations"],
    }

# -- VEEA Lobster Trap security endpoints ---------------------------------

@app.get("/api/security/stats")
async def get_security_stats():
    """
    Get VEEA Lobster Trap security statistics.
    Shows prompt inspection counts, threats blocked, and audit data.
    """
    orchestrator: Orchestrator = app.state.orchestrator
    return orchestrator.veea.get_stats()

@app.get("/api/security/audit")
async def get_security_audit(limit: int = 50):
    """
    Get full security audit trail from VEEA Guard.
    Compliance-grade logging of all agent interactions.
    """
    orchestrator: Orchestrator = app.state.orchestrator
    return orchestrator.veea.get_audit_trail(limit=limit)

@app.get("/api/security/lobster-trap/config")
async def get_lobster_trap_config():
    """
    Get Lobster Trap integration configuration.
    Shows how to set up the DPI proxy for agent security.
    """
    orchestrator: Orchestrator = app.state.orchestrator
    return orchestrator.veea.get_lobster_trap_config()

@app.post("/api/security/lobster-trap/configure")
async def configure_lobster_trap(req: LobsterTrapConfigRequest):
    """
    Enable/disable Lobster Trap integration.
    """
    orchestrator: Orchestrator = app.state.orchestrator
    orchestrator.veea.enabled = req.enabled
    orchestrator.veea.lobster_trap_url = req.url
    settings.LOBSTER_TRAP_ENABLED = req.enabled
    settings.LOBSTER_TRAP_URL = req.url
    return {
        "enabled": req.enabled,
        "url": req.url,
        "status": "configured",
    }

# -- Policy endpoints -----------------------------------------------------

@app.get("/api/policy")
async def get_policy():
    """Get current safety policy configuration."""
    policy_path = Path(__file__).parent / "safety_policy.json"
    if policy_path.exists():
        return json.loads(policy_path.read_text())
    return {"error": "Policy file not found"}

@app.post("/api/policy")
async def update_policy(req: PolicyUpdateRequest):
    """Update safety policy configuration."""
    policy_path = Path(__file__).parent / "safety_policy.json"
    policy_path.write_text(json.dumps(req.policy, indent=2))
    return {"status": "updated", "policy": req.policy}

# -- Statistics endpoint --------------------------------------------------

@app.get("/api/stats")
async def get_stats():
    """Get pipeline statistics and agent performance metrics."""
    orchestrator: Orchestrator = app.state.orchestrator
    return orchestrator.get_stats()

# -- Audit trail endpoint -------------------------------------------------

@app.get("/api/audit")
async def get_audit():
    """Get complete audit trail including VEEA and Supervisor data."""
    orchestrator: Orchestrator = app.state.orchestrator
    return orchestrator.get_audit_trail()

# -- WebSocket endpoint ---------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time WebSocket for live analysis updates."""
    await websocket.accept()
    app.state.ws_clients.add(websocket)
    logger.info("WebSocket client connected | Total: %d", len(app.state.ws_clients))

    try:
        await websocket.send_json({
            "type": "connected",
            "message": "SafeOps v3.0 real-time feed active",
            "features": {
                "agentic_vision": settings.AGENTIC_VISION_ENABLED,
                "multiview_fusion": settings.MULTIVIEW_FUSION_ENABLED,
                "veea_lobster_trap": settings.LOBSTER_TRAP_ENABLED,
            },
        })

        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
    finally:
        app.state.ws_clients.discard(websocket)

# -- Health check ---------------------------------------------------------

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "3.0.0",
        "models_available": bool(settings.GEMINI_API_KEY),
        "timestamp": datetime.utcnow().isoformat(),
    }

# -- Run ------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level="info",
    )
