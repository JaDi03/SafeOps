import { useState, useRef, useCallback, useEffect } from 'react';
import './index.css';
import { 
  analyzeScene, 
  readGauge, 
  analyzeTrajectory, 
  planRobotResponse, 
  getStats, 
  generateReport,
  getPolicy,
  updatePolicy
} from './api';

/* ── Helpers ───────────────────────────────────────────────────── */

const RISK_EMOJI = { safe: '✅', low: '🟢', medium: '🟡', high: '🟠', critical: '🔴' };
const HAZARD_EMOJI = {
  ppe_missing: '🪖', zone_intrusion: '🚧', proximity_danger: '⚡',
  spill_detected: '💧', posture_unsafe: '🦴', collision_risk: '💥',
  exit_blocked: '🚪', gauge_anomaly: '🔧', equipment_misuse: '⚠️', fire_risk: '🔥',
};

function formatUSD(n) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
}

/* ── Components ────────────────────────────────────────────────── */

const ViewSlot = ({ id, title, icon, onFileSelect, preview, loading, data, specialty }) => {
  const fileInputRef = useRef(null);
  const canvasRef = useRef(null);
  const [fileType, setFileType] = useState('image');

  const handleClick = () => fileInputRef.current?.click();

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setFileType(file.type.startsWith('video') ? 'video' : 'image');
    onFileSelect(id, file);
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data) return;

    const ctx = canvas.getContext('2d');
    const { width, height } = canvas.getBoundingClientRect();
    canvas.width = width;
    canvas.height = height;

    ctx.clearRect(0, 0, width, height);

    const scaleX = (x) => (x / 1000) * width;
    const scaleY = (y) => (y / 1000) * height;

    // ── Draw Bounding Boxes (Detected Objects) ──
    if (data.detected_objects) {
      data.detected_objects.forEach(obj => {
        // Robotics-ER returns box_2d as [ymin, xmin, ymax, xmax]
        const box = obj.box_2d || obj.bounding_box;
        if (box && Array.isArray(box)) {
          const [ymin, xmin, ymax, xmax] = box;
          ctx.strokeStyle = '#3b82f6';
          ctx.lineWidth = 2;
          ctx.strokeRect(scaleX(xmin), scaleY(ymin), scaleX(xmax - xmin), scaleY(ymax - ymin));
          
          ctx.fillStyle = '#3b82f6';
          ctx.font = 'bold 12px Inter';
          ctx.fillText(obj.label || obj.category, scaleX(xmin), scaleY(ymin) - 5);
        }
      });
    }

    // ── Draw Hazards (Red Dots) ──
    if (data.hazards) {
      data.hazards.forEach(h => {
        // Robotics-ER returns location as [y, x]
        const loc = h.location;
        if (loc && Array.isArray(loc)) {
          const [y, x] = loc;
          ctx.fillStyle = h.risk_level === 'critical' ? '#ef4444' : '#f59e0b';
          ctx.shadowBlur = 10;
          ctx.shadowColor = ctx.fillStyle;
          ctx.beginPath();
          ctx.arc(scaleX(x), scaleY(y), 8, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = 'white';
          ctx.lineWidth = 2;
          ctx.stroke();
          ctx.shadowBlur = 0;
        }
      });
    }

    // ── Draw Trajectories (Predicted Paths) ──
    const entities = data.entities || [];
    entities.forEach(entity => {
      const path = entity.predicted_trajectory;
      if (path && path.length > 1) {
        ctx.strokeStyle = '#10b981';
        ctx.setLineDash([5, 5]);
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        // Robotics-ER returns trajectory points as [y, x]
        const startPos = entity.current_position || path[0];
        ctx.moveTo(scaleX(startPos[1]), scaleY(startPos[0]));
        
        path.forEach(pt => {
          ctx.lineTo(scaleX(pt[1]), scaleY(pt[0]));
        });
        ctx.stroke();
        ctx.setLineDash([]);
      }
    });
  }, [data, preview]);

  return (
    <div className={`view-slot ${loading ? 'loading' : ''}`} onClick={!preview ? handleClick : undefined}>
      <div className="view-slot-header">
        <div className="view-slot-title">
          <span>{icon}</span> {title}
        </div>
        {preview && <span className="view-slot-badge">{specialty}</span>}
      </div>
      <input type="file" ref={fileInputRef} hidden accept="image/*,video/*" onChange={handleFileChange} />
      {preview ? (
        <div style={{ width: '100%', height: '100%', position: 'relative' }}>
          {fileType === 'video' ? (
            <video src={preview} autoPlay muted loop style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <img src={preview} alt={title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          )}
          <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }} />
          {loading && <div className="loading-overlay"><div className="spinner" /></div>}
          <div className="view-slot-controls">
            <button className="btn btn-sm btn-outline" onClick={(e) => { e.stopPropagation(); handleClick(); }}>🔄 Change</button>
          </div>
        </div>
      ) : (
        <div className="view-slot-placeholder">
          <div style={{ fontSize: '1.5rem', opacity: 0.5 }}>{icon}</div>
          <div>Click to Add Source</div>
        </div>
      )}
    </div>
  );
};

