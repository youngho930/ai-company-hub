import os

PIXEL_OFFICE_COMPONENT = r''''use client';

import React, { useEffect, useRef } from 'react';
import { useOfficeStore } from '@/store/useOfficeStore';

interface SpriteAgent {
  id: string;
  name: string;
  dept: string;
  role: 'CEO' | 'SUPERVISOR' | 'WORKER1' | 'WORKER2';
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  status: string;
  hairColor: string;
  shirtColor: string;
  taskLabel: string;
  bubbleText: string;
  progress: number;
}

// 캔버스 논리 해상도 (800 x 620)
const CW = 800;
const CH = 620;

// 방별 주요 좌석 좌표 정의 (인스타 영상과 동일한 4분할 구조)
const SPOTS = {
  RESEARCH_DESK_1: { x: 140, y: 135 }, // 좌상단: 리서치실 좌측 책상
  RESEARCH_DESK_2: { x: 265, y: 135 }, // 좌상단: 리서치실 우측 책상
  DEV_DESK_1: { x: 545, y: 135 },      // 우상단: 개발실 좌측 책상
  DEV_DESK_2: { x: 675, y: 135 },      // 우상단: 개발실 우측 책상
  MEETING_TOP: { x: 200, y: 430 },     // 좌하단: 회의실 원형 테이블 상단 (CEO/팀장)
  MEETING_LEFT: { x: 135, y: 485 },    // 좌하단: 회의실 좌측 (실무자1)
  MEETING_RIGHT: { x: 265, y: 485 },   // 좌하단: 회의실 우측 (실무자2)
  LOUNGE_1: { x: 560, y: 450 },        // 우하단: 휴게실 대기석 1
  LOUNGE_2: { x: 650, y: 490 },        // 우하단: 휴게실 대기석 2
  CORRIDOR_CENTER: { x: 400, y: 310 }, // 중앙 십자 복도 교차점
};

export default function PixelRpgOffice() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const agentsRef = useRef<Record<string, SpriteAgent>>({});
  const frameCountRef = useRef<number>(0);

  const { nodes, messages, metrics } = useOfficeStore();

  // 1. Zustand 스토어의 에이전트 상태(nodes, messages)를 2D 캐릭터 목표 좌표로 실시간 동기화
  useEffect(() => {
    const currentMap = agentsRef.current;
    const latestMsgByAgent: Record<string, string> = {};
    messages.forEach((m) => {
      const txt = (m.payload?.text || m.payload?.rejectReason || '').replace(/\s+/g, ' ').trim();
      if (txt) latestMsgByAgent[m.agentId] = txt.slice(0, 26) + (txt.length > 26 ? '...' : '');
    });

    const lastEvent = messages[messages.length - 1];
    const isRejectMoment = lastEvent?.type === 'QC_REJECT';

    // 기본 4인 구성 (노드가 아직 없을 때도 오피스에 기본 캐릭터 배치)
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
      { hair: '#fbbf24', shirt: '#4f46e5' }, // CEO (금발 + 인디고 정장)
      { hair: '#f43f5e', shirt: '#be123c' }, // 팀장 (로즈 헤어 + 버건디)
      { hair: '#38bdf8', shirt: '#0284c7' }, // 실무자1 (민트/하늘색 헤어 - 영상 속 캐릭터 오마주)
      { hair: '#a855f7', shirt: '#7e22ce' }, // 실무자2 (퍼플 헤어)
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

      // 역할 및 현재 상태별 목표 방/책상 좌표 계산
      let target = SPOTS.LOUNGE_1;
      let taskLabel = '대기 중';

      if (role === 'CEO') {
        target = { x: 165, y: 425 };
        taskLabel = '총괄 집무·결재';
      } else if (role === 'SUPERVISOR') {
        if (isRejectMoment || status === 'REJECTED') {
          target = SPOTS.MEETING_TOP;
          taskLabel = '🚨 QC 반려 회의 소집';
        } else if (status === 'WORKING') {
          target = SPOTS.RESEARCH_DESK_2;
          taskLabel = '루브릭 품질 심사 중';
        } else if (status === 'DONE') {
          target = { x: 235, y: 425 };
          taskLabel = '최종 결재 상신 완료';
        } else {
          target = { x: 400, y: 245 };
          taskLabel = '오피스 순찰 중';
        }
      } else if (role === 'WORKER1') {
        if (isRejectMoment || status === 'REJECTED') {
          target = SPOTS.MEETING_LEFT;
          taskLabel = '팀장 피드백 수령';
        } else if (status === 'WORKING' || status === 'REVIEWING') {
          target = SPOTS.RESEARCH_DESK_1;
          taskLabel = 'Playwright 3단계 웹 탐색';
        } else if (status === 'DONE') {
          target = SPOTS.LOUNGE_1;
          taskLabel = '1차 팩트 추출 완료';
        } else {
          target = { x: 540, y: 450 };
          taskLabel = '휴게실 대기';
        }
      } else {
        // WORKER2
        if (isRejectMoment) {
          target = SPOTS.MEETING_RIGHT;
          taskLabel = '보완 지시 인수인계';
        } else if (status === 'WORKING') {
          target = SPOTS.DEV_DESK_1;
          taskLabel = 'Extractive RAG 보고서 합성';
        } else if (status === 'DONE') {
          target = SPOTS.DEV_DESK_2;
          taskLabel = '보고서 구조화 완료';
        } else {
          target = SPOTS.LOUNGE_2;
          taskLabel = '휴게실 대기';
        }
      }

      if (!currentMap[id]) {
        currentMap[id] = {
          id,
          name,
          dept,
          role,
          x: SPOTS.CORRIDOR_CENTER.x + (idx - 1.5) * 40,
          y: SPOTS.CORRIDOR_CENTER.y,
          targetX: target.x,
          targetY: target.y,
          status,
          hairColor: palettes[idx % palettes.length].hair,
          shirtColor: palettes[idx % palettes.length].shirt,
          taskLabel,
          bubbleText: latestMsgByAgent[id] || '',
          progress: status === 'WORKING' ? 35 : status === 'DONE' ? 100 : 0,
        };
      } else {
        currentMap[id].name = name;
        currentMap[id].dept = dept;
        currentMap[id].status = status;
        currentMap[id].targetX = target.x;
        currentMap[id].targetY = target.y;
        currentMap[id].taskLabel = taskLabel;
        if (latestMsgByAgent[id]) {
          currentMap[id].bubbleText = latestMsgByAgent[id];
        }
        if (status === 'DONE') currentMap[id].progress = 100;
        else if (status === 'IDLE') currentMap[id].progress = 0;
      }
    });

    Object.keys(currentMap).forEach((k) => {
      if (!updatedIds.has(k)) delete currentMap[k];
    });
  }, [nodes, messages]);

  // 2. 60FPS Canvas 2D 도트 오피스 & 캐릭터 애니메이션 루프
  useEffect(() => {
    let animId: number;

    const drawTileFloor = (
      ctx: CanvasRenderingContext2D,
      rx: number,
      ry: number,
      rw: number,
      rh: number,
      c1: string,
      c2: string,
      tileSize = 24
    ) => {
      for (let y = ry; y < ry + rh; y += tileSize) {
        for (let x = rx; x < rx + rw; x += tileSize) {
          const isEven = ((x / tileSize) + (y / tileSize)) % 2 === 0;
          ctx.fillStyle = isEven ? c1 : c2;
          ctx.fillRect(x, y, Math.min(tileSize, rx + rw - x), Math.min(tileSize, ry + rh - y));
        }
      }
    };

    const drawDeskWithMonitor = (
      ctx: CanvasRenderingContext2D,
      dx: number,
      dy: number,
      isActive: boolean,
      frame: number
    ) => {
      // 책상 그림자 및 상판
      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.fillRect(dx - 38, dy - 18, 76, 42);
      ctx.fillStyle = '#78350f';
      ctx.fillRect(dx - 36, dy - 22, 72, 36);
      ctx.fillStyle = '#92400e';
      ctx.fillRect(dx - 34, dy - 20, 68, 30);

      // 듀얼 모니터 & 노트북 화면 (작업 중일 때 화면이 반짝임)
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(dx - 22, dy - 30, 44, 18);
      ctx.fillStyle = isActive ? (frame % 20 < 10 ? '#38bdf8' : '#34d399') : '#334155';
      ctx.fillRect(dx - 19, dy - 28, 38, 13);

      // 모니터 스탠드 & 커피잔
      ctx.fillStyle = '#475569';
      ctx.fillRect(dx - 5, dy - 12, 10, 5);
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(dx + 22, dy - 12, 7, 8);
    };

    const drawBookshelf = (ctx: CanvasRenderingContext2D, bx: number, by: number) => {
      ctx.fillStyle = '#451a03';
      ctx.fillRect(bx, by, 68, 38);
      ctx.fillStyle = '#78350f';
      ctx.fillRect(bx + 3, by + 3, 62, 32);
      const bookColors = ['#ef4444', '#3b82f6', '#10b981', '#eab308', '#a855f7', '#ec4899'];
      for (let row = 0; row < 2; row++) {
        for (let i = 0; i < 7; i++) {
          ctx.fillStyle = bookColors[(i + row * 3) % bookColors.length];
          ctx.fillRect(bx + 6 + i * 8, by + 6 + row * 15, 6, 11);
        }
      }
    };

    const drawPlant = (ctx: CanvasRenderingContext2D, px: number, py: number) => {
      ctx.fillStyle = '#b45309';
      ctx.fillRect(px - 8, py, 16, 14);
      ctx.fillStyle = '#15803d';
      ctx.beginPath();
      ctx.arc(px, py - 6, 13, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#22c55e';
      ctx.beginPath();
      ctx.arc(px - 3, py - 9, 8, 0, Math.PI * 2);
      ctx.fill();
    };

    const render = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      frameCountRef.current += 1;
      const f = frameCountRef.current;

      ctx.clearRect(0, 0, CW, CH);

      // 1) 전체 배경 (중앙 십자 복도 타일)
      drawTileFloor(ctx, 0, 0, CW, CH, '#475569', '#3f4d63', 28);

      // 2) 좌상단: 리서치실 (우드 타일 + 책장 + 데스크 2개)
      drawTileFloor(ctx, 16, 16, 330, 240, '#78350f', '#71320d', 20);
      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 6;
      ctx.strokeRect(16, 16, 330, 240);
      drawBookshelf(ctx, 32, 24);
      drawBookshelf(ctx, 110, 24);
      drawBookshelf(ctx, 250, 24);
      drawPlant(ctx, 215, 48);

      // 3) 우상단: 개발실 (딥블루 코딩 타일 + 서버랙 + 데스크 2개)
      drawTileFloor(ctx, 454, 16, 330, 240, '#1e3a5f', '#172e4d', 20);
      ctx.strokeRect(454, 16, 330, 240);
      drawBookshelf(ctx, 475, 24);
      drawBookshelf(ctx, 690, 24);
      drawPlant(ctx, 610, 48);

      // 4) 좌하단: 회의실 & CEO 결재실 (옐로우 골드 카펫 + 원형 회의 테이블)
      drawTileFloor(ctx, 16, 355, 330, 248, '#a16207', '#935805', 20);
      ctx.strokeRect(16, 355, 330, 248);
      // 원형 회의 테이블
      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.beginPath();
      ctx.arc(200, 485, 52, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#b45309';
      ctx.beginPath();
      ctx.arc(200, 480, 50, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#d97706';
      ctx.beginPath();
      ctx.arc(200, 480, 42, 0, Math.PI * 2);
      ctx.fill();
      // 회의실 노트북/서류 아이콘
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(188, 468, 24, 16);
      drawPlant(ctx, 45, 395);

      // 5) 우하단: 휴게실 (그린/슬레이트 라운지 + 소파 + 커피머신)
      drawTileFloor(ctx, 454, 355, 330, 248, '#334155', '#2c3849', 20);
      ctx.strokeRect(454, 355, 330, 248);
      // 라운지 그린 러그
      ctx.fillStyle = '#065f46';
      ctx.fillRect(515, 425, 210, 125);
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 2;
      ctx.strokeRect(515, 425, 210, 125);
      // 소파
      ctx.fillStyle = '#3b82f6';
      ctx.fillRect(540, 385, 110, 28);
      drawPlant(ctx, 745, 395);
      drawPlant(ctx, 485, 560);

      // 방 이름 뱃지 (영상 속 스타일 그대로 재현)
      const drawRoomBadge = (label: string, bx: number, by: number, color: string) => {
        ctx.fillStyle = 'rgba(15, 23, 42, 0.88)';
        ctx.fillRect(bx, by, 92, 22);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(bx, by, 92, 22);
        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(label, bx + 46, by + 15);
      };

      drawRoomBadge('🔍 리서치실', 26, 26, '#38bdf8');
      drawRoomBadge('💻 개발·합성실', 464, 26, '#818cf8');
      drawRoomBadge('📋 결재·회의실', 26, 365, '#fbbf24');
      drawRoomBadge('☕ 휴게실', 464, 365, '#34d399');

      // 책상 렌더링 (에이전트가 근처에서 WORKING 중이면 모니터 점등)
      const agentList = Object.values(agentsRef.current);
      const isNearWorking = (tx: number, ty: number) =>
        agentList.some((a) => a.status === 'WORKING' && Math.hypot(a.x - tx, a.y - ty) < 40);

      drawDeskWithMonitor(ctx, SPOTS.RESEARCH_DESK_1.x, SPOTS.RESEARCH_DESK_1.y, isNearWorking(SPOTS.RESEARCH_DESK_1.x, SPOTS.RESEARCH_DESK_1.y), f);
      drawDeskWithMonitor(ctx, SPOTS.RESEARCH_DESK_2.x, SPOTS.RESEARCH_DESK_2.y, isNearWorking(SPOTS.RESEARCH_DESK_2.x, SPOTS.RESEARCH_DESK_2.y), f);
      drawDeskWithMonitor(ctx, SPOTS.DEV_DESK_1.x, SPOTS.DEV_DESK_1.y, isNearWorking(SPOTS.DEV_DESK_1.x, SPOTS.DEV_DESK_1.y), f);
      drawDeskWithMonitor(ctx, SPOTS.DEV_DESK_2.x, SPOTS.DEV_DESK_2.y, isNearWorking(SPOTS.DEV_DESK_2.x, SPOTS.DEV_DESK_2.y), f);

      // 6) 에이전트 캐릭터 이동(Pathfinding 보간) 및 도트 아바타 그리기
      agentList.forEach((ag, idx) => {
        const dx = ag.targetX - ag.x;
        const dy = ag.targetY - ag.y;
        const dist = Math.hypot(dx, dy);
        const isWalking = dist > 2.5;

        if (isWalking) {
          // 직각 복도 느낌을 살리기 위해 부드럽게 이동
          const speed = 3.2;
          ag.x += (dx / dist) * speed;
          ag.y += (dy / dist) * speed;
        } else {
          ag.x = ag.targetX;
          ag.y = ag.targetY;
        }

        if (ag.status === 'WORKING') {
          ag.progress = Math.min(95, ag.progress + 0.25);
        }

        // 걷거나 타이핑할 때 위아래 바운스 효과
        const bounce = isWalking
          ? Math.sin(f * 0.35 + idx) * 3.5
          : ag.status === 'WORKING'
          ? Math.sin(f * 0.25 + idx) * 1.2
          : 0;

        const cx = ag.x;
        const cy = ag.y + bounce;

        // 발밑 그림자 및 상태 오라(Aura)
        ctx.fillStyle =
          ag.status === 'REJECTED'
            ? 'rgba(244, 63, 94, 0.45)'
            : ag.status === 'WORKING'
            ? 'rgba(16, 185, 129, 0.4)'
            : 'rgba(0, 0, 0, 0.35)';
        ctx.beginPath();
        ctx.ellipse(ag.x, ag.y + 18, 15, 6, 0, 0, Math.PI * 2);
        ctx.fill();

        // 다리 (걸을 때 교차 애니메이션)
        const legOffset = isWalking ? Math.sin(f * 0.4) * 4 : 0;
        ctx.fillStyle = '#1e293b';
        ctx.fillRect(cx - 7, cy + 7 + legOffset, 5, 9);
        ctx.fillRect(cx + 2, cy + 7 - legOffset, 5, 9);

        // 몸통 (셔츠)
        ctx.fillStyle = ag.shirtColor;
        ctx.fillRect(cx - 10, cy - 6, 20, 15);

        // 팔 (타이핑 중일 때 빠르게 움직임)
        const armWave = ag.status === 'WORKING' ? Math.sin(f * 0.6) * 2.5 : 0;
        ctx.fillStyle = ag.shirtColor;
        ctx.fillRect(cx - 14, cy - 4 + armWave, 4, 11);
        ctx.fillRect(cx + 10, cy - 4 - armWave, 4, 11);

        // 얼굴 (피부톤)
        ctx.fillStyle = '#fde68a';
        ctx.fillRect(cx - 10, cy - 22, 20, 16);

        // 머리카락 (도트 캐릭터 스타일)
        ctx.fillStyle = ag.hairColor;
        ctx.fillRect(cx - 11, cy - 25, 22, 7);
        ctx.fillRect(cx - 12, cy - 22, 4, 11);
        ctx.fillRect(cx + 8, cy - 22, 4, 11);

        // 눈 (깜빡임 포함)
        if (f % 140 > 5) {
          ctx.fillStyle = '#0f172a';
          ctx.fillRect(cx - 5, cy - 14, 3, 4);
          ctx.fillRect(cx + 2, cy - 14, 3, 4);
        }

        // 이름표 & 직책 박스 (캐릭터 하단 - 인스타 영상 스타일)
        ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
        ctx.fillRect(ag.x - 42, ag.y + 22, 84, 18);
        ctx.strokeStyle =
          ag.status === 'REJECTED' ? '#f43f5e' : ag.status === 'WORKING' ? '#10b981' : '#475569';
        ctx.lineWidth = 1.2;
        ctx.strokeRect(ag.x - 42, ag.y + 22, 84, 18);

        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 10px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(ag.name.split(' ')[0], ag.x, ag.y + 34);

        // 영상 속 하단 프로그레스 게이지 바 & 현재 태스크 표시
        ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
        ctx.fillRect(ag.x - 52, ag.y + 42, 104, 15);
        if (ag.progress > 0) {
          ctx.fillStyle = ag.status === 'DONE' ? '#10b981' : '#38bdf8';
          ctx.fillRect(ag.x - 50, ag.y + 44, (100 * ag.progress) / 100, 11);
        }
        ctx.fillStyle = '#e2e8f0';
        ctx.font = '9px sans-serif';
        ctx.fillText(ag.taskLabel.slice(0, 13), ag.x, ag.y + 52);

        // 머리 위 실시간 말풍선 (보고/반려 메시지)
        if (ag.bubbleText) {
          const bw = 136;
          const bh = 22;
          const bx = Math.max(10, Math.min(CW - bw - 10, ag.x - bw / 2));
          const by = cy - 50;

          ctx.fillStyle = ag.status === 'REJECTED' ? '#881337' : '#ffffff';
          ctx.fillRect(bx, by, bw, bh);
          ctx.strokeStyle = ag.status === 'REJECTED' ? '#fb7185' : '#0f172a';
          ctx.lineWidth = 1.5;
          ctx.strokeRect(bx, by, bw, bh);

          ctx.fillStyle = ag.status === 'REJECTED' ? '#ffe4e6' : '#0f172a';
          ctx.font = 'bold 9.5px sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(ag.bubbleText.slice(0, 17), bx + bw / 2, by + 14);
        }
      });

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, []);

  return (
    <div className="relative w-full h-full flex flex-col bg-slate-950 overflow-hidden select-none">
      {/* 상단 미니 상태 바 (영상 속 상단 '오피스 서버 연결됨' 표시 재현) */}
      <div className="shrink-0 px-3 py-1.5 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between text-[11px]">
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-bold text-emerald-300">2D PIXEL AGENT OFFICE</span>
          <span className="text-slate-400 text-[10px]">| SSE 실시간 캐릭터 연동됨</span>
        </div>
        <div className="text-[10px] text-slate-400">
          가동 캐릭터: <strong className="text-sky-400">{Math.max(4, metrics.activeAgents + 1)}명</strong>
        </div>
      </div>

      {/* 메인 2D RPG 캔버스 */}
      <div className="flex-1 min-h-0 flex items-center justify-center p-2 bg-slate-950">
        <canvas
          ref={canvasRef}
          width={CW}
          height={CH}
          className="w-full h-full object-contain rounded-xl border border-slate-800 shadow-2xl bg-slate-900"
        />
      </div>

      {/* 하단 실시간 타임라인 미니 오버레이 (영상 하단 '최근 이벤트' 창 재현) */}
      <div className="shrink-0 h-24 bg-slate-950/95 border-t border-slate-800 px-3 py-1.5 overflow-y-auto font-mono text-[10px] space-y-1">
        <div className="text-amber-400 font-bold text-[10px] sticky top-0 bg-slate-950 pb-0.5">
          ⚡ 실시간 에이전트 룸 이동 & 액션 이벤트
        </div>
        {messages.length === 0 ? (
          <div className="text-slate-500">
            상단 [▶️ 업무 하달 실행]을 누르면 캐릭터들이 리서치실·개발실·회의실로 걸어가 업무를 수행합니다.
          </div>
        ) : (
          messages.slice(-5).map((m, idx) => (
            <div key={idx} className="flex items-center gap-2 truncate">
              <span className="text-slate-500 shrink-0">{m.timestamp}</span>
              <span
                className={`px-1.5 py-0.2 rounded text-[9px] font-bold shrink-0 ${
                  m.type === 'QC_REJECT'
                    ? 'bg-rose-900/70 text-rose-200'
                    : m.role === 'SUPERVISOR'
                    ? 'bg-indigo-900/70 text-indigo-200'
                    : 'bg-emerald-900/70 text-emerald-200'
                }`}
              >
                {m.agentName}
              </span>
              <span className="text-slate-300 truncate">
                {(m.payload.text || m.payload.rejectReason || '').replace(/\s+/g, ' ')}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
'''

