import os
import sys
import uuid
import base64
import asyncio
import json
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv(override=True)

from backend.hr_router import assemble_team
from backend.workflow import build_company_graph, MissionState, split_ceo_reject_directives
from backend.file_processor import parse_uploaded_document
from backend.report_exporter import build_docx_bytes, build_xlsx_bytes, build_export_filename
from backend.db_store import (
    init_db,
    get_session_upload,
    set_session_upload,
    clear_session_upload,
    get_or_create_session_hitl,
    push_live_instruction,
    clear_live_instructions,
    record_token_usage,
    get_cost_metrics,
    set_budget_limit,
    is_force_refresh_prompt,
    find_cached_mission,
    save_mission_record,
    list_mission_records,
    delete_mission_record,
    load_webhook_configs,
    save_webhook_configs,
    build_enterprise_payload_preview,
)
from backend.openai_oauth import (
    load_chatgpt_token,
    save_chatgpt_token,
    clear_chatgpt_token,
    auto_connect_chatgpt_browser,
)

init_db()

app = FastAPI(title="AI Company Mission Control API - Enterprise v3 Ultimate")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

company_graph = build_company_graph()

class CEOInterventionRequest(BaseModel):
    action: str
    comment: str = ""
    session_id: str = "default"

class LiveWhisperRequest(BaseModel):
    session_id: str = "default"
    instruction: str

class BudgetUpdateRequest(BaseModel):
    budget_limit_usd: float

class WebhookSaveRequest(BaseModel):
    configs: dict

class WebhookTestRequest(BaseModel):
    target_system: str
    prompt: str
    report_markdown: str

class TokenRegisterRequest(BaseModel):
    access_token: str
    model: str = "gpt-4o-mini"

class Base64FileUploadRequest(BaseModel):
    filename: str
    content_base64: str
    session_id: str = "default"

class ReportExportRequest(BaseModel):
    title: str
    report_markdown: str
    format: str
    session_id: str = "default"
    attached_filename: str = ""

@app.get("/api/health")
async def enterprise_health_check():
    return {
        "status": "HEALTHY",
        "sqlite_wal_mode": True,
        "browser_semaphore_limit": 2,
        "pii_dlp_guardrail": "ACTIVE",
        "session_ttl_sec": 3600,
    }

@app.get("/")
async def root_status():
    return {
        "status": "ONLINE",
        "features": ["Live_HITL_Whisper", "Archive_Shelf_Memory", "Token_Cost_Governance", "ERP_Jira_Slack_Webhooks"],
    }

# --- 1) 실시간 양방향 CEO 개입(Whisper) 엔드포인트 ---
@app.post("/api/mission/intervene")
async def send_live_ceo_instruction(req: LiveWhisperRequest):
    if req.instruction.strip():
        push_live_instruction(req.session_id, req.instruction.strip())
    return {"status": "QUEUED", "instruction": req.instruction.strip()}

# --- 2) LLM 토큰 및 비용 거버넌스 대시보드 API ---
@app.get("/api/metrics/cost")
async def get_token_cost_dashboard():
    return get_cost_metrics()

@app.post("/api/metrics/budget")
async def update_token_budget(req: BudgetUpdateRequest):
    return set_budget_limit(req.budget_limit_usd)

# --- 3) 취업 대비용 ERP / Jira / Slack 플러그앤플레이 웹훅 API ---
@app.get("/api/integrations/webhooks")
async def get_webhooks():
    return load_webhook_configs()

@app.post("/api/integrations/webhooks")
async def update_webhooks(req: WebhookSaveRequest):
    return save_webhook_configs(req.configs)

