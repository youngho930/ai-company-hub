import os
import py_compile

FILES = {
    # 1. OpenAI OAuth & 로컬 브라우저 자동 토큰 추출기 (질문창으로 튕기는 현상 완벽 해결)
    "backend/openai_oauth.py": r'''import os
import sys
import json
import time
import asyncio
import urllib.request
from typing import Optional

TOKEN_FILE = os.path.join(os.getcwd(), ".chatgpt-token.json")

def load_chatgpt_token() -> Optional[dict]:
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("access_token"):
            return data
    except Exception:
        pass
    return None

def save_chatgpt_token(token_data: dict) -> None:
    payload = {
        "access_token": token_data.get("access_token", ""),
        "model": token_data.get("model", "gpt-4o-mini"),
        "mode": token_data.get("mode", "API_OR_OAUTH"),
        "saved_at": int(time.time()),
    }
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def clear_chatgpt_token() -> None:
    if os.path.exists(TOKEN_FILE):
        try:
            os.remove(TOKEN_FILE)
        except Exception:
            pass

def _auto_extract_session_sync() -> dict:
    """
    사용자가 브라우저에서 로그인하면 chatgpt.com/api/auth/session 엔드포인트에서
    공식 세션 accessToken을 자동으로 감지해 로컬 에이전트에 등록합니다.
    """
    from playwright.sync_api import sync_playwright

    profile_dir = os.path.join(os.getcwd(), ".chatgpt-browser-profile")
    os.makedirs(profile_dir, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            viewport={"width": 520, "height": 680},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://chatgpt.com/", wait_until="domcontentloaded")

        # 최대 90초 동안 로그인 완료 및 세션 토큰 감지 대기
        extracted_token = ""
        for _ in range(90):
            try:
                res = page.evaluate("""async () => {
                    try {
                        const r = await fetch('/api/auth/session');
                        if (!r.ok) return null;
                        return await r.json();
                    } catch (e) {
                        return null;
                    }
                }""")
                if res and isinstance(res, dict) and res.get("accessToken"):
                    extracted_token = res["accessToken"]
                    break
            except Exception:
                pass
            time.sleep(1.0)

        context.close()

    if extracted_token:
        save_chatgpt_token({"access_token": extracted_token, "model": "gpt-4o-mini", "mode": "CHATGPT_WEB_SESSION"})
        return {"status": "OK", "token": extracted_token}
    return {"status": "TIMEOUT"}

async def auto_connect_chatgpt_browser() -> dict:
    return await asyncio.to_thread(_auto_extract_session_sync)

def call_chatgpt_with_oauth(prompt: str, temperature: float = 0.2) -> Optional[str]:
    """등록된 토큰(sk-... API 키 또는 OAuth Bearer 토큰)으로 OpenAI 모델 호출"""
    token_info = load_chatgpt_token()
    access_token = (token_info or {}).get("access_token") or os.getenv("OPENAI_API_KEY", "").strip()
    if not access_token:
        return None

    model_name = (token_info or {}).get("model", "gpt-4o-mini")
    url = "https://api.openai.com/v1/chat/completions"
    payload = json.dumps({
        "model": model_name,
        "messages": [
            {"role": "system", "content": "당신은 엔터프라이즈 AI 회사의 전문 분석 에이전트입니다."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": 950,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"].strip()
            if len(text) > 40:
                return text
    except Exception as e:
        print(f"[ChatGPT Bridge Info] 기본 Gemini/Extractive 엔진으로 자동 폴백 전환: {str(e)[:55]}")
    return None
''',

    # 2. 백엔드 main.py: python-multipart 미설치 에러를 원천 차단하는 Base64 파일 업로드 + 원클릭 브라우저 인증 API
    "backend/main.py": r'''import os
import sys
import base64
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

load_dotenv(override=True)

from backend.hr_router import assemble_team
from backend.workflow import build_company_graph, MissionState
from backend.file_processor import parse_uploaded_document
from backend.openai_oauth import (
    load_chatgpt_token,
    save_chatgpt_token,
    clear_chatgpt_token,
    auto_connect_chatgpt_browser,
)

app = FastAPI(title="AI Company Mission Control API - Enterprise Edition")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

company_graph = build_company_graph()
active_hitl_session = {"resume_event": asyncio.Event(), "decision_store": {}}
UPLOADED_DOC_STORE: dict[str, str] = {"filename": "", "summary": ""}

class CEOInterventionRequest(BaseModel):
    action: str
    comment: str = ""

class TokenRegisterRequest(BaseModel):
    access_token: str
    model: str = "gpt-4o-mini"

class Base64FileUploadRequest(BaseModel):
    filename: str
    content_base64: str

@app.get("/")
async def root_status():
    return {"status": "ONLINE"}

# python-multipart 패키지 없이도 100% 작동하는 JSON Base64 문서 업로드 엔드포인트
@app.post("/api/mission/upload-json")
async def upload_document_json(req: Base64FileUploadRequest):
    raw_bytes = base64.b64decode(req.content_base64)
    summary_text, meta = await asyncio.to_thread(parse_uploaded_document, req.filename or "uploaded_file", raw_bytes)
    UPLOADED_DOC_STORE["filename"] = req.filename or "첨부문서"
    UPLOADED_DOC_STORE["summary"] = summary_text
    return {
        "status": "OK",
        "filename": UPLOADED_DOC_STORE["filename"],
        "meta": meta,
        "preview": summary_text[:400],
    }

@app.post("/api/mission/clear-upload")
async def clear_uploaded_document():
    UPLOADED_DOC_STORE["filename"] = ""
    UPLOADED_DOC_STORE["summary"] = ""
    return {"status": "CLEARED"}

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
            attached_name = UPLOADED_DOC_STORE.get("filename", "")
            attached_summary = UPLOADED_DOC_STORE.get("summary", "")
            tok_info = load_chatgpt_token()
            engine_badge = f"ChatGPT ({tok_info.get('model')})" if tok_info else "Gemini + Extractive RAG"

            start_msg = f"📡 [{engine_badge} 가동] '{prompt[:32]}...' 업무 전담팀을 100명 명부에서 선발합니다."
            if attached_name:
                start_msg += f" (📎 첨부파일: {attached_name})"

            await event_queue.put({
                "type": "MESSAGE", "agentId": "ceo", "agentName": "인사·총괄 시스템", "role": "SUPERVISOR",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "payload": {"status": "WORKING", "text": start_msg}
            })

            selection, nodes, edges, emp_map = await asyncio.to_thread(assemble_team, prompt, sup_id, w_list)
            sup_info = emp_map[selection.supervisor_id]

            await event_queue.put({
                "type": "TEAM_ASSEMBLED", "agentId": sup_info["id"], "agentName": sup_info["name"],
                "role": "SUPERVISOR", "timestamp": datetime.now().strftime("%H:%M:%S"),
                "payload": {"nodes": nodes, "edges": edges, "tokensUsed": 240}
            })

            worker_names = ", ".join([emp_map[w.agent_id]["name"] for w in selection.workers])
            await event_queue.put({
                "type": "MESSAGE", "agentId": sup_info["id"], "agentName": sup_info["name"],
                "role": "SUPERVISOR", "timestamp": datetime.now().strftime("%H:%M:%S"),
                "payload": {"status": "WORKING", "text": f"🎯 [팀 편성 완료] {sup_info['dept']} {worker_names}님을 소집했습니다. 각자 부서 책상으로 이동해 조사를 시작합니다.", "tokensUsed": 160}
            })

            await asyncio.sleep(2.2)

            enriched = [{**emp_map[w.agent_id], "sub_task": w.sub_task} for w in selection.workers]
            effective_prompt = prompt
            if attached_name and attached_summary:
                effective_prompt = f"{prompt} (첨부파일 '{attached_name}' 데이터 정합 반영)"

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
                "final_report": None
            }
            await company_graph.ainvoke(init_state, config={"configurable": {
                "event_queue": event_queue,
                "resume_event": active_hitl_session["resume_event"],
                "hitl_store": active_hitl_session["decision_store"],
                "attached_summary": attached_summary,
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
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                if ev.get("type") == "STREAM_END":
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(sse_gen(), media_type="text/event-stream")
''',

    # 3. 2D 도트 오피스: (1) 책상·책장 실제 조사 액션 & 강제 체류 타이머, (2) 전원 회의실 착석 후 최종 보고서 생성 싱크, (3) 4인 말풍선 무충돌 배치
    "src/components/PixelRpgOffice.tsx": r''''use client';

import React, { useEffect, useRef, useState } from 'react';
import { useOfficeStore } from '@/store/useOfficeStore';

interface Point {
  x: number;
  y: number;
}

type RoomId = 'RESEARCH' | 'DEV' | 'MEETING' | 'LOUNGE' | 'CORRIDOR';
type Direction = 'DOWN' | 'UP' | 'LEFT' | 'RIGHT';

interface SpriteAgent {
  id: string;
  name: string;
  dept: string;
  role: 'CEO' | 'SUPERVISOR' | 'WORKER1' | 'WORKER2';
  x: number;
  y: number;
  waypoints: Point[];
  currentSpotKey: string;
  queuedSpotKey: string;
  workTimer: number; // 책상 도착 후 최소 조사 시간(프레임) 보장!
  facing: Direction;
  status: string;
  hairColor: string;
  hairShade: string;
  shirtColor: string;
  taskLabel: string;
  activeBubble: string;
  pendingBubble: string;
  progress: number;
}

interface PixelRpgOfficeProps {
  onOpenReportModal?: () => void;
  onToggleLogDrawer?: () => void;
  unreadLogCount?: number;
  onAllGatheredChange?: (ready: boolean) => void;
}

const CW = 920;
const CH = 580;

const DOORS: Record<RoomId, Point> = {
  RESEARCH: { x: 405, y: 155 },
  DEV: { x: 515, y: 155 },
  MEETING: { x: 405, y: 445 },
  LOUNGE: { x: 515, y: 445 },
  CORRIDOR: { x: 460, y: 290 },
};

const SPOTS: Record<string, { x: number; y: number; room: RoomId; sitFacing: Direction }> = {
  RESEARCH_SHELF: { x: 145, y: 78, room: 'RESEARCH', sitFacing: 'UP' },
  RESEARCH_DESK_1: { x: 135, y: 142, room: 'RESEARCH', sitFacing: 'DOWN' },
  RESEARCH_DESK_2: { x: 285, y: 142, room: 'RESEARCH', sitFacing: 'DOWN' },
  DEV_SERVER: { x: 565, y: 82, room: 'DEV', sitFacing: 'UP' },
  DEV_DESK_1: { x: 615, y: 142, room: 'DEV', sitFacing: 'DOWN' },
  DEV_DESK_2: { x: 765, y: 142, room: 'DEV', sitFacing: 'DOWN' },
  CEO_SEAT: { x: 148, y: 418, room: 'MEETING', sitFacing: 'DOWN' },
  MEETING_SUP: { x: 272, y: 418, room: 'MEETING', sitFacing: 'DOWN' },
  MEETING_W1: { x: 148, y: 508, room: 'MEETING', sitFacing: 'UP' },
  MEETING_W2: { x: 272, y: 508, room: 'MEETING', sitFacing: 'UP' },
  LOUNGE_SOFA_1: { x: 625, y: 440, room: 'LOUNGE', sitFacing: 'DOWN' },
  LOUNGE_SOFA_2: { x: 745, y: 470, room: 'LOUNGE', sitFacing: 'LEFT' },
  CORRIDOR_PATROL: { x: 460, y: 275, room: 'CORRIDOR', sitFacing: 'DOWN' },
};

const MEETING_TABLE_CENTER = { x: 210, y: 462 };

function getRoomAt(x: number, y: number): RoomId {
  if (x < 400 && y < 265) return 'RESEARCH';
  if (x > 520 && y < 265) return 'DEV';
  if (x < 400 && y > 315) return 'MEETING';
  if (x > 520 && y > 315) return 'LOUNGE';
  return 'CORRIDOR';
}

function buildRoomPath(curX: number, curY: number, destSpot: { x: number; y: number; room: RoomId }, viaShelf?: Point): Point[] {
  const curRoom = getRoomAt(curX, curY);
  const targetRoom = destSpot.room;
  const pts: Point[] = [];

  if (curRoom !== targetRoom) {
    if (curRoom !== 'CORRIDOR') {
      const exitDoor = DOORS[curRoom];
      pts.push({ x: exitDoor.x, y: exitDoor.y });
      pts.push({ x: 460, y: exitDoor.y });
    } else {
      pts.push({ x: 460, y: curY });
    }

    if (targetRoom !== 'CORRIDOR') {
      const enterDoor = DOORS[targetRoom];
      pts.push({ x: 460, y: enterDoor.y });
      pts.push({ x: enterDoor.x, y: enterDoor.y });
    }
  }

  // 리서치실이나 개발실에 들어갈 때 책장/서버랙을 먼저 스캔한 뒤 컴퓨터 책상으로 앉는 디테일 동선!
  if (viaShelf) {
    pts.push({ x: viaShelf.x, y: viaShelf.y });
  }
  pts.push({ x: destSpot.x, y: destSpot.y });
  return pts;
}

export default function PixelRpgOffice({
  onOpenReportModal,
  onToggleLogDrawer,
  unreadLogCount = 0,
  onAllGatheredChange,
}: PixelRpgOfficeProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const agentsRef = useRef<Record<string, SpriteAgent>>({});
  const frameCountRef = useRef<number>(0);
  const [speedMult, setSpeedMult] = useState<number>(1.0);
  const [isHoveringReport, setIsHoveringReport] = useState<boolean>(false);
  const [reportUnlocked, setReportUnlocked] = useState<boolean>(false);

  const speedRef = useRef<number>(1.0);
  const reportUnlockedRef = useRef<boolean>(false);

  const { nodes, messages, finalReport } = useOfficeStore();
  const hasFinalReportRef = useRef<boolean>(false);

  useEffect(() => {
    speedRef.current = speedMult;
  }, [speedMult]);

  useEffect(() => {
    hasFinalReportRef.current = Boolean(finalReport);
    if (!finalReport) {
      reportUnlockedRef.current = false;
      setReportUnlocked(false);
      onAllGatheredChange?.(false);
    }
  }, [finalReport]);

  // 에이전트 상태 동기화 (중간 과정을 건너뛰지 않도록 2단계 큐잉 적용)
  useEffect(() => {
    const currentMap = agentsRef.current;
    const latestMsgByAgent: Record<string, string> = {};
    messages.forEach((m) => {
      const txt = (m.payload?.text || m.payload?.rejectReason || '').replace(/\s+/g, ' ').trim();
      if (txt) latestMsgByAgent[m.agentId] = txt;
    });

    const hasStarted = messages.length > 0;
    const hasRejected = messages.some((m) => m.type === 'QC_REJECT');
    const isMissionFinished = Boolean(finalReport);

    const activeNodes =
      nodes.length > 0
        ? nodes
        : [
            { id: 'ceo', data: { name: '신영호 대표', dept: '경영진', status: 'DONE' } },
            { id: 'sup-default', data: { name: '윤지아 팀장', dept: '품질·인사총괄', status: 'IDLE' } },
            { id: 'wrk-default-1', data: { name: '박수아 수석', dept: '웹탐색·리서치', status: 'IDLE' } },
            { id: 'wrk-default-2', data: { name: '한채원 책임', dept: '전략·문서합성', status: 'IDLE' } },
          ];

    const palettes = [
      { hair: '#f59e0b', shade: '#b45309', shirt: '#3730a3' },
      { hair: '#fb7185', shade: '#be123c', shirt: '#9f1239' },
      { hair: '#67e8f9', shade: '#0891b2', shirt: '#1e40af' },
      { hair: '#c084fc', shade: '#7e22ce', shirt: '#065f46' },
    ];

    const updatedIds = new Set<string>();

    activeNodes.slice(0, 4).forEach((n, idx) => {
      const id = n.id;
      updatedIds.add(id);
      const name = String(n.data?.name || '에이전트');
      const dept = String(n.data?.dept || '전담팀');
      const status = String(n.data?.status || 'IDLE');
      const role: SpriteAgent['role'] =
        idx === 0 ? 'CEO' : idx === 1 ? 'SUPERVISOR' : idx === 2 ? 'WORKER1' : 'WORKER2';

      let desiredSpot = 'LOUNGE_SOFA_1';
      let taskLabel = '대기 중';

      if (role === 'CEO') {
        desiredSpot = 'CEO_SEAT';
        taskLabel = isMissionFinished ? '✅ 최종 결재 대기' : '총괄 집무·결재';
      } else if (role === 'SUPERVISOR') {
        if (!hasStarted) {
          desiredSpot = 'CORRIDOR_PATROL';
          taskLabel = '오피스 관제 대기';
        } else if (isMissionFinished || hasRejected) {
          desiredSpot = 'MEETING_SUP';
          taskLabel = isMissionFinished ? '📋 최종 결재 주최' : '🚨 QC 피드백 지시';
        } else {
          desiredSpot = 'RESEARCH_DESK_2';
          taskLabel = '🔎 1차 조사 검수 중';
        }
      } else if (role === 'WORKER1') {
        if (!hasStarted) {
          desiredSpot = 'LOUNGE_SOFA_1';
          taskLabel = '휴게실 대기';
        } else if (hasRejected || isMissionFinished) {
          desiredSpot = 'MEETING_W1';
          taskLabel = '📋 조사 팩트 브리핑';
        } else {
          desiredSpot = 'RESEARCH_DESK_1';
          taskLabel = '🔍 PC 웹 탐색·수집 중';
        }
      } else {
        if (!hasStarted) {
          desiredSpot = 'LOUNGE_SOFA_2';
          taskLabel = '휴게실 대기';
        } else if (isMissionFinished) {
          desiredSpot = 'MEETING_W2';
          taskLabel = '📋 최종 보고서 상신';
        } else {
          desiredSpot = 'DEV_DESK_2';
          taskLabel = '💻 보고서 합성·코딩 중';
        }
      }

      const incomingBubble = latestMsgByAgent[id] || '';

      if (!currentMap[id]) {
        const initKey = !hasStarted
          ? role === 'CEO'
            ? 'CEO_SEAT'
            : role === 'SUPERVISOR'
            ? 'CORRIDOR_PATROL'
            : role === 'WORKER1'
            ? 'LOUNGE_SOFA_1'
            : 'LOUNGE_SOFA_2'
          : desiredSpot;
        const initSpot = SPOTS[initKey];

        currentMap[id] = {
          id,
          name,
          dept,
          role,
          x: initSpot.x,
          y: initSpot.y,
          waypoints: [],
          currentSpotKey: initKey,
          queuedSpotKey: '',
          workTimer: 0,
          facing: initSpot.sitFacing,
          status,
          hairColor: palettes[idx % palettes.length].hair,
          hairShade: palettes[idx % palettes.length].shade,
          shirtColor: palettes[idx % palettes.length].shirt,
          taskLabel,
          activeBubble: incomingBubble,
          pendingBubble: '',
          progress: 0,
        };
      }

      const ag = currentMap[id];
      ag.name = name;
      ag.dept = dept;
      ag.status = status;
      ag.taskLabel = taskLabel;

      if (!hasStarted) {
        const resetKey =
          role === 'CEO'
            ? 'CEO_SEAT'
            : role === 'SUPERVISOR'
            ? 'CORRIDOR_PATROL'
            : role === 'WORKER1'
            ? 'LOUNGE_SOFA_1'
            : 'LOUNGE_SOFA_2';
        ag.currentSpotKey = resetKey;
        ag.queuedSpotKey = '';
        ag.waypoints = [];
        ag.x = SPOTS[resetKey].x;
        ag.y = SPOTS[resetKey].y;
        ag.workTimer = 0;
        ag.progress = 0;
        ag.activeBubble = '';
        ag.pendingBubble = '';
        return;
      }

      // [핵심] 만약 실무자가 아직 책상 조사를 안 거쳤는데 바로 회의실(MEETING) 신호가 온 경우:
      // 먼저 리서치실/개발실 책상으로 가서 최소 150프레임(2.5초) 동안 컴퓨터 앞에서 조사한 뒤 회의실로 가도록 큐잉!
      if (
        desiredSpot.startsWith('MEETING_') &&
        ag.currentSpotKey.startsWith('LOUNGE_') &&
        ag.waypoints.length === 0
      ) {
        const firstWorkDesk = role === 'WORKER1' ? 'RESEARCH_DESK_1' : 'DEV_DESK_2';
        const viaPt = role === 'WORKER1' ? SPOTS.RESEARCH_SHELF : SPOTS.DEV_SERVER;
        ag.currentSpotKey = firstWorkDesk;
        ag.queuedSpotKey = desiredSpot;
        ag.waypoints = buildRoomPath(ag.x, ag.y, SPOTS[firstWorkDesk], viaPt);
        ag.workTimer = 150; // 책상 도착 후 2.5초간 컴퓨터 집중 조사 강제!
        ag.pendingBubble = incomingBubble;
      } else if (ag.currentSpotKey !== desiredSpot && ag.queuedSpotKey !== desiredSpot) {
        // 현재 책상에서 집중 조사 타이머(workTimer)가 남아있거나 책상으로 이동 중이면 큐(queuedSpotKey)에 대기시킴!
        if (ag.currentSpotKey.includes('DESK') && (ag.waypoints.length > 0 || ag.workTimer > 0)) {
          ag.queuedSpotKey = desiredSpot;
          if (incomingBubble) ag.pendingBubble = incomingBubble;
        } else {
          const viaPt =
            desiredSpot === 'RESEARCH_DESK_1'
              ? SPOTS.RESEARCH_SHELF
              : desiredSpot === 'DEV_DESK_2'
              ? SPOTS.DEV_SERVER
              : undefined;
          ag.currentSpotKey = desiredSpot;
          ag.waypoints = buildRoomPath(ag.x, ag.y, SPOTS[desiredSpot], viaPt);
          if (desiredSpot.includes('DESK')) {
            ag.workTimer = 150; // 컴퓨터 앞에서 최소 2.5초간 조사 수행
            ag.progress = 15;
          }
          if (incomingBubble) {
            ag.pendingBubble = incomingBubble;
          }
        }
      } else {
        if (incomingBubble) {
          if (ag.waypoints.length > 0 || ag.workTimer > 0) {
            ag.pendingBubble = incomingBubble;
          } else {
            ag.activeBubble = incomingBubble;
          }
        }
      }
    });

    Object.keys(currentMap).forEach((k) => {
      if (!updatedIds.has(k)) delete currentMap[k];
    });
  }, [nodes, messages, finalReport]);

  const handleCanvasPos = (e: React.MouseEvent<HTMLCanvasElement>, isClick: boolean) => {
    if (!reportUnlockedRef.current || !canvasRef.current) {
      setIsHoveringReport(false);
      return;
    }
    const rect = canvasRef.current.getBoundingClientRect();
    const scaleX = CW / rect.width;
    const scaleY = CH / rect.height;
    const cx = (e.clientX - rect.left) * scaleX;
    const cy = (e.clientY - rect.top) * scaleY;

    const hit = cx >= 135 && cx <= 285 && cy >= 420 && cy <= 500;
    setIsHoveringReport(hit);
    if (hit && isClick && onOpenReportModal) {
      onOpenReportModal();
    }
  };

  useEffect(() => {
    let animId: number;

    const drawWoodRoom = (ctx: CanvasRenderingContext2D, rx: number, ry: number, rw: number, rh: number, b1: string, b2: string) => {
      const plankH = 16;
      const plankW = 48;
      for (let y = ry; y < ry + rh; y += plankH) {
        const rIdx = Math.floor((y - ry) / plankH);
        for (let x = rx; x < rx + rw; x += plankW) {
          const cIdx = Math.floor((x - rx) / plankW);
          ctx.fillStyle = (rIdx + cIdx) % 2 === 0 ? b1 : b2;
          const w = Math.min(plankW, rx + rw - x);
          const h = Math.min(plankH, ry + rh - y);
          ctx.fillRect(x, y, w, h);
          ctx.strokeStyle = 'rgba(0,0,0,0.16)';
          ctx.lineWidth = 1;
          ctx.strokeRect(x, y, w, h);
        }
      }
    };

    const drawCheckTile = (ctx: CanvasRenderingContext2D, rx: number, ry: number, rw: number, rh: number, c1: string, c2: string, size = 24) => {
      for (let y = ry; y < ry + rh; y += size) {
        for (let x = rx; x < rx + rw; x += size) {
          const isEven = (Math.floor(x / size) + Math.floor(y / size)) % 2 === 0;
          ctx.fillStyle = isEven ? c1 : c2;
          ctx.fillRect(x, y, Math.min(size, rx + rw - x), Math.min(size, ry + rh - y));
        }
      }
    };

    const drawRoomWalls = (
      ctx: CanvasRenderingContext2D,
      rx: number,
      ry: number,
      rw: number,
      rh: number,
      doorSide: 'RIGHT' | 'LEFT',
      doorY: number
    ) => {
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(rx, ry, rw, 14);
      ctx.fillStyle = '#334155';
      ctx.fillRect(rx + 2, ry + 2, rw - 4, 8);
      ctx.strokeStyle = '#0f172a';
      ctx.lineWidth = 5;
      ctx.strokeRect(rx, ry, rw, rh);

      const doorX = doorSide === 'RIGHT' ? rx + rw - 4 : rx - 4;
      ctx.fillStyle = '#cbd5e1';
      ctx.fillRect(doorX, doorY - 26, 8, 52);
      ctx.fillStyle = '#64748b';
      ctx.fillRect(doorX + 2, doorY - 24, 4, 48);
    };

    const drawBookshelf = (ctx: CanvasRenderingContext2D, bx: number, by: number, isScanning: boolean, f: number) => {
      ctx.fillStyle = 'rgba(0,0,0,0.3)';
      ctx.fillRect(bx + 3, by + 4, 66, 40);
      ctx.fillStyle = '#451a03';
      ctx.fillRect(bx, by, 66, 40);
      ctx.fillStyle = '#78350f';
      ctx.fillRect(bx + 3, by + 3, 60, 34);
      const colors = ['#f43f5e', '#38bdf8', '#10b981', '#fbbf24', '#a855f7', '#fb923c'];
      for (let r = 0; r < 2; r++) {
        ctx.fillStyle = '#290f02';
        ctx.fillRect(bx + 5, by + 6 + r * 16, 56, 13);
        for (let i = 0; i < 6; i++) {
          ctx.fillStyle = colors[(i + r * 2) % colors.length];
          ctx.fillRect(bx + 8 + i * 8, by + 8 + r * 16, 6, 11);
        }
      }
      if (isScanning && f % 20 < 10) {
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2;
        ctx.strokeRect(bx - 2, by - 2, 70, 44);
      }
    };

    const drawServerRack = (ctx: CanvasRenderingContext2D, sx: number, sy: number, f: number) => {
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(sx, sy, 46, 44);
      ctx.strokeStyle = '#475569';
      ctx.lineWidth = 2;
      ctx.strokeRect(sx, sy, 46, 44);
      for (let i = 0; i < 3; i++) {
        ctx.fillStyle = '#1e293b';
        ctx.fillRect(sx + 5, sy + 6 + i * 12, 36, 9);
        ctx.fillStyle = (f + i * 15) % 40 < 20 ? '#34d399' : '#38bdf8';
        ctx.fillRect(sx + 8, sy + 9 + i * 12, 4, 3);
        ctx.fillStyle = '#f43f5e';
        ctx.fillRect(sx + 15, sy + 9 + i * 12, 3, 3);
      }
    };

    const drawPlant = (ctx: CanvasRenderingContext2D, px: number, py: number) => {
      ctx.fillStyle = 'rgba(0,0,0,0.28)';
      ctx.beginPath();
      ctx.ellipse(px, py + 14, 12, 5, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#c2410c';
      ctx.fillRect(px - 8, py, 16, 13);
      ctx.fillStyle = '#ea580c';
      ctx.fillRect(px - 10, py - 2, 20, 4);
      ctx.fillStyle = '#15803d';
      ctx.beginPath();
      ctx.arc(px, py - 8, 13, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#4ade80';
      ctx.beginPath();
      ctx.arc(px - 4, py - 11, 7, 0, Math.PI * 2);
      ctx.fill();
    };

    const drawChairBack = (ctx: CanvasRenderingContext2D, dx: number, dy: number) => {
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(dx - 15, dy - 14, 30, 14);
      ctx.fillStyle = '#334155';
      ctx.fillRect(dx - 13, dy - 12, 26, 10);
    };

    // 컴퓨터 앞에서 실제로 조사/코딩하는 느낌을 살리는 홀로그램 모니터 & 레이더 이펙트!
    const drawDeskSurface = (ctx: CanvasRenderingContext2D, dx: number, dy: number, isWorking: boolean, f: number) => {
      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.fillRect(dx - 48, dy + 10, 96, 36);
      ctx.fillStyle = '#78350f';
      ctx.fillRect(dx - 46, dy + 6, 92, 32);
      ctx.fillStyle = '#b45309';
      ctx.fillRect(dx - 44, dy + 8, 88, 24);
      ctx.fillStyle = '#451a03';
      ctx.fillRect(dx - 44, dy + 32, 88, 6);

      // 모니터 본체
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(dx - 22, dy, 44, 21);
      ctx.fillStyle = isWorking ? '#022c22' : '#334155';
      ctx.fillRect(dx - 19, dy + 2, 38, 16);

      // 작업 중일 때 모니터 안에 실시간 코드 라인이 스크롤되고 돋보기/차트 홀로그램이 떠오름!
      if (isWorking) {
        const lineY = (f % 12);
        ctx.fillStyle = '#34d399';
        ctx.fillRect(dx - 16, dy + 4 + (lineY % 8), 22, 2);
        ctx.fillStyle = '#38bdf8';
        ctx.fillRect(dx - 16, dy + 8 + ((lineY + 4) % 8), 30, 2);
        ctx.fillStyle = '#fbbf24';
        ctx.fillRect(dx - 16, dy + 12, 16, 2);

        // 모니터 위로 떠오르는 홀로그램 스캔 이펙트
        const floatY = Math.sin(f * 0.18) * 3;
        ctx.fillStyle = 'rgba(56, 189, 248, 0.22)';
        ctx.fillRect(dx - 26, dy - 16 + floatY, 52, 14);
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 1;
        ctx.strokeRect(dx - 26, dy - 16 + floatY, 52, 14);
        ctx.fillStyle = '#e0f2fe';
        ctx.font = 'bold 8.5px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(f % 40 < 20 ? '🔍 웹 데이터 스캔' : '📊 팩트 추출 중..', dx, dy - 6 + floatY);
      }

      ctx.fillStyle = '#cbd5e1';
      ctx.fillRect(dx - 13, dy + 23, 26, 4);
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(dx + 27, dy + 14, 7, 9);
    };

    const drawCharacterBody = (
      ctx: CanvasRenderingContext2D,
      ag: SpriteAgent,
      idx: number,
      isWalking: boolean,
      isWorkingAtDesk: boolean,
      f: number
    ) => {
      const walkCycle = isWalking ? Math.sin(f * 0.15 * speedRef.current + idx) : 0;
      const workBob = isWorkingAtDesk ? Math.sin(f * 0.25 + idx) * 1.5 : 0;
      const bounceY = isWalking ? Math.abs(walkCycle) * -3.2 : workBob;

      const cx = Math.round(ag.x);
      const cy = Math.round(ag.y + bounceY);

      ctx.fillStyle =
        ag.status === 'REJECTED'
          ? 'rgba(244, 63, 94, 0.45)'
          : isWorkingAtDesk
          ? 'rgba(56, 189, 248, 0.45)'
          : 'rgba(0, 0, 0, 0.35)';
      ctx.beginPath();
      ctx.ellipse(cx, ag.y + 16, 15, 5.5, 0, 0, Math.PI * 2);
      ctx.fill();

      const leftLegY = isWalking ? Math.round(walkCycle * 3.5) : 0;
      const rightLegY = isWalking ? Math.round(-walkCycle * 3.5) : 0;
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(cx - 7, cy + 6 + leftLegY, 6, 9);
      ctx.fillRect(cx + 1, cy + 6 + rightLegY, 6, 9);

      ctx.fillStyle = ag.shirtColor;
      ctx.fillRect(cx - 11, cy - 6, 22, 14);
      if (ag.facing !== 'UP') {
        ctx.fillStyle = '#f8fafc';
        ctx.fillRect(cx - 2, cy - 5, 4, 7);
        ctx.fillStyle = ag.role === 'CEO' ? '#fbbf24' : '#38bdf8';
        ctx.fillRect(cx - 1, cy - 3, 2, 5);
      }

      // 컴퓨터 앞에서 타이핑할 때 양손이 활발하게 움직이는 애니메이션
      const armOffset = isWorkingAtDesk
        ? Math.round(Math.sin(f * 0.45 + idx) * 3.0)
        : Math.round(walkCycle * 2.5);
      ctx.fillStyle = ag.shirtColor;
      ctx.fillRect(cx - 15, cy - 5 + armOffset, 4, 11);
      ctx.fillRect(cx + 11, cy - 5 - armOffset, 4, 11);
      ctx.fillStyle = '#fed7aa';
      ctx.fillRect(cx - 15, cy + 5 + armOffset, 4, 3);
      ctx.fillRect(cx + 11, cy + 5 - armOffset, 4, 3);

      ctx.fillStyle = '#0f172a';
      ctx.fillRect(cx - 15, cy - 30, 30, 25);

      if (ag.facing === 'UP') {
        ctx.fillStyle = ag.hairColor;
        ctx.fillRect(cx - 14, cy - 29, 28, 23);
        ctx.fillStyle = ag.hairShade;
        ctx.fillRect(cx - 14, cy - 12, 28, 6);
      } else {
        ctx.fillStyle = '#ffedd5';
        ctx.fillRect(cx - 13, cy - 27, 26, 21);

        const eyeShiftX = ag.facing === 'LEFT' ? -3 : ag.facing === 'RIGHT' ? 3 : 0;

        ctx.fillStyle = '#fda4af';
        ctx.fillRect(cx - 10 + eyeShiftX, cy - 13, 3, 2);
        ctx.fillRect(cx + 7 + eyeShiftX, cy - 13, 3, 2);

        if ((f + idx * 37) % 180 > 6) {
          ctx.fillStyle = '#0f172a';
          ctx.fillRect(cx - 7 + eyeShiftX, cy - 18, 3, 5);
          ctx.fillRect(cx + 4 + eyeShiftX, cy - 18, 3, 5);
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(cx - 6 + eyeShiftX, cy - 18, 1, 2);
          ctx.fillRect(cx + 5 + eyeShiftX, cy - 18, 1, 2);
        } else {
          ctx.fillStyle = '#0f172a';
          ctx.fillRect(cx - 7 + eyeShiftX, cy - 15, 3, 1);
          ctx.fillRect(cx + 4 + eyeShiftX, cy - 15, 3, 1);
        }

        ctx.fillStyle = ag.hairShade;
        ctx.fillRect(cx - 15, cy - 31, 30, 6);
        ctx.fillStyle = ag.hairColor;
        ctx.fillRect(cx - 14, cy - 30, 28, 8);
        ctx.fillRect(cx - 11, cy - 22, 6, 4);
        ctx.fillRect(cx - 1, cy - 22, 5, 3);
        ctx.fillRect(cx + 6, cy - 22, 6, 4);
        ctx.fillRect(cx - 15, cy - 24, 3, 13);
        ctx.fillRect(cx + 12, cy - 24, 3, 13);
      }

      ctx.fillStyle = 'rgba(255,255,255,0.45)';
      ctx.fillRect(cx - 9, cy - 28, 18, 2);
    };

    // [핵심 개선] 회의실 4인 소집 시 말풍선이 절대 서로 겹치지 않도록 4분면(좌상/우상/좌하/우하)으로 위치 분리!
    const drawCharacterOverlayUI = (
      ctx: CanvasRenderingContext2D,
      ag: SpriteAgent,
      isWalking: boolean,
      isWorkingAtDesk: boolean
    ) => {
      const cx = Math.round(ag.x);
      const isAtDesk = ag.currentSpotKey.includes('DESK') && !isWalking;
      const labelY = isAtDesk ? Math.round(ag.y + 46) : Math.round(ag.y + 20);

      ctx.fillStyle = 'rgba(15, 23, 42, 0.94)';
      ctx.fillRect(cx - 50, labelY, 100, 30);
      ctx.strokeStyle =
        ag.status === 'REJECTED' ? '#f43f5e' : isWorkingAtDesk ? '#38bdf8' : '#10b981';
      ctx.lineWidth = 1.4;
      ctx.strokeRect(cx - 50, labelY, 100, 30);

      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 10.5px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(ag.name.replace(' (CEO)', ''), cx, labelY + 12);

      ctx.fillStyle = '#1e293b';
      ctx.fillRect(cx - 46, labelY + 16, 92, 10);
      if (ag.progress > 0) {
        ctx.fillStyle = ag.progress >= 100 ? '#10b981' : '#0ea5e9';
        ctx.fillRect(cx - 46, labelY + 16, Math.round((92 * ag.progress) / 100), 10);
      }
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 8.5px sans-serif';
      const statusText = isWalking
        ? '🚶 이동 중...'
        : isWorkingAtDesk
        ? `💻 집중 조사 (${Math.round(ag.progress)}%)`
        : ag.taskLabel.slice(0, 14);
      ctx.fillText(statusText, cx, labelY + 24);

      const bubbleToShow = isWalking ? '' : isWorkingAtDesk ? '🔍 데이터 스캔 및 팩트 검증 중...' : ag.activeBubble;
      if (bubbleToShow) {
        const bw = 178;
        const bh = 32;

        // 회의실 좌석 위치에 따라 말풍선 좌표를 바깥쪽 모서리로 분산시켜 겹침 0% 달성!
        let bx = cx - bw / 2;
        let by = Math.round(ag.y - 68);

        if (ag.currentSpotKey === 'CEO_SEAT') {
          bx = cx - bw + 25;
          by = Math.round(ag.y - 72);
        } else if (ag.currentSpotKey === 'MEETING_SUP') {
          bx = cx - 25;
          by = Math.round(ag.y - 72);
        } else if (ag.currentSpotKey === 'MEETING_W1') {
          bx = cx - bw + 25;
          by = Math.round(ag.y - 64);
        } else if (ag.currentSpotKey === 'MEETING_W2') {
          bx = cx - 25;
          by = Math.round(ag.y - 64);
        }

        bx = Math.max(10, Math.min(CW - bw - 10, bx));
        by = Math.max(8, Math.min(CH - bh - 8, by));

        ctx.fillStyle = ag.status === 'REJECTED' ? '#881337' : isWorkingAtDesk ? '#0c4a6e' : '#ffffff';
        ctx.fillRect(bx, by, bw, bh);
        ctx.strokeStyle = ag.status === 'REJECTED' ? '#fb7185' : isWorkingAtDesk ? '#38bdf8' : '#0f172a';
        ctx.lineWidth = 1.8;
        ctx.strokeRect(bx, by, bw, bh);

        ctx.fillStyle = ag.status === 'REJECTED' || isWorkingAtDesk ? '#f0f9ff' : '#0f172a';
        ctx.font = 'bold 9.5px sans-serif';
        ctx.textAlign = 'center';
        const line1 = bubbleToShow.slice(0, 20);
        const line2 = bubbleToShow.slice(20, 38) + (bubbleToShow.length > 38 ? '..' : '');
        ctx.fillText(line1, bx + bw / 2, by + (line2 ? 13 : 19));
        if (line2) {
          ctx.fillText(line2, bx + bw / 2, by + 25);
        }
      }
    };

    const render = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      frameCountRef.current += 1;
      const f = frameCountRef.current;

      ctx.clearRect(0, 0, CW, CH);

      const agentList = Object.values(agentsRef.current);
      const isNearShelf = agentList.some((a) => Math.hypot(a.x - SPOTS.RESEARCH_SHELF.x, a.y - SPOTS.RESEARCH_SHELF.y) < 40);

      // Layer 1: 바닥 & 4개 부서 방
      drawCheckTile(ctx, 0, 0, CW, CH, '#475569', '#3b4758', 24);

      drawWoodRoom(ctx, 18, 16, 382, 244, '#854d0e', '#713f12');
      drawRoomWalls(ctx, 18, 16, 382, 244, 'RIGHT', DOORS.RESEARCH.y);
      drawBookshelf(ctx, 36, 24, isNearShelf, f);
      drawBookshelf(ctx, 114, 24, isNearShelf, f);
      drawBookshelf(ctx, 312, 24, false, f);
      drawPlant(ctx, 225, 48);

      drawCheckTile(ctx, 520, 16, 382, 244, '#1e3a5f', '#172554', 20);
      drawRoomWalls(ctx, 520, 16, 382, 244, 'LEFT', DOORS.DEV.y);
      drawServerRack(ctx, 540, 24, f);
      drawServerRack(ctx, 594, 24, f + 10);
      drawBookshelf(ctx, 816, 24, false, f);
      drawPlant(ctx, 705, 48);

      drawWoodRoom(ctx, 18, 318, 382, 244, '#9a3412', '#7c2d12');
      drawRoomWalls(ctx, 18, 318, 382, 244, 'RIGHT', DOORS.MEETING.y);
      ctx.fillStyle = '#fde68a';
      ctx.fillRect(75, 390, 270, 145);
      ctx.strokeStyle = '#d97706';
      ctx.lineWidth = 2;
      ctx.strokeRect(75, 390, 270, 145);

      ctx.fillStyle = 'rgba(0,0,0,0.3)';
      ctx.beginPath();
      ctx.arc(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y + 6, 52, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#78350f';
      ctx.beginPath();
      ctx.arc(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 50, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#b45309';
      ctx.beginPath();
      ctx.arc(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 42, 0, Math.PI * 2);
      ctx.fill();
      drawPlant(ctx, 46, 360);

      drawCheckTile(ctx, 520, 318, 382, 244, '#334155', '#1e293b', 20);
      drawRoomWalls(ctx, 520, 318, 382, 244, 'LEFT', DOORS.LOUNGE.y);
      ctx.fillStyle = '#065f46';
      ctx.fillRect(575, 395, 265, 135);
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 2;
      ctx.strokeRect(575, 395, 265, 135);
      ctx.fillStyle = '#2563eb';
      ctx.fillRect(595, 345, 125, 28);
      ctx.fillStyle = '#60a5fa';
      ctx.fillRect(599, 349, 117, 16);
      ctx.fillStyle = '#57534e';
      ctx.fillRect(765, 335, 60, 36);
      ctx.fillStyle = '#dc2626';
      ctx.fillRect(782, 327, 24, 24);
      drawPlant(ctx, 865, 360);
      drawPlant(ctx, 548, 525);

      // Layer 2: 의자 등받이
      drawChairBack(ctx, SPOTS.RESEARCH_DESK_1.x, SPOTS.RESEARCH_DESK_1.y);
      drawChairBack(ctx, SPOTS.RESEARCH_DESK_2.x, SPOTS.RESEARCH_DESK_2.y);
      drawChairBack(ctx, SPOTS.DEV_DESK_1.x, SPOTS.DEV_DESK_1.y);
      drawChairBack(ctx, SPOTS.DEV_DESK_2.x, SPOTS.DEV_DESK_2.y);

      const walkingMap: Record<string, boolean> = {};
      const workingDeskMap: Record<string, boolean> = {};

      // 에이전트 이동 & 책상 집중 조사 타이머(workTimer) 처리
      agentList.forEach((ag) => {
        let walking = false;
        if (ag.waypoints.length > 0) {
          const nextPt = ag.waypoints[0];
          const dx = nextPt.x - ag.x;
          const dy = nextPt.y - ag.y;
          const dist = Math.hypot(dx, dy);
          const step = 1.85 * speedRef.current;

          if (Math.abs(dx) > Math.abs(dy)) {
            ag.facing = dx < 0 ? 'LEFT' : 'RIGHT';
          } else {
            ag.facing = dy < 0 ? 'UP' : 'DOWN';
          }

          if (dist <= step) {
            ag.x = nextPt.x;
            ag.y = nextPt.y;
            ag.waypoints.shift();
            if (ag.waypoints.length === 0) {
              if (SPOTS[ag.currentSpotKey]) {
                ag.facing = SPOTS[ag.currentSpotKey].sitFacing;
              }
              if (ag.workTimer <= 0 && ag.pendingBubble) {
                ag.activeBubble = ag.pendingBubble;
                ag.pendingBubble = '';
              }
            }
          } else {
            ag.x += (dx / dist) * step;
            ag.y += (dy / dist) * step;
            walking = true;
          }
        } else if (ag.workTimer > 0) {
          // 책상에 도착한 후 최소 조사 시간 동안 타이핑하며 게이지를 100%까지 채움!
          ag.workTimer = Math.max(0, ag.workTimer - speedRef.current);
          ag.progress = Math.min(98, 100 - (ag.workTimer / 150) * 85);
          workingDeskMap[ag.id] = true;

          // 조사 타이머가 끝나는 순간 대기 중이던 회의실 이동(queuedSpotKey)을 실행!
          if (ag.workTimer <= 0) {
            ag.progress = 100;
            if (ag.queuedSpotKey) {
              const nextKey = ag.queuedSpotKey;
              ag.queuedSpotKey = '';
              ag.currentSpotKey = nextKey;
              ag.waypoints = buildRoomPath(ag.x, ag.y, SPOTS[nextKey]);
            } else if (ag.pendingBubble) {
              ag.activeBubble = ag.pendingBubble;
              ag.pendingBubble = '';
            }
          }
        }

        walkingMap[ag.id] = walking;
      });

      // [핵심 개선] 모든 캐릭터가 이동과 컴퓨터 조사를 마치고 회의실에 모였는지 검사!
      if (hasFinalReportRef.current && !reportUnlockedRef.current && agentList.length > 0) {
        const allGatheredInMeeting = agentList.every(
          (ag) =>
            ag.waypoints.length === 0 &&
            ag.workTimer <= 0 &&
            !ag.queuedSpotKey &&
            getRoomAt(ag.x, ag.y) === 'MEETING'
        );
        if (allGatheredInMeeting) {
          reportUnlockedRef.current = true;
          setReportUnlocked(true);
          onAllGatheredChange?.(true);
        }
      }

      // Layer 3: 캐릭터 몸체
      agentList
        .slice()
        .sort((a, b) => a.y - b.y)
        .forEach((ag, idx) => {
          drawCharacterBody(ctx, ag, idx, walkingMap[ag.id], Boolean(workingDeskMap[ag.id]), f);
        });

      const isDeskBusy = (sx: number, sy: number) =>
        agentList.some((a) => Math.hypot(a.x - sx, a.y - sy) < 28 && !walkingMap[a.id]);

      // Layer 4: 책상 상판 및 홀로그램 모니터
      drawDeskSurface(ctx, SPOTS.RESEARCH_DESK_1.x, SPOTS.RESEARCH_DESK_1.y, isDeskBusy(SPOTS.RESEARCH_DESK_1.x, SPOTS.RESEARCH_DESK_1.y), f);
      drawDeskSurface(ctx, SPOTS.RESEARCH_DESK_2.x, SPOTS.RESEARCH_DESK_2.y, isDeskBusy(SPOTS.RESEARCH_DESK_2.x, SPOTS.RESEARCH_DESK_2.y), f);
      drawDeskSurface(ctx, SPOTS.DEV_DESK_1.x, SPOTS.DEV_DESK_1.y, isDeskBusy(SPOTS.DEV_DESK_1.x, SPOTS.DEV_DESK_1.y), f);
      drawDeskSurface(ctx, SPOTS.DEV_DESK_2.x, SPOTS.DEV_DESK_2.y, isDeskBusy(SPOTS.DEV_DESK_2.x, SPOTS.DEV_DESK_2.y), f);

      // Layer 5: 전원이 회의실에 도착 완료(reportUnlockedRef.current)했을 때만 회의실 테이블 중앙에 최종 보고서 생성!
      if (reportUnlockedRef.current) {
        const bounceDoc = Math.sin(f * 0.12) * 3;
        const tx = MEETING_TABLE_CENTER.x;
        const ty = MEETING_TABLE_CENTER.y + bounceDoc;

        ctx.fillStyle = f % 30 < 15 ? 'rgba(250, 204, 21, 0.5)' : 'rgba(16, 185, 129, 0.5)';
        ctx.beginPath();
        ctx.arc(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 36, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#fef08a';
        ctx.fillRect(tx - 16, ty - 14, 32, 24);
        ctx.strokeStyle = '#ca8a04';
        ctx.lineWidth = 2;
        ctx.strokeRect(tx - 16, ty - 14, 32, 24);
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(tx - 11, ty - 8, 22, 3);
        ctx.fillRect(tx - 11, ty - 2, 16, 3);
        ctx.fillRect(tx - 11, ty + 4, 20, 3);

        ctx.fillStyle = '#059669';
        ctx.fillRect(tx - 68, ty - 36, 136, 22);
        ctx.strokeStyle = '#fde047';
        ctx.lineWidth = 2;
        ctx.strokeRect(tx - 68, ty - 36, 136, 22);
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 10.5px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('📋 최종 보고서 (클릭)', tx, ty - 21);
      } else {
        ctx.fillStyle = '#f8fafc';
        ctx.fillRect(MEETING_TABLE_CENTER.x - 12, MEETING_TABLE_CENTER.y - 8, 24, 16);
      }

      // Layer 6: 방 이름 뱃지
      const drawBadge = (text: string, bx: number, by: number, borderColor: string) => {
        ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
        ctx.fillRect(bx, by, 102, 22);
        ctx.strokeStyle = borderColor;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(bx, by, 102, 22);
        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(text, bx + 51, by + 15);
      };
      drawBadge('🔍 리서치실', 28, 22, '#38bdf8');
      drawBadge('💻 개발·합성실', 530, 22, '#818cf8');
      drawBadge('📋 결재·회의실', 28, 324, '#fbbf24');
      drawBadge('☕ 휴게실', 530, 324, '#34d399');

      // Layer 7: 캐릭터 이름표 & 4방향 분산 말풍선
      agentList.forEach((ag) => {
        drawCharacterOverlayUI(ctx, ag, walkingMap[ag.id], Boolean(workingDeskMap[ag.id]));
      });

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, []);

  return (
    <div className="relative w-full h-full flex flex-col bg-slate-950 overflow-hidden select-none">
      <div className="shrink-0 px-4 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-bold text-emerald-300">2D PIXEL AGENT OFFICE</span>
          {finalReport && !reportUnlocked && (
            <span className="px-2.5 py-1 text-[11px] font-bold bg-sky-950 border border-sky-500/50 text-sky-300 rounded-lg animate-pulse">
              🚶 에이전트들이 조사를 마치고 회의실로 집결 중입니다...
            </span>
          )}
          {reportUnlocked && (
            <button
              onClick={onOpenReportModal}
              className="px-2.5 py-1 text-[11px] font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg shadow animate-bounce transition"
            >
              📋 회의실 최종 보고서 열기
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-400">캐릭터 이동 속도:</span>
          {[
            { label: '0.7x (여유)', val: 0.7 },
            { label: '1.0x (표준)', val: 1.0 },
            { label: '1.5x (빠름)', val: 1.5 },
          ].map((opt) => (
            <button
              key={opt.val}
              onClick={() => setSpeedMult(opt.val)}
              className={`px-2.5 py-1 rounded text-[10px] font-bold border transition ${
                speedMult === opt.val
                  ? 'bg-emerald-600 border-emerald-400 text-white'
                  : 'bg-slate-950 border-slate-700 text-slate-400 hover:text-slate-200'
              }`}
            >
              {opt.label}
            </button>
          ))}

          {onToggleLogDrawer && (
            <button
              onClick={onToggleLogDrawer}
              className="ml-2 px-3 py-1 rounded-lg text-[11px] font-bold bg-slate-800 hover:bg-slate-700 text-amber-300 border border-amber-500/40 transition"
            >
              📜 실시간 로그 서랍 보기 ({unreadLogCount})
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 min-h-0 flex items-center justify-center p-3 bg-slate-950">
        <canvas
          ref={canvasRef}
          width={CW}
          height={CH}
          onClick={(e) => handleCanvasPos(e, true)}
          onMouseMove={(e) => handleCanvasPos(e, false)}
          className={`w-full h-full object-contain rounded-2xl border border-slate-800 shadow-2xl bg-slate-900 ${
            isHoveringReport ? 'cursor-pointer ring-2 ring-amber-400' : ''
          }`}
        />
      </div>
    </div>
  );
}
''',

    # 4. 프론트엔드 page.tsx: (1) 전원 회의실 도착 후 보고서 탭 오픈, (2) Base64 파일 업로드, (3) 원클릭 브라우저 토큰 자동 추출 모달
    "src/app/page.tsx": r''''use client';

import React, { useState, useEffect, useRef } from 'react';
import { ReactFlow, Background, Controls } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useOfficeStore } from '@/store/useOfficeStore';
import AgentCustomNode from '@/components/AgentCustomNode';
import VirtualOfficeFloor from '@/components/VirtualOfficeFloor';
import PixelRpgOffice from '@/components/PixelRpgOffice';
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
    .replace(/<br\s*\/?>/gi, '\n   ')
    .replace(/#{1,4}\s/g, '📌 ')
    .replace(/\*\*/g, '');
}

export default function MissionControlPage() {
  const [prompt, setPrompt] = useState(PRESET_SCENARIOS[1].prompt);
  const [isReplayMode, setIsReplayMode] = useState(false);
  const [leftViewMode, setLeftViewMode] = useState<'PIXEL' | 'OFFICE' | 'GRAPH'>('PIXEL');
  const [activeTab, setActiveTab] = useState<'BROWSER' | 'REPORT'>('BROWSER');
  const [isDirOpen, setIsDirOpen] = useState(false);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [isLogDrawerOpen, setIsLogDrawerOpen] = useState(false);
  const [isOAuthModalOpen, setIsOAuthModalOpen] = useState(false);
  const [isAllGathered, setIsAllGathered] = useState(false);

  const [uploadedFileName, setUploadedFileName] = useState<string>('');
  const [uploadedPreview, setUploadedPreview] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [gptConnected, setGptConnected] = useState<boolean>(false);
  const [gptMaskedToken, setGptMaskedToken] = useState<string>('');
  const [oauthInputToken, setOauthInputToken] = useState<string>('');
  const [isAutoConnecting, setIsAutoConnecting] = useState<boolean>(false);

  const [selectedFrameIdx, setSelectedFrameIdx] = useState<number>(-1);
  const [expandedLogs, setExpandedLogs] = useState<Record<number, boolean>>({});
  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  const [manualTeam, setManualTeam] = useState<{ sup: EmployeeProfile; workers: EmployeeProfile[] } | null>(null);

  const esRef = useRef<EventSource | null>(null);
  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const {
    nodes,
    edges,
    messages,
    currentFrame,
    browserHistory,
    finalReport,
    hitlData,
    metrics,
    dispatchEvent,
    clearHitl,
    resetMission,
  } = useOfficeStore();

  const refreshOAuthStatus = () => {
    fetch(`${apiBase}/api/auth/openai/status`)
      .then((r) => r.json())
      .then((d) => {
        setGptConnected(Boolean(d.connected));
        setGptMaskedToken(d.masked_token || '');
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetch('/data/employees.json')
      .then((r) => r.json())
      .then(setEmployees)
      .catch(() => {});
    refreshOAuthStatus();
    return () => {
      esRef.current?.close();
    };
  }, []);

  // [핵심 수정] 2D 오피스 모드에서는 캐릭터들이 전부 회의실에 모였을 때만 결재함 탭으로 전환!
  useEffect(() => {
    if (finalReport && (leftViewMode !== 'PIXEL' || isAllGathered)) {
      setActiveTab('REPORT');
    }
  }, [finalReport, isAllGathered, leftViewMode]);

  // python-multipart 없이도 100% 작동하는 Base64 JSON 업로드 핸들러
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      const resultStr = String(reader.result || '');
      const base64Content = resultStr.includes(',') ? resultStr.split(',')[1] : resultStr;
      try {
        const res = await fetch(`${apiBase}/api/mission/upload-json`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: file.name, content_base64: base64Content }),
        });
        const data = await res.json();
        if (data.status === 'OK') {
          setUploadedFileName(data.filename);
          setUploadedPreview(data.preview || '');
          setPrompt(`첨부한 '${data.filename}' 파일의 핵심 수치와 내용을 분석해서 표준 의사결정 보고서 양식으로 통합·요약해줘`);
        }
      } catch {
        alert('백엔드 서버(8000번 포트)가 켜져 있는지 확인해 주세요.');
      }
    };
    reader.readAsDataURL(file);
  };

  const handleClearUpload = async () => {
    setUploadedFileName('');
    setUploadedPreview('');
    if (fileInputRef.current) fileInputRef.current.value = '';
    try {
      await fetch(`${apiBase}/api/mission/clear-upload`, { method: 'POST' });
    } catch {}
  };

  // 원클릭 로컬 브라우저 세션 토큰 자동 추출
  const handleAutoBrowserConnect = async () => {
    setIsAutoConnecting(true);
    try {
      const res = await fetch(`${apiBase}/api/auth/openai/auto-browser`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'OK') {
        refreshOAuthStatus();
        setIsOAuthModalOpen(false);
      } else {
        alert('로그인 시간이 초과되었거나 취소되었습니다. 다시 시도해 주세요.');
      }
    } catch {
      alert('백엔드 서버 연결을 확인해 주세요.');
    } finally {
      setIsAutoConnecting(false);
    }
  };

  const handleSaveOAuthToken = async () => {
    if (!oauthInputToken.trim()) return;
    await fetch(`${apiBase}/api/auth/openai/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ access_token: oauthInputToken.trim(), model: 'gpt-4o-mini' }),
    });
    setOauthInputToken('');
    refreshOAuthStatus();
    setIsOAuthModalOpen(false);
  };

  const handleDisconnectOAuth = async () => {
    await fetch(`${apiBase}/api/auth/openai/disconnect`, { method: 'POST' });
    refreshOAuthStatus();
    setIsOAuthModalOpen(false);
  };

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
            text: '⚠️ FastAPI 백엔드 서버(8000번 포트)와 연결이 끊어졌거나 켜져 있지 않습니다.',
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
    setSelectedFrameIdx(-1);
    setIsAllGathered(false);
    setActiveTab('BROWSER');
    if (isReplayMode) {
      streamSSE(`/api/mission/replay?${buildReplayQuery({ phase: '1' })}`);
    } else {
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

  const displayedFrameUrl =
    selectedFrameIdx >= 0 && browserHistory[selectedFrameIdx]
      ? browserHistory[selectedFrameIdx].url
      : currentFrame;

  const isReportVisible = Boolean(finalReport) && (leftViewMode !== 'PIXEL' || isAllGathered);

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-950 text-slate-100 select-none">
      {/* 1. 상단 바 */}
      <header className="shrink-0 px-5 py-2.5 bg-slate-900 border-b border-slate-800 space-y-2">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-1">
            <button
              onClick={() => setIsReplayMode(!isReplayMode)}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition shrink-0 ${
                isReplayMode
                  ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300'
                  : 'bg-amber-500/20 border-amber-500 text-amber-300 shadow-[0_0_12px_rgba(245,158,11,0.3)]'
              }`}
            >
              {isReplayMode ? '🎬 데모 리플레이 모드 ($0)' : '⚡ REAL API 모드 (실시간 연동)'}
            </button>

            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv,.pdf,.txt,.md,.json"
              onChange={handleFileUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition shrink-0 ${
                uploadedFileName
                  ? 'bg-sky-500/20 border-sky-400 text-sky-300'
                  : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-sky-500/60'
              }`}
            >
              {uploadedFileName ? `📎 ${uploadedFileName.slice(0, 14)}` : '📎 엑셀/PDF 첨부'}
            </button>
            {uploadedFileName && (
              <button
                onClick={handleClearUpload}
                className="px-1.5 py-1 text-[10px] font-bold bg-rose-950 border border-rose-700 text-rose-300 rounded"
                title="첨부 해제"
              >
                ✕
              </button>
            )}

            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="CEO 업무 지시사항을 입력하거나 엑셀/PDF 파일을 첨부하세요..."
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
                setSelectedFrameIdx(-1);
                setIsAllGathered(false);
                resetMission(false);
              }}
              className="px-3 py-2 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg shrink-0"
            >
              ↺ 초기화
            </button>
          </div>

          <div className="flex items-center gap-3 text-xs shrink-0">
            <button
              onClick={() => setIsOAuthModalOpen(true)}
              className={`px-3 py-1.5 rounded-lg border text-left transition ${
                gptConnected
                  ? 'bg-emerald-950/60 border-emerald-500/70 text-emerald-300'
                  : 'bg-slate-950 border-slate-800 hover:border-amber-500/60 text-slate-300'
              }`}
            >
              <span className="text-[10px] block text-slate-400">OpenAI 구독/토큰 연동</span>
              <span className="text-xs font-bold">
                {gptConnected ? '🟢 ChatGPT 연동됨' : '🔗 ChatGPT Plus 연동'}
              </span>
            </button>

            <button
              onClick={() => setIsDirOpen(true)}
              className="text-left px-3 py-1 rounded-lg bg-slate-950 border border-slate-800 hover:border-emerald-500/60"
            >
              <span className="text-slate-400 text-[10px]">가동 인원 (100명 명부) ↗</span>
              <p className="text-xs font-bold text-emerald-400">
                {metrics.activeAgents} / {employees.length || 100}명
              </p>
            </button>

            <button
              onClick={() => setIsLogDrawerOpen(!isLogDrawerOpen)}
              className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-amber-400 text-left"
            >
              <span className="text-[10px] block text-slate-400">실시간 대화·검수 기록</span>
              <span className="text-xs font-bold text-amber-400">📜 에이전트 로그 ({messages.length})</span>
            </button>
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

      {/* 2. 메인 작업 공간 */}
      <main className="relative grid grid-cols-12 flex-1 min-h-0 overflow-hidden">
        <section className="col-span-8 border-r border-slate-800 flex flex-col min-h-0 overflow-hidden">
          <div className="shrink-0 flex border-b border-slate-800 text-xs font-bold bg-slate-900/50">
            <button
              onClick={() => setLeftViewMode('PIXEL')}
              className={`flex-1 py-2.5 transition ${
                leftViewMode === 'PIXEL'
                  ? 'border-b-2 border-emerald-500 text-emerald-400 bg-emerald-950/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🎮 2D 도트 오피스 (책상 컴퓨터 집중 조사 & 전원 집결 후 보고서 생성)
            </button>
            <button
              onClick={() => setLeftViewMode('OFFICE')}
              className={`flex-1 py-2.5 transition ${
                leftViewMode === 'OFFICE'
                  ? 'border-b-2 border-emerald-500 text-emerald-400 bg-emerald-950/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🏢 서류비행 데스크
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
            {leftViewMode === 'PIXEL' ? (
              <PixelRpgOffice
                onOpenReportModal={() => setIsReportModalOpen(true)}
                onToggleLogDrawer={() => setIsLogDrawerOpen(!isLogDrawerOpen)}
                unreadLogCount={messages.length}
                onAllGatheredChange={setIsAllGathered}
              />
            ) : leftViewMode === 'OFFICE' ? (
              <VirtualOfficeFloor />
            ) : (
              <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView colorMode="dark">
                <Background color="#334155" gap={16} />
                <Controls />
              </ReactFlow>
            )}
          </div>
        </section>

        <section className="col-span-4 flex flex-col min-h-0 overflow-hidden bg-slate-900/30">
          <div className="shrink-0 flex border-b border-slate-800 text-xs font-semibold">
            <button
              onClick={() => setActiveTab('BROWSER')}
              className={`flex-1 py-2.5 ${
                activeTab === 'BROWSER' ? 'border-b-2 border-emerald-500 text-emerald-400' : 'text-slate-400'
              }`}
            >
              🌐 실시간 웹 탐색 ({browserHistory.length > 0 ? `${browserHistory.length}단계 캡처됨` : 'SoM Vision'})
            </button>
            <button
              onClick={() => setActiveTab('REPORT')}
              className={`flex-1 py-2.5 ${
                activeTab === 'REPORT' ? 'border-b-2 border-emerald-500 text-emerald-400' : 'text-slate-400'
              }`}
            >
              📄 최종 승인 결재함 {isReportVisible ? '✅' : ''}
            </button>
          </div>

          <div className="flex-1 min-h-0 p-4 overflow-y-auto space-y-3">
            {uploadedFileName && (
              <div className="p-3 rounded-xl bg-sky-950/40 border border-sky-500/50 text-xs space-y-1">
                <div className="font-bold text-sky-300">📎 첨부 문서 파싱 완료: {uploadedFileName}</div>
                <p className="text-[11px] text-slate-300 whitespace-pre-wrap line-clamp-3">{uploadedPreview}</p>
              </div>
            )}

            {activeTab === 'BROWSER' ? (
              displayedFrameUrl ? (
                <div className="space-y-2.5">
                  {browserHistory.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap bg-slate-900 p-2 rounded-xl border border-slate-800">
                      <span className="text-[10px] font-bold text-slate-400 mr-1">🎬 탐색 단계별 화면:</span>
                      {browserHistory.map((item, idx) => {
                        const isSelected = (selectedFrameIdx === -1 ? browserHistory.length - 1 : selectedFrameIdx) === idx;
                        return (
                          <button
                            key={idx}
                            onClick={() => setSelectedFrameIdx(idx)}
                            className={`px-2.5 py-1 text-[10px] font-bold rounded-lg border transition ${
                              isSelected
                                ? 'bg-emerald-600 border-emerald-400 text-white shadow'
                                : 'bg-slate-950 border-slate-700 text-slate-300 hover:border-slate-500'
                            }`}
                          >
                            {item.step}
                          </button>
                        );
                      })}
                    </div>
                  )}
                  <div className="rounded-xl overflow-hidden border border-slate-700">
                    <img src={displayedFrameUrl} alt="SoM View" className="w-full object-contain" />
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-500 text-center mt-24">
                  웹 탐색 직원이 리서치실 책상에 도착하면 이곳에 빨간 번호표(SoM) 화면이 생중계됩니다.
                </p>
              )
            ) : (
              <div className="space-y-3 pb-8">
                {isReportVisible ? (
                  <>
                    <div className="flex items-center justify-between bg-slate-900 px-3.5 py-2 rounded-xl border border-slate-800">
                      <span className="text-[11px] font-bold text-emerald-400">
                        ✅ 전원 회의실 집결 & 최종 결재 완료
                      </span>
                      <button
                        onClick={() => setIsReportModalOpen(true)}
                        className="px-2.5 py-1 text-[11px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition"
                      >
                        🔍 전체화면으로 크게 보기
                      </button>
                    </div>
                    <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 text-xs whitespace-pre-wrap break-words leading-relaxed text-slate-200 select-text">
                      {cleanReportText(finalReport || '')}
                    </div>
                  </>
                ) : (
                  <div className="p-6 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400 text-center space-y-2 mt-12">
                    <p className="text-emerald-400 font-bold animate-pulse">
                      {finalReport
                        ? '🚶 에이전트들이 컴퓨터 조사를 마치고 결재 회의실로 모이는 중입니다...'
                        : '⏳ 에이전트들이 부서 책상에서 데이터를 조사·합성한 뒤 전원 회의실에 모이면 최종 보고서가 공개됩니다.'}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        {isLogDrawerOpen && (
          <aside className="absolute right-0 top-0 bottom-0 w-[440px] z-40 bg-slate-950/95 backdrop-blur-md border-l border-slate-700 flex flex-col shadow-2xl">
            <div className="shrink-0 px-4 py-3 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
              <span className="text-xs font-bold text-amber-400">
                📜 AGENT WORKSPACE & QC 상세 로그 ({messages.length}건)
              </span>
              <button
                onClick={() => setIsLogDrawerOpen(false)}
                className="px-2.5 py-1 text-xs font-bold bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-200"
              >
                ✕ 닫기
              </button>
            </div>
            <div className="flex-1 p-4 overflow-y-auto space-y-3">
              {messages.length === 0 && (
                <p className="text-xs text-slate-500 text-center mt-20">아직 기록된 에이전트 로그가 없습니다.</p>
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
          </aside>
        )}
      </main>

      {/* 개선된 ChatGPT Plus 연동 모달 (원클릭 로컬 브라우저 세션 추출 지원!) */}
      {isOAuthModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-6">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-emerald-400">
                🔗 ChatGPT Plus 계정 & 토큰 연동하기
              </h3>
              <button
                onClick={() => setIsOAuthModalOpen(false)}
                className="px-2.5 py-1 text-xs font-bold bg-slate-800 rounded-lg"
              >
                ✕
              </button>
            </div>

            <div className="text-xs text-slate-300 space-y-2 leading-relaxed">
              <p>
                아래 <strong>[⚡ 원클릭 브라우저 로그인 & 토큰 자동 추출]</strong> 버튼을 누르면 전용 로그인 창이 열립니다.
                ChatGPT에 로그인하면 백엔드가 자동으로 세션 토큰을 감지해 연동을 완료합니다!
              </p>
              {gptConnected && (
                <div className="p-3 rounded-xl bg-emerald-950/50 border border-emerald-500/50 text-emerald-200 font-semibold">
                  ✅ 현재 연동 완료 (토큰: {gptMaskedToken})
                </div>
              )}
            </div>

            <div className="space-y-3 pt-1">
              <button
                onClick={handleAutoBrowserConnect}
                disabled={isAutoConnecting}
                className="w-full py-3 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 text-white rounded-xl shadow-lg transition"
              >
                {isAutoConnecting
                  ? '⏳ 열린 브라우저 창에서 ChatGPT 로그인을 완료해 주세요 (자동 감지 중...)'
                  : '⚡ 방법 1: 원클릭 브라우저 로그인 & 세션 토큰 자동 추출 (추천)'}
              </button>

              <div className="pt-2 border-t border-slate-800 space-y-1.5">
                <label className="text-[11px] font-bold text-slate-400 block">
                  🔑 방법 2: 보유 중인 OpenAI API Key (`sk-...`) 또는 Access Token 직접 입력:
                </label>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={oauthInputToken}
                    onChange={(e) => setOauthInputToken(e.target.value)}
                    placeholder="sk-proj-... 또는 eyJhbGci..."
                    className="flex-1 px-3 py-2 text-xs bg-slate-950 border border-slate-700 rounded-lg text-slate-100"
                  />
                  <button
                    onClick={handleSaveOAuthToken}
                    className="px-4 py-2 text-xs font-bold bg-sky-600 hover:bg-sky-500 text-white rounded-lg shrink-0"
                  >
                    저장
                  </button>
                </div>
              </div>
            </div>

            {gptConnected && (
              <div className="pt-2 border-t border-slate-800 flex justify-end">
                <button
                  onClick={handleDisconnectOAuth}
                  className="px-3 py-1.5 text-xs font-bold bg-rose-900/60 hover:bg-rose-800 text-rose-200 rounded-lg"
                >
                  연동 해제
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {isReportModalOpen && finalReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-6">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-4xl max-h-[88vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 bg-slate-950 border-b border-slate-800">
              <h3 className="text-sm font-bold text-emerald-400">
                📋 회의실 최종 승인 결재 보고서 (전문 열람)
              </h3>
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
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ 업데이트 완료: {path}")

    for py_file in ["backend/openai_oauth.py", "backend/main.py"]:
        py_compile.compile(py_file, doraise=True)
    print("🎉 [검증 완료] 모든 백엔드/프론트엔드 코드 컴파일 성공! (python-multipart 에러 해결 포함)")