if __name__ == "__main__":
    os.makedirs("src/components", exist_ok=True)
    with open("src/components/PixelRpgOffice.tsx", "w", encoding="utf-8") as f:
        f.write(PIXEL_OFFICE_COMPONENT)
    print("✅ 1. 2D 픽셀 RPG 오피스 컴포넌트 생성 완료: src/components/PixelRpgOffice.tsx")

    with open("src/app/page.tsx", "r", encoding="utf-8") as f:
        page_code = f.read()

    if "PixelRpgOffice" not in page_code:
        page_code = page_code.replace(
            "import VirtualOfficeFloor from '@/components/VirtualOfficeFloor';",
            "import VirtualOfficeFloor from '@/components/VirtualOfficeFloor';\nimport PixelRpgOffice from '@/components/PixelRpgOffice';"
        )
        # 기본 뷰를 바로 2D 픽셀 오피스('PIXEL')로 설정하고 3단 탭(2D 픽셀 오피스 / 카드 오피스 / React Flow 조직도) 지원
        page_code = page_code.replace(
            "const [leftViewMode, setLeftViewMode] = useState<'OFFICE' | 'GRAPH'>('OFFICE');",
            "const [leftViewMode, setLeftViewMode] = useState<'PIXEL' | 'OFFICE' | 'GRAPH'>('PIXEL');"
        )

        old_tabs = """          <div className="shrink-0 flex border-b border-slate-800 text-xs font-bold bg-slate-900/50">
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
          </div>"""

        new_tabs = """          <div className="shrink-0 flex border-b border-slate-800 text-[11px] font-bold bg-slate-900/50">
            <button
              onClick={() => setLeftViewMode('PIXEL')}
              className={`flex-1 py-2.5 transition ${
                leftViewMode === 'PIXEL'
                  ? 'border-b-2 border-emerald-500 text-emerald-400 bg-emerald-950/20'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🎮 2D 도트 오피스
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
              🕸️ 조직도
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-hidden">
            {leftViewMode === 'PIXEL' ? (
              <PixelRpgOffice />
            ) : leftViewMode === 'OFFICE' ? (
              <VirtualOfficeFloor />
            ) : (
              <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView colorMode="dark">
                <Background color="#334155" gap={16} />
                <Controls />
              </ReactFlow>
            )}
          </div>"""

        page_code = page_code.replace(old_tabs, new_tabs)
        with open("src/app/page.tsx", "w", encoding="utf-8") as f:
            f.write(page_code)
        print("✅ 2. 좌측 패널에 [🎮 2D 도트 오피스] 탭 연동 완료: src/app/page.tsx")