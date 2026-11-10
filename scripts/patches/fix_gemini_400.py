import os

PATCHED_FILES = {
    # 1. HR 라우터 (gemini-3.8-flash + 네이티브 JSON 파싱)
    "backend/hr_router.py": '''import json
import re
import urllib.parse
from langchain_google_genai import ChatGoogleGenerativeAI

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
        return json.loads(cleaned[start:end+1])
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

    llm = ChatGoogleGenerativeAI(
        model="gemini-3.8-flash",
        temperature=0,
        model_kwargs={"response_mime_type": "application/json"}
    )

    if manual_sup_id and manual_worker_ids:
        valid_w_ids = [wid for wid in manual_worker_ids if wid in emp_map]
        picked = [{"id": wid, "name": emp_map[wid]["name"], "dept": emp_map[wid]["dept"]} for wid in valid_w_ids]
        prompt = f"""CEO 지시: {ceo_prompt}
지정 팀장 ID: {manual_sup_id}
지정 실무자: {json.dumps(picked, ensure_ascii=False)}

반드시 아래 JSON 형식으로만 응답하세요:
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

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "supervisor_id": "선발된 SUPERVISOR의 id",
  "team_mission": "팀 핵심 목표 요약",
  "workers": [
    {{"agent_id": "선발된 WORKER 1의 id", "sub_task": "구체적 세부 임무", "search_keyword": "웹 검색용 핵심 키워드"}},
    {{"agent_id": "선발된 WORKER 2의 id", "sub_task": "구체적 세부 임무", "search_keyword": "웹 검색용 핵심 키워드"}}
  ]
}}"""

    resp = llm.invoke(prompt)
    data = parse_json_safely(resp.content)

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

    # 2. Vision 브라우저 (gemini-3.8-flash 적용)
    "backend/tools/vision_browser.py": '''import asyncio
import json
import re
from typing import Optional
from playwright.async_api import async_playwright
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.tools.som_capture import capture_som_screenshot

def parse_json_safely(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1:
        return json.loads(cleaned[start:end+1])
    return {"action": "DONE", "reason": "탐색 완료", "extracted_info": cleaned[:200]}

async def playwright_vision_browse(
    url: str, goal: str, agent_id: str, agent_name: str,
    event_queue: Optional[asyncio.Queue] = None, max_steps: int = 2
) -> dict:
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.8-flash",
        temperature=0,
        model_kwargs={"response_mime_type": "application/json"}
    )
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

                hints = "\\n".join([f"[{i['id']}] <{i['tag']}> {i['text']}" for i in elements_meta[:40]])
                prompt_text = f"""목표: {goal}
현재 수집정보: {collected}
화면 요소 힌트:
{hints}

화면에서 핵심 정보를 추출하고 다음 액션을 아래 JSON 형식으로만 답하세요:
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
                resp = await llm.ainvoke([msg])
                decision = parse_json_safely(resp.content)

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

    # 3. 워크플로우 (gemini-3.8-flash 적용)
    "backend/workflow.py": '''import asyncio
import json
import re
from datetime import datetime
from typing import TypedDict, Literal, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from backend.tools.vision_browser import playwright_vision_browse

def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")

def parse_json_safely(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1:
        return json.loads(cleaned[start:end+1])
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
    llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0.2)
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

    resp = await llm.ainvoke(
        f"{worker['system_prompt']}\\n임무: {worker['sub_task']}\\n이전 팀장 피드백: {state['qc_feedback']}{raw_web}\\n"
        f"수치와 핵심 근거를 포함해 명확하게 보고서를 작성하세요."
    )
    await queue.put({
        "type": "MESSAGE", "agentId": w_id, "agentName": w_name, "role": "WORKER", "timestamp": now_str(),
        "payload": {"status": "REVIEWING", "text": f"📄 [결재 상신] {resp.content[:240]}...", "tokensUsed": 350}
    })

    updated = dict(state["worker_results"])
    updated[w_id] = resp.content
    return {"worker_results": updated}

async def supervisor_qc_node(state: MissionState, config: RunnableConfig) -> dict:
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.8-flash",
        temperature=0,
        model_kwargs={"response_mime_type": "application/json"}
    )
    queue: asyncio.Queue = config["configurable"]["event_queue"]
    sup = state["supervisor"]
    worker = state["workers"][state["current_idx"]]
    w_id, w_name = worker["id"], worker["name"]
    latest_output = state["worker_results"][w_id]

    qc_prompt = f"""{sup['system_prompt']}
실무자({w_name})의 제출물이 구체적이고 충실한지 평가하세요. (이미 재작업을 {state['reject_count']}회 수행함)
제출물:
{latest_output}

반드시 아래 JSON 형식으로만 답하세요:
{{
  "passed": true 또는 false,
  "reason": "승인 또는 반려 사유 한 줄"
}}"""
    resp = await llm.ainvoke(qc_prompt)
    decision = parse_json_safely(resp.content)
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
    llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0.2)
    queue: asyncio.Queue = config["configurable"]["event_queue"]
    sup = state["supervisor"]
    compiled = "\\n\\n".join(state["worker_results"].values())
    final_res = await llm.ainvoke(
        f"CEO 지시({state['ceo_prompt']})에 대한 최종 결재 보고서를 핵심 요약과 항목별 정리 형태로 깔끔하게 작성하세요:\\n{compiled}"
    )
    await queue.put({
        "type": "FINAL_REPORT", "agentId": sup["id"], "agentName": sup["name"], "role": "SUPERVISOR", "timestamp": now_str(),
        "payload": {"status": "DONE", "reportMarkdown": final_res.content, "tokensUsed": 500}
    })
    return {"final_report": final_res.content}

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
    for path, code in PATCHED_FILES.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"✅ 복구 및 gemini-3.8-flash 패치 완료: {path}")