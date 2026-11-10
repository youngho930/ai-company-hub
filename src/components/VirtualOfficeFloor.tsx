'use client';

import React, { useMemo, useRef, useState, useEffect } from 'react';
import { useOfficeStore } from '@/store/useOfficeStore';
import { AgentStatus } from '@/types/agent';

interface FlyingDoc {
  id: string;
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
  label: string;
  icon: string;
  colorClass: string;
  lineColor: string;
  active: boolean;
}

export default function VirtualOfficeFloor() {
  const { nodes, messages, hitlData } = useOfficeStore();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const deskRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const lastWorkerIdRef = useRef<string>('wrk-web-01');
  const [flyingDocs, setFlyingDocs] = useState<FlyingDoc[]>([]);

  const latestMessageByAgent = useMemo(() => {
    const map: Record<string, { text: string; type: string; timestamp: string }> = {};
    messages.forEach((msg) => {
      map[msg.agentId] = {
        text: msg.payload.text || msg.payload.rejectReason || '',
        type: msg.type,
        timestamp: msg.timestamp,
      };
    });
    return map;
  }, [messages]);

  const officeDesks = useMemo(() => {
    if (nodes.length === 0) {
      return [
        { id: 'ceo', name: '신영호 대표 (CEO)', dept: '임원실', status: 'IDLE' as AgentStatus, isLeader: true },
        { id: 'sup-mkt-01', name: '김민준 팀장', dept: '마케팅·커머스전략실', status: 'IDLE' as AgentStatus, isLeader: true },
        { id: 'wrk-web-01', name: '이서연 수석', dept: '웹데이터수집팀', status: 'IDLE' as AgentStatus, isLeader: false },
        { id: 'wrk-doc-03', name: '박도윤 선임', dept: '콘텐츠·리포트팀', status: 'IDLE' as AgentStatus, isLeader: false },
      ];
    }
    return nodes.map((n) => ({
      id: n.id,
      name: String(n.data.name),
      dept: String(n.data.dept),
      status: (n.data.status || 'IDLE') as AgentStatus,
      isLeader: n.id === 'ceo' || n.id.startsWith('sup-'),
    }));
  }, [nodes]);

  const triggerDocumentFlight = (
    fromId: string,
    toId: string,
    icon: string,
    label: string,
    colorClass: string,
    lineColor: string
  ) => {
    const container = containerRef.current;
    const fromEl = deskRefs.current[fromId];
    const toEl = deskRefs.current[toId];
    if (!container || !fromEl || !toEl) return;

    const cRect = container.getBoundingClientRect();
    const fRect = fromEl.getBoundingClientRect();
    const tRect = toEl.getBoundingClientRect();

    // 스크롤 오프셋까지 보정하여 언제나 정확한 책상 중앙 좌표 계산
    const fromX = fRect.left - cRect.left + container.scrollLeft + fRect.width / 2;
    const fromY = fRect.top - cRect.top + container.scrollTop + fRect.height / 2;
    const toX = tRect.left - cRect.left + container.scrollLeft + tRect.width / 2;
    const toY = tRect.top - cRect.top + container.scrollTop + tRect.height / 2;

    const docId = `${Date.now()}-${Math.random()}`;
    setFlyingDocs((prev) => [
      ...prev,
      { id: docId, fromX, fromY, toX, toY, label, icon, colorClass, lineColor, active: false },
    ]);

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setFlyingDocs((prev) => prev.map((d) => (d.id === docId ? { ...d, active: true } : d)));
      });
    });

    setTimeout(() => {
      setFlyingDocs((prev) => prev.filter((d) => d.id !== docId));
    }, 900);
  };

  useEffect(() => {
    if (messages.length === 0) return;
    const lastMsg = messages[messages.length - 1];
    const supDesk = officeDesks.find((d) => d.id.startsWith('sup-')) || officeDesks[1];
    const defaultWorkerDesk = officeDesks.find((d) => !d.isLeader) || officeDesks[2];
    if (!supDesk || !defaultWorkerDesk) return;

    if (lastMsg.role === 'WORKER') {
      lastWorkerIdRef.current = lastMsg.agentId;
      triggerDocumentFlight(
        lastMsg.agentId,
        supDesk.id,
        '📄',
        '결재 보고서 상신',
        'bg-emerald-600 border-emerald-300 text-white shadow-[0_0_20px_rgba(16,185,129,0.85)]',
        '#10b981'
      );
    } else if (lastMsg.type === 'QC_REJECT') {
      const targetWId = lastMsg.payload.targetWorkerId || lastWorkerIdRef.current || defaultWorkerDesk.id;
      triggerDocumentFlight(
        supDesk.id,
        targetWId,
        '🚨',
        '반려·재작업 지시서',
        'bg-rose-600 border-rose-300 text-white shadow-[0_0_20px_rgba(244,63,94,0.85)]',
        '#f43f5e'
      );
    } else if (lastMsg.role === 'SUPERVISOR') {
      const fromId = lastMsg.agentId === 'ceo' ? 'ceo' : supDesk.id;
      const toId = lastMsg.agentId === 'ceo' ? supDesk.id : defaultWorkerDesk.id;
      triggerDocumentFlight(
        fromId,
        toId,
        '📋',
        '업무 지시·승인서',
        'bg-indigo-600 border-indigo-300 text-white shadow-[0_0_20px_rgba(99,102,241,0.85)]',
        '#6366f1'
      );
    }
  }, [messages, officeDesks]);

  return (
    <div
      ref={containerRef}
      className="relative flex flex-col h-full bg-slate-950 p-4 select-none overflow-y-auto overflow-x-hidden"
    >
      {/* 공중 서류 비행 레이어 */}
      <div className="pointer-events-none absolute inset-0 z-40 overflow-hidden">
        <svg className="w-full h-full absolute inset-0">
          {flyingDocs.map((doc) => (
            <line
              key={`line-${doc.id}`}
              x1={doc.fromX}
              y1={doc.fromY}
              x2={doc.toX}
              y2={doc.toY}
              stroke={doc.lineColor}
              strokeWidth="2.5"
              strokeDasharray="6 6"
              className="opacity-80 animate-pulse"
            />
          ))}
        </svg>

        {flyingDocs.map((doc) => {
          const currentX = doc.active ? doc.toX : doc.fromX;
          const currentY = doc.active ? doc.toY : doc.fromY;
          return (
            <div
              key={doc.id}
              style={{
                transform: `translate(${currentX - 65}px, ${currentY - 18}px) scale(${doc.active ? 1.06 : 0.85})`,
                transition: 'transform 780ms cubic-bezier(0.22, 1, 0.36, 1)',
              }}
              className={`absolute top-0 left-0 px-3 py-1 rounded-full border-2 text-[11px] font-extrabold flex items-center gap-1.5 whitespace-nowrap ${doc.colorClass}`}
            >
              <span>{doc.icon}</span>
              <span>{doc.label}</span>
            </div>
          );
        })}
      </div>

      {/* 오피스 상단 컨트롤 바 */}
      <div className="flex items-center justify-between mb-4 pb-2.5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span className="text-[11px] font-bold text-slate-200">
            {hitlData ? '🚨 CEO 긴급 결재 대기 중' : 'LIVE OFFICE FLOOR'}
          </span>
        </div>
        <button
          onClick={() => {
            const sup = officeDesks.find((d) => d.id.startsWith('sup-'))?.id || officeDesks[1]?.id;
            const wrk = officeDesks.find((d) => !d.isLeader)?.id || officeDesks[2]?.id;
            if (sup && wrk) {
              triggerDocumentFlight(
                wrk,
                sup,
                '📄',
                '결재 보고서 상신',
                'bg-emerald-600 border-emerald-300 text-white shadow-[0_0_20px_rgba(16,185,129,0.85)]',
                '#10b981'
              );
            }
          }}
          className="px-2.5 py-1 text-[10px] font-bold bg-slate-800 hover:bg-emerald-600 text-emerald-300 hover:text-white border border-emerald-500/40 rounded-lg transition"
        >
          📄 서류 비행 테스트 ➔
        </button>
      </div>

      {/* 데스크 그리드 */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-x-4 gap-y-20 pt-14 px-1 pb-6">
        {officeDesks.map((desk) => {
          const msg = latestMessageByAgent[desk.id];
          const isWorking = desk.status === 'WORKING';
          const isReviewing = desk.status === 'REVIEWING';
          const isRejected = desk.status === 'REJECTED' || msg?.type === 'QC_REJECT';
          const isDone = desk.status === 'DONE';

          return (
            <div
              key={desk.id}
              ref={(el) => {
                deskRefs.current[desk.id] = el;
              }}
              className={`relative rounded-2xl border-2 p-3.5 transition-all duration-300 ${
                isRejected
                  ? 'border-rose-500 bg-rose-950/25 shadow-[0_0_20px_rgba(244,63,94,0.3)]'
                  : isWorking
                  ? 'border-emerald-500 bg-emerald-950/20 shadow-[0_0_20px_rgba(16,185,129,0.25)]'
                  : isReviewing
                  ? 'border-amber-500 bg-amber-950/20'
                  : isDone
                  ? 'border-sky-500/60 bg-slate-900/80'
                  : 'border-slate-800 bg-slate-900/40 opacity-65'
              }`}
            >
              {(msg || isWorking) && (
                <div
                  key={msg?.timestamp || desk.status}
                  className={`absolute -top-16 left-2 right-2 z-20 px-3 py-1.5 rounded-2xl border shadow-xl transition-all duration-300 animate-bounce ${
                    msg?.type === 'QC_REJECT'
                      ? 'bg-rose-950 border-rose-400 text-rose-100'
                      : desk.isLeader
                      ? 'bg-indigo-950 border-indigo-400 text-indigo-100'
                      : 'bg-slate-800 border-emerald-400/80 text-slate-100'
                  }`}
                  style={{ animationIterationCount: 1.5, animationDuration: '0.45s' }}
                >
                  <div className="flex items-center justify-between text-[9px] mb-0.5 opacity-80">
                    <span className="font-bold">
                      {msg?.type === 'QC_REJECT' ? '🚨 팀장 반려 통보!' : '💬 실시간 말풍선'}
                    </span>
                    <span className="font-mono">{msg?.timestamp || '작성 중'}</span>
                  </div>
                  {msg ? (
                    <p className="text-[10px] font-medium line-clamp-2 leading-snug">{msg.text}</p>
                  ) : (
                    <p className="text-[10px] text-emerald-300">● ● ● 데이터 분석 및 타이핑 중...</p>
                  )}
                </div>
              )}

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center text-base font-extrabold border-2 ${
                      isWorking
                        ? 'bg-emerald-600 border-emerald-300 text-white'
                        : isRejected
                        ? 'bg-rose-600 border-rose-300 text-white animate-pulse'
                        : desk.isLeader
                        ? 'bg-indigo-600 border-indigo-300 text-white'
                        : 'bg-slate-800 border-slate-600 text-slate-300'
                    }`}
                  >
                    {desk.id === 'ceo' ? '👑' : desk.isLeader ? '👔' : '🧑‍💻'}
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-400">{desk.dept}</div>
                    <div className="text-xs font-bold text-white">{desk.name}</div>
                    <div className="text-[10px] font-mono text-emerald-400">
                      {isWorking && '⚡ 타이핑 중...'}
                      {isReviewing && '📤 결재 상신!'}
                      {isRejected && '🚨 반려 재작업!'}
                      {isDone && '✅ 승인 완료'}
                      {desk.status === 'IDLE' && '☕ 대기 중'}
                    </div>
                  </div>
                </div>

                <div className="px-2 py-1 rounded-lg border bg-slate-950 border-slate-800 text-right font-mono text-[9px] text-slate-400">
                  <div>🖥️ DESK</div>
                  <div className="font-bold">{desk.status}</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
