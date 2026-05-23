"""
Clinical Trial AI Observability — FastAPI Backend
Provides all endpoints with realistic sample data for frontend development.
"""
from fastapi import FastAPI, HTTPException, Depends, Header, Query, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import uuid, random, time, json, csv, io
from datetime import datetime, timedelta, timezone

app = FastAPI(title="Clinical Trial AI Observability API", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-memory state ────────────────────────────────────────────────────────
_start_time = time.time()
_sessions: dict = {}  # token -> user
_runs: list = [
    {"run_id": "RUN_20240610_001", "input_mode": "CSV Upload", "rows": 500, "status": "approved",
     "review_status": "approved", "started_at": "2024-06-10T08:15:00Z", "completed_at": "2024-06-10T08:22:45Z",
     "description": "Morning batch — high glucose cohort"},
    {"run_id": "RUN_20240609_003", "input_mode": "Synthetic", "rows": 300, "status": "completed",
     "review_status": "pending_review", "started_at": "2024-06-09T14:30:00Z", "completed_at": "2024-06-09T14:38:22Z",
     "description": "Synthetic high_nulls scenario"},
    {"run_id": "RUN_20240609_001", "input_mode": "External API", "rows": 750, "status": "approved",
     "review_status": "approved", "started_at": "2024-06-09T09:05:00Z", "completed_at": "2024-06-09T09:18:11Z",
     "description": "External hospital feed"},
    {"run_id": "RUN_20240608_002", "input_mode": "CSV Upload", "rows": 420, "status": "failed",
     "review_status": None, "started_at": "2024-06-08T16:00:00Z", "completed_at": "2024-06-08T16:04:30Z",
     "description": "Failed — schema mismatch"},
    {"run_id": "RUN_20240607_001", "input_mode": "Synthetic", "rows": 500, "status": "approved",
     "review_status": "approved", "started_at": "2024-06-07T11:20:00Z", "completed_at": "2024-06-07T11:31:00Z",
     "description": "Baseline validation run"},
]
_alerts_store: list = [
    {"id": "ALT_001", "severity": "CRITICAL", "title": "Null Rate Exceeds Threshold — glucose_level",
     "description": "glucose_level column has 47.3% null rate, exceeding 5% threshold by 9.46x",
     "source": "data_quality_agent", "run_id": "RUN_20240610_001",
     "time": "2024-06-10T08:20:12Z", "status": "New",
     "impact": "42% of glucose measurements missing — cohort analysis unreliable",
     "metrics": {"null_rate_pct": 47.3, "threshold_pct": 5.0, "affected_records": 237, "total_records": 500, "column": "glucose_level"},
     "recommended_action": "Investigate data pipeline from glucose monitoring devices. Check device connectivity logs.",
     "history": []},
    {"id": "ALT_002", "severity": "HIGH", "title": "Consumer Lag Spike Detected",
     "description": "Kafka consumer lag reached 1,842 messages, well above the 1,000 threshold",
     "source": "streaming_monitor", "run_id": "RUN_20240610_001",
     "time": "2024-06-10T08:19:05Z", "status": "Acknowledged",
     "impact": "Processing delay of ~92 seconds. Data freshness degraded.",
     "metrics": {"null_rate_pct": None, "threshold_pct": None, "affected_records": 1842, "total_records": 5000, "column": "consumer_lag"},
     "recommended_action": "Scale Kafka consumer group. Increase partition count for clinical_trial_events topic.",
     "history": [{"action": "Acknowledged", "by": "dr.johnson", "at": "2024-06-10T08:25:00Z"}]},
    {"id": "ALT_003", "severity": "HIGH", "title": "Statistical Drift Detected — age distribution",
     "description": "KS-test p-value 0.021 below threshold 0.05 for age column. Distribution shifted.",
     "source": "rca_agent", "run_id": "RUN_20240610_001",
     "time": "2024-06-10T08:20:50Z", "status": "New",
     "impact": "Age cohort composition changed significantly vs. baseline. Stratified analysis results may be invalid.",
     "metrics": {"null_rate_pct": None, "threshold_pct": 0.05, "affected_records": 500, "total_records": 500, "column": "age"},
     "recommended_action": "Compare current patient cohort enrollment criteria with protocol v3.2. Notify PI.",
     "history": []},
    {"id": "ALT_004", "severity": "MEDIUM", "title": "Low Confidence Score — Compliance Agent",
     "description": "compliance_agent returned confidence score 54/100, below 60 threshold",
     "source": "compliance_agent", "run_id": "RUN_20240609_003",
     "time": "2024-06-09T14:37:10Z", "status": "New",
     "impact": "Regulatory compliance review may be incomplete. Manual review recommended.",
     "metrics": {"null_rate_pct": None, "threshold_pct": None, "affected_records": None, "total_records": None, "column": None},
     "recommended_action": "Schedule manual FDA 21 CFR Part 11 compliance review. Re-run with larger window.",
     "history": []},
    {"id": "ALT_005", "severity": "LOW", "title": "Low Row Count — 87 records",
     "description": "Dataset has only 87 rows, below recommended minimum of 100",
     "source": "validation_service", "run_id": "RUN_20240608_002",
     "time": "2024-06-08T16:01:15Z", "status": "Acknowledged",
     "impact": "Statistical power may be insufficient for cohort-level conclusions.",
     "metrics": {"null_rate_pct": None, "threshold_pct": None, "affected_records": 87, "total_records": 87, "column": None},
     "recommended_action": "Collect additional patient records before re-running analysis.",
     "history": [{"action": "Acknowledged", "by": "dr.johnson", "at": "2024-06-08T17:00:00Z"}]},
]
_audit_events: list = [
    {"id": "EVT_001", "time": "2024-06-10T08:22:41Z", "event_type": "AI Agent Execution", "event_type_color": "purple",
     "agent_source": "data_quality_agent", "description": "Data quality analysis completed",
     "detail": "5 pillars evaluated, 2 critical findings", "user": "system", "status": "Success", "run_id": "RUN_20240610_001"},
    {"id": "EVT_002", "time": "2024-06-10T08:22:05Z", "event_type": "AI Agent Execution", "event_type_color": "purple",
     "agent_source": "rca_agent", "description": "Root cause analysis completed",
     "detail": "3 incidents identified, 1 critical", "user": "system", "status": "Success", "run_id": "RUN_20240610_001"},
    {"id": "EVT_003", "time": "2024-06-10T08:21:30Z", "event_type": "Data Validation", "event_type_color": "green",
     "agent_source": "validation_service", "description": "Pre-ingest validation completed",
     "detail": "0 hard blocks, 2 soft warnings", "user": "system", "status": "Success", "run_id": "RUN_20240610_001"},
    {"id": "EVT_004", "time": "2024-06-10T08:20:15Z", "event_type": "Pipeline Start", "event_type_color": "blue",
     "agent_source": "pipeline_service", "description": "Pipeline started by user",
     "detail": "input_mode=CSV, window_size=500", "user": "dr.johnson", "status": "Success", "run_id": "RUN_20240610_001"},
    {"id": "EVT_005", "time": "2024-06-10T08:18:00Z", "event_type": "User Action", "event_type_color": "teal",
     "agent_source": None, "description": "Report approved", "detail": "reviewer_id=USR_001, notes=Approved with caveats",
     "user": "dr.johnson", "status": "Success", "run_id": "RUN_20240610_001"},
    {"id": "EVT_006", "time": "2024-06-10T08:15:00Z", "event_type": "User Login", "event_type_color": "teal",
     "agent_source": None, "description": "User authenticated", "detail": "role=Clinical Data Manager",
     "user": "dr.johnson", "status": "Success", "run_id": None},
    {"id": "EVT_007", "time": "2024-06-10T08:22:55Z", "event_type": "Alert Triggered", "event_type_color": "red",
     "agent_source": "data_quality_agent", "description": "CRITICAL alert: Null Rate Exceeds Threshold",
     "detail": "glucose_level: 47.3% null rate", "user": "system", "status": "Triggered", "run_id": "RUN_20240610_001"},
    {"id": "EVT_008", "time": "2024-06-10T08:23:10Z", "event_type": "Data Access", "event_type_color": "blue",
     "agent_source": None, "description": "Artifact download: incident_report_draft.md",
     "detail": "size=14.2kb", "user": "dr.johnson", "status": "Success", "run_id": "RUN_20240610_001"},
]
_active_run: dict = {"run_id": None, "status": "idle"}
_pipeline_stages_state: dict = {}

# ─── Auth helpers ────────────────────────────────────────────────────────────
def get_token(authorization: str = Header(None)) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    return parts[1] if len(parts) == 2 else None

def require_auth(authorization: str = Header(None)):
    token = get_token(authorization)
    if not token or token not in _sessions:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return _sessions[token]

# ─── AUTH ────────────────────────────────────────────────────────────────────
class LoginReq(BaseModel):
    username: str
    password: str

class SignupReq(BaseModel):
    fullName: str
    username: str
    email: str
    password: str
    role: str

class ForgotPwReq(BaseModel):
    email: str

@app.post("/auth/login")
def login(req: LoginReq):
    if req.username == "admin" and req.password == "admin123":
        token = "tok_" + str(uuid.uuid4()).replace("-","")
        user = {"id":"USR_001","username":"admin","fullName":"Dr. Sarah Johnson",
                "email":"sarah.johnson@clinicaltrials.ai","role":"Clinical Data Manager","avatar_initials":"SJ"}
        _sessions[token] = user
        return {"success": True, "token": token, "user": user}
    raise HTTPException(status_code=401, detail={"success": False, "error": "Invalid credentials"})

@app.post("/auth/signup", status_code=201)
def signup(req: SignupReq):
    token = "tok_" + str(uuid.uuid4()).replace("-","")
    user = {"id":"USR_"+str(uuid.uuid4())[:6].upper(),"username":req.username,"fullName":req.fullName,
            "email":req.email,"role":req.role,"avatar_initials":"".join(p[0].upper() for p in req.fullName.split()[:2])}
    _sessions[token] = user
    return {"success": True, "token": token, "user": user}

@app.post("/auth/logout")
def logout(user=Depends(require_auth), authorization: str = Header(None)):
    token = get_token(authorization)
    _sessions.pop(token, None)
    return {"success": True, "message": "Logged out successfully"}

@app.post("/auth/forgot-password")
def forgot_password(req: ForgotPwReq):
    return {"success": True, "message": "Reset instructions sent if email exists"}

# ─── SYSTEM ──────────────────────────────────────────────────────────────────
@app.get("/system/status")
def system_status():
    return {"status":"operational","services":{"kafka":"healthy","agents":"healthy","api":"healthy","storage":"healthy"},
            "version":"4.0 Enhanced","uptime_seconds":int(time.time()-_start_time)}

# ─── PIPELINE ────────────────────────────────────────────────────────────────
@app.get("/pipeline/runs")
def get_runs(page:int=1, limit:int=10, user=Depends(require_auth)):
    start=(page-1)*limit
    return {"runs":_runs[start:start+limit],"total":len(_runs),"page":page,"limit":limit}

@app.get("/pipeline/runs/recent")
def recent_runs(limit:int=5):
    return {"runs":_runs[:limit],"total":len(_runs)}

@app.get("/pipeline/runs/active")
def active_run(user=Depends(require_auth)):
    return _active_run

@app.post("/pipeline/upload")
async def upload_file(file: UploadFile = File(...), run_id: str = Form(None), user=Depends(require_auth)):
    rid = run_id or "RUN_"+datetime.now().strftime("%Y%m%d")+"_"+str(uuid.uuid4())[:3].upper()
    content = await file.read()
    size_mb = round(len(content)/1024/1024, 3)
    cols = [
        {"name":"patient_id","type":"string","sample":"PAT_00001","null_count":0,"null_pct":0.0},
        {"name":"age","type":"int","sample":"34","null_count":5,"null_pct":1.0},
        {"name":"glucose_level","type":"float","sample":"98.4","null_count":237,"null_pct":47.3},
        {"name":"visit_date","type":"date","sample":"2024-06-01","null_count":0,"null_pct":0.0},
        {"name":"severity","type":"string","sample":"Medium","null_count":0,"null_pct":0.0},
        {"name":"treatment_group","type":"string","sample":"Control","null_count":12,"null_pct":2.4},
        {"name":"site_id","type":"string","sample":"SITE_A","null_count":0,"null_pct":0.0},
        {"name":"adverse_events","type":"string","sample":"None","null_count":8,"null_pct":1.6},
        {"name":"blood_pressure","type":"float","sample":"120.5","null_count":15,"null_pct":3.0},
        {"name":"patient_name","type":"string","sample":"<MASKED>","null_count":0,"null_pct":0.0},
    ]
    return {"run_id":rid,"filename":file.filename,"file_size_mb":size_mb,"total_rows":500,
            "total_columns":10,"detected_format":"CSV","encoding":"UTF-8","columns":cols[:5],
            "file_hash":"md5_"+str(uuid.uuid4())[:16],"saved_to":f"data/uploads/{rid}_{file.filename}"}

class SyntheticReq(BaseModel):
    scenario: str = "normal"
    rows: int = 500
    null_rate: float = 5.0
    outlier_pct: float = 2.0
    date_drift_days: int = 0
    duplicate_rate: float = 0.0

@app.post("/pipeline/generate-synthetic")
def gen_synthetic(req: SyntheticReq, user=Depends(require_auth)):
    rid = "RUN_"+datetime.now().strftime("%Y%m%d")+"_"+str(uuid.uuid4())[:3].upper()
    return {"run_id":rid,"scenario":req.scenario,"rows_generated":req.rows,
            "columns":["patient_id","age","glucose_level","visit_date","severity","treatment_group","site_id","adverse_events","blood_pressure","patient_name"],
            "saved_to":f"data/clinical/synthetic_{rid}.csv","generated_at":datetime.utcnow().isoformat()+"Z",
            "preview":{"null_rate_avg":req.null_rate,"outlier_pct":req.outlier_pct,
                        "severity_distribution":{"Low":25,"Medium":45,"High":20,"Critical":10}}}

class APIConnReq(BaseModel):
    url: str
    auth_type: str = "Bearer"
    token: str = ""
    poll_interval_seconds: int = 30
    max_records_per_poll: int = 500

@app.post("/pipeline/test-api-connection")
def test_api(req: APIConnReq, user=Depends(require_auth)):
    if "invalid" in req.url.lower() or not req.url.startswith("http"):
        raise HTTPException(400, {"connected":False,"error":"Could not connect to endpoint"})
    return {"connected":True,"endpoint":req.url,"auth_type":req.auth_type,"response_format":"JSON",
            "avg_latency_ms":142,"sample_record_count":12,
            "field_names":["patient_id","age","glucose_level","visit_date","severity","treatment_group"]}

@app.post("/pipeline/preflight/{run_id}")
def preflight(run_id:str, user=Depends(require_auth)):
    return {"run_id":run_id,"passed":True,"checked_at":datetime.utcnow().isoformat()+"Z","row_count":500,
            "hard_blocks":[],"soft_warnings":[
                {"id":"W001","check":"high_null_rate","column":"glucose_level","message":"glucose_level has 47.3% null rate (threshold: 30%)","detail":"237 of 500 records missing glucose measurement"},
                {"id":"W002","check":"severity_imbalance","column":"severity","message":"'Medium' severity represents 71.2% of records","detail":"Single severity dominates dataset — statistical power for subgroup analysis may be limited"}
            ],"cross_field_violations":[]}

@app.get("/pipeline/preflight/{run_id}")
def get_preflight(run_id:str, user=Depends(require_auth)):
    return {"run_id":run_id,"passed":True,"checked_at":datetime.utcnow().isoformat()+"Z","row_count":500,
            "hard_blocks":[],"soft_warnings":[
                {"id":"W001","check":"high_null_rate","column":"glucose_level","message":"glucose_level has 47.3% null rate","detail":"237 of 500 records"}
            ],"cross_field_violations":[]}

class RunPipelineReq(BaseModel):
    run_id: str
    run_name: str = ""
    input_mode: str = "csv"
    window_size: int = 500
    inter_event_delay_ms: int = 50
    description: str = ""

_pipeline_start: dict = {}

@app.post("/pipeline/run", status_code=202)
def run_pipeline(req: RunPipelineReq, user=Depends(require_auth), x_api_key: str = Header(None)):
    global _active_run
    _active_run = {"run_id":req.run_id,"status":"running","review_status":None,"started_at":datetime.utcnow().isoformat()+"Z","completed_at":None}
    _pipeline_start[req.run_id] = time.time()
    _pipeline_stages_state[req.run_id] = {"status":"running","stage_index":1,"started_at":datetime.utcnow().isoformat()+"Z"}
    return {"run_id":req.run_id,"status":"running","started_at":datetime.utcnow().isoformat()+"Z",
            "current_stage":"Input Discovery","stage_index":1,"total_stages":7}

@app.get("/pipeline/status/{run_id}")
def pipeline_status(run_id:str, user=Depends(require_auth)):
    elapsed = time.time() - _pipeline_start.get(run_id, time.time()-999)
    # simulate stage progression
    if elapsed < 3: stage_idx,status = 1,"running"
    elif elapsed < 7: stage_idx,status = 2,"running"
    elif elapsed < 12: stage_idx,status = 3,"running"
    elif elapsed < 18: stage_idx,status = 4,"running"
    elif elapsed < 25: stage_idx,status = 5,"running"
    elif elapsed < 30: stage_idx,status = 6,"running"
    elif elapsed < 35: stage_idx,status = 7,"running"
    else:
        stage_idx,status = 7,"completed"
        global _active_run
        if _active_run.get("run_id") == run_id:
            _active_run = {"run_id":run_id,"status":"completed","review_status":"pending_review",
                           "started_at":_active_run.get("started_at"),"completed_at":datetime.utcnow().isoformat()+"Z"}

    stages_labels = ["Input Discovery","Entry Validation","Preprocessing","PII/PHI Masking","AI Agents","Incident Report","Awaiting Review"]
    stages = []
    for i, lbl in enumerate(stages_labels):
        si = i+1
        if si < stage_idx: st = "completed"
        elif si == stage_idx: st = "active" if status=="running" else "completed"
        else: st = "pending"
        stages.append({"num":si,"label":lbl,"status":st,"duration_ms":random.randint(800,4200) if si<stage_idx else None})
    return {"run_id":run_id,"status":status,"current_stage":stages_labels[min(stage_idx-1,6)],
            "stage_index":stage_idx,"total_stages":7,"stages":stages,"events_processed":min(int(elapsed*14),500),
            "started_at":datetime.utcnow().isoformat()+"Z"}

@app.post("/pipeline/reset")
def reset_pipeline(body:dict, user=Depends(require_auth)):
    run_id = body.get("run_id","")
    _pipeline_start.pop(run_id, None)
    _pipeline_stages_state.pop(run_id, None)
    global _active_run
    _active_run = {"run_id":None,"status":"idle"}
    return {"success":True,"message":"Pipeline state reset successfully"}

@app.get("/pipeline/kafka-health")
def kafka_health():
    return {"kafka_available":True,"bootstrap_servers":"localhost:9092","topic":"clinical_trial_events","message":"Kafka operational"}

# ─── STREAMING ───────────────────────────────────────────────────────────────
@app.get("/streaming/status/{run_id}")
def streaming_status(run_id:str, user=Depends(require_auth)):
    elapsed = time.time() - _pipeline_start.get(run_id, time.time()-60)
    evts = min(int(elapsed*10), 500)
    lag = random.randint(80, 1200)
    mins, secs = divmod(int(elapsed), 60)
    hrs, mins = divmod(mins, 60)
    return {
        "run_id": run_id, "pipeline_status": "running",
        "uptime": f"{hrs:02d}:{mins:02d}:{secs:02d}",
        "uptime_seconds": int(elapsed),
        "records_processed": evts, "events_processed": evts,
        "throughput_per_sec": round(random.uniform(7,14), 1),
        "events_per_sec_avg": 9.8,
        "consumer_lag": lag,
        "anomalies_detected": random.randint(3, 15),
        "partitions": 1,
        "kafka_connected": True,
        "last_event_time": datetime.utcnow().isoformat()+"Z",
        "producer": {"status":"RUNNING","records_sent":evts+12,"send_rate_msg_per_sec":10.2,"errors":0},
        "consumer": {"status":"RUNNING","records_consumed":evts,"consumer_rate_msg_per_sec":9.8,"consumer_lag_avg":lag,"errors":0},
        "topic": {"name":"clinical_trial_events","status":"HEALTHY","partitions":1},
        "progress": {"total_target_events":500,"events_processed":evts,"events_pending":max(0,500-evts),"pct_complete":round(evts/5,1)}
    }

@app.get("/streaming/lag-history/{run_id}")
def lag_history(run_id:str, window:str="5m", user=Depends(require_auth)):
    now = datetime.utcnow()
    pts = [{"timestamp":(now-timedelta(seconds=300-i*30)).isoformat()+"Z","consumer_lag":random.randint(80,1200)} for i in range(11)]
    return {"run_id":run_id,"window":window,"lag_threshold":1000,"data_points":pts}

@app.get("/streaming/throughput-history/{run_id}")
def throughput_history(run_id:str, window:str="5m", user=Depends(require_auth)):
    now = datetime.utcnow()
    pts = [{"timestamp":(now-timedelta(seconds=300-i*30)).isoformat()+"Z","events_per_sec":round(random.uniform(7,14),1)} for i in range(11)]
    return {"run_id":run_id,"window":window,"avg_msg_per_sec":9.8,"data_points":pts}

@app.get("/streaming/events/recent/{run_id}")
def recent_events(run_id:str, limit:int=5, user=Depends(require_auth)):
    types = ["PATIENT_RECORD","GLUCOSE_READING","ADVERSE_EVENT","VISIT_RECORD","LAB_RESULT"]
    evts = [{"event_id":f"EVT_{uuid.uuid4().hex[:8].upper()}","event_type":random.choice(types),
             "time":datetime.utcnow().isoformat()+"Z","status":"VALID"} for _ in range(limit)]
    return {"events":evts}

@app.get("/streaming/agents/status/{run_id}")
def agents_status(run_id:str, user=Depends(require_auth)):
    elapsed = time.time() - _pipeline_start.get(run_id, time.time()-999)
    def agt_status(threshold):
        if elapsed < threshold: return "PENDING"
        elif elapsed < threshold+5: return "RUNNING"
        return "COMPLETED"
    agents = [
        {"name":"data_quality_agent","status":agt_status(20),"last_run":datetime.utcnow().isoformat()+"Z","confidence":87,"findings":"2 critical findings in glucose_level and age distribution"},
        {"name":"log_analysis_agent","status":agt_status(23),"last_run":datetime.utcnow().isoformat()+"Z","confidence":92,"findings":"14 warnings, 3 errors in ETL log"},
        {"name":"rca_agent","status":agt_status(26),"last_run":datetime.utcnow().isoformat()+"Z","confidence":78,"findings":"3 incidents — 1 critical, 1 high, 1 medium"},
        {"name":"recommendation_agent","status":agt_status(29),"last_run":datetime.utcnow().isoformat()+"Z","confidence":83,"findings":"5 remediation actions identified"},
        {"name":"compliance_agent","status":agt_status(32),"last_run":datetime.utcnow().isoformat()+"Z","confidence":54,"findings":"FDA 21 CFR Part 11 — 2 gaps identified"},
    ]
    return {"agents":agents}

@app.get("/streaming/ai-findings/live/{run_id}")
def live_findings(run_id:str, limit:int=5, user=Depends(require_auth)):
    findings = [
        {"id":"F001","severity":"critical","message":"glucose_level null rate at 47.3% — exceeds 5% threshold","agent":"data_quality_agent","timestamp":datetime.utcnow().isoformat()+"Z"},
        {"id":"F002","severity":"warning","message":"Consumer lag spike: 1842 messages","agent":"streaming_monitor","timestamp":(datetime.utcnow()-timedelta(seconds=45)).isoformat()+"Z"},
        {"id":"F003","severity":"warning","message":"KS-test drift detected in age distribution (p=0.021)","agent":"rca_agent","timestamp":(datetime.utcnow()-timedelta(seconds=90)).isoformat()+"Z"},
        {"id":"F004","severity":"info","message":"Severity distribution: Medium 71.2% — imbalanced","agent":"data_quality_agent","timestamp":(datetime.utcnow()-timedelta(seconds=120)).isoformat()+"Z"},
        {"id":"F005","severity":"critical","message":"Compliance agent confidence below threshold: 54/100","agent":"compliance_agent","timestamp":(datetime.utcnow()-timedelta(seconds=180)).isoformat()+"Z"},
    ]
    return {"findings":findings[:limit]}

@app.get("/streaming/window/status/{run_id}")
def window_status(run_id:str, user=Depends(require_auth)):
    elapsed = time.time() - _pipeline_start.get(run_id, time.time()-60)
    evts = min(int(elapsed*10), 500)
    now = datetime.utcnow()
    return {"current_window":1,"window_start":(now-timedelta(seconds=50)).isoformat()+"Z",
            "window_end":now.isoformat()+"Z","events_in_window":evts,"window_size":500,"rolling_metrics_status":"ACTIVE"}

# ─── REVIEW ──────────────────────────────────────────────────────────────────
@app.get("/review/pending")
def pending_reviews(user=Depends(require_auth)):
    pending = [r for r in _runs if r.get("review_status") == "pending_review"]
    return [{**r, "records_processed": r.get("rows", 0)} for r in pending]

@app.get("/review/findings/{run_id}")
def review_findings(run_id: str, user=Depends(require_auth)):
    # Returns flat list of ReviewFinding objects, one per finding (not per agent)
    findings = [
        # data_quality findings
        {"finding_type":"Null Rate Exceeds Threshold","severity":"critical","confidence":91,
         "description":"glucose_level column has 47.3% null rate, exceeding the 5% protocol threshold by 9.46x. 237 of 500 records are missing glucose measurements.",
         "agent":"data_quality","affected_field":"glucose_level",
         "record_ids":["SUBJ_0145","SUBJ_0146","SUBJ_0147","SUBJ_0382"],
         "recommendation":"Investigate glucose monitoring device connectivity at Site A. Check network switch port 4."},
        {"finding_type":"Distribution Drift — Age","severity":"high","confidence":87,
         "description":"KS-test detected statistically significant drift in age distribution (p=0.021, below threshold 0.05). Mean age shifted from 42.3 to 51.7 years.",
         "agent":"data_quality","affected_field":"age",
         "record_ids":["SUBJ_0102","SUBJ_0134"],
         "recommendation":"Review enrollment criteria against protocol v3.2. Notify PI of cohort composition change."},
        {"finding_type":"Duplicate Patient IDs","severity":"medium","confidence":95,
         "description":"23 duplicate patient_id values detected across 500 records (4.6% duplication rate).",
         "agent":"data_quality","affected_field":"patient_id",
         "record_ids":["SUBJ_0023","SUBJ_0087","SUBJ_0091"],
         "recommendation":"Deduplicate records and investigate upstream patient registration system."},
        {"finding_type":"Blood Pressure IQR Outliers","severity":"low","confidence":82,
         "description":"8 blood pressure readings fall outside 3×IQR bounds (1.6% of records).",
         "agent":"data_quality","affected_field":"blood_pressure",
         "record_ids":["SUBJ_0201","SUBJ_0309"],
         "recommendation":"Verify with clinical staff — may reflect genuine hypertensive events."},
        # log_analysis findings
        {"finding_type":"ETL Pipeline Errors","severity":"medium","confidence":93,
         "description":"3 ETL errors recorded during processing. All were caught and recovered but indicate instability.",
         "agent":"log_analysis","affected_field":None,
         "record_ids":[],
         "recommendation":"Review ETL error handlers and add alerting for error rate > 1%."},
        {"finding_type":"API Timeout Detected","severity":"low","confidence":89,
         "description":"1 API timeout recorded at 08:19:33Z during hospital data ingestion. Auto-recovered after retry.",
         "agent":"log_analysis","affected_field":None,
         "record_ids":[],
         "recommendation":"Monitor API timeout pattern; implement circuit breaker if rate increases."},
        # rca findings
        {"finding_type":"Glucose Device Connectivity Failure","severity":"critical","confidence":88,
         "description":"Root cause identified: IoT sensor network interruption at Site A between 07:45–08:15Z caused 237 consecutive null values.",
         "agent":"rca","affected_field":"glucose_level",
         "record_ids":["SUBJ_0145","SUBJ_0382"],
         "recommendation":"Dispatch IT personnel to Site A. Implement sensor heartbeat monitoring with 60s alert threshold."},
        {"finding_type":"Consumer Lag Spike — Root Cause","severity":"medium","confidence":76,
         "description":"Kafka consumer lag spike to 1,842 messages was downstream effect of glucose device failure causing record backlog.",
         "agent":"rca","affected_field":None,
         "record_ids":[],
         "recommendation":"Scale consumer group partition count from 1 to 3 to handle burst traffic."},
        # recommendation findings
        {"finding_type":"Immediate Action Required — Site A IT","severity":"critical","confidence":85,
         "description":"237 missing glucose measurements represent 47.3% data loss. This is unacceptable for trial integrity and requires immediate remediation.",
         "agent":"recommendation","affected_field":None,
         "record_ids":[],
         "recommendation":"Deploy IT personnel to Site A glucose monitoring rack immediately. Check network switch port 4 (documented failure history)."},
        {"finding_type":"Baseline Recalculation Required","severity":"high","confidence":80,
         "description":"Age cohort composition change invalidates historical baseline comparisons. All prior comparative analyses must be stratified.",
         "agent":"recommendation","affected_field":"age",
         "record_ids":[],
         "recommendation":"Schedule baseline recalculation with updated cohort (65+ age group now included per protocol amendment 3.2)."},
        # compliance findings
        {"finding_type":"ICH E6 GCP — Data Integrity Gap","severity":"critical","confidence":54,
         "description":"47.3% glucose data missing violates ICH E6 Section 5.18.4 data completeness requirements. This constitutes a protocol deviation.",
         "agent":"compliance","affected_field":"glucose_level",
         "record_ids":["SUBJ_0145","SUBJ_0382"],
         "recommendation":"Do not submit this data window to regulatory authority. File protocol deviation report. Notify Principal Investigator within 24 hours per SOP."},
        {"finding_type":"PI Notification Obligation","severity":"high","confidence":72,
         "description":"Protocol requires Principal Investigator notification within 24 hours of any data integrity deviation exceeding 10%. Current deviation is 47.3%.",
         "agent":"compliance","affected_field":None,
         "record_ids":[],
         "recommendation":"Send PI notification immediately. Document in trial master file."},
    ]
    return findings

@app.get("/review/token-usage/{run_id}")
def token_usage(run_id: str, user=Depends(require_auth)):
    input_t, output_t = 13716, 4358
    total_t = input_t + output_t
    return {
        "run_id": run_id,
        "input_tokens": input_t,
        "output_tokens": output_t,
        "total_tokens": total_t,
        "estimated_cost": round(total_t * 0.000004, 4),
        "model": "claude-sonnet-4-5",
    }

@app.get("/review/artifacts/{run_id}")
def artifacts(run_id: str, user=Depends(require_auth)):
    return [
        {"name":"incident_report_draft.md","type":"Markdown Report","size":"14.2 KB"},
        {"name":"rolling_metrics.json","type":"JSON Data","size":"38.7 KB"},
        {"name":"etl_run.log","type":"Log File","size":"8.1 KB"},
        {"name":"agent_responses.json","type":"JSON Data","size":"22.4 KB"},
        {"name":"sanitized_metrics.json","type":"JSON Data","size":"36.9 KB"},
    ]

@app.post("/review/approve")
def approve(body: dict, user=Depends(require_auth)):
    run_id = body.get("run_id","")
    for r in _runs:
        if r["run_id"] == run_id:
            r["review_status"] = "approved"; r["status"] = "approved"
    return {"success": True, "run_id": run_id, "status": "approved",
            "approved_at": datetime.utcnow().isoformat()+"Z"}

@app.post("/review/reject")
def reject(body: dict, user=Depends(require_auth)):
    run_id = body.get("run_id","")
    for r in _runs:
        if r["run_id"] == run_id:
            r["review_status"] = "rejected"
    return {"success": True, "run_id": run_id, "status": "rejected",
            "rejected_at": datetime.utcnow().isoformat()+"Z"}

# ─── DASHBOARD ───────────────────────────────────────────────────────────────
@app.get("/dashboard/summary")
def dash_summary(user=Depends(require_auth)):
    approved = [r for r in _runs if r.get("review_status") == "approved"]
    approved_id = approved[0]["run_id"] if approved else None
    return {
        "total_runs": 47, "runs_trend": 12.6,
        "total_anomalies": 128, "anomalies_trend": -8.2,
        "avg_confidence_score": 81, "confidence_trend": 4.3,
        "total_token_cost": 3.76, "cost_trend": 2.1,
        "approved_run_id": approved_id,
        "last_updated": datetime.utcnow().isoformat()+"Z",
        "pillar_scores": {
            "data_integrity":    {"score": 62, "findings": 6, "status": "warning"},
            "safety_monitoring": {"score": 88, "findings": 2, "status": "normal"},
            "protocol_compliance": {"score": 54, "findings": 4, "status": "critical"},
            "statistical_validity": {"score": 79, "findings": 3, "status": "warning"},
            "operational_efficiency": {"score": 95, "findings": 1, "status": "normal"},
        },
    }

@app.get("/dashboard/pipeline-runs-over-time")
def runs_over_time(user=Depends(require_auth)):
    now = datetime.utcnow()
    return [{"time": (now-timedelta(hours=23-i)).strftime("%H:%M"),
             "completed": random.randint(1,4), "failed": random.randint(0,1)} for i in range(24)]

@app.get("/dashboard/anomalies-by-severity")
def anomalies_severity(user=Depends(require_auth)):
    return [
        {"name": "Critical", "value": 7,  "color": "#EF4444"},
        {"name": "High",     "value": 23, "color": "#F59E0B"},
        {"name": "Medium",   "value": 54, "color": "#3B82F6"},
        {"name": "Low",      "value": 44, "color": "#10B981"},
    ]

@app.get("/dashboard/agents-performance")
def agents_perf(user=Depends(require_auth)):
    return [
        {"name": "Data Quality",    "confidence": 87, "inferences": 47},
        {"name": "Log Analysis",    "confidence": 92, "inferences": 47},
        {"name": "Root Cause",      "confidence": 78, "inferences": 47},
        {"name": "Recommendation",  "confidence": 83, "inferences": 47},
        {"name": "Compliance",      "confidence": 61, "inferences": 47},
    ]

@app.get("/dashboard/token-usage")
def dash_token_usage(user=Depends(require_auth)):
    runs = ["RUN_001","RUN_002","RUN_003","RUN_004","RUN_005","RUN_006","RUN_007"]
    return [{"run": r, "cost": round(random.uniform(0.05, 0.12), 3)} for r in runs]

@app.get("/dashboard/pipeline-health")
def pipeline_health(user=Depends(require_auth)):
    return {
        "availability": 99.2, "success_rate": 87.2,
        "avg_processing_time_s": 468, "data_freshness_s": 23,
        "kafka_uptime": 99.8, "agent_accuracy": 81.0,
    }

@app.get("/dashboard/anomalies-trend")
def anomalies_trend(user=Depends(require_auth)):
    now = datetime.utcnow()
    return [{"date": (now-timedelta(days=6-i)).strftime("%b %d"),
             "critical": random.randint(0,3), "high": random.randint(2,8),
             "medium": random.randint(5,20), "low": random.randint(8,25)} for i in range(7)]

@app.get("/dashboard/top-anomaly-types")
def top_anomaly_types(user=Depends(require_auth)):
    return [
        {"type": "High Null Rate",      "count": 34},
        {"type": "Statistical Drift",   "count": 28},
        {"type": "Outlier Detection",   "count": 22},
        {"type": "Duplicate Records",   "count": 26},
        {"type": "Schema Violation",    "count": 18},
    ]

@app.get("/dashboard/run-status-distribution")
def run_status_dist(user=Depends(require_auth)):
    return [
        {"name": "Completed", "value": 41, "color": "#10B981"},
        {"name": "Failed",    "value": 4,  "color": "#EF4444"},
        {"name": "Running",   "value": 2,  "color": "#3B82F6"},
    ]

@app.get("/dashboard/recent-alerts")
def dash_recent_alerts(user=Depends(require_auth)):
    return [_normalize_alert(a) for a in _alerts_store[:5]]

@app.get("/dashboard/{run_id}/tokens")
def run_tokens(run_id: str, user=Depends(require_auth)):
    run = next((r for r in _runs if r["run_id"] == run_id), None)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.get("review_status") != "approved":
        raise HTTPException(403, "Run not yet approved — dashboard locked")
    return {"run_id": run_id, "total_tokens": 16074, "total_cost_usd": 0.0735}

# ─── ALERTS ──────────────────────────────────────────────────────────────────
def _normalize_alert(a: dict) -> dict:
    """Normalize alert to camelCase-free, consistent schema."""
    sev = a.get("severity","low").lower()
    stat = a.get("status","active").lower().replace(" ","_")
    # map legacy status values
    stat_map = {"new": "active", "acknowledged": "acknowledged", "escalated": "escalated", "resolved": "resolved"}
    stat = stat_map.get(stat, stat)
    return {
        "id": a.get("id"),
        "severity": sev,
        "title": a.get("title",""),
        "message": a.get("description",""),
        "source": a.get("source",""),
        "run_id": a.get("run_id"),
        "triggered_at": a.get("time",""),
        "acknowledged_at": next((h["at"] for h in a.get("history",[]) if h.get("action","").lower().startswith("ack")), None),
        "status": stat,
        "read": stat != "active",
        "category": a.get("source","").replace("_"," "),
        "recommendation": a.get("recommended_action",""),
    }

@app.get("/alerts")
def get_alerts(severity: str = "all", status: str = "all",
               page: int = 1, limit: int = 50, user=Depends(require_auth)):
    filtered = _alerts_store
    if severity and severity != "all":
        filtered = [a for a in filtered if a["severity"].lower() == severity.lower()]
    if status and status != "all":
        stat_map_rev = {"acknowledged": "Acknowledged", "escalated": "Escalated", "active": "New", "resolved": "Resolved"}
        target = stat_map_rev.get(status, status)
        filtered = [a for a in filtered if a["status"].lower() == target.lower()]
    start = (page-1) * limit
    return [_normalize_alert(a) for a in filtered[start:start+limit]]

@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str, user=Depends(require_auth)):
    a = next((x for x in _alerts_store if x["id"] == alert_id), None)
    if not a: raise HTTPException(404)
    return _normalize_alert(a)