/* ── Main App ──────────────────────────────────────────────────── */

export default function App() {
  const [slots, setSlots] = useState({
    s1: { id: 's1', title: 'Safety Vision', icon: '🔍', specialty: 'General Analysis', preview: null, loading: false, data: null },
    s2: { id: 's2', title: 'Trajectory AI', icon: '📈', specialty: 'Spatial Prediction', preview: null, loading: false, data: null },
    s3: { id: 's3', title: 'Gauge Intel', icon: '🔧', specialty: 'Code Execution', preview: null, loading: false, data: null },
    s4: { id: 's4', title: 'Operation Control', icon: '🤖', specialty: 'Function Calling', preview: null, loading: false, data: null },
  });

  const [globalStats, setGlobalStats] = useState(null);
  const [activeTab, setActiveTab] = useState('hazards');
  const [isSystemActive, setIsSystemActive] = useState(false);
  const [isPolicyOpen, setIsPolicyOpen] = useState(false);
  const [lastAnalysisTime, setLastAnalysisTime] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [policy, setPolicy] = useState(null);
  const [policyDraft, setPolicyDraft] = useState('');

  // Load stats & policy
  useEffect(() => {
    const fetchData = async () => {
      try { 
        const s = await getStats(); setGlobalStats(s); 
        const p = await getPolicy(); setPolicy(p); setPolicyDraft(JSON.stringify(p, null, 2));
      } catch(e) {}
    };
    fetchData();
    const interval = setInterval(async () => {
      if (!isSystemActive) return; 
      try { const s = await getStats(); setGlobalStats(s); } catch(e) {}
    }, 10000);
    return () => clearInterval(interval);
  }, [isSystemActive]);

  const handleFileSelect = (slotId, file) => {
    if (!file) return;
    const previewUrl = URL.createObjectURL(file);
    setSlots(prev => ({ 
      ...prev, 
      [slotId]: { 
        ...prev[slotId], 
        preview: previewUrl, 
        file: file, 
        loading: false, 
        data: null 
      } 
    }));
  };

  // ── Smart Continuous Monitoring Loop ──
  useEffect(() => {
    let timeoutId;
    
    const runSentinel = async () => {
      if (isSystemActive) {
        await startOperation();
        // Only schedule the next run after the current one finishes
        timeoutId = setTimeout(runSentinel, 5000); 
      }
    };

    if (isSystemActive) {
      runSentinel();
    }

    return () => clearTimeout(timeoutId);
  }, [isSystemActive]);

  const startOperation = async () => {
    const activeSlots = Object.values(slots).filter(s => s.file);
    if (activeSlots.length === 0) {
      if (isSystemActive) setIsSystemActive(false);
      return;
    }
    
    // Set loading state for active slots
    setSlots(prev => {
      const next = { ...prev };
      activeSlots.forEach(s => { next[s.id] = { ...next[s.id], loading: true }; });
      return next;
    });

    try {
      const result = await analyzeScene(activeSlots.map(s => s.file));
      setAnalysisResult(result);
      setLastAnalysisTime(new Date().toLocaleTimeString());
      
      setSlots(prev => {
        const next = { ...prev };
        activeSlots.forEach(s => {
          next[s.id] = { ...next[s.id], loading: false, data: result.field_report };
        });
        return next;
      });
    } catch (err) {
      console.error(`Sentinel analysis cycle failed:`, err);
      setSlots(prev => {
        const next = { ...prev };
        activeSlots.forEach(s => { next[s.id] = { ...next[s.id], loading: false }; });
        return next;
      });
    }
  };

  const stopOperation = () => {
    setIsSystemActive(false);
  };

  const savePolicy = async () => {
    try {
      const newPolicy = JSON.parse(policyDraft);
      await updatePolicy(newPolicy);
      setPolicy(newPolicy);
      setIsPolicyOpen(false);
      alert('Plant Policy Updated Successfully!');
    } catch (err) {
      alert('Invalid JSON format in policy');
    }
  };

  const handleGenerateReport = async () => {
    try {
      const result = await generateReport();
      const w = window.open('', '_blank');
      w.document.write(`<html><head><title>SafeOps Report</title><style>body{background:#0a0e1a;color:#fff;font-family:sans-serif;padding:40px;}pre{color:#94a3b8;}</style></head><body><h1>🛡️ SafeOps Report</h1><pre>${result.report}</pre></body></html>`);
    } catch (err) { alert('Error generating report'); }
  };

  const allHazards = Object.values(slots).filter(s => s.data?.hazards).flatMap(s => s.data.hazards);
  const latestAudit = Object.values(slots).filter(s => s.data?.audit).reverse()[0]?.data?.audit || null;
  const latestFinancial = latestAudit?.financial_summary || {};
  const worstRisk = Object.values(slots).filter(s => s.data?.overall_risk_level).map(s => s.data.overall_risk_level).reduce((acc, curr) => {
    const priority = { critical: 4, high: 3, medium: 2, low: 1, safe: 0 };
    return priority[curr] > priority[acc] ? curr : acc;
  }, 'safe');
  const avgScore = Object.values(slots).filter(s => s.data?.overall_risk_score).map(s => s.data.overall_risk_score);
  const currentScore = avgScore.length > 0 ? Math.max(...avgScore) : 0;

  return (
    <div className="app">
      <header className="header">
        <div className="header-brand">
          <div className="header-logo">🛡️</div>
          <div className="header-title">SafeOps Enterprise</div>
          <div className="header-subtitle">Multi-Agent: Robotics-ER 1.6 + Gemini 2.5 Pro</div>
        </div>
        <div className="header-status flex items-center gap-4">
          <button className="btn btn-outline btn-sm" onClick={() => setIsPolicyOpen(true)}>⚙️ Policy</button>
          
          <div className="flex gap-4 items-center">
            {!isSystemActive ? (
              <button
                onClick={() => setIsSystemActive(true)}
                className="px-8 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl font-bold hover:shadow-[0_0_20px_rgba(37,99,235,0.4)] transition-all flex items-center gap-2"
              >
                🚀 START SENTINEL
              </button>
            ) : (
              <button
                onClick={stopOperation}
                className="px-8 py-3 bg-red-500/20 text-red-400 border border-red-500/50 rounded-xl font-bold shadow-[0_0_15px_rgba(239,68,68,0.3)] transition-all flex items-center gap-2"
              >
                <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                🛑 STOP SYSTEM
              </button>
            )}

            <button 
              className="px-4 py-3 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-all text-white font-bold"
              onClick={handleGenerateReport}
            >
              📝 REPORT
            </button>
          </div>
        </div>

        {lastAnalysisTime && isSystemActive && (
          <div className="flex items-center gap-2 mb-6 px-4 py-2 bg-white/5 rounded-lg border border-white/10 w-fit">
            <span className="text-xs text-white/40 uppercase tracking-widest font-medium">Last Intelligence Sync:</span>
            <span className="text-xs text-blue-400 font-mono">{lastAnalysisTime}</span>
          </div>
        )}
      </header>

      <main className="main-content">
        <div className={`risk-banner ${worstRisk}`}>
          <div className="risk-banner-left">
            <div className={`risk-score-circle ${worstRisk}`}>{currentScore}</div>
            <div className="risk-info">
              <h2>{worstRisk === 'safe' ? '✅ System Nominal' : `⚠️ ${worstRisk.toUpperCase()} RISK`}</h2>
              <p>{allHazards.length} Active hazards across sources</p>
            </div>
          </div>
          <div className="risk-banner-stats">
            <div className="risk-stat" style={{ textAlign: 'right' }}>
              <div className="risk-stat-value" style={{ color: 'var(--safe)' }}>{formatUSD(globalStats?.cumulative_savings_usd || 0)}</div>
              <div className="risk-stat-label">Cumulative ROI</div>
            </div>
          </div>
        </div>

        <div className="dashboard-body">
          <div className="left-panel">
            <div className="multi-view-grid">
              {Object.values(slots).map(slot => (<ViewSlot key={slot.id} {...slot} onFileSelect={handleFileSelect} />))}
            </div>
            <div className="card">
              <div className="card-header"><div className="card-title">🧠 Agent Pipeline</div></div>
              <div className="card-body">
                <div className="reasoning-box">
                  {Object.values(slots).filter(s => s.data).slice(0, 1).map((s, i) => (
                    <div key={i} style={{ marginBottom: 16 }}>
                      {/* Supervisor Strategic Plan */}
                      {s.data.supervisor_plan && (
                        <div style={{ marginBottom: 12, padding: 10, background: 'rgba(59,130,246,0.05)', borderRadius: 6, border: '1px dashed #3b82f6' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                            <span style={{ background: '#3b82f6', color: '#fff', padding: '2px 6px', borderRadius: 4, fontSize: '0.6rem', fontWeight: 800 }}>SUPERVISOR</span>
                            <span style={{ fontSize: '0.6rem', color: 'var(--text-secondary)' }}>Gemini 2.5 Pro (Strategic Orchestrator)</span>
                          </div>
                          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>Strategic Plan:</div>
                          <div style={{ fontSize: '0.8rem', marginBottom: 6 }}>{s.data.supervisor_plan.orchestration_plan?.reasoning}</div>
                          <div style={{ display: 'flex', gap: 6 }}>
                            {s.data.supervisor_plan.orchestration_plan?.priority_zones?.map(z => (
                              <span key={z} style={{ fontSize: '0.6rem', background: 'rgba(59,130,246,0.2)', padding: '1px 5px', borderRadius: 3 }}>📍 {z}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Field Operator Output */}
                      <div style={{ marginBottom: 8, borderBottom: '1px solid var(--border)', paddingBottom: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                          <span style={{ background: '#3b82f6', color: '#fff', padding: '2px 6px', borderRadius: 4, fontSize: '0.6rem', fontWeight: 800 }}>FIELD OPERATOR</span>
                          <span style={{ fontSize: '0.6rem', color: 'var(--text-secondary)' }}>Robotics-ER 1.6 (Spatial Expert)</span>
                        </div>
                        <div style={{ fontSize: '0.8rem' }}>{s.data.ai_reasoning || s.data.reasoning || 'Analysis complete.'}</div>
                      </div>

                      {/* Auditor Output */}
                      {s.data.audit && (
                        <div style={{ borderLeft: '3px solid #f59e0b', paddingLeft: 10 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                            <span style={{ background: '#f59e0b', color: '#000', padding: '2px 6px', borderRadius: 4, fontSize: '0.6rem', fontWeight: 800 }}>AUDITOR</span>
                            <span style={{ fontSize: '0.6rem', color: 'var(--text-secondary)' }}>Gemini 2.5 Pro (OSHA Expert)</span>
                          </div>
                          <div style={{ fontSize: '0.8rem' }}>{s.data.audit.executive_summary}</div>
                          {s.data.audit.violations?.map((v, vi) => (
                            <div key={vi} style={{ marginTop: 6, fontSize: '0.7rem', background: 'rgba(245,158,11,0.1)', padding: 6, borderRadius: 4 }}>
                              <strong style={{ color: '#f59e0b' }}>📋 {v.osha_standard}</strong> — {v.standard_title}<br/>
                              <span style={{ color: 'var(--text-secondary)' }}>{v.description}</span><br/>
                              <span style={{ color: 'var(--critical)' }}>Fine: {formatUSD(v.estimated_fine_usd || 0)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      
                      {/* Pipeline Log */}
                      {s.data.pipeline_log && (
                        <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
                          {s.data.pipeline_log.map((step, si) => (
                            <div key={si} style={{ fontSize: '0.6rem', padding: '2px 8px', borderRadius: 4, background: step.status === 'complete' ? 'rgba(16,185,129,0.15)' : step.status === 'skipped' ? 'rgba(100,116,139,0.15)' : 'rgba(59,130,246,0.15)', color: step.status === 'complete' ? '#10b981' : step.status === 'skipped' ? '#64748b' : '#3b82f6' }}>
                              {step.agent} {step.status === 'complete' ? `✓ ${step.duration_ms}ms` : step.status === 'skipped' ? '○ skipped' : '...'}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  {!Object.values(slots).some(s => s.data) && "Awaiting input — Upload media to activate the multi-agent pipeline..."}
                </div>
              </div>
            </div>
          </div>

          <aside className="right-sidebar">
            <div className="tabs">
              {['hazards', 'actions', 'financial'].map(t => (
                <button key={t} className={`tab ${activeTab === t ? 'active' : ''}`} onClick={() => setActiveTab(t)}>
                  {t === 'hazards' ? '⚠️ Hazards' : t === 'actions' ? '⚡ Actions' : '💰 Savings'}
                </button>
              ))}
            </div>
            <div className="card" style={{ flex: 1 }}>
              <div className="card-body">
                {activeTab === 'hazards' && (
                  <div className="hazard-list">
                    {allHazards.map((h, i) => (
                      <div key={i} className="hazard-item">
                        <div className={`hazard-icon ${h.risk_level}`}>{HAZARD_EMOJI[h.type] || '⚠️'}</div>
                        <div className="hazard-info">
                          <div style={{ fontWeight: 700 }}>{(h.type || '').replace(/_/g, ' ')}</div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{h.description}</div>
                        </div>
                        <div style={{ fontWeight: 800 }}>{h.risk_score}</div>
                      </div>
                    ))}
                    {allHazards.length === 0 && <div style={{ textAlign: 'center', padding: 20 }}>No hazards</div>}
                  </div>
                )}
                {activeTab === 'actions' && (
                  <div className="action-list">
                    {Object.values(slots).flatMap(slot => [...(slot.data?.proposed_actions || []), ...(slot.data?.function_calls || [])]).map((a, i) => (
                      <div key={i} className="hazard-item">
                        <span style={{ color: a.function ? 'var(--accent-blue)' : 'var(--safe)' }}>{a.function ? '🤖' : '✓'}</span>
                        <div>
                          <div style={{ fontWeight: 700 }}>{a.action_type || `ROBOT: ${a.function}`}</div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{a.description || JSON.stringify(a.args)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {activeTab === 'financial' && (
                  <div className="financial-grid" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    <div><div className="risk-stat-label">OSHA Fines (Auditor)</div><div className="risk-stat-value" style={{ color: 'var(--critical)' }}>{formatUSD(latestFinancial.total_potential_fines || 0)}</div></div>
                    <div><div className="risk-stat-label">Injury Liability</div><div className="risk-stat-value" style={{ color: 'var(--critical)' }}>{formatUSD(latestFinancial.potential_injury_liability || 0)}</div></div>
                    <div><div className="risk-stat-label">Downtime Cost</div><div className="risk-stat-value" style={{ color: 'var(--critical)' }}>{formatUSD(latestFinancial.potential_downtime_cost || 0)}</div></div>
                    <div style={{ height: '1px', background: 'var(--border)' }} />
                    <div><div className="risk-stat-label">TOTAL EXPOSURE</div><div className="risk-stat-value" style={{ color: 'var(--safe)', fontSize: '1.8rem' }}>{formatUSD(latestFinancial.total_exposure || globalStats?.cumulative_savings_usd || 0)}</div></div>
                    {latestAudit && <div style={{ fontSize: '0.65rem', color: '#f59e0b', marginTop: 4 }}>📋 Calculated by Auditor Agent (Gemini 2.5 Pro)</div>}
                  </div>
                )}
              </div>
            </div>
            <div className="card" style={{ marginTop: 'auto' }}>
              <div className="card-header"><div className="card-title">🤖 Active Agents</div></div>
              <div className="card-body" style={{ fontSize: '0.7rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#3b82f6', display: 'inline-block' }} />
                  <strong>Field Operator</strong> <span style={{ color: 'var(--text-secondary)' }}>Robotics-ER 1.6</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} />
                  <strong>Auditor</strong> <span style={{ color: 'var(--text-secondary)' }}>Gemini 2.5 Pro</span>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </main>

      {isPolicyOpen && (
        <div className="loading-overlay" style={{ background: 'rgba(0,0,0,0.85)' }}>
          <div className="card" style={{ width: '600px', maxHeight: '80vh' }}>
            <div className="card-header">
              <div className="card-title">⚙️ Industrial Safety Policy Configuration</div>
              <button className="btn btn-outline btn-sm" onClick={() => setIsPolicyOpen(false)}>Close</button>
            </div>
            <div className="card-body">
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 10 }}>
                Define thresholds, PPE requirements, and plant rules. Gemini will use this as the "Ground Truth".
              </p>
              <textarea 
                style={{ width: '100%', height: '300px', background: '#000', color: '#0f0', fontFamily: 'monospace', padding: 10, border: '1px solid var(--border)' }}
                value={policyDraft}
                onChange={(e) => setPolicyDraft(e.target.value)}
              />
              <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
                <button className="btn btn-primary" style={{ flex: 1 }} onClick={savePolicy}>Apply & Save Policy</button>
                <button className="btn btn-outline" style={{ flex: 1 }} onClick={() => setPolicyDraft(JSON.stringify(policy, null, 2))}>Reset</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