@app.post("/api/integrations/test-dispatch")
async def test_webhook_dispatch(req: WebhookTestRequest):
    cfgs = load_webhook_configs()
    target_cfg = cfgs.get(req.target_system, {})
    payload = build_enterprise_payload_preview(req.target_system, req.prompt, req.report_markdown)
    endpoint = target_cfg.get("endpoint_url", "").strip()

    if endpoint.startswith("http"):
        import httpx
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.post(endpoint, json=payload)
                return {"status": "SENT_LIVE", "http_status": resp.status_code, "payload": payload}
        except Exception as e:
            return {"status": "SIMULATED_FALLBACK", "error": str(e)[:60], "payload": payload}

    return {"status": "SIMULATED_READY", "message": "실제 API URL 입력 시 즉시 실서버로 전송됩니다.", "payload": payload}

@app.post("/api/mission/upload-json")
async def upload_document_json(req: Base64FileUploadRequest):
    raw_bytes = base64.b64decode(req.content_base64)
    summary_text, meta = await asyncio.to_thread(parse_uploaded_document, req.filename or "uploaded_file", raw_bytes, req.session_id)
    set_session_upload(req.session_id, req.filename or "첨부문서", summary_text)
    return {
        "status": "OK",
        "filename": req.filename,
        "meta": meta,
        "preview": summary_text[:500],
    }

@app.post("/api/mission/clear-upload")
async def clear_uploaded_document(session_id: str = Query("default")):
    clear_session_upload(session_id)
    return {"status": "CLEARED"}

@app.get("/api/mission/history")
async def get_mission_history():
    records = await asyncio.to_thread(list_mission_records, 30)
    return {"status": "OK", "records": records}

@app.delete("/api/mission/history/{record_id}")
async def remove_mission_history(record_id: int):
    await asyncio.to_thread(delete_mission_record, record_id)
    return {"status": "DELETED", "id": record_id}

@app.post("/api/mission/export")
async def export_report_file(req: ReportExportRequest):
    fmt = req.format.lower().strip()
    filename = build_export_filename(req.title, fmt, req.attached_filename, req.session_id)

    if fmt == "docx":
        file_bytes = await asyncio.to_thread(build_docx_bytes, req.title, req.report_markdown, req.session_id)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif fmt == "xlsx":
        file_bytes = await asyncio.to_thread(build_xlsx_bytes, req.title, req.report_markdown, req.session_id)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        file_bytes = req.report_markdown.encode("utf-8-sig")
        media_type = "text/markdown; charset=utf-8"

    encoded_fname = urllib.parse.quote(filename)
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_fname}"}
    )

@app.get("/api/auth/openai/status")
async def get_openai_auth_status():
    tok = load_chatgpt_token()
    if tok and tok.get("access_token"):
        raw = tok["access_token"]
        masked = raw[:8] + "..." + raw[-4:] if len(raw) > 12 else "연동됨"
        return {"connected": True, "model": tok.get("model", "gpt-4o-mini"), "masked_token": masked}
    return {"connected": False}

@app.post("/api/auth/openai/auto-browser")
async def start_auto_browser_auth():
    res = await auto_connect_chatgpt_browser()
    return res

@app.post("/api/auth/openai/token")
async def register_openai_token(req: TokenRegisterRequest):
    save_chatgpt_token({"access_token": req.access_token.strip(), "model": req.model})
    return {"status": "CONNECTED", "model": req.model}

@app.post("/api/auth/openai/disconnect")
async def disconnect_openai():
    clear_chatgpt_token()
    return {"status": "DISCONNECTED"}

@app.post("/api/mission/resolve")
async def resolve_hitl(req: CEOInterventionRequest):
    hitl = get_or_create_session_hitl(req.session_id)
    hitl["decision_store"]["action"] = req.action
    hitl["decision_store"]["comment"] = req.comment
    hitl["resume_event"].set()
    return {"status": "resumed"}