@app.post("/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: str, body: dict, user=Depends(require_auth)):
    a = next((x for x in _alerts_store if x["id"] == alert_id), None)
    if a:
        a["status"] = "Acknowledged"
        a.setdefault("history",[]).append({"action":"Acknowledged","by":body.get("acknowledged_by","user"),"at":datetime.utcnow().isoformat()+"Z"})
    return {"success": True, "alert_id": alert_id, "status": "acknowledged"}

@app.post("/alerts/{alert_id}/escalate")
def escalate(alert_id: str, body: dict, user=Depends(require_auth)):
    a = next((x for x in _alerts_store if x["id"] == alert_id), None)
    if a: a["status"] = "Escalated"
    return {"success": True, "alert_id": alert_id, "status": "escalated"}

@app.post("/alerts/{alert_id}/read")
def mark_read(alert_id: str, body: dict, user=Depends(require_auth)):
    return {"success": True, "alert_id": alert_id, "read": True}

# ─── AUDIT ───────────────────────────────────────────────────────────────────
def _normalize_audit(e: dict) -> dict:
    return {
        "id": e.get("id"),
        "timestamp": e.get("time",""),
        "event_type": e.get("event_type","").lower().replace(" ","_"),
        "user": e.get("user"),
        "run_id": e.get("run_id"),
        "details": e.get("description","") + ((" — " + e.get("detail","")) if e.get("detail") else ""),
        "ip_address": "192.168.1.100",
        "has_prompt": e.get("agent_source") is not None,
        "metadata": {"agent_source": e.get("agent_source"), "status": e.get("status")},
        "hash": "sha256:" + uuid.uuid4().hex[:40],
    }

@app.get("/audit/summary")
def audit_summary(user=Depends(require_auth)):
    return {
        "total_events": len(_audit_events),
        "pipeline_events": sum(1 for e in _audit_events if "pipeline" in e.get("event_type","").lower()),
        "alert_events": sum(1 for e in _audit_events if "alert" in e.get("event_type","").lower()),
        "prompt_events": sum(1 for e in _audit_events if e.get("agent_source") is not None),
        "user_events": sum(1 for e in _audit_events if e.get("user") not in [None, "system"]),
    }

@app.get("/audit/events")
def audit_events(event_type: str = "all", user_filter: str = "all",
                  status: str = "all", page: int = 1, limit: int = 50,
                  from_date: str = "", to_date: str = "",
                  user=Depends(require_auth)):
    filtered = _audit_events
    if event_type and event_type != "all":
        filtered = [e for e in filtered if event_type.lower() in e["event_type"].lower().replace(" ","_")]
    if user_filter and user_filter != "all":
        filtered = [e for e in filtered if e.get("user","").lower() == user_filter.lower()]
    return [_normalize_audit(e) for e in filtered]

@app.get("/audit/events/{event_id}")
def audit_event_detail(event_id: str, user=Depends(require_auth)):
    e = next((x for x in _audit_events if x["id"] == event_id), None)
    if not e: raise HTTPException(404)
    return _normalize_audit(e)

@app.get("/audit/events/{event_id}/prompt")
def audit_prompt(event_id: str, user=Depends(require_auth)):
    e = next((x for x in _audit_events if x["id"] == event_id), None)
    agent_name = e.get("agent_source","system") if e else "system"
    return {
        "event_id": event_id,
        "agent": agent_name,
        "model": "claude-3-5-sonnet-20241022",
        "system_prompt": "You are a Clinical Data Quality Specialist analyzing observability metrics from a clinical trial streaming pipeline. Your goal is to identify anomalies, data quality issues, and compliance violations.",
        "user_prompt": f"Analyze the following clinical trial dataset metrics from run RUN_20240610_001 and identify any data quality issues, statistical anomalies, or protocol deviations...\n\n[Dataset metrics would be injected here in production]",
        "response": "Based on my analysis of the clinical trial metrics:\n\n1. **Critical: Missing Data** — glucose_level shows 47.3% null rate, exceeding the 5% protocol threshold.\n2. **High: Distribution Drift** — Age distribution has shifted significantly (KS-test p=0.021).\n3. **Recommendation** — Immediate investigation of glucose sensor connectivity is required.",
        "tokens": 2734,
        "latency_ms": 892,
    }

@app.get("/audit/export")
def audit_export(format:str="csv", user=Depends(require_auth)):
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["id","time","event_type","agent_source","description","user","status","run_id"])
        writer.writeheader()
        for e in _audit_events:
            writer.writerow({k:e.get(k,"") for k in ["id","time","event_type","agent_source","description","user","status","run_id"]})
        output.seek(0)
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                                  headers={"Content-Disposition":"attachment; filename=audit_export.csv"})
    return StreamingResponse(iter([json.dumps(_audit_events, indent=2)]), media_type="application/json",
                              headers={"Content-Disposition":"attachment; filename=audit_export.json"})

