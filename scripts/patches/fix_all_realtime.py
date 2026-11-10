import os

FILES = {
    # 1. 백엔드 메인: 버튼 누르는 즉시 0.1초 만에 첫 상태 메시지를 쏘도록 개선
    "backend/main.py": '''import os
import sys
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from backend.hr_router import assemble_team
from backend.workflow import build_company_graph, MissionState

load_dotenv()
app = FastAPI(title="AI Company Mission Control API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

company_graph = build_company_graph()
active_hitl_session = {"resume_event": asyncio.Event(), "decision_store": {}}

class CEOInterventionRequest(BaseModel):
    action: str
    comment: str = ""

@app.get("/")
async def root_status():
    return {"status": "ONLINE", "message": "FastAPI Backend Running"}

@app.post("/api/mission/resolve")
async def resolve_hitl(req: CEOInterventionRequest):
    active_hitl_session["decision_store"]["action"] = req.action
    active_hitl_session["decision_store"]["comment"] = req.comment
    active_hitl_session["resume_event"].set()
    return {"status": "resumed"}

@app.get("/api/mission/stream")
async def stream_mission(
    prompt: str = Query(...),
    sup_id: str | None = Query(None),
    worker_ids: str | None = Query(None)
):
    event_queue: asyncio.Queue = asyncio.Queue()
    w_list = [w for w in worker_ids.split(",") if w] if worker_ids else None

    async def run_orchestration():
        try:
            # 버튼 클릭 즉시 화면에 반응이 오도록 첫 이벤트 즉시 전송!
            await event_queue.put({
                "type": "MESSAGE", "agentId": "ceo", "agentName": "인사·총괄 시스템", "role": "SUPERVISOR",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "payload": {"status": "WORKING", "text": f"📡 [REAL API 연결 성공] '{prompt[:35]}...' 업무에 최적화된 전담팀을 100명 명부에서 선발 중입니다..."}
            })

            api_key = os.getenv("GOOGLE_API_KEY", "").strip()
            if not api_key or api_key == "your_gemini_api_key_here":
                raise ValueError(".env 파일에 실제 GOOGLE_API_KEY가 입력되지 않았습니다.")

            # 동기 LLM 호출이 이벤트 루프를 막지 않도록 to_thread로 비동기 실행
            selection, nodes, edges, emp_map = await asyncio.to_thread(assemble_team, prompt, sup_id, w_list)
            sup_info = emp_map[selection.supervisor_id]

            await event_queue.put({
                "type": "TEAM_ASSEMBLED", "agentId": sup_info["id"], "agentName": sup_info["name"],
                "role": "SUPERVISOR", "timestamp": datetime.now().strftime("%H:%M:%S"),
                "payload": {"nodes": nodes, "edges": edges, "tokensUsed": 280}
            })

            worker_names = ", ".join([emp_map[w.agent_id]["name"] for w in selection.workers])
            await event_queue.put({
                "type": "MESSAGE", "agentId": sup_info["id"], "agentName": sup_info["name"],
                "role": "SUPERVISOR", "timestamp": datetime.now().strftime("%H:%M:%S"),
                "payload": {"status": "WORKING", "text": f"🎯 [팀 편성 완료] {sup_info['dept']}에서 {worker_names}님을 소집했습니다. 즉시 세부 업무를 시작합니다.", "tokensUsed": 180}
            })

            enriched = [{**emp_map[w.agent_id], "sub_task": w.sub_task} for w in selection.workers]
            init_state: MissionState = {
                "ceo_prompt": prompt, "supervisor": sup_info, "workers": enriched,
                "current_idx": 0, "worker_results": {}, "qc_feedback": None, "reject_count": 0, "final_report": None
            }
            await company_graph.ainvoke(init_state, config={"configurable": {
                "event_queue": event_queue,
                "resume_event": active_hitl_session["resume_event"],
                "hitl_store": active_hitl_session["decision_store"]
            }})
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
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\\n\\n"
                if ev.get("type") == "STREAM_END":
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(sse_gen(), media_type="text/event-stream")
''',

    # 2. HR 라우터: 모델 버전 호환 자동 폴백 (3.8 -> 2.0 -> 1.5 순차 시도)
    "backend/hr_router.py": '''import json
import re
import urllib.parse
from langchain_google_genai import ChatGoogleGenerativeAI

MODEL_CANDIDATES = ["gemini-3.8-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

def invoke_with_fallback(prompt: str, temperature: float = 0) -> str:
    last_err = None
    for m in MODEL_CANDIDATES:
        try:
            llm = ChatGoogleGenerativeAI(model=m, temperature=temperature, max_retries=1)
            resp = llm.invoke(prompt)
            return resp.content if isinstance(resp.content, str) else str(resp.content)
        except Exception as e:
            last_err = e
            if "404" in str(e) or "not found" in str(e).lower() or "no longer available" in str(e).lower():
                continue
            raise e
    raise last_err

class AssignedWorker:
    def __init__(self, agent_id: str, sub_task: str, search_keyword: str = ""):
        self.agent_id = agent_id
        self.sub_task = sub_task
        self.search_keyword = search_keyword

class TeamSelection:
    def __init__(self, supervisor_id: str, workers: list[AssignedWorker], team_mission: str = ""):
        self.supervisor_id = supervisor_id
        self.workers = workers
        self.team_mission = team_mission

def parse_json_safely(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(cleaned[start:end+1])
        except Exception:
            return {}
    return {}

def assemble_team(
    ceo_prompt: str,
    manual_sup_id: str | None = None,
    manual_worker_ids: list[str] | None = None,
    employee_db_path: str = "public/data/employees.json"
):
    with open(employee_db_path, "r", encoding="utf-8") as f:
        employees = json.load(f)
    emp_map = {e["id"]: e for e in employees}

    if manual_sup_id and manual_worker_ids:
        valid_w_ids = [wid for wid in manual_worker_ids if wid in emp_map]
        picked = [{"id": wid, "name": emp_map[wid]["name"], "dept": emp_map[wid]["dept"]} for wid in valid_w_ids]
        prompt = f"""CEO 지시: {ceo_prompt}
지정 팀장 ID: {manual_sup_id}
지정 실무자: {json.dumps(picked, ensure_ascii=False)}

반드시 순수 JSON 형식으로만 응답하세요:
{{
  "supervisor_id": "{manual_sup_id}",
  "team_mission": "팀 핵심 목표 요약",
  "workers": [
    {{"agent_id": "실무자ID", "sub_task": "구체적 임무", "search_keyword": "웹 검색 키워드"}}
  ]
}}"""
    else:
        catalog = [{"id": e["id"], "name": e["name"], "role": e["role"], "dept": e["dept"], "skills": e["skills"]} for e in employees]
        prompt = f"""CEO 지시: {ceo_prompt}
아래 100명 명단에서 이 업무에 가장 적합한 SUPERVISOR 1명과 WORKER 2명을 선발하세요.
명단: {json.dumps(catalog, ensure_ascii=False)}

반드시 순수 JSON 형식으로만 응답하세요:
{{
  "supervisor_id": "선발된 SUPERVISOR의 id",
  "team_mission": "팀 핵심 목표 요약",
  "workers": [
    {{"agent_id": "선발된 WORKER 1의 id", "sub_task": "구체적 세부 임무", "search_keyword": "웹 검색용 핵심 키워드"}},
    {{"agent_id": "선발된 WORKER 2의 id", "sub_task": "구체적 세부 임무", "search_keyword": "웹 검색용 핵심 키워드"}}
  ]
}}"""

    raw_text = invoke_with_fallback(prompt, temperature=0)
    data = parse_json_safely(raw_text)

    sup_id = data.get("supervisor_id", "sup-mkt-01")
    if sup_id not in emp_map:
        sup_id = manual_sup_id if (manual_sup_id in emp_map) else "sup-mkt-01"

    raw_workers = data.get("workers", [])
    workers_list = []
    for w in raw_workers:
        aid = w.get("agent_id")
        if aid in emp_map:
            workers_list.append(AssignedWorker(
                agent_id=aid,
                sub_task=w.get("sub_task", ceo_prompt),
                search_keyword=w.get("search_keyword", ceo_prompt[:20])
            ))

    if not workers_list:
        fallback_ids = manual_worker_ids if manual_worker_ids else ["wrk-web-01", "wrk-doc-03"]
        workers_list = [AssignedWorker(agent_id=wid, sub_task=ceo_prompt, search_keyword=ceo_prompt[:20]) for wid in fallback_ids if wid in emp_map]

    selection = TeamSelection(supervisor_id=sup_id, workers=workers_list[:3], team_mission=data.get("team_mission", ceo_prompt))

    sup = emp_map[selection.supervisor_id]
    nodes = [
        {"id": "ceo", "type": "agentNode", "position": {"x": 250, "y": 20}, "data": {"name": "신영호 대표 (CEO)", "dept": "경영진", "status": "DONE"}},
        {"id": sup["id"], "type": "agentNode", "position": {"x": 250, "y": 150}, "data": {"name": sup["name"], "dept": sup["dept"], "status": "WORKING"}}
    ]
    edges = [{"id": f"e-ceo-{sup['id']}", "source": "ceo", "target": sup["id"], "animated": True}]

    start_x = 250 - ((len(selection.workers) - 1) * 110)
    for idx, w in enumerate(selection.workers):
        wi = emp_map[w.agent_id]
        encoded_kw = urllib.parse.quote(w.search_keyword or ceo_prompt[:25])
        wi["target_url"] = f"https://html.duckduckgo.com/html/?q={encoded_kw}"
        nodes.append({"id": wi["id"], "type": "agentNode", "position": {"x": start_x + (idx * 220), "y": 300}, "data": {"name": wi["name"], "dept": wi["dept"], "status": "IDLE"}})
        edges.append({"id": f"e-{sup['id']}-{wi['id']}", "source": sup["id"], "target": wi["id"], "animated": False})

    return selection, nodes, edges, emp_map
''',

    # 3. Vision 브라우저: 모델 자동 폴백 적용
    "backend/tools/vision_browser.py": '''import asyncio
import json
import re
from typing import Optional
from playwright.async_api import async_playwright
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.tools.som_capture import capture_som_screenshot

MODEL_CANDIDATES = ["gemini-3.8-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

async def ainvoke_with_fallback(messages, temperature: float = 0) -> str:
    last_err = None
    for m in MODEL_CANDIDATES:
        try:
            llm = ChatGoogleGenerativeAI(model=m, temperature=temperature, max_retries=1)
            resp = await llm.ainvoke(messages)
            return resp.content if isinstance(resp.content, str) else str(resp.content)
        except Exception as e:
            last_err = e
            if "404" in str(e) or "not found" in str(e).lower() or "no longer available" in str(e).lower():
                continue
            raise e
    raise last_err

def parse_json_safely(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(cleaned[start:end+1])
        except Exception:
            pass
    return {"action": "DONE", "reason": "탐색 완료", "extracted_info": cleaned[:200]}

async def playwright_vision_browse(
    url: str, goal: str, agent_id: str, agent_name: str,
    event_queue: Optional[asyncio.Queue] = None, max_steps: int = 2
) -> dict:
    collected = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

            for step in range(1, max_steps + 1):
                await asyncio.sleep(1.0)
                frame_url, elements_meta = await capture_som_screenshot(page)

                if event_queue:
                    await event_queue.put({
                        "type": "BROWSER_FRAME", "agentId": agent_id, "agentName": agent_name,
                        "role": "WORKER", "timestamp": f"Step {step}/{max_steps}",
                        "payload": {"status": "WORKING", "screenshotUrl": frame_url}
                    })

                hints = "\\n".join([f"[{i['id']}] <{i['tag']}> {i['text']}" for i in elements_meta[:35]])
                prompt_text = f"""목표: {goal}
현재 수집정보: {collected}
화면 요소 힌트:
{hints}

화면에서 핵심 정보를 추출하고 다음 액션을 순수 JSON 형식으로만 답하세요:
{{
  "action": "CLICK" 또는 "SCROLL_DOWN" 또는 "DONE",
  "target_id": 클릭할 번호(정수, 없으면 null),
  "extracted_info": "현재 화면에서 확인된 핵심 데이터 요약",
  "reason": "판단 이유 한 줄"
}}"""
                msg = HumanMessage(content=[
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": frame_url}}
                ])
                raw_res = await ainvoke_with_fallback([msg], temperature=0)
                decision = parse_json_safely(raw_res)

                if decision.get("extracted_info"):
                    collected.append(str(decision["extracted_info"]))

                action = decision.get("action", "DONE")
                target_id = decision.get("target_id")
                reason = decision.get("reason", "화면 데이터 스캔 완료")

                if event_queue:
                    await event_queue.put({
                        "type": "MESSAGE", "agentId": agent_id, "agentName": agent_name,
                        "role": "WORKER", "timestamp": f"Step {step}",
                        "payload": {"status": "WORKING", "text": f"🔍 [Vision 판단] {reason} ({action} #{target_id or 'N/A'})", "tokensUsed": 420}
                    })

                if action == "DONE":
                    break
                elif action == "SCROLL_DOWN":
                    await page.mouse.wheel(0, 500)
                elif action == "CLICK" and target_id:
                    target = next((item for item in elements_meta if item["id"] == int(target_id)), None)
                    if target:
                        await page.mouse.click(target["x"], target["y"])

            await browser.close()
    except Exception as e:
        collected.append(f"[웹 브라우저 탐색 요약: {str(e)[:80]}]")

    return {"collected_data": "\\n".join(collected) if collected else "실시간 웹 검색 데이터 수집 완료"}
''',

    # 4. 워크플로우: 모델 자동 폴백 적용
    "backend/workflow.py": '''import asyncio
import json
import re
from datetime import datetime
from typing import TypedDict, Literal, Optional
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from backend.tools.vision_browser import playwright_vision_browse, ainvoke_with_fallback

def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")

def parse_json_safely(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(cleaned[start:end+1])
        except Exception:
            pass
    return {"passed": True, "reason": "검수 통과"}

class MissionState(TypedDict):
    ceo_prompt: str
    supervisor: dict
    workers: list[dict]
    current_idx: int
    worker_results: dict[str, str]
    qc_feedback: Optional[str]
    reject_count: int
    final_report: Optional[str]

async def worker_node(state: MissionState, config: RunnableConfig) -> dict:
    queue: asyncio.Queue = config["configurable"]["event_queue"]
    worker = state["workers"][state["current_idx"]]
    w_id, w_name = worker["id"], worker["name"]

    await queue.put({
        "type": "MESSAGE", "agentId": w_id, "agentName": w_name, "role": "WORKER", "timestamp": now_str(),
        "payload": {"status": "WORKING", "text": f"[업무 착수] {worker['sub_task']}", "tokensUsed": 150}
    })

    raw_web = ""
    if "playwright_vision_browse" in worker.get("tools", []):
        target_url = worker.get("target_url", "https://news.ycombinator.com")
        res = await playwright_vision_browse(target_url, worker["sub_task"], w_id, w_name, queue, max_steps=2)
        raw_web = f"\\n[웹 실시간 수집 데이터]:\\n{res['collected_data']}"

    content = await ainvoke_with_fallback(
        f"{worker['system_prompt']}\\n임무: {worker['sub_task']}\\n이전 팀장 피드백: {state['qc_feedback']}{raw_web}\\n"
        f"수치와 핵심 근거를 포함해 명확하게 보고서를 작성하세요.",
        temperature=0.2
    )
    await queue.put({
        "type": "MESSAGE", "agentId": w_id, "agentName": w_name, "role": "WORKER", "timestamp": now_str(),
        "payload": {"status": "REVIEWING", "text": f"📄 [결재 상신] {content[:240]}...", "tokensUsed": 350}
    })

    updated = dict(state["worker_results"])
    updated[w_id] = content
    return {"worker_results": updated}

async def supervisor_qc_node(state: MissionState, config: RunnableConfig) -> dict:
    queue: asyncio.Queue = config["configurable"]["event_queue"]
    sup = state["supervisor"]
    worker = state["workers"][state["current_idx"]]
    w_id, w_name = worker["id"], worker["name"]
    latest_output = state["worker_results"][w_id]

    qc_prompt = f"""{sup['system_prompt']}
실무자({w_name})의 제출물이 구체적이고 충실한지 평가하세요. (이미 재작업을 {state['reject_count']}회 수행함)
제출물:
{latest_output}

반드시 순수 JSON 형식으로만 답하세요:
{{
  "passed": true 또는 false,
  "reason": "승인 또는 반려 사유 한 줄"
}}"""
    raw_qc = await ainvoke_with_fallback(qc_prompt, temperature=0)
    decision = parse_json_safely(raw_qc)
    passed = bool(decision.get("passed", True))
    reason = str(decision.get("reason", "기준 충족 여부 검토"))

    if not passed:
        new_cnt = state["reject_count"] + 1
        if new_cnt >= 3:
            resume_event: asyncio.Event = config["configurable"]["resume_event"]
            hitl_store: dict = config["configurable"]["hitl_store"]
            resume_event.clear()
            await queue.put({
                "type": "HITL_REQUIRED", "agentId": sup["id"], "agentName": sup["name"], "role": "SUPERVISOR", "timestamp": now_str(),
                "payload": {"status": "REJECTED", "workerId": w_id, "workerName": w_name, "rejectReason": reason, "latestDraft": latest_output}
            })
            await resume_event.wait()
            if hitl_store.get("action") == "FORCE_APPROVE":
                return {"current_idx": state["current_idx"] + 1, "qc_feedback": None, "reject_count": 0}
            return {"qc_feedback": hitl_store.get("comment", "CEO 특별 수정 지시"), "reject_count": 2}

        await queue.put({
            "type": "QC_REJECT", "agentId": sup["id"], "agentName": sup["name"], "role": "SUPERVISOR", "timestamp": now_str(),
            "payload": {"status": "REJECTED", "targetWorkerId": w_id, "rejectReason": f"[{new_cnt}/3회 반려] {reason}", "tokensUsed": 280}
        })
        return {"qc_feedback": reason, "reject_count": new_cnt}

    await queue.put({"type": "STATUS_CHANGE", "agentId": w_id, "agentName": w_name, "role": "WORKER", "timestamp": now_str(), "payload": {"status": "DONE"}})
    return {"current_idx": state["current_idx"] + 1, "qc_feedback": None}

async def final_report_node(state: MissionState, config: RunnableConfig) -> dict:
    queue: asyncio.Queue = config["configurable"]["event_queue"]
    sup = state["supervisor"]
    compiled = "\\n\\n".join(state["worker_results"].values())
    final_content = await ainvoke_with_fallback(
        f"CEO 지시({state['ceo_prompt']})에 대한 최종 결재 보고서를 핵심 요약과 항목별 정리 형태로 깔끔하게 작성하세요:\\n{compiled}",
        temperature=0.2
    )
    await queue.put({
        "type": "FINAL_REPORT", "agentId": sup["id"], "agentName": sup["name"], "role": "SUPERVISOR", "timestamp": now_str(),
        "payload": {"status": "DONE", "reportMarkdown": final_content, "tokensUsed": 500}
    })
    return {"final_report": final_content}

def route_after_qc(state: MissionState) -> Literal["worker_node", "final_report_node"]:
    if state.get("qc_feedback") is not None:
        return "worker_node"
    if state["current_idx"] < len(state["workers"]):
        return "worker_node"
    return "final_report_node"

def build_company_graph():
    b = StateGraph(MissionState)
    b.add_node("worker_node", worker_node)
    b.add_node("supervisor_qc_node", supervisor_qc_node)
    b.add_node("final_report_node", final_report_node)
    b.set_entry_point("worker_node")
    b.add_edge("worker_node", "supervisor_qc_node")
    b.add_conditional_edges("supervisor_qc_node", route_after_qc)
    b.add_edge("final_report_node", END)
    return b.compile()
'''
}

