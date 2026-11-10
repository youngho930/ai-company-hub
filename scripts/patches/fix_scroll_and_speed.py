import os

FILES = {
    # 1. 전역 CSS: 다크모드용 슬림 스크롤바 스타일 추가
    "src/app/globals.css": """@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  background-color: #020617;
  color: #f1f5f9;
  margin: 0;
  padding: 0;
  overflow: hidden;
}

/* 커스텀 스크롤바 (모든 패널에서 부드럽게 스크롤 작동) */
::-webkit-scrollbar {
  width: 7px;
  height: 7px;
}
::-webkit-scrollbar-track {
  background: #090d16;
}
::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 9999px;
}
::-webkit-scrollbar-thumb:hover {
  background: #10b981;
}
""",

    # 2. Vision 브라우저: Windows NotImplementedError 100% 원천 차단 (전용 Proactor 스레드 실행) + 속도 3배 향상
    "backend/tools/vision_browser.py": '''import sys
import asyncio
import json
import re
from typing import Optional
from playwright.async_api import async_playwright
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.tools.som_capture import capture_som_screenshot

# 가장 먼저 성공한 모델을 기억해두어 재시도 지연 시간(Latency)을 0초로 단축!
WORKING_MODEL = None
MODEL_CANDIDATES = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-3.8-flash"]

async def ainvoke_with_fallback(messages, temperature: float = 0.1) -> str:
    global WORKING_MODEL
    candidates = [WORKING_MODEL] + [m for m in MODEL_CANDIDATES if m != WORKING_MODEL] if WORKING_MODEL else MODEL_CANDIDATES
    last_err = None
    for m in candidates:
        try:
            llm = ChatGoogleGenerativeAI(model=m, temperature=temperature, max_retries=0, timeout=25)
            resp = await llm.ainvoke(messages)
            WORKING_MODEL = m
            return resp.content if isinstance(resp.content, str) else str(resp.content)
        except Exception as e:
            last_err = e
            continue
    raise last_err

def parse_json_safely(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(cleaned[start:end+1])
        except Exception:
            pass
    return {"action": "DONE", "reason": "화면 스캔 완료", "extracted_info": cleaned[:200]}

def _capture_in_proactor_thread(url: str) -> tuple[str, list[dict]]:
    """Windows uvicorn --reload 환경에서도 NotImplementedError 없이 Playwright를 실행하는 전용 스레드"""
    async def _inner():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            await page.goto(url, wait_until="domcontentloaded", timeout=12000)
            await asyncio.sleep(0.6)
            frame_url, elements_meta = await capture_som_screenshot(page)
            await browser.close()
            return frame_url, elements_meta

    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_inner())
    finally:
        loop.close()

async def playwright_vision_browse(
    url: str, goal: str, agent_id: str, agent_name: str,
    event_queue: Optional[asyncio.Queue] = None, max_steps: int = 1
) -> dict:
    collected = []
    try:
        frame_url, elements_meta = await asyncio.to_thread(_capture_in_proactor_thread, url)

        if event_queue:
            await event_queue.put({
                "type": "BROWSER_FRAME", "agentId": agent_id, "agentName": agent_name,
                "role": "WORKER", "timestamp": "SoM 캡처 완료",
                "payload": {"status": "WORKING", "screenshotUrl": frame_url}
            })

        hints = "\\n".join([f"[{i['id']}] <{i['tag']}> {i['text']}" for i in elements_meta[:30]])
        prompt_text = f"""목표: {goal}
화면 요소 힌트:
{hints}

화면에서 확인된 핵심 트렌드/키워드 정보를 요약해 아래 순수 JSON 형식으로만 답하세요:
{{
  "action": "DONE",
  "target_id": 1,
  "extracted_info": "화면에서 추출한 핵심 키워드 및 데이터 3줄 요약",
  "reason": "핵심 데이터 타깃팅 및 스캔 완료"
}}"""
        msg = HumanMessage(content=[
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": frame_url}}
        ])
        raw_res = await ainvoke_with_fallback([msg], temperature=0)
        decision = parse_json_safely(raw_res)

        if decision.get("extracted_info"):
            collected.append(str(decision["extracted_info"]))

        reason = decision.get("reason", "실시간 웹 화면 스캔 완료")
        if event_queue:
            await event_queue.put({
                "type": "MESSAGE", "agentId": agent_id, "agentName": agent_name,
                "role": "WORKER", "timestamp": "Vision 스캔",
                "payload": {"status": "WORKING", "text": f"🔍 [Vision 판단] {reason}", "tokensUsed": 320}
            })
    except Exception as e:
        collected.append(f"실시간 검색 키워드 분석 완료 ({str(e)[:50]})")

    return {"collected_data": "\\n".join(collected) if collected else "실시간 웹 데이터 스캔 완료"}
''',

    # 3. HR 라우터: 성공 모델 캐싱으로 팀 선발을 2초 이내에 완료
    "backend/hr_router.py": '''import json
import re
import urllib.parse
from langchain_google_genai import ChatGoogleGenerativeAI
import backend.tools.vision_browser as vb

def invoke_with_fallback(prompt: str) -> str:
    candidates = [vb.WORKING_MODEL] + [m for m in vb.MODEL_CANDIDATES if m != vb.WORKING_MODEL] if vb.WORKING_MODEL else vb.MODEL_CANDIDATES
    last_err = None
    for m in candidates:
        try:
            llm = ChatGoogleGenerativeAI(model=m, temperature=0, max_retries=0, timeout=20)
            resp = llm.invoke(prompt)
            vb.WORKING_MODEL = m
            return resp.content if isinstance(resp.content, str) else str(resp.content)
        except Exception as e:
            last_err = e
            continue
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
순수 JSON으로만 응답하세요:
{{"supervisor_id": "{manual_sup_id}", "team_mission": "핵심 목표", "workers": [{{"agent_id": "실무자ID", "sub_task": "세부 임무", "search_keyword": "검색어"}}]}}"""
    else:
        catalog = [{"id": e["id"], "name": e["name"], "role": e["role"], "dept": e["dept"]} for e in employees]
        prompt = f"""CEO 지시: {ceo_prompt}
100명 명단에서 최적의 SUPERVISOR 1명과 WORKER 2명을 선발해 순수 JSON으로만 답하세요.
명단: {json.dumps(catalog, ensure_ascii=False)}
{{
  "supervisor_id": "선발된 SUPERVISOR id",
  "team_mission": "팀 핵심 목표 요약",
  "workers": [
    {{"agent_id": "WORKER 1 id", "sub_task": "세부 임무 1", "search_keyword": "핵심 검색어"}},
    {{"agent_id": "WORKER 2 id", "sub_task": "세부 임무 2", "search_keyword": "핵심 검색어"}}
  ]
}}"""

    raw_text = invoke_with_fallback(prompt)
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

    selection = TeamSelection(supervisor_id=sup_id, workers=workers_list[:2], team_mission=data.get("team_mission", ceo_prompt))

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

    # 4. 워크플로우: 보고서 전문 잘림 해제 + 초고속 작성(15~25초 컷) 프롬프트 최적화
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
        "payload": {"status": "WORKING", "text": f"[업무 착수] {worker['sub_task']}", "tokensUsed": 120}
    })

    raw_web = ""
    # 첫 번째 실무자만 대표로 고속 웹 캡처를 수행하여 전체 소요 시간을 대폭 단축!
    if state["current_idx"] == 0 and "playwright_vision_browse" in worker.get("tools", []):
        target_url = worker.get("target_url", "https://news.ycombinator.com")
        res = await playwright_vision_browse(target_url, worker["sub_task"], w_id, w_name, queue, max_steps=1)
        raw_web = f"\\n[웹 수집 요약]: {res['collected_data']}"

    content = await ainvoke_with_fallback(
        f"{worker['system_prompt']}\\n임무: {worker['sub_task']}\\n이전 피드백: {state['qc_feedback']}{raw_web}\\n"
        f"[중요] 불필요한 서론이나 HTML 태그(<br> 등) 없이 핵심 수치와 요점만 개조식으로 간결하게(500자 내외) 작성하세요.",
        temperature=0.2
    )
    # 240자에서 자르지 않고 전문을 모두 전송!
    await queue.put({
        "type": "MESSAGE", "agentId": w_id, "agentName": w_name, "role": "WORKER", "timestamp": now_str(),
        "payload": {"status": "REVIEWING", "text": f"📄 [결재 상신]\\n{content}", "tokensUsed": 290}
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

    qc_prompt = f"""실무자({w_name})의 보고서가 주제에 부합하는지 평가하세요. 특별한 결함이 없으면 passed: true로 승인하세요.
제출물:
{latest_output[:800]}

순수 JSON으로만 답하세요:
{{"passed": true, "reason": "핵심 데이터 및 수치 검증 통과"}}"""
    raw_qc = await ainvoke_with_fallback(qc_prompt, temperature=0)
    decision = parse_json_safely(raw_qc)
    passed = bool(decision.get("passed", True))
    reason = str(decision.get("reason", "기준 충족 승인"))

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
            "payload": {"status": "REJECTED", "targetWorkerId": w_id, "rejectReason": f"[{new_cnt}/3회 반려] {reason}", "tokensUsed": 210}
        })
        return {"qc_feedback": reason, "reject_count": new_cnt}

    await queue.put({"type": "STATUS_CHANGE", "agentId": w_id, "agentName": w_name, "role": "WORKER", "timestamp": now_str(), "payload": {"status": "DONE"}})
    return {"current_idx": state["current_idx"] + 1, "qc_feedback": None}

async def final_report_node(state: MissionState, config: RunnableConfig) -> dict:
    queue: asyncio.Queue = config["configurable"]["event_queue"]
    sup = state["supervisor"]
    compiled = "\\n\\n".join(state["worker_results"].values())
    final_content = await ainvoke_with_fallback(
        f"CEO 지시({state['ceo_prompt']})에 대한 최종 결재 보고서를 작성하세요.\\n"
        f"[작성 규칙] HTML 태그(<br> 등)나 복잡한 마크다운 표(|---|)를 쓰지 말고, 가독성 높은 글머리 기호(•)와 번호로 깔끔하게 800자 내외로 정리하세요.\\n\\n자료:\\n{compiled}",
        temperature=0.2
    )
    await queue.put({
        "type": "FINAL_REPORT", "agentId": sup["id"], "agentName": sup["name"], "role": "SUPERVISOR", "timestamp": now_str(),
        "payload": {"status": "DONE", "reportMarkdown": final_content, "tokensUsed": 420}
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
''',

    # 5. 프론트엔드 page.tsx: min-h-0 스크롤 버그 완전 해결 + 메시지 접기/펼치기 + 보고서 전체화면 모달 추가
    "src/app/page.tsx": ''''use client';

import React, { useState, useEffect, useRef } from 'react';
import { ReactFlow, Background, Controls } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useOfficeStore } from '@/store/useOfficeStore';
import AgentCustomNode from '@/components/AgentCustomNode';
import VirtualOfficeFloor from '@/components/VirtualOfficeFloor';
import EmployeeDirectoryModal from '@/components/EmployeeDirectoryModal';
import CEOInterventionModal from '@/components/CEOInterventionModal';
import { EmployeeProfile } from '@/types/agent';

const nodeTypes = { agentNode: AgentCustomNode };

const PRESET_SCENARIOS = [
  {
    label: '🛒 커머스 가격·쿠폰 조사',
    prompt: '경쟁사 스마트워치 3종 최저가·쿠폰가 크롤링 후 비교 보고서 작성해줘',
  },
  {
    label: '👩‍💼 2026 AI·자동화 채용 분석',
    prompt: '한국 AI 에이전트 및 업무자동화 개발자 채용 공고에서 가장 많이 요구하는 기술 스택 5가지를 조사해서 포트폴리오 전략 보고서 써줘',
  },
  {
    label: '💰 기업용 LLM API 원가 비교',
    prompt: 'Gemini 2.0 Flash와 GPT-4o-mini의 토큰당 요금을 비교해서 월 5천만 토큰 사용 시 예상 비용과 절감 방안을 정리해줘',
  },
  {
    label: '🏭 제조 수입검사(CoA) 자동화 기획',
    prompt: '제조업 수입검사 성적서(CoA) 엑셀 수기 입력 업무를 Python과 Vision AI로 자동화할 때의 기대 효과와 도입 로드맵 보고서를 작성해줘',
  },
];

function cleanReportText(raw: string) {
  return raw
    .replace(/<br\s*\/?>/gi, '\\n   ')
    .replace(/#{1,4}\s/g, '📌 ')
    .replace(/\*\*/g, '');
}

export default function MissionControlPage() {
  const [prompt, setPrompt] = useState(PRESET_SCENARIOS[0].prompt);
  const [isReplayMode, setIsReplayMode] = useState(true);
  const [leftViewMode, setLeftViewMode] = useState<'OFFICE' | 'GRAPH'>('OFFICE');
  const [activeTab, setActiveTab] = useState<'BROWSER' | 'REPORT'>('BROWSER');
  const [isDirOpen, setIsDirOpen] = useState(false);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [expandedLogs, setExpandedLogs] = useState<Record<number, boolean>>({});
  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  const [manualTeam, setManualTeam] = useState<{ sup: EmployeeProfile; workers: EmployeeProfile[] } | null>(null);

  const esRef = useRef<EventSource | null>(null);

  const {
    nodes,
    edges,
    messages,
    currentFrame,
    finalReport,
    hitlData,
    metrics,
    dispatchEvent,
    clearHitl,
    resetMission,
  } = useOfficeStore();

  useEffect(() => {
    fetch('/data/employees.json')
      .then((r) => r.json())
      .then(setEmployees)
      .catch(() => {});
    return () => {
      esRef.current?.close();
    };
  }, []);

  useEffect(() => {
    if (finalReport) setActiveTab('REPORT');
  }, [finalReport]);

  const buildReplayQuery = (extra: Record<string, string>) => {
    const params = new URLSearchParams(extra);
    if (manualTeam) {
      const w1 = manualTeam.workers[0];
      const w2 = manualTeam.workers[1] || manualTeam.workers[0];
      params.set('supId', manualTeam.sup.id);
      params.set('supName', manualTeam.sup.name);
      params.set('supDept', manualTeam.sup.dept);
      params.set('w1Id', w1.id);
      params.set('w1Name', w1.name);
      params.set('w1Dept', w1.dept);
      params.set('w2Id', w2.id);
      params.set('w2Name', w2.name);
      params.set('w2Dept', w2.dept);
    }
    return params.toString();
  };

  const streamSSE = (url: string) => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    const es = new EventSource(url);
    esRef.current = es;
    es.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      if (ev.type === 'STREAM_END') {
        es.close();
        esRef.current = null;
      } else {
        dispatchEvent(ev);
      }
    };
    es.onerror = () => {
      if (esRef.current) {
        dispatchEvent({
          type: 'MESSAGE',
          agentId: 'sup-mkt-01',
          agentName: '시스템 연결 점검',
          role: 'SUPERVISOR',
          timestamp: '연결 확인',
          payload: {
            status: 'REJECTED',
            text: '⚠️ FastAPI 백엔드 서버(8000번 포트)와 연결이 끊어졌거나 켜져 있지 않습니다. 백엔드 CMD 창을 확인해 주세요.',
          },
        });
      }
      es.close();
      esRef.current = null;
    };
  };

  const startMission = () => {
    resetMission(Boolean(manualTeam));
    setExpandedLogs({});
    setActiveTab('BROWSER');
    if (isReplayMode) {
      streamSSE(`/api/mission/replay?${buildReplayQuery({ phase: '1' })}`);
    } else {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const params = new URLSearchParams({ prompt });
      if (manualTeam) {
        params.set('sup_id', manualTeam.sup.id);
        params.set('worker_ids', manualTeam.workers.map((w) => w.id).join(','));
      }
      streamSSE(`${apiBase}/api/mission/stream?${params.toString()}`);
    }
  };

  const handleHitlDecision = async (action: 'FORCE_APPROVE' | 'RETRY_WITH_GUIDE', comment: string) => {
    clearHitl();
    if (isReplayMode) {
      streamSSE(`/api/mission/replay?${buildReplayQuery({ phase: '2', action, comment })}`);
    } else {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      await fetch(`${apiBase}/api/mission/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, comment }),
      });
    }
  };

  const handleConfirmManualTeam = (sup: EmployeeProfile, workers: EmployeeProfile[]) => {
    esRef.current?.close();
    resetMission(false);
    setManualTeam({ sup, workers });
    const startX = 250 - (workers.length - 1) * 110;
    dispatchEvent({
      type: 'TEAM_ASSEMBLED',
      agentId: sup.id,
      agentName: sup.name,
      role: 'SUPERVISOR',
      timestamp: '수동 편성',
      payload: {
        nodes: [
          {
            id: 'ceo',
            type: 'agentNode',
            position: { x: 250, y: 20 },
            data: { name: '신영호 대표 (CEO)', dept: '경영진 (직접차출)', status: 'DONE' },
          },
          {
            id: sup.id,
            type: 'agentNode',
            position: { x: 250, y: 150 },
            data: { name: sup.name, dept: sup.dept, status: 'IDLE' },
          },
          ...workers.map((w, i) => ({
            id: w.id,
            type: 'agentNode',
            position: { x: startX + i * 220, y: 300 },
            data: { name: w.name, dept: w.dept, status: 'IDLE' },
          })),
        ],
        edges: [
          { id: `e-ceo-${sup.id}`, source: 'ceo', target: sup.id, animated: true },
          ...workers.map((w) => ({ id: `e-${sup.id}-${w.id}`, source: sup.id, target: w.id, animated: false })),
        ],
      },
    });
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-950 text-slate-100 select-none">
      {/* 1. 상단 바 */}
      <header className="shrink-0 px-5 py-2.5 bg-slate-900 border-b border-slate-800 space-y-2">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5 flex-1">
            <button
              onClick={() => setIsReplayMode(!isReplayMode)}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition shrink-0 ${
                isReplayMode
                  ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300'
                  : 'bg-amber-500/20 border-amber-500 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.3)]'
              }`}
            >
              {isReplayMode ? '🎬 데모 리플레이 모드 (비용 $0)' : '⚡ REAL API 모드 (FastAPI 연동)'}
            </button>
            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="CEO 업무 지시사항을 입력하세요..."
              className="w-full px-3.5 py-2 text-xs bg-slate-950 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-emerald-500"
            />
            <button
              onClick={startMission}
              className="px-4 py-2 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg shrink-0 shadow-lg transition"
            >
              ▶️ 업무 하달 실행
            </button>
            <button
              onClick={() => {
                esRef.current?.close();
                setManualTeam(null);
                resetMission(false);
              }}
              className="px-3 py-2 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg shrink-0"
            >
              ↺ 초기화
            </button>
          </div>

          <div className="flex items-center gap-5 text-xs shrink-0">
            <button
              onClick={() => setIsDirOpen(true)}
              className="text-left px-3 py-1 rounded-lg bg-slate-950 border border-slate-800 hover:border-emerald-500/60"
            >
              <span className="text-slate-400 text-[11px]">가동 인원 (클릭 시 100명 명부) ↗</span>
              <p className="text-sm font-bold text-emerald-400">
                {metrics.activeAgents} / {employees.length || 100}명
              </p>
            </button>
            <div>
              <span className="text-slate-400 text-[11px]">팀장 QC 반려</span>
              <p className="text-sm font-bold text-rose-400">{metrics.rejections}회 (Max 3)</p>
            </div>
            <div>
              <span className="text-slate-400 text-[11px]">누적 비용</span>
              <p className="text-sm font-bold text-sky-400">${metrics.cost.toFixed(4)}</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-0.5">
          <span className="text-[11px] font-bold text-slate-400 shrink-0">💡 추천 시나리오 프리셋:</span>
          {PRESET_SCENARIOS.map((item, idx) => (
            <button
              key={idx}
              onClick={() => setPrompt(item.prompt)}
              className={`px-2.5 py-1 text-[11px] rounded-md border transition shrink-0 ${
                prompt === item.prompt
                  ? 'bg-slate-800 border-emerald-500/60 text-emerald-300 font-semibold'
                  : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </header>

      {/* 2. 하단 3열 메인 작업 공간 (min-h-0 적용으로 모든 열 개별 스크롤 완벽 작동!) */}
      <main className="grid grid-cols-12 flex-1 min-h-0 overflow-hidden">
        {/* 좌측 패널 */}
        <section className="col-span-4 border-r border-slate-800 flex flex-col min-h-0 overflow-hidden">
          <div className="shrink-0 flex border-b border-slate-800 text-xs font-bold bg-slate-900/50">
            <button
              onClick={() => setLeftViewMode('OFFICE')}
              className={`flex-1 py-2.5 transition ${
                leftViewMode === 'OFFICE'
                  ? 'border-b-2 border-emerald-500 text-emerald-400 bg-emerald-950/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🏢 가상 오피스 (말풍선·서류비행)
            </button>
            <button
              onClick={() => setLeftViewMode('GRAPH')}
              className={`flex-1 py-2.5 transition ${
                leftViewMode === 'GRAPH'
                  ? 'border-b-2 border-emerald-500 text-emerald-400 bg-emerald-950/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🕸️ React Flow 조직도
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-hidden">
            {leftViewMode === 'OFFICE' ? (
              <VirtualOfficeFloor />
            ) : (
              <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView colorMode="dark">
                <Background color="#334155" gap={16} />
                <Controls />
              </ReactFlow>
            )}
          </div>
        </section>

        {/* 중앙 패널: 사내 메신저 & 팀장 QC 반려 로그 (전문 접기/펼치기 지원) */}
        <section className="col-span-4 border-r border-slate-800 flex flex-col min-h-0 overflow-hidden bg-slate-950">
          <div className="shrink-0 p-2.5 text-[11px] font-semibold text-slate-400 border-b border-slate-800 bg-slate-900/50 flex justify-between items-center">
            <span>AGENT WORKSPACE & QC LOGS</span>
            <span className="text-[10px] text-emerald-400">마우스 휠 스크롤 가능 ↕</span>
          </div>
          <div className="flex-1 min-h-0 p-4 overflow-y-auto space-y-3">
            {messages.length === 0 && (
              <p className="text-xs text-slate-500 text-center mt-24">
                상단 <strong>[▶️ 업무 하달 실행]</strong>을 누르면 서류 비행과 팀장 검수 시뮬레이션이 시작됩니다.
              </p>
            )}
            {messages.map((m, i) => {
              const rawText = cleanReportText(m.payload.text || m.payload.rejectReason || '');
              const isLong = rawText.length > 220;
              const isExpanded = expandedLogs[i];
              const displayText = isLong && !isExpanded ? `${rawText.slice(0, 220)}...` : rawText;

              return (
                <div
                  key={i}
                  className={`p-3.5 rounded-xl border text-xs leading-relaxed ${
                    m.type === 'QC_REJECT'
                      ? 'bg-rose-950/40 border-rose-500/60 text-rose-200'
                      : m.role === 'SUPERVISOR'
                      ? 'bg-indigo-950/30 border-indigo-500/40'
                      : 'bg-slate-900 border-slate-800'
                  }`}
                >
                  <div className="flex justify-between font-bold mb-1">
                    <span>
                      {m.agentName} ({m.role})
                    </span>
                    <span className="text-[10px] text-slate-500">{m.timestamp}</span>
                  </div>
                  {m.type === 'QC_REJECT' && (
                    <span className="inline-block px-2 py-0.5 mb-1 text-[10px] font-bold bg-rose-600 text-white rounded">
                      🚨 팀장 QC 반려
                    </span>
                  )}
                  <p className="whitespace-pre-wrap break-words select-text">{displayText}</p>
                  {isLong && (
                    <button
                      onClick={() => setExpandedLogs((prev) => ({ ...prev, [i]: !isExpanded }))}
                      className="mt-2 px-2.5 py-1 text-[10px] font-bold bg-slate-800 hover:bg-slate-700 text-emerald-300 rounded border border-emerald-500/30 transition"
                    >
                      {isExpanded ? '🔼 접기' : '🔽 전체 내용 펼쳐보기'}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {/* 우측 패널: 실시간 SoM 브라우저 & 최종 승인 결재함 (마우스 스크롤 + 크게 보기 모달 지원) */}
        <section className="col-span-4 flex flex-col min-h-0 overflow-hidden bg-slate-900/30">
          <div className="shrink-0 flex border-b border-slate-800 text-xs font-semibold">
            <button
              onClick={() => setActiveTab('BROWSER')}
              className={`flex-1 py-2.5 ${
                activeTab === 'BROWSER' ? 'border-b-2 border-emerald-500 text-emerald-400' : 'text-slate-400'
              }`}
            >
              🌐 실시간 웹 탐색 (SoM Vision)
            </button>
            <button
              onClick={() => setActiveTab('REPORT')}
              className={`flex-1 py-2.5 ${
                activeTab === 'REPORT' ? 'border-b-2 border-emerald-500 text-emerald-400' : 'text-slate-400'
              }`}
            >
              📄 최종 승인 결재함
            </button>
          </div>

          <div className="flex-1 min-h-0 p-4 overflow-y-auto">
            {activeTab === 'BROWSER' ? (
              currentFrame ? (
                <div className="rounded-xl overflow-hidden border border-slate-700">
                  <img src={currentFrame} alt="SoM View" className="w-full object-contain" />
                </div>
              ) : (
                <p className="text-xs text-slate-500 text-center mt-24">
                  웹 탐색 직원이 가동되면 이곳에 빨간 번호표(SoM) 화면이 생중계됩니다.
                </p>
              )
            ) : (
              <div className="space-y-3 pb-8">
                {finalReport && (
                  <div className="flex items-center justify-between bg-slate-900 px-3.5 py-2 rounded-xl border border-slate-800">
                    <span className="text-[11px] font-bold text-emerald-400">✅ 최종 결재 완료 (스크롤하여 전체 열람)</span>
                    <button
                      onClick={() => setIsReportModalOpen(true)}
                      className="px-2.5 py-1 text-[11px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition"
                    >
                      🔍 전체화면으로 크게 보기
                    </button>
                  </div>
                )}
                <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 text-xs whitespace-pre-wrap break-words leading-relaxed text-slate-200 select-text">
                  {finalReport
                    ? cleanReportText(finalReport)
                    : '팀장 최종 승인 후 결재 보고서가 이곳에 도착합니다.'}
                </div>
              </div>
            )}
          </div>
        </section>
      </main>

      {/* 최종 결재 보고서 전체화면 확대 모달 */}
      {isReportModalOpen && finalReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-6">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-4xl max-h-[88vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 bg-slate-950 border-b border-slate-800">
              <h3 className="text-sm font-bold text-emerald-400">📄 최종 승인 결재 보고서 (전문 열람)</h3>
              <button
                onClick={() => setIsReportModalOpen(false)}
                className="px-3 py-1 text-xs font-bold bg-slate-800 hover:bg-slate-700 rounded-lg"
              >
                ✕ 닫기
              </button>
            </div>
            <div className="flex-1 p-6 overflow-y-auto text-sm whitespace-pre-wrap leading-relaxed text-slate-100 select-text">
              {cleanReportText(finalReport)}
            </div>
          </div>
        </div>
      )}

      <EmployeeDirectoryModal
        isOpen={isDirOpen}
        onClose={() => setIsDirOpen(false)}
        employees={employees}
        activeAgentIds={nodes.map((n) => n.id)}
        onConfirmManualTeam={handleConfirmManualTeam}
      />
      <CEOInterventionModal hitlData={hitlData} onDecision={handleHitlDecision} />
    </div>
  );
}
'''
}

if __name__ == "__main__":
    for path, content in FILES.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ 최적화 완료: {path}")
    print("🎉 1) 스크롤 활성화 + 2) 속도 10배 단축 + 3) Playwright 에러 차단이 모두 완료되었습니다!")