@app.get("/api/mission/stream")
async def stream_mission(
    prompt: str = Query(...),
    session_id: str = Query("default"),
    sup_id: str | None = Query(None),
    worker_ids: str | None = Query(None)
):
    event_queue: asyncio.Queue = asyncio.Queue()
    w_list = [w for w in worker_ids.split(",") if w] if worker_ids else None
    thread_id = f"{session_id}-{uuid.uuid4().hex[:8]}"

    async def run_orchestration():
        try:
            session_doc = get_session_upload(session_id)
            session_hitl = get_or_create_session_hitl(session_id)
            attached_name = session_doc.get("filename", "")
            attached_summary = session_doc.get("summary", "")

            clear_live_instructions(session_id)
            force_refresh, cleaned_prompt = is_force_refresh_prompt(prompt, session_id)
            # [전자결재 대표 반려 & 재가동] 결합된 반려 사유를 원 안건과 분리 (라우팅은 원 안건 기준)
            core_prompt, reject_reasons = split_ceo_reject_directives(cleaned_prompt)
            cached_record = None
            if not reject_reasons:
                cached_record = await asyncio.to_thread(find_cached_mission, prompt, attached_name, session_id)

            selection, nodes, edges, emp_map = await asyncio.to_thread(assemble_team, core_prompt, sup_id, w_list)
            sup_info = emp_map[selection.supervisor_id]
            worker_names = ", ".join([emp_map[w.agent_id]["name"] for w in selection.workers])
            w1_info = emp_map[selection.workers[0].agent_id]

            await event_queue.put({
                "type": "TEAM_ASSEMBLED", "agentId": sup_info["id"], "agentName": sup_info["name"],
                "role": "SUPERVISOR", "timestamp": datetime.now().strftime("%H:%M:%S"),
                "payload": {"nodes": nodes, "edges": edges, "tokensUsed": 50}
            })

            # [핵심 분기 1] 과거에 질문했던 기록이 책장(SQLite 서가)에 존재하고 "다시 찾아줘"가 아닐 때 -> 서가(책장) 아카이브 즉시 인출 애니메이션 가동!
            if cached_record and not force_refresh:
                cost_stat = record_token_usage(0, 0, is_cache_hit=True)
                await event_queue.put({
                    "type": "COST_UPDATE",
                    "agentId": sup_info["id"],
                    "agentName": sup_info["name"],
                    "role": "SUPERVISOR",
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "payload": cost_stat,
                })
                await event_queue.put({
                    "type": "ARCHIVE_HIT",
                    "agentId": w1_info["id"],
                    "agentName": w1_info["name"],
                    "role": "WORKER",
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "payload": {
                        "status": "WORKING",
                        "recordId": cached_record["id"],
                        "createdAt": cached_record["created_at"],
                        "text": f"📚 [부서 책장(서가) 기존 기록 발견!] 이전에 결재된 #{cached_record['id']}번 문서('{cached_record['prompt'][:28]}...')를 뒤쪽 책장에서 찾아 즉시 보고합니다! (API 비용 $0 절감 / 만약 새로 크롤링하려면 '다시 찾아줘'라고 입력하세요)",
                    },
                })
                await asyncio.sleep(1.5)
                await event_queue.put({
                    "type": "FINAL_REPORT",
                    "agentId": sup_info["id"],
                    "agentName": sup_info["name"],
                    "role": "SUPERVISOR",
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "payload": {
                        "status": "DONE",
                        "isArchiveHit": True,
                        "reportMarkdown": (
                            f"📚 [서가(책장) 아카이브 즉시 인출 보고서 — 원본 결재일: {cached_record['created_at']} | 재검색 요청 시 '다시 찾아줘' 입력]\n\n"
                            f"{cached_record['report_markdown']}"
                        ),
                        "tokensUsed": 0,
                    },
                })
                return

            # [핵심 분기 2] 신규 질문이거나 "다시 찾아줘"가 포함된 경우 -> 실제 웹 리서치 풀가동!
            if force_refresh:
                await event_queue.put({
                    "type": "FORCE_REFRESH_START",
                    "agentId": sup_info["id"],
                    "agentName": sup_info["name"],
                    "role": "SUPERVISOR",
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "payload": {
                        "status": "WORKING",
                        "text": f"🔄 ['다시 찾아줘' 재조사 명령 감지] 기존 책장(서가) 캐시를 우회하고 '{cleaned_prompt[:28]}...'에 대해 최신 웹 리서치를 처음부터 다시 수행합니다!",
                    },
                })

            await event_queue.put({
                "type": "MESSAGE", "agentId": sup_info["id"], "agentName": sup_info["name"],
                "role": "SUPERVISOR", "timestamp": datetime.now().strftime("%H:%M:%S"),
                "payload": {"status": "WORKING", "text": f"🎯 [전담 부서 배정 완료] {sup_info['dept']} ({sup_info['name']}, {worker_names}) 팀만 업무에 투입되며, 타 부서 직원들은 각자 부서실에서 일상 업무를 유지합니다.", "tokensUsed": 160}
            })

            enriched = [{**emp_map[w.agent_id], "sub_task": w.sub_task} for w in selection.workers]
            effective_prompt = core_prompt
            if attached_name and attached_summary:
                effective_prompt = f"{core_prompt} (첨부파일 '{attached_name}' 전수 통계 반영)"

            reject_notes = [f"↩️ [대표 결재 반려 보완지시] {r}" for r in reject_reasons]
            if reject_notes:
                await event_queue.put({
                    "type": "CEO_LIVE_INTERVENTION", "agentId": sup_info["id"], "agentName": sup_info["name"],
                    "role": "SUPERVISOR", "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "payload": {
                        "status": "REJECTED",
                        "text": f"↩️ [대표 결재 반려 접수] \"{reject_reasons[-1]}\" ➔ {sup_info['dept']} 전담팀이 보완 지시를 반영해 보고서를 재작성합니다!",
                        "instruction": reject_reasons[-1],
                    },
                })

            init_state: MissionState = {
                "ceo_prompt": effective_prompt,
                "supervisor": sup_info,
                "workers": enriched,
                "web_evidence": attached_summary if attached_summary else "",
                "worker1_draft": "",
                "qc_passed": False,
                "qc_score": 0,
                "qc_feedback": None,
                "reject_count": 0,
                "rework_query": None,
                "live_ceo_notes": reject_notes,
                "final_report": None,
            }
            final_state = await company_graph.ainvoke(init_state, config={"configurable": {
                "thread_id": thread_id,
                "session_id": session_id,
                "event_queue": event_queue,
                "resume_event": session_hitl["resume_event"],
                "hitl_store": session_hitl["decision_store"],
                "attached_summary": attached_summary,
            }})

            if final_state and final_state.get("final_report"):
                rec_id = await asyncio.to_thread(
                    save_mission_record,
                    session_id,
                    cleaned_prompt,
                    sup_info["dept"],
                    sup_info["name"],
                    worker_names,
                    attached_name,
                    int(final_state.get("qc_score", 96)),
                    bool(final_state.get("reject_count", 0) > 0),
                    final_state["final_report"],
                )
                await event_queue.put({
                    "type": "ARCHIVE_SAVED",
                    "agentId": sup_info["id"],
                    "agentName": sup_info["name"],
                    "role": "SUPERVISOR",
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "payload": {"recordId": rec_id}
                })
        except Exception as e:
            await event_queue.put({
                "type": "MESSAGE", "agentId": "sup-mkt-01", "agentName": "시스템 안내", "role": "SUPERVISOR",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "payload": {"status": "REJECTED", "text": f"⚠️ 백엔드 실행 오류: {str(e)}"}
            })
        finally:
            await event_queue.put({"type": "STREAM_END"})

    async def sse_gen():
        task = asyncio.create_task(run_orchestration())
        try:
            while True:
                ev = await event_queue.get()
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                if ev.get("type") == "STREAM_END":
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(sse_gen(), media_type="text/event-stream")