# ─── ALIAS ROUTES (no run_id param for streaming) ────────────────────────────
DEFAULT_STREAM_RUN = "RUN_20240609_003"

@app.get("/streaming/lag-history")
def lag_history_norun(user=Depends(require_auth)):
    now = datetime.utcnow()
    pts = [{"time": (now-timedelta(seconds=300-i*30)).strftime("%H:%M:%S"),
             "lag": random.randint(80, 1200)} for i in range(11)]
    return pts

@app.get("/streaming/throughput-history")
def throughput_history_norun(user=Depends(require_auth)):
    now = datetime.utcnow()
    pts = [{"time": (now-timedelta(seconds=300-i*30)).strftime("%H:%M:%S"),
             "in": round(random.uniform(7, 14), 1),
             "out": round(random.uniform(5, 12), 1)} for i in range(11)]
    return pts

@app.get("/streaming/events/recent")
def recent_events_norun(limit: int = 20, user=Depends(require_auth)):
    event_types = ["anomaly_detected", "record_processed", "agent_inference", "window_closed", "lag_spike"]
    sev_choices = [None, None, None, "high", "critical", "medium", "low"]
    agents = ["data_quality", "log_analysis", "rca", "recommendation", "compliance"]
    records = []
    for i in range(min(limit, 20)):
        etype = random.choice(event_types)
        sev = random.choice(sev_choices)
        records.append({
            "event_type": etype,
            "message": {
                "anomaly_detected": "Anomaly detected in glucose_level field",
                "record_processed": f"Record SUBJ_{random.randint(1000,9999)} processed successfully",
                "agent_inference": f"{random.choice(agents)} agent completed inference",
                "window_closed": f"Window #{random.randint(1,20)} closed with {random.randint(100,500)} events",
                "lag_spike": f"Consumer lag spike: {random.randint(800,2000)} messages behind",
            }.get(etype, "Event processed"),
            "severity": sev,
            "agent": random.choice(agents) if etype in ["anomaly_detected", "agent_inference"] else None,
            "record_id": f"SUBJ_{random.randint(1000,9999)}" if etype == "record_processed" else None,
            "timestamp": (datetime.utcnow()-timedelta(seconds=i*15)).isoformat()+"Z",
        })
    return records

