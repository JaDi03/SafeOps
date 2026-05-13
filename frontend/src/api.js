/**
 * SafeOps — API Client
 * Communicates with the FastAPI backend for scene analysis,
 * object detection, trajectory, gauge reading, digital twin,
 * robot response simulation, and compliance reports.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_BASE  = import.meta.env.VITE_WS_URL  || 'ws://localhost:8000';

/* ── REST Helpers ──────────────────────────────────────────────── */

async function postFile(endpoint, file) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}${endpoint}`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json();
}

async function postJSON(endpoint, data) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json();
}

async function get(endpoint) {
  const res = await fetch(`${API_BASE}${endpoint}`);
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json();
}

/* ── Public API ────────────────────────────────────────────────── */

/** Full safety scene analysis (file upload). */
export async function analyzeScene(file) {
  return postFile('/api/analyze', file);
}

/** Full safety analysis from base64 image (webcam frame). */
export async function analyzeBase64(imageBase64, mimeType = 'image/jpeg') {
  return postJSON('/api/analyze/base64', { image: imageBase64, mime_type: mimeType });
}

/** Object detection with bounding boxes. */
export async function detectObjects(file) {
  return postFile('/api/detect', file);
}

/** Trajectory prediction & collision risk. */
export async function analyzeTrajectory(file) {
  return postFile('/api/trajectory', file);
}

/** Analog gauge reading. */
export async function readGauge(file) {
  return postFile('/api/gauge', file);
}

/** Build 2D digital twin of the scene. */
export async function buildDigitalTwin(file) {
  return postFile('/api/digital-twin', file);
}

/** Robot response simulation via function calling. */
export async function planRobotResponse(file) {
  return postFile('/api/robot-response', file);
}

/** Annotate image with hazard markers (code execution). */
export async function annotateImage(file) {
  return postFile('/api/annotate', file);
}

/** Generate OSHA compliance report. */
export async function generateReport() {
  return postJSON('/api/report', {});
}

/** Get session statistics. */
export async function getStats() {
  return get('/api/stats');
}

/** Get safety policy. */
export async function getPolicy() {
  return get('/api/policy');
}

/** Update safety policy. */
export async function updatePolicy(policy) {
  return postJSON('/api/policy', policy);
}

/** Health check. */
export async function healthCheck() {
  return get('/health');
}

/* ── WebSocket ─────────────────────────────────────────────────── */

/**
 * Create a WebSocket connection for real-time streaming.
 * Returns { send, close, ws } object.
 */
export function createWSConnection(onMessage, onStatus) {
  let ws = null;
  let reconnectTimer = null;

  function connect() {
    ws = new WebSocket(`${WS_BASE}/ws`);

    ws.onopen = () => {
      onStatus?.('connected');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        onMessage?.(msg);
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    ws.onclose = () => {
      onStatus?.('disconnected');
      // Auto-reconnect after 3 seconds
      reconnectTimer = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      onStatus?.('error');
    };
  }

  connect();

  return {
    send: (data) => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(data));
      }
    },
    close: () => {
      clearTimeout(reconnectTimer);
      ws?.close();
    },
    get ws() { return ws; },
  };
}
