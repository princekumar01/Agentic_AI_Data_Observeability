import { useState, useEffect, useRef, useCallback } from 'react';
import { GlassCard, StatusBadge, LoadingSpinner, Toast } from '../components/ui/index';
import { pipelineApi } from '../lib/api';
import { PreflightReport, PipelineStatus, Run, UploadResult } from '../lib/types';
import { formatDateTime, SCENARIOS } from '../lib/utils';

const STAGE_ICONS = ['💾','✓','⚙','🛡','🤖','📄','👤'];
const STAGE_LABELS = ['Input Discovery','Entry Validation','Preprocessing','PII/PHI Masking','AI Agents','Incident Report','Awaiting Review'];

export default function Pipeline() {
  const [mode, setMode] = useState<1|2|3>(1);
  const [uploadResult, setUploadResult] = useState<UploadResult|null>(null);
  const [syntheticResult, setSyntheticResult] = useState<any>(null);
  const [apiConnResult, setApiConnResult] = useState<any>(null);
  const [preflight, setPreflight] = useState<PreflightReport|null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus|null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [activeRunId, setActiveRunId] = useState<string|null>(null);
  const [loading, setLoading] = useState<Record<string,boolean>>({});
  const [toast, setToast] = useState<{msg:string;type:'success'|'error'|'info'}|null>(null);
  const [runConfig, setRunConfig] = useState({ run_name:'', window_size:5, delay_ms:50, description:'' });
  const [synConfig, setSynConfig] = useState({ scenario:'normal', rows:500, null_rate:5, outlier_pct:2, date_drift_days:0, duplicate_rate:0 });
  const [apiConfig, setApiConfig] = useState({ url:'', auth_type:'Bearer', token:'', poll_interval_seconds:30, max_records_per_poll:500 });
  const pollRef = useRef<ReturnType<typeof setInterval>|null>(null);
  const dragRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);

  const showToast = useCallback((msg:string, type:'success'|'error'|'info'='info') => {
    setToast({msg,type}); setTimeout(() => setToast(null), 3500);
  },[]);

  useEffect(() => {
    pipelineApi.getRuns().then((d:any) => setRuns(d.runs||[])).catch(()=>{});
  },[]);

  useEffect(() => {
    if (!activeRunId) return;
    const poll = () => pipelineApi.getStatus(activeRunId).then(setPipelineStatus).catch(()=>{});
    poll();
    pollRef.current = setInterval(poll, 2000);
    return () => { pollRef.current && clearInterval(pollRef.current); };
  },[activeRunId]);

  useEffect(() => {
    if (['completed', 'failed', 'pending_review', 'approved', 'rejected'].includes(pipelineStatus?.status || '')) {
      pollRef.current && clearInterval(pollRef.current);
      pipelineApi.getRuns().then((d:any) => setRuns(d.runs||[])).catch(()=>{});
    }
  },[pipelineStatus?.status]);

  async function handleFileUpload(file:File) {
    setLoading(l=>({...l,upload:true}));
    try {
      const res = await pipelineApi.uploadFile(file);
      setUploadResult(res);
      showToast('File uploaded successfully','success');
    } catch { showToast('Upload failed','error'); }
    finally { setLoading(l=>({...l,upload:false})); }
  }

  async function handlePreflight() {
    const rid = uploadResult?.run_id || syntheticResult?.run_id || `RUN_${Date.now()}`;
    setLoading(l=>({...l,preflight:true}));
    try {
      const res = await pipelineApi.runPreflight(rid);
      setPreflight(res);
    } catch { showToast('Preflight check failed','error'); }
    finally { setLoading(l=>({...l,preflight:false})); }
  }

  async function handleRunPipeline() {
    const rid = uploadResult?.run_id || syntheticResult?.run_id || `RUN_${Date.now().toString().slice(-8)}`;
    setLoading(l=>({...l,run:true}));
    try {
      const inputMode = ['csv','synthetic','api'][mode-1];
      await pipelineApi.runPipeline({
        run_id:rid,
        run_name:runConfig.run_name,
        input_mode:inputMode,
        window_size:runConfig.window_size,
        inter_event_delay_ms:runConfig.delay_ms,
        description:runConfig.description,
        ...(inputMode === 'api' ? {
          api_url: apiConfig.url,
          api_auth_type: apiConfig.auth_type,
          api_token: apiConfig.token,
          api_max_records_per_poll: apiConfig.max_records_per_poll,
        } : {}),
      });
      setActiveRunId(rid);
      setPipelineStatus(null);
      showToast('Pipeline started!','success');
    } catch (err:any) {
      if (err.status===429) showToast('Too many requests — wait before retrying','error');
      else showToast('Failed to start pipeline','error');
    } finally { setLoading(l=>({...l,run:false})); }
  }

  async function handleReset() {
    if (!activeRunId) return;
    await pipelineApi.reset(activeRunId).catch(()=>{});
    setActiveRunId(null); setPipelineStatus(null); setPreflight(null);
    setUploadResult(null); setSyntheticResult(null); setApiConnResult(null);
    showToast('Pipeline reset','info');
  }

  async function handleGenerateSynthetic() {
    setLoading(l=>({...l,synthetic:true}));
    try {
      const res = await pipelineApi.generateSynthetic({ scenario:synConfig.scenario, rows:synConfig.rows, null_rate:synConfig.null_rate, outlier_pct:synConfig.outlier_pct, date_drift_days:synConfig.date_drift_days, duplicate_rate:synConfig.duplicate_rate });
      setSyntheticResult(res);
      showToast('Synthetic dataset generated','success');
    } catch { showToast('Generation failed','error'); }
    finally { setLoading(l=>({...l,synthetic:false})); }
  }

  async function handleTestConnection() {
    setLoading(l=>({...l,conn:true}));
    try {
      const res = await pipelineApi.testApiConnection(apiConfig);
      setApiConnResult(res);
      showToast('Connection successful','success');
    } catch { showToast('Connection failed','error'); setApiConnResult({connected:false,error:'Could not connect'}); }
    finally { setLoading(l=>({...l,conn:false})); }
  }

  const apiReady = mode !== 3 || !!apiConnResult?.connected;
  const canRun = !!preflight?.passed && apiReady && !loading.run && pipelineStatus?.status !== 'running';
  const isRunning = pipelineStatus?.status === 'running';

  return (
    <div style={{padding:'24px',display:'flex',gap:20}}>
          {/* Left column */}
          <div style={{flex:1,display:'flex',flexDirection:'column',gap:20}}>
            {/* Mode selection */}
            <GlassCard>
              <h2 style={{fontSize:15,fontWeight:700,color:'var(--text-primary)',fontFamily:'Space Grotesk',marginBottom:16}}>Choose Data Input Mode</h2>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:12,marginBottom:20}}>
                {[
                  {n:1 as 1,icon:'📁',label:'Upload CSV / JSON',desc:'Upload your clinical trial dataset',color:'#3B82F6'},
                  {n:2 as 2,icon:'🧬',label:'Generate Synthetic',desc:'Scenario-based synthetic data generation',color:'#7C3AED'},
                  {n:3 as 3,icon:'🌐',label:'External API',desc:'Connect to live hospital data API',color:'#10B981'},
                ].map(m => (
                  <button key={m.n} onClick={() => setMode(m.n)} style={{background:mode===m.n?`${m.color}15`:'rgba(6,13,26,0.5)',border:`2px solid ${mode===m.n?m.color:'var(--border-color)'}`,borderRadius:10,padding:'14px 12px',cursor:'pointer',textAlign:'center',transition:'all 0.2s'}}>
                    <p style={{fontSize:24,marginBottom:8}}>{m.icon}</p>
                    <p style={{fontSize:12,fontWeight:700,color:mode===m.n?m.color:'var(--text-primary)',fontFamily:'Space Grotesk'}}>{m.label}</p>
                    <p style={{fontSize:11,color:'var(--text-muted)',marginTop:4}}>{m.desc}</p>
                  </button>
                ))}
              </div>

              {/* Mode 1: Upload */}
              {mode===1 && (
                <div>
                  <div ref={dragRef} onDragOver={e=>{e.preventDefault();setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={e=>{e.preventDefault();setDragging(false);const f=e.dataTransfer.files[0];if(f)handleFileUpload(f);}}
                    style={{border:`2px dashed ${dragging?'var(--accent-blue)':'var(--border-color)'}`,borderRadius:12,padding:'32px 20px',textAlign:'center',background:dragging?'rgba(59,130,246,0.05)':'rgba(6,13,26,0.4)',transition:'all 0.2s',cursor:'pointer'}}
                    onClick={()=>document.getElementById('fileInput')?.click()}>
                    <p style={{fontSize:32,marginBottom:10}}>☁️</p>
                    <p style={{fontSize:14,fontWeight:600,color:'var(--text-primary)',fontFamily:'Space Grotesk'}}>Drop your CSV or JSON file here</p>
                    <p style={{fontSize:12,color:'var(--text-muted)',marginTop:4}}>or click to browse files</p>
                    {loading.upload && <div style={{marginTop:12,display:'flex',justifyContent:'center'}}><LoadingSpinner/></div>}
                    <input id="fileInput" type="file" accept=".csv,.json" style={{display:'none'}} onChange={e=>{const f=e.target.files?.[0];if(f)handleFileUpload(f);}}/>
                  </div>
                  {uploadResult && (
                    <div style={{marginTop:14}}>
                      <div style={{background:'rgba(16,185,129,0.08)',border:'1px solid rgba(16,185,129,0.2)',borderRadius:8,padding:'10px 14px',marginBottom:12,display:'flex',alignItems:'center',gap:8}}>
                        <span style={{color:'#10B981'}}>✓</span>
                        <span style={{fontSize:13,color:'#10B981',fontFamily:'Space Grotesk',fontWeight:600}}>File uploaded — {uploadResult.total_columns} columns detected</span>
                      </div>
                      <table className="data-table" style={{marginBottom:12}}>
                        <tbody>
                          {[['Filename',uploadResult.filename],['Rows',uploadResult.total_rows],['Columns',uploadResult.total_columns],['Format',uploadResult.detected_format],['Encoding',uploadResult.encoding]].map(([k,v])=>(
                            <tr key={k}><td style={{color:'var(--text-muted)',fontSize:12,width:120}}>{k}</td><td style={{fontFamily:'JetBrains Mono',fontSize:12,color:'var(--text-primary)'}}>{String(v)}</td></tr>
                          ))}
                        </tbody>
                      </table>
                      <h4 style={{fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:8}}>Schema Preview</h4>
                      <table className="data-table">
                        <thead><tr><th>Column</th><th>Type</th><th>Sample</th><th>Null %</th></tr></thead>
                        <tbody>{uploadResult.columns.map(col=>(
                          <tr key={col.name}><td style={{fontFamily:'JetBrains Mono',fontSize:11}}>{col.name}</td><td style={{color:'var(--accent-cyan)',fontSize:11}}>{col.type}</td><td style={{fontFamily:'JetBrains Mono',fontSize:11,color:'var(--text-muted)'}}>{col.sample}</td><td style={{color:col.null_pct>30?'var(--accent-red)':col.null_pct>5?'var(--accent-orange)':'var(--text-secondary)',fontSize:11}}>{col.null_pct.toFixed(1)}%</td></tr>
                        ))}</tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Mode 2: Synthetic */}
              {mode===2 && (
                <div>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:12}}>
                    <div>
                      <label style={{display:'block',fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:4}}>Scenario</label>
                      <select className="field" value={synConfig.scenario} onChange={e=>setSynConfig(c=>({...c,scenario:e.target.value}))}>
                        {SCENARIOS.map(s=><option key={s.value} value={s.value}>{s.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label style={{display:'block',fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:4}}>Row Count</label>
                      <input className="field" type="number" min={100} max={10000} value={synConfig.rows} onChange={e=>setSynConfig(c=>({...c,rows:+e.target.value}))}/>
                    </div>
                    <div>
                      <label style={{display:'block',fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:4}}>Null Rate %</label>
                      <input className="field" type="number" min={0} max={100} value={synConfig.null_rate} onChange={e=>setSynConfig(c=>({...c,null_rate:+e.target.value}))}/>
                    </div>
                    <div>
                      <label style={{display:'block',fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:4}}>Outlier %</label>
                      <input className="field" type="number" min={0} max={50} value={synConfig.outlier_pct} onChange={e=>setSynConfig(c=>({...c,outlier_pct:+e.target.value}))}/>
                    </div>
                  </div>
                  <button onClick={handleGenerateSynthetic} className="btn-primary" disabled={loading.synthetic}>
                    {loading.synthetic&&<LoadingSpinner size="sm"/>} Generate Dataset
                  </button>
                  {syntheticResult && (
                    <div style={{marginTop:12,background:'rgba(124,58,237,0.08)',border:'1px solid rgba(124,58,237,0.25)',borderRadius:8,padding:12}}>
                      <p style={{fontSize:13,color:'#7C3AED',fontWeight:600,fontFamily:'Space Grotesk'}}>✓ Generated: {syntheticResult.rows_generated} rows — {syntheticResult.scenario}</p>
                      <p style={{fontSize:11,color:'var(--text-muted)',marginTop:4,fontFamily:'JetBrains Mono'}}>{syntheticResult.saved_to}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Mode 3: External API */}
              {mode===3 && (
                <div>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:12}}>
                    <div style={{gridColumn:'1/-1'}}>
                      <label style={{display:'block',fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:4}}>API URL</label>
                      <input className="field" type="url" placeholder="https://api.hospital.example/patients" value={apiConfig.url} onChange={e=>setApiConfig(c=>({...c,url:e.target.value}))}/>
                    </div>
                    <div>
                      <label style={{display:'block',fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:4}}>Auth Type</label>
                      <select className="field" value={apiConfig.auth_type} onChange={e=>setApiConfig(c=>({...c,auth_type:e.target.value}))}>
                        <option value="Bearer">Bearer Token</option><option value="API Key">API Key</option><option value="None">None</option>
                      </select>
                    </div>
                    {apiConfig.auth_type!=='None'&&<div>
                      <label style={{display:'block',fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:4}}>Token / API Key</label>
                      <input className="field" type="password" placeholder="Enter token" value={apiConfig.token} onChange={e=>setApiConfig(c=>({...c,token:e.target.value}))}/>
                    </div>}
                    <div>
                      <label style={{display:'block',fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:4}}>Poll Interval</label>
                      <select className="field" value={apiConfig.poll_interval_seconds} onChange={e=>setApiConfig(c=>({...c,poll_interval_seconds:+e.target.value}))}>
                        <option value={5}>5s</option><option value={30}>30s</option><option value={60}>60s</option>
                      </select>
                    </div>
                    <div>
                      <label style={{display:'block',fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:4}}>Max Records / Poll</label>
                      <input className="field" type="number" min={1} max={5000} value={apiConfig.max_records_per_poll} onChange={e=>setApiConfig(c=>({...c,max_records_per_poll:+e.target.value}))}/>
                    </div>
                  </div>
                  <button onClick={handleTestConnection} className="btn-secondary" disabled={loading.conn||!apiConfig.url}>
                    {loading.conn&&<LoadingSpinner size="sm"/>} Test Connection
                  </button>
                  {apiConnResult && (
                    <div style={{marginTop:12,background:apiConnResult.connected?'rgba(16,185,129,0.08)':'rgba(239,68,68,0.08)',border:`1px solid ${apiConnResult.connected?'rgba(16,185,129,0.25)':'rgba(239,68,68,0.25)'}`,borderRadius:8,padding:12}}>
                      <p style={{fontSize:13,color:apiConnResult.connected?'#10B981':'#EF4444',fontWeight:600,fontFamily:'Space Grotesk'}}>{apiConnResult.connected?`✓ Connected — ${apiConnResult.sample_record_count} records, avg ${apiConnResult.avg_latency_ms}ms`:`✕ ${apiConnResult.error}`}</p>
                    </div>
                  )}
                </div>
              )}
            </GlassCard>

            {/* Run Configuration */}
            <GlassCard>
              <h2 style={{fontSize:15,fontWeight:700,color:'var(--text-primary)',fontFamily:'Space Grotesk',marginBottom:16}}>Run Configuration</h2>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:12}}>
                <div>
                  <label style={{display:'block',fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:4}}>Run Name</label>
                  <input className="field" placeholder="Morning batch — high glucose cohort" value={runConfig.run_name} onChange={e=>setRunConfig(c=>({...c,run_name:e.target.value}))}/>
                </div>
                <div>
                  <label style={{display:'block',fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:4}}>Window Size (events)</label>
                  <input className="field" type="number" min={1} max={5000} value={runConfig.window_size} onChange={e=>setRunConfig(c=>({...c,window_size:+e.target.value}))}/>
                </div>
                <div>
                  <label style={{display:'block',fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:4}}>Inter-event Delay (ms)</label>
                  <input className="field" type="number" min={10} max={5000} value={runConfig.delay_ms} onChange={e=>setRunConfig(c=>({...c,delay_ms:+e.target.value}))}/>
                </div>
                <div>
                  <label style={{display:'block',fontSize:12,fontWeight:600,color:'var(--text-muted)',fontFamily:'Space Grotesk',marginBottom:4}}>Description</label>
                  <input className="field" placeholder="Optional description" value={runConfig.description} onChange={e=>setRunConfig(c=>({...c,description:e.target.value}))}/>
                </div>
              </div>
              <div style={{display:'flex',gap:12,alignItems:'center'}}>
                <button onClick={handleRunPipeline} className="btn-primary" disabled={!canRun} style={{padding:'12px 28px',fontSize:15}}>
                  {loading.run||isRunning?<LoadingSpinner size="sm"/>:'▶'} {isRunning?'Pipeline Running…':'Run Pipeline'}
                </button>
                <button onClick={handleReset} className="btn-secondary">⟳ Reset</button>
                {!preflight&&<span style={{fontSize:12,color:'var(--accent-orange)'}}>⚠ Run preflight checks first</span>}
                {mode===3&&!apiConnResult?.connected&&<span style={{fontSize:12,color:'var(--accent-orange)'}}>⚠ Test API connection first</span>}
                {preflight&&preflight.hard_blocks.length>0&&<span style={{fontSize:12,color:'var(--accent-red)'}}>✕ Fix hard blocks to enable run</span>}
                {preflight&&preflight.hard_blocks.length===0&&apiReady&&<span style={{fontSize:12,color:'var(--accent-green)'}}>✓ All clear — ready to run</span>}
              </div>
            </GlassCard>

            {/* Pipeline Progress */}
            {pipelineStatus && (
              <GlassCard>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:20}}>
                  <h2 style={{fontSize:15,fontWeight:700,color:'var(--text-primary)',fontFamily:'Space Grotesk'}}>Pipeline Progress</h2>
                  <StatusBadge status={pipelineStatus.status}/>
                </div>
                <div style={{display:'flex',gap:0,overflowX:'auto',paddingBottom:8}}>
                  {pipelineStatus.stages.map((stage,i) => (
                    <div key={stage.num} style={{display:'flex',alignItems:'center',flexShrink:0}}>
                      <div style={{textAlign:'center',width:90}}>
                        <div style={{width:40,height:40,borderRadius:'50%',margin:'0 auto 8px',display:'flex',alignItems:'center',justifyContent:'center',fontSize:16,border:'2px solid',
                          borderColor:stage.status==='completed'?'var(--accent-green)':stage.status==='active'?'var(--accent-blue)':stage.status==='failed'?'var(--accent-red)':'var(--border-color)',
                          background:stage.status==='completed'?'rgba(16,185,129,0.12)':stage.status==='active'?'rgba(59,130,246,0.12)':stage.status==='failed'?'rgba(239,68,68,0.12)':'rgba(6,13,26,0.4)',
                          position:'relative',
                        }}>
                          {stage.status==='active'?<LoadingSpinner size="sm"/>:stage.status==='completed'?<span style={{color:'var(--accent-green)'}}>✓</span>:stage.status==='failed'?<span style={{color:'var(--accent-red)'}}>✕</span>:<span style={{color:'var(--text-muted)'}}>{STAGE_ICONS[i]}</span>}
                        </div>
                        <p style={{fontSize:10,fontFamily:'Space Grotesk',fontWeight:600,color:stage.status==='completed'?'var(--accent-green)':stage.status==='active'?'var(--accent-blue)':stage.status==='failed'?'var(--accent-red)':'var(--text-muted)',lineHeight:1.3}}>{stage.label}</p>
                        {stage.duration_ms&&<p style={{fontSize:9,color:'var(--text-muted)',fontFamily:'JetBrains Mono',marginTop:2}}>{(stage.duration_ms/1000).toFixed(1)}s</p>}
                      </div>
                      {i<pipelineStatus.stages.length-1&&<div style={{width:20,height:2,background:'var(--border-color)',flexShrink:0,margin:'0 2px 28px'}}/>}
                    </div>
                  ))}
                </div>
                <div style={{marginTop:12,padding:'8px 12px',background:'rgba(59,130,246,0.06)',borderRadius:8,display:'flex',gap:20}}>
                  <span style={{fontSize:12,color:'var(--text-secondary)'}}>Current Stage: <b style={{color:'var(--accent-blue)'}}>{pipelineStatus.current_stage}</b></span>
                  <span style={{fontSize:12,color:'var(--text-secondary)'}}>Events Processed: <b style={{color:'var(--text-primary)',fontFamily:'JetBrains Mono'}}>{pipelineStatus.events_processed}</b></span>
                </div>
                {['completed','pending_review'].includes(pipelineStatus.status)&&(
                  <div style={{marginTop:12,padding:'10px 14px',background:'rgba(16,185,129,0.1)',border:'1px solid rgba(16,185,129,0.25)',borderRadius:8}}>
                    <p style={{fontSize:13,color:'#10B981',fontFamily:'Space Grotesk',fontWeight:600}}>✓ Pipeline completed — navigate to Review to approve the AI report</p>
                  </div>
                )}
              </GlassCard>
            )}

            {/* Previous Runs */}
            <GlassCard>
              <h2 style={{fontSize:15,fontWeight:700,color:'var(--text-primary)',fontFamily:'Space Grotesk',marginBottom:14}}>Previous Runs</h2>
              <table className="data-table">
                <thead><tr><th>Run ID</th><th>Input Mode</th><th>Rows</th><th>Status</th><th>Started At</th></tr></thead>
                <tbody>{runs.map(r=>(
                  <tr key={r.run_id}>
                    <td><span style={{fontFamily:'JetBrains Mono',fontSize:11,color:'var(--accent-cyan)'}}>{r.run_id}</span></td>
                    <td style={{color:'var(--text-secondary)'}}>{r.input_mode}</td>
                    <td style={{color:'var(--text-secondary)'}}>{r.rows}</td>
                    <td><StatusBadge status={r.status}/></td>
                    <td style={{color:'var(--text-muted)',fontFamily:'JetBrains Mono',fontSize:11}}>{formatDateTime(r.started_at)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </GlassCard>
          </div>

          {/* Right column — Preflight Gate */}
          <div style={{width:320,flexShrink:0,display:'flex',flexDirection:'column',gap:16}}>
            <GlassCard>
              <h2 style={{fontSize:14,fontWeight:700,color:'var(--text-primary)',fontFamily:'Space Grotesk',marginBottom:14}}>Preflight Validation Gate</h2>
              <button onClick={handlePreflight} className="btn-secondary" style={{width:'100%',justifyContent:'center',marginBottom:14}} disabled={loading.preflight}>
                {loading.preflight&&<LoadingSpinner size="sm"/>} Run Checks
              </button>
              {preflight && (
                <div>
                  {/* Summary */}
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:14}}>
                    <div style={{background:'rgba(239,68,68,0.08)',border:'1px solid rgba(239,68,68,0.2)',borderRadius:8,padding:'10px 12px',textAlign:'center'}}>
                      <p style={{fontSize:22,fontWeight:700,color:'#EF4444',fontFamily:'Space Grotesk'}}>{preflight.hard_blocks.length}</p>
                      <p style={{fontSize:11,color:'var(--text-muted)'}}>Hard Blocks</p>
                    </div>
                    <div style={{background:'rgba(245,158,11,0.08)',border:'1px solid rgba(245,158,11,0.2)',borderRadius:8,padding:'10px 12px',textAlign:'center'}}>
                      <p style={{fontSize:22,fontWeight:700,color:'#F59E0B',fontFamily:'Space Grotesk'}}>{preflight.soft_warnings.length}</p>
                      <p style={{fontSize:11,color:'var(--text-muted)'}}>Soft Warnings</p>
                    </div>
                  </div>
                  <p style={{fontSize:11,color:'var(--text-muted)',marginBottom:8}}>Checked: {formatDateTime(preflight.checked_at)} · {preflight.row_count} rows</p>

                  {preflight.hard_blocks.length>0&&(
                    <div style={{marginBottom:12}}>
                      <p style={{fontSize:12,fontWeight:600,color:'#EF4444',fontFamily:'Space Grotesk',marginBottom:6}}>Hard Blocks</p>
                      {preflight.hard_blocks.map(b=>(
                        <div key={b.id} style={{background:'rgba(239,68,68,0.06)',border:'1px solid rgba(239,68,68,0.2)',borderRadius:6,padding:'8px 10px',marginBottom:6}}>
                          <p style={{fontSize:12,color:'#EF4444',fontWeight:600,fontFamily:'Space Grotesk'}}>{b.message}</p>
                          <p style={{fontSize:11,color:'var(--text-muted)',marginTop:2}}>{b.detail}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {preflight.soft_warnings.length>0&&(
                    <div style={{marginBottom:12}}>
                      <p style={{fontSize:12,fontWeight:600,color:'#F59E0B',fontFamily:'Space Grotesk',marginBottom:6}}>Soft Warnings</p>
                      {preflight.soft_warnings.map(w=>(
                        <div key={w.id} style={{background:'rgba(245,158,11,0.06)',border:'1px solid rgba(245,158,11,0.2)',borderRadius:6,padding:'8px 10px',marginBottom:6}}>
                          <p style={{fontSize:12,color:'#F59E0B',fontWeight:600,fontFamily:'Space Grotesk'}}>{w.message}</p>
                          <p style={{fontSize:11,color:'var(--text-muted)',marginTop:2}}>{w.detail}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {preflight.hard_blocks.length===0 ? (
                    <div style={{background:'rgba(16,185,129,0.1)',border:'1px solid rgba(16,185,129,0.25)',borderRadius:8,padding:'10px 12px',textAlign:'center'}}>
                      <p style={{fontSize:13,color:'#10B981',fontWeight:700,fontFamily:'Space Grotesk'}}>✓ All Clear — Ready to Run</p>
                    </div>
                  ) : (
                    <div style={{background:'rgba(239,68,68,0.1)',border:'1px solid rgba(239,68,68,0.25)',borderRadius:8,padding:'10px 12px',textAlign:'center'}}>
                      <p style={{fontSize:12,color:'#EF4444',fontWeight:600,fontFamily:'Space Grotesk'}}>✕ Fix Hard Blocks to Enable Run</p>
                    </div>
                  )}
                </div>
              )}
              {!preflight&&<p style={{fontSize:12,color:'var(--text-muted)',textAlign:'center',padding:'16px 0'}}>Click "Run Checks" to validate your data</p>}
            </GlassCard>

            {/* Active Run panel */}
            <GlassCard>
              <h3 style={{fontSize:13,fontWeight:700,color:'var(--text-primary)',fontFamily:'Space Grotesk',marginBottom:10}}>Active Run</h3>
              {activeRunId ? (
                <div>
                  <p style={{fontFamily:'JetBrains Mono',fontSize:11,color:'var(--accent-cyan)',marginBottom:8,wordBreak:'break-all'}}>{activeRunId}</p>
                  {pipelineStatus&&<StatusBadge status={pipelineStatus.status}/>}
                  {isRunning&&<div style={{marginTop:8,display:'flex',alignItems:'center',gap:6}}><LoadingSpinner size="sm"/><span style={{fontSize:12,color:'var(--text-muted)'}}>Processing…</span></div>}
                </div>
              ) : <p style={{fontSize:12,color:'var(--text-muted)'}}>No active run</p>}
            </GlassCard>
          </div>
      {toast&&<Toast message={toast.msg} type={toast.type}/>}
    </div>
  );
}