@app.get("/streaming/agents/status")
def agents_status_norun(user=Depends(require_auth)):
    agents = [
        {"agent_id": "data_quality", "name": "Data Quality Agent", "status": "COMPLETED",
         "last_run": datetime.utcnow().isoformat()+"Z", "confidence": 87,
         "inferences": 124, "findings_count": 8, "avg_latency_ms": 342},
        {"agent_id": "log_analysis", "name": "Log Analysis Agent", "status": "COMPLETED",
         "last_run": datetime.utcnow().isoformat()+"Z", "confidence": 92,
         "inferences": 89, "findings_count": 5, "avg_latency_ms": 218},
        {"agent_id": "rca", "name": "Root Cause Agent", "status": "COMPLETED",
         "last_run": datetime.utcnow().isoformat()+"Z", "confidence": 78,
         "inferences": 37, "findings_count": 3, "avg_latency_ms": 891},
        {"agent_id": "recommendation", "name": "Recommendation Agent", "status": "COMPLETED",
         "last_run": datetime.utcnow().isoformat()+"Z", "confidence": 83,
         "inferences": 22, "findings_count": 7, "avg_latency_ms": 445},
        {"agent_id": "compliance", "name": "Compliance Agent", "status": "COMPLETED",
         "last_run": datetime.utcnow().isoformat()+"Z", "confidence": 54,
         "inferences": 61, "findings_count": 4, "avg_latency_ms": 672},
    ]
    return agents

