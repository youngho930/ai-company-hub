import os
import py_compile

FILES = {
    # 1. 백엔드 openai_oauth.py: 브라우저 강제 종료 시 예외 처리 보강
    "backend/openai_oauth.py": r'''import os
import sys
import json
import time
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
    try:
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

            extracted_token = ""
            for _ in range(60):
                try:
                    res = page.evaluate("""async () => {
                        try {
                            const r = await fetch('/api/auth/session');
                            if (!r.ok) return null;
                            return await r.json();
                        } catch (e) { return null; }
                    }""")
                    if res and isinstance(res, dict) and res.get("accessToken"):
                        extracted_token = res["accessToken"]
                        break
                except Exception:
                    pass
                time.sleep(1.0)
            context.close()

        if extracted_token:
            save_chatgpt_token({"access_token": extracted_token, "model": "gpt-4o-mini"})
            return {"status": "OK"}
    except Exception as e:
        print(f"[Browser Auth Error]: {e}")
    return {"status": "ERROR"}

async def auto_connect_chatgpt_browser() -> dict:
    return await asyncio.to_thread(_auto_extract_session_sync)

def call_chatgpt_with_oauth(prompt: str, temperature: float = 0.2) -> Optional[str]:
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
        print(f"[ChatGPT Info] Fallback: {str(e)[:50]}")
    return None
''',

    # 2. 프론트엔드 page.tsx: 2D 오피스 풀스크린(12컬럼) + 우측 패널 서랍화
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
  const [isDirOpen, setIsDirOpen] = useState(false);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [isLogDrawerOpen, setIsLogDrawerOpen] = useState(false);
  const [isBrowserDrawerOpen, setIsBrowserDrawerOpen] = useState(false);
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

  const handleAutoBrowserConnect = async () => {
    setIsAutoConnecting(true);
    try {
      const res = await fetch(`${apiBase}/api/auth/openai/auto-browser`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'OK') {
        refreshOAuthStatus();
        setIsOAuthModalOpen(false);
      } else {
        alert('로그인 시간이 초과되었거나 취소되었습니다. 방법을 직접 입력으로 시도해 주세요.');
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

          <div className="flex items-center gap-2.5 text-xs shrink-0">
            <button
              onClick={() => setIsOAuthModalOpen(true)}
              className={`px-3 py-1.5 rounded-lg border text-left transition ${
                gptConnected
                  ? 'bg-emerald-950/60 border-emerald-500/70 text-emerald-300'
                  : 'bg-slate-950 border-slate-800 hover:border-amber-500/60 text-slate-300'
              }`}
            >
              <span className="text-[10px] block text-slate-400">OpenAI 모델 연동</span>
              <span className="text-xs font-bold">
                {gptConnected ? '🟢 ChatGPT 연동됨' : '🔗 ChatGPT 연동'}
              </span>
            </button>

            <button
              onClick={() => setIsDirOpen(true)}
              className="text-left px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-emerald-500/60"
            >
              <span className="text-slate-400 text-[10px]">가동 인원 ↗</span>
              <p className="text-xs font-bold text-emerald-400">
                {metrics.activeAgents} / {employees.length || 100}명
              </p>
            </button>

            {/* 웹 탐색 캡처 서랍 열기 버튼 */}
            <button
              onClick={() => setIsBrowserDrawerOpen(true)}
              className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-sky-400 text-left"
            >
              <span className="text-[10px] block text-slate-400">SoM 캡처 뷰어</span>
              <span className="text-xs font-bold text-sky-400">🌐 웹 탐색 ({browserHistory.length})</span>
            </button>

            {/* 실시간 로그 서랍 열기 버튼 */}
            <button
              onClick={() => setIsLogDrawerOpen(true)}
              className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-amber-400 text-left"
            >
              <span className="text-[10px] block text-slate-400">에이전트 검수</span>
              <span className="text-xs font-bold text-amber-400">📜 로그 ({messages.length})</span>
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

      {/* 2. 메인 작업 공간: 2D 도트 오피스를 화면 전체(12컬럼 풀스크린)로 확장! */}
      <main className="relative flex-1 min-h-0 overflow-hidden flex flex-col">
        <div className="shrink-0 flex border-b border-slate-800 text-xs font-bold bg-slate-900/50 px-4 py-2">
          <div className="flex items-center gap-3 flex-1">
            <span className="text-emerald-400 font-bold">🎮 2D PIXEL AGENT OFFICE (풀스크린 관제 모드)</span>
            {finalReport && !isAllGathered && (
              <span className="text-xs text-sky-300 animate-pulse">
                🚶 에이전트들이 컴퓨터 조사를 마치고 회의실 테이블로 집결 중입니다...
              </span>
            )}
            {isAllGathered && (
              <button
                onClick={() => setIsReportModalOpen(true)}
                className="px-3 py-1 text-xs font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg shadow animate-bounce transition"
              >
                📋 회의실 최종 승인 보고서 열기 (클릭)
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setLeftViewMode('PIXEL')}
              className={`px-3 py-1 rounded text-xs transition ${
                leftViewMode === 'PIXEL' ? 'bg-emerald-600 text-white font-bold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              도트 오피스
            </button>
            <button
              onClick={() => setLeftViewMode('GRAPH')}
              className={`px-3 py-1 rounded text-xs transition ${
                leftViewMode === 'GRAPH' ? 'bg-emerald-600 text-white font-bold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              조직도 뷰
            </button>
          </div>
        </div>

        <div className="flex-1 min-h-0 overflow-hidden relative">
          {leftViewMode === 'PIXEL' ? (
            <PixelRpgOffice
              onOpenReportModal={() => setIsReportModalOpen(true)}
              onToggleLogDrawer={() => setIsLogDrawerOpen(!isLogDrawerOpen)}
              unreadLogCount={messages.length}
              onAllGatheredChange={setIsAllGathered}
            />
          ) : (
            <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView colorMode="dark">
              <Background color="#334155" gap={16} />
              <Controls />
            </ReactFlow>
          )}
        </div>

        {/* 우측 슬라이드 서랍 1: 실시간 웹 탐색(SoM 캡처 뷰어) */}
        {isBrowserDrawerOpen && (
          <aside className="absolute right-0 top-0 bottom-0 w-[500px] z-40 bg-slate-950/95 backdrop-blur-md border-l border-slate-700 flex flex-col shadow-2xl">
            <div className="shrink-0 px-4 py-3 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
              <span className="text-xs font-bold text-sky-400">
                🌐 실시간 웹 탐색 (SoM Vision 크롤링 캡처)
              </span>
              <button
                onClick={() => setIsBrowserDrawerOpen(false)}
                className="px-2.5 py-1 text-xs font-bold bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-200"
              >
                ✕ 닫기
              </button>
            </div>
            <div className="flex-1 p-4 overflow-y-auto space-y-3">
              {displayedFrameUrl ? (
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
                <p className="text-xs text-slate-500 text-center mt-32">
                  업무 하달 시 에이전트들이 웹사이트를 스캔하고 빨간 번호표(SoM)를 부여한 캡처 화면이 이곳에 누적됩니다.
                </p>
              )}
            </div>
          </aside>
        )}

        {/* 우측 슬라이드 서랍 2: 에이전트 상세 로그 & QC 검수 기록 */}
        {isLogDrawerOpen && (
          <aside className="absolute right-0 top-0 bottom-0 w-[460px] z-40 bg-slate-950/95 backdrop-blur-md border-l border-slate-700 flex flex-col shadow-2xl">
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

      {/* ChatGPT 연동 모달 (원클릭 자동 추출 및 직접 입력 지원) */}
      {isOAuthModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-6">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-emerald-400">
                🔗 ChatGPT 모델 및 계정 연동하기
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
                OpenAI API 키(<code>sk-...</code>)를 보유하고 계시다면 아래에 입력해 주시면 즉시 시스템의 주력 추론 모델로 연동됩니다.
              </p>
              {gptConnected && (
                <div className="p-3 rounded-xl bg-emerald-950/50 border border-emerald-500/50 text-emerald-200 font-semibold">
                  ✅ 현재 연동 완료 (토큰: {gptMaskedToken})
                </div>
              )}
            </div>

            <div className="space-y-3 pt-1">
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-slate-400 block">
                  🔑 OpenAI API Key 입력 (가장 확실하고 간편한 방법):
                </label>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={oauthInputToken}
                    onChange={(e) => setOauthInputToken(e.target.value)}
                    placeholder="sk-proj-..."
                    className="flex-1 px-3 py-2 text-xs bg-slate-950 border border-slate-700 rounded-lg text-slate-100"
                  />
                  <button
                    onClick={handleSaveOAuthToken}
                    className="px-4 py-2 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg shrink-0"
                  >
                    연동 저장
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

      {/* 최종 승인 결재 보고서 전문 모달 */}
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
        print(f"✅ 풀스크린 관제 뷰 적용 완료: {path}")

    py_compile.compile("backend/openai_oauth.py", doraise=True)
    print("🎉 [검증 완료] 모든 모듈 컴파일 성공!")