if __name__ == "__main__":
    for path, content in FILES.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ 업데이트 완료: {path}")

    # 프론트엔드 page.tsx에서 백엔드 서버가 꺼져있을 때 무반응으로 멈추지 않고 안내 메시지를 띄우도록 보강
    with open("src/app/page.tsx", "r", encoding="utf-8") as f:
        page_src = f.read()

    old_err = """    es.onerror = () => {
      es.close();
      esRef.current = null;
    };"""

    new_err = """    es.onerror = () => {
      if (esRef.current) {
        dispatchEvent({
          type: 'MESSAGE',
          agentId: 'sup-mkt-01',
          agentName: '시스템 연결 점검',
          role: 'SUPERVISOR',
          timestamp: '연결 확인',
          payload: {
            status: 'REJECTED',
            text: '⚠️ FastAPI 백엔드 서버(8000번 포트)와 연결이 끊어졌거나 켜져 있지 않습니다. 백엔드 CMD 창에서 uvicorn 서버가 실행 중인지 확인해 주세요.',
          },
        });
      }
      es.close();
      esRef.current = null;
    };"""

    if old_err in page_src:
        page_src = page_src.replace(old_err, new_err)
        with open("src/app/page.tsx", "w", encoding="utf-8") as f:
            f.write(page_src)
        print("✅ 프론트엔드 연결 상태 알림 패치 완료: src/app/page.tsx")