@app.get("/streaming/ai-findings/live")
def live_findings_norun(limit: int = 30, user=Depends(require_auth)):
    findings = [
        {"finding_type": "Missing Value Rate Critical", "severity": "critical", "confidence": 91,
         "description": "glucose_level null rate at 47.3% exceeds the 5% threshold set in the protocol.",
         "agent": "data_quality", "record_ids": ["SUBJ_1023", "SUBJ_1047", "SUBJ_1089"],
         "affected_field": "glucose_level", "recommendation": "Investigate data collection pipeline for glucose sensor failures."},
        {"finding_type": "Consumer Lag Spike", "severity": "high", "confidence": 88,
         "description": "Consumer lag spiked to 1,842 messages behind producer, risking data loss.",
         "agent": "log_analysis", "record_ids": [], "affected_field": None,
         "recommendation": "Scale Kafka consumer group or reduce producer throughput temporarily."},
        {"finding_type": "Distribution Drift Detected", "severity": "high", "confidence": 79,
         "description": "KS-test detected statistically significant drift in age distribution (p=0.021).",
         "agent": "rca", "record_ids": ["SUBJ_1102", "SUBJ_1134"],
         "affected_field": "age", "recommendation": "Review enrollment criteria and stratification."},
        {"finding_type": "Severity Imbalance", "severity": "medium", "confidence": 74,
         "description": "Adverse event severity distribution skewed: Medium 71.2% — may bias safety analysis.",
         "agent": "data_quality", "record_ids": [],
         "affected_field": "severity", "recommendation": "Validate severity classification algorithm."},
        {"finding_type": "Compliance Gap — 21 CFR Part 11", "severity": "critical", "confidence": 54,
         "description": "Two audit trail gaps identified in electronic record submissions per FDA 21 CFR Part 11.",
         "agent": "compliance", "record_ids": ["SUBJ_1200", "SUBJ_1201"],
         "affected_field": "audit_trail", "recommendation": "Immediately review and re-submit affected records with proper audit trail."},
        {"finding_type": "Batch Processing Delay", "severity": "low", "confidence": 82,
         "description": "Batch window processing latency averaging 1.2s above SLA threshold of 500ms.",
         "agent": "log_analysis", "record_ids": [],
         "affected_field": None, "recommendation": "Optimize batch processing query and consider indexing."},
    ]
    return findings[:limit]

@app.get("/streaming/window/status")
def window_status_norun(user=Depends(require_auth)):
    now = int(time.time())
    window_size = 60
    elapsed_in_window = now % window_size
    return {
        "window_size_seconds": window_size,
        "current_window": now // window_size,
        "windows_closed": (now // window_size) - 100,
        "next_close_in": window_size - elapsed_in_window,
        "events_in_window": random.randint(80, 500),
    }
