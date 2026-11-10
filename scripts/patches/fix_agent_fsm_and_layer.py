import os

PIXEL_FSM_FIXED = r''''use client';

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
  finalTargetKey: string;
  facing: Direction;
  status: string;
  hairColor: string;
  hairShade: string;
  shirtColor: string;
  taskLabel: string;
  bubbleText: string;
  progress: number;
}

const CW = 800;
const CH = 560;

// 각 방의 출입문 좌표
const DOORS: Record<RoomId, Point> = {
  RESEARCH: { x: 356, y: 150 },
  DEV: { x: 444, y: 150 },
  MEETING: { x: 356, y: 435 },
  LOUNGE: { x: 444, y: 435 },
  CORRIDOR: { x: 400, y: 280 },
};

// 좌석 좌표 (책상 아래쪽에서 위쪽 모니터를 바라보는 구조 + 위쪽에서 아래를 보는 구조 분리)
const SPOTS: Record<string, { x: number; y: number; room: RoomId; sitFacing: Direction }> = {
  RESEARCH_DESK_1: { x: 115, y: 138, room: 'RESEARCH', sitFacing: 'DOWN' },
  RESEARCH_DESK_2: { x: 245, y: 138, room: 'RESEARCH', sitFacing: 'DOWN' },
  DEV_DESK_1: { x: 545, y: 138, room: 'DEV', sitFacing: 'DOWN' },
  DEV_DESK_2: { x: 675, y: 138, room: 'DEV', sitFacing: 'DOWN' },
  CEO_SEAT: { x: 145, y: 420, room: 'MEETING', sitFacing: 'DOWN' },
  MEETING_SUP: { x: 235, y: 420, room: 'MEETING', sitFacing: 'DOWN' },
  MEETING_W1: { x: 145, y: 498, room: 'MEETING', sitFacing: 'UP' },
  MEETING_W2: { x: 235, y: 498, room: 'MEETING', sitFacing: 'UP' },
  LOUNGE_SOFA_1: { x: 555, y: 435, room: 'LOUNGE', sitFacing: 'DOWN' },
  LOUNGE_SOFA_2: { x: 655, y: 465, room: 'LOUNGE', sitFacing: 'LEFT' },
  CORRIDOR_PATROL: { x: 400, y: 265, room: 'CORRIDOR', sitFacing: 'DOWN' },
};

function getRoomAt(x: number, y: number): RoomId {
  if (x < 350 && y < 255) return 'RESEARCH';
  if (x > 450 && y < 255) return 'DEV';
  if (x < 350 && y > 305) return 'MEETING';
  if (x > 450 && y > 305) return 'LOUNGE';
  return 'CORRIDOR';
}

function buildRoomPath(curX: number, curY: number, destSpot: { x: number; y: number; room: RoomId }): Point[] {
  const curRoom = getRoomAt(curX, curY);
  const targetRoom = destSpot.room;
  const pts: Point[] = [];

  if (curRoom === targetRoom) {
    pts.push({ x: destSpot.x, y: destSpot.y });
    return pts;
  }

  if (curRoom !== 'CORRIDOR') {
    const exitDoor = DOORS[curRoom];
    pts.push({ x: exitDoor.x, y: exitDoor.y });
    pts.push({ x: 400, y: exitDoor.y });
  } else {
    pts.push({ x: 400, y: curY });
  }

  if (targetRoom !== 'CORRIDOR') {
    const enterDoor = DOORS[targetRoom];
    pts.push({ x: 400, y: enterDoor.y });
    pts.push({ x: enterDoor.x, y: enterDoor.y });
  }

  pts.push({ x: destSpot.x, y: destSpot.y });
  return pts;
}

export default function PixelRpgOffice() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const logContainerRef = useRef<HTMLDivElement | null>(null);
  const agentsRef = useRef<Record<string, SpriteAgent>>({});
  const frameCountRef = useRef<number>(0);
  const [speedMult, setSpeedMult] = useState<number>(1.0);
  const speedRef = useRef<number>(1.0);

  const { nodes, messages, finalReport } = useOfficeStore();

  useEffect(() => {
    speedRef.current = speedMult;
  }, [speedMult]);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [messages]);

  // [핵심 수정 1] 핑퐁(왔다갔다) 버그를 원천 차단하는 단방향 워크플로우 상태 머신(FSM)
  useEffect(() => {
    const currentMap = agentsRef.current;
    const latestMsgByAgent: Record<string, string> = {};
    messages.forEach((m) => {
      const txt = (m.payload?.text || m.payload?.rejectReason || '').replace(/\s+/g, ' ').trim();
      if (txt) latestMsgByAgent[m.agentId] = txt;
    });

    // 전체 메시지 히스토리를 기준으로 현재 미션의 단계(Phase)를 정확히 판별 (순간 이벤트로 흔들리지 않음!)
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
      { hair: '#f59e0b', shade: '#b45309', shirt: '#3730a3' }, // CEO
      { hair: '#fb7185', shade: '#be123c', shirt: '#9f1239' }, // 팀장
      { hair: '#67e8f9', shade: '#0891b2', shirt: '#1e40af' }, // 실무자1
      { hair: '#c084fc', shade: '#7e22ce', shirt: '#065f46' }, // 실무자2
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

      // [단방향 동선 규칙]
      // 미션 시작 전(IDLE): 실무자들은 휴게실 대기 -> 시작 시 각자 리서치실/개발실 착석 -> 반려/결재 시 회의실 집결 (중간에 휴게실로 절대 가지 않음!)
      let spotKey = 'LOUNGE_SOFA_1';
      let taskLabel = '대기 중';

      if (role === 'CEO') {
        spotKey = 'CEO_SEAT';
        taskLabel = isMissionFinished ? '✅ 최종 승인 완료' : '총괄 집무·결재';
      } else if (role === 'SUPERVISOR') {
        if (!hasStarted) {
          spotKey = 'CORRIDOR_PATROL';
          taskLabel = '오피스 관제 대기';
        } else if (isMissionFinished) {
          spotKey = 'MEETING_SUP';
          taskLabel = '✅ 결재 상신 완료';
        } else if (hasRejected) {
          spotKey = 'MEETING_SUP';
          taskLabel = '🚨 QC 피드백·검수';
        } else {
          spotKey = 'RESEARCH_DESK_2';
          taskLabel = '1차 조사 모니터링';
        }
      } else if (role === 'WORKER1') {
        if (!hasStarted) {
          spotKey = 'LOUNGE_SOFA_1';
          taskLabel = '휴게실 대기';
        } else if (hasRejected || isMissionFinished) {
          // 1차 조사를 마치고 QC 단계로 넘어가면 휴게실로 가지 않고 회의실 브리핑석으로 이동해 대기!
          spotKey = 'MEETING_W1';
          taskLabel = isMissionFinished ? '✅ 팩트 검증 완료' : '회의실 브리핑·대기';
        } else {
          spotKey = 'RESEARCH_DESK_1';
          taskLabel = '🔍 3단계 웹 탐색 중';
        }
      } else {
        // WORKER2 (보라색 머리)
        if (!hasStarted) {
          spotKey = 'LOUNGE_SOFA_2';
          taskLabel = '휴게실 대기';
        } else if (isMissionFinished) {
          spotKey = 'MEETING_W2';
          taskLabel = '✅ 최종 보고 완료';
        } else if (hasRejected || status === 'WORKING') {
          spotKey = 'DEV_DESK_2';
          taskLabel = '💻 보고서 작성·보완';
        } else {
          spotKey = 'DEV_DESK_1';
          taskLabel = '데이터 수신 대기';
        }
      }

      const destSpot = SPOTS[spotKey];

      if (!currentMap[id]) {
        currentMap[id] = {
          id,
          name,
          dept,
          role,
          x: destSpot.x,
          y: destSpot.y,
          waypoints: [],
          finalTargetKey: spotKey,
          facing: destSpot.sitFacing,
          status,
          hairColor: palettes[idx % palettes.length].hair,
          hairShade: palettes[idx % palettes.length].shade,
          shirtColor: palettes[idx % palettes.length].shirt,
          taskLabel,
          bubbleText: latestMsgByAgent[id] || '',
          progress: status === 'WORKING' ? 30 : status === 'DONE' ? 100 : 0,
        };
      } else {
        const ag = currentMap[id];
        ag.name = name;
        ag.dept = dept;
        ag.status = status;
        ag.taskLabel = taskLabel;
        if (latestMsgByAgent[id]) {
          ag.bubbleText = latestMsgByAgent[id];
        }
        // 목적지가 실제로 변경되었을 때만 새 경로 생성 (중간 경로 흔들림 방지)
        if (ag.finalTargetKey !== spotKey) {
          ag.finalTargetKey = spotKey;
          ag.waypoints = buildRoomPath(ag.x, ag.y, destSpot);
        }
        if (isMissionFinished || status === 'DONE') ag.progress = 100;
        else if (!hasStarted) ag.progress = 0;
      }
    });

    Object.keys(currentMap).forEach((k) => {
      if (!updatedIds.has(k)) delete currentMap[k];
    });
  }, [nodes, messages, finalReport]);

  // 2. 캔버스 렌더링 (레이어 Z-Index 분리 + 4방향 시선 애니메이션)
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

    const drawBookshelf = (ctx: CanvasRenderingContext2D, bx: number, by: number) => {
      ctx.fillStyle = 'rgba(0,0,0,0.3)';
      ctx.fillRect(bx + 3, by + 4, 62, 40);
      ctx.fillStyle = '#451a03';
      ctx.fillRect(bx, by, 62, 40);
      ctx.fillStyle = '#78350f';
      ctx.fillRect(bx + 3, by + 3, 56, 34);
      const colors = ['#f43f5e', '#38bdf8', '#10b981', '#fbbf24', '#a855f7', '#fb923c'];
      for (let r = 0; r < 2; r++) {
        ctx.fillStyle = '#290f02';
        ctx.fillRect(bx + 5, by + 6 + r * 16, 52, 13);
        for (let i = 0; i < 6; i++) {
          ctx.fillStyle = colors[(i + r * 2) % colors.length];
          ctx.fillRect(bx + 7 + i * 8, by + 8 + r * 16, 6, 11);
        }
      }
    };

    const drawServerRack = (ctx: CanvasRenderingContext2D, sx: number, sy: number, f: number) => {
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(sx, sy, 44, 44);
      ctx.strokeStyle = '#475569';
      ctx.lineWidth = 2;
      ctx.strokeRect(sx, sy, 44, 44);
      for (let i = 0; i < 3; i++) {
        ctx.fillStyle = '#1e293b';
        ctx.fillRect(sx + 5, sy + 6 + i * 12, 34, 9);
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
      ctx.fillRect(dx - 14, dy - 14, 28, 14);
      ctx.fillStyle = '#334155';
      ctx.fillRect(dx - 12, dy - 12, 24, 10);
    };

    const drawDeskSurface = (ctx: CanvasRenderingContext2D, dx: number, dy: number, isWorking: boolean, f: number) => {
      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.fillRect(dx - 44, dy + 10, 88, 34);
      ctx.fillStyle = '#78350f';
      ctx.fillRect(dx - 42, dy + 6, 84, 30);
      ctx.fillStyle = '#b45309';
      ctx.fillRect(dx - 40, dy + 8, 80, 22);
      ctx.fillStyle = '#451a03';
      ctx.fillRect(dx - 40, dy + 30, 80, 6);

      // 모니터 및 키보드
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(dx - 18, dy + 2, 36, 18);
      ctx.fillStyle = isWorking ? (f % 36 < 18 ? '#38bdf8' : '#34d399') : '#475569';
      ctx.fillRect(dx - 15, dy + 4, 30, 13);
      ctx.fillStyle = '#cbd5e1';
      ctx.fillRect(dx - 12, dy + 22, 24, 4);
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(dx + 25, dy + 13, 7, 9);
    };

    // [핵심 수정 2] 캐릭터 몸체만 그리는 함수 (4방향 시선 지원: 상/하/좌/우)
    const drawCharacterBody = (
      ctx: CanvasRenderingContext2D,
      ag: SpriteAgent,
      idx: number,
      isWalking: boolean,
      f: number
    ) => {
      const walkCycle = isWalking ? Math.sin(f * 0.15 * speedRef.current + idx) : 0;
      const workBob = !isWalking && ag.status === 'WORKING' ? Math.sin(f * 0.12 + idx) * 1.0 : 0;
      const bounceY = isWalking ? Math.abs(walkCycle) * -3.0 : workBob;

      const cx = Math.round(ag.x);
      const cy = Math.round(ag.y + bounceY);

      // 발밑 그림자
      ctx.fillStyle =
        ag.status === 'REJECTED'
          ? 'rgba(244, 63, 94, 0.45)'
          : ag.status === 'WORKING'
          ? 'rgba(56, 189, 248, 0.38)'
          : 'rgba(0, 0, 0, 0.35)';
      ctx.beginPath();
      ctx.ellipse(cx, ag.y + 15, 14, 5, 0, 0, Math.PI * 2);
      ctx.fill();

      // 다리
      const leftLegY = isWalking ? Math.round(walkCycle * 3.5) : 0;
      const rightLegY = isWalking ? Math.round(-walkCycle * 3.5) : 0;
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(cx - 7, cy + 6 + leftLegY, 6, 8);
      ctx.fillRect(cx + 1, cy + 6 + rightLegY, 6, 8);

      // 몸통
      ctx.fillStyle = ag.shirtColor;
      ctx.fillRect(cx - 10, cy - 6, 20, 13);
      if (ag.facing !== 'UP') {
        ctx.fillStyle = '#f8fafc';
        ctx.fillRect(cx - 2, cy - 5, 4, 7);
        ctx.fillStyle = ag.role === 'CEO' ? '#fbbf24' : '#38bdf8';
        ctx.fillRect(cx - 1, cy - 3, 2, 5);
      }

      // 양팔
      const armOffset = ag.status === 'WORKING' ? Math.round(Math.sin(f * 0.25 + idx) * 2) : Math.round(walkCycle * 2.5);
      ctx.fillStyle = ag.shirtColor;
      ctx.fillRect(cx - 14, cy - 5 + armOffset, 4, 10);
      ctx.fillRect(cx + 10, cy - 5 - armOffset, 4, 10);
      ctx.fillStyle = '#fed7aa';
      ctx.fillRect(cx - 14, cy + 4 + armOffset, 4, 3);
      ctx.fillRect(cx + 10, cy + 4 - armOffset, 4, 3);

      // 머리 외곽선 및 피부
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(cx - 14, cy - 29, 28, 24);

      if (ag.facing === 'UP') {
        // 뒷모습일 때는 얼굴 대신 뒷머리로 꽉 채움
        ctx.fillStyle = ag.hairColor;
        ctx.fillRect(cx - 13, cy - 28, 26, 22);
        ctx.fillStyle = ag.hairShade;
        ctx.fillRect(cx - 13, cy - 12, 26, 6);
      } else {
        ctx.fillStyle = '#ffedd5';
        ctx.fillRect(cx - 12, cy - 26, 24, 20);

        // 시선 방향(LEFT / RIGHT / DOWN)에 따른 눈과 볼터치 위치 이동
        const eyeShiftX = ag.facing === 'LEFT' ? -3 : ag.facing === 'RIGHT' ? 3 : 0;

        ctx.fillStyle = '#fda4af';
        ctx.fillRect(cx - 10 + eyeShiftX, cy - 13, 3, 2);
        ctx.fillRect(cx + 7 + eyeShiftX, cy - 13, 3, 2);

        if ((f + idx * 37) % 180 > 6) {
          ctx.fillStyle = '#0f172a';
          ctx.fillRect(cx - 7 + eyeShiftX, cy - 17, 3, 5);
          ctx.fillRect(cx + 4 + eyeShiftX, cy - 17, 3, 5);
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(cx - 6 + eyeShiftX, cy - 17, 1, 2);
          ctx.fillRect(cx + 5 + eyeShiftX, cy - 17, 1, 2);
        } else {
          ctx.fillStyle = '#0f172a';
          ctx.fillRect(cx - 7 + eyeShiftX, cy - 15, 3, 1);
          ctx.fillRect(cx + 4 + eyeShiftX, cy - 15, 3, 1);
        }

        // 윗머리 및 앞머리
        ctx.fillStyle = ag.hairShade;
        ctx.fillRect(cx - 14, cy - 30, 28, 6);
        ctx.fillStyle = ag.hairColor;
        ctx.fillRect(cx - 13, cy - 29, 26, 8);
        ctx.fillRect(cx - 10, cy - 22, 6, 4);
        ctx.fillRect(cx - 1, cy - 22, 5, 3);
        ctx.fillRect(cx + 6, cy - 22, 5, 4);
        ctx.fillRect(cx - 14, cy - 24, 3, 12);
        ctx.fillRect(cx + 11, cy - 24, 3, 12);
      }

      ctx.fillStyle = 'rgba(255,255,255,0.45)';
      ctx.fillRect(cx - 8, cy - 27, 16, 2);
    };

    // [핵심 수정 3] 이름표, 상태 게이지, 말풍선은 모든 가구(책상) 위에 그려서 절대 가려지지 않게 분리!
    const drawCharacterOverlayUI = (ctx: CanvasRenderingContext2D, ag: SpriteAgent, idx: number) => {
      const cx = Math.round(ag.x);
      // 책상에 앉아있을 때는 이름표를 책상 하단(ag.y + 42)에 배치해 책상과 겹치지 않게 처리
      const isAtDesk = ag.finalTargetKey.includes('DESK') && ag.waypoints.length === 0;
      const labelY = isAtDesk ? Math.round(ag.y + 44) : Math.round(ag.y + 20);

      ctx.fillStyle = 'rgba(15, 23, 42, 0.94)';
      ctx.fillRect(cx - 48, labelY, 96, 30);
      ctx.strokeStyle =
        ag.status === 'REJECTED' ? '#f43f5e' : ag.status === 'WORKING' ? '#38bdf8' : '#10b981';
      ctx.lineWidth = 1.4;
      ctx.strokeRect(cx - 48, labelY, 96, 30);

      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(ag.name.replace(' (CEO)', ''), cx, labelY + 12);

      ctx.fillStyle = '#1e293b';
      ctx.fillRect(cx - 44, labelY + 16, 88, 10);
      if (ag.progress > 0) {
        ctx.fillStyle = ag.status === 'DONE' || ag.progress >= 100 ? '#10b981' : '#0ea5e9';
        ctx.fillRect(cx - 44, labelY + 16, Math.round((88 * ag.progress) / 100), 10);
      }
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 8.5px sans-serif';
      ctx.fillText(ag.taskLabel.slice(0, 13), cx, labelY + 24);

      if (ag.bubbleText) {
        const bw = 156;
        const bh = 22;
        const bx = Math.max(12, Math.min(CW - bw - 12, cx - bw / 2));
        const staggerOffset = (idx % 2) * 25;
        const by = Math.max(8, Math.round(ag.y - 54 - staggerOffset));

        ctx.fillStyle = ag.status === 'REJECTED' ? '#881337' : '#ffffff';
        ctx.fillRect(bx, by, bw, bh);
        ctx.strokeStyle = ag.status === 'REJECTED' ? '#fb7185' : '#0f172a';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(bx, by, bw, bh);

        ctx.fillStyle = ag.status === 'REJECTED' ? '#ffe4e6' : '#0f172a';
        ctx.font = 'bold 9.5px sans-serif';
        ctx.textAlign = 'center';
        const cleanBubble = ag.bubbleText.slice(0, 18) + (ag.bubbleText.length > 18 ? '..' : '');
        ctx.fillText(cleanBubble, bx + bw / 2, by + 14);
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

      // Layer 1: 바닥 & 벽면 & 후면 가구
      drawCheckTile(ctx, 0, 0, CW, CH, '#475569', '#3b4758', 24);

      drawWoodRoom(ctx, 18, 16, 332, 236, '#854d0e', '#713f12');
      drawRoomWalls(ctx, 18, 16, 332, 236, 'RIGHT', DOORS.RESEARCH.y);
      drawBookshelf(ctx, 32, 24);
      drawBookshelf(ctx, 104, 24);
      drawBookshelf(ctx, 268, 24);
      drawPlant(ctx, 200, 48);

      drawCheckTile(ctx, 450, 16, 332, 236, '#1e3a5f', '#172554', 20);
      drawRoomWalls(ctx, 450, 16, 332, 236, 'LEFT', DOORS.DEV.y);
      drawServerRack(ctx, 468, 24, f);
      drawServerRack(ctx, 518, 24, f + 10);
      drawBookshelf(ctx, 698, 24);
      drawPlant(ctx, 610, 48);

      drawWoodRoom(ctx, 18, 308, 332, 236, '#9a3412', '#7c2d12');
      drawRoomWalls(ctx, 18, 308, 332, 236, 'RIGHT', DOORS.MEETING.y);
      ctx.fillStyle = '#fde68a';
      ctx.fillRect(70, 385, 240, 135);
      ctx.strokeStyle = '#d97706';
      ctx.lineWidth = 2;
      ctx.strokeRect(70, 385, 240, 135);

      ctx.fillStyle = 'rgba(0,0,0,0.3)';
      ctx.beginPath();
      ctx.arc(190, 462, 46, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#78350f';
      ctx.beginPath();
      ctx.arc(190, 456, 44, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#b45309';
      ctx.beginPath();
      ctx.arc(190, 456, 36, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(178, 448, 24, 16);
      drawPlant(ctx, 44, 350);

      drawCheckTile(ctx, 450, 308, 332, 236, '#334155', '#1e293b', 20);
      drawRoomWalls(ctx, 450, 308, 332, 236, 'LEFT', DOORS.LOUNGE.y);
      ctx.fillStyle = '#065f46';
      ctx.fillRect(500, 390, 235, 125);
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 2;
      ctx.strokeRect(500, 390, 235, 125);
      ctx.fillStyle = '#2563eb';
      ctx.fillRect(520, 340, 115, 28);
      ctx.fillStyle = '#60a5fa';
      ctx.fillRect(524, 344, 107, 16);
      ctx.fillStyle = '#57534e';
      ctx.fillRect(675, 330, 55, 36);
      ctx.fillStyle = '#dc2626';
      ctx.fillRect(690, 322, 22, 24);
      drawPlant(ctx, 750, 355);
      drawPlant(ctx, 476, 515);

      // Layer 2: 의자 등받이 (캐릭터 뒤편)
      drawChairBack(ctx, SPOTS.RESEARCH_DESK_1.x, SPOTS.RESEARCH_DESK_1.y);
      drawChairBack(ctx, SPOTS.RESEARCH_DESK_2.x, SPOTS.RESEARCH_DESK_2.y);
      drawChairBack(ctx, SPOTS.DEV_DESK_1.x, SPOTS.DEV_DESK_1.y);
      drawChairBack(ctx, SPOTS.DEV_DESK_2.x, SPOTS.DEV_DESK_2.y);

      const agentList = Object.values(agentsRef.current);
      const walkingMap: Record<string, boolean> = {};

      // 에이전트 이동 좌표 및 4방향 시선(facing) 업데이트
      agentList.forEach((ag) => {
        let walking = false;
        if (ag.waypoints.length > 0) {
          const nextPt = ag.waypoints[0];
          const dx = nextPt.x - ag.x;
          const dy = nextPt.y - ag.y;
          const dist = Math.hypot(dx, dy);
          const step = 1.6 * speedRef.current;

          if (Math.abs(dx) > Math.abs(dy)) {
            ag.facing = dx < 0 ? 'LEFT' : 'RIGHT';
          } else {
            ag.facing = dy < 0 ? 'UP' : 'DOWN';
          }

          if (dist <= step) {
            ag.x = nextPt.x;
            ag.y = nextPt.y;
            ag.waypoints.shift();
            if (ag.waypoints.length === 0 && SPOTS[ag.finalTargetKey]) {
              ag.facing = SPOTS[ag.finalTargetKey].sitFacing;
            }
          } else {
            ag.x += (dx / dist) * step;
            ag.y += (dy / dist) * step;
            walking = true;
          }
        }
        walkingMap[ag.id] = walking;
        if (ag.status === 'WORKING' && !walking) {
          ag.progress = Math.min(96, ag.progress + 0.15 * speedRef.current);
        }
      });

      // Layer 3: 캐릭터 몸체 렌더링
      agentList
        .slice()
        .sort((a, b) => a.y - b.y)
        .forEach((ag, idx) => {
          drawCharacterBody(ctx, ag, idx, walkingMap[ag.id], f);
        });

      const isDeskBusy = (sx: number, sy: number) =>
        agentList.some((a) => Math.hypot(a.x - sx, a.y - sy) < 28);

      // Layer 4: 책상 상판 및 모니터 (캐릭터 하반신을 자연스럽게 덮어 착석 효과 연출)
      drawDeskSurface(ctx, SPOTS.RESEARCH_DESK_1.x, SPOTS.RESEARCH_DESK_1.y, isDeskBusy(SPOTS.RESEARCH_DESK_1.x, SPOTS.RESEARCH_DESK_1.y), f);
      drawDeskSurface(ctx, SPOTS.RESEARCH_DESK_2.x, SPOTS.RESEARCH_DESK_2.y, isDeskBusy(SPOTS.RESEARCH_DESK_2.x, SPOTS.RESEARCH_DESK_2.y), f);
      drawDeskSurface(ctx, SPOTS.DEV_DESK_1.x, SPOTS.DEV_DESK_1.y, isDeskBusy(SPOTS.DEV_DESK_1.x, SPOTS.DEV_DESK_1.y), f);
      drawDeskSurface(ctx, SPOTS.DEV_DESK_2.x, SPOTS.DEV_DESK_2.y, isDeskBusy(SPOTS.DEV_DESK_2.x, SPOTS.DEV_DESK_2.y), f);

      // Layer 5: 방 이름 뱃지
      const drawBadge = (text: string, bx: number, by: number, borderColor: string) => {
        ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
        ctx.fillRect(bx, by, 96, 22);
        ctx.strokeStyle = borderColor;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(bx, by, 96, 22);
        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(text, bx + 48, by + 15);
      };
      drawBadge('🔍 리서치실', 28, 22, '#38bdf8');
      drawBadge('💻 개발·합성실', 460, 22, '#818cf8');
      drawBadge('📋 결재·회의실', 28, 314, '#fbbf24');
      drawBadge('☕ 휴게실', 460, 314, '#34d399');

      // Layer 6 (최상단): 캐릭터 이름표, 프로그레스 바, 말풍선 (책상에 절대 가려지지 않음!)
      agentList.forEach((ag, idx) => {
        drawCharacterOverlayUI(ctx, ag, idx);
      });

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, []);

  return (
    <div className="relative w-full h-full flex flex-col bg-slate-950 overflow-hidden select-none">
      <div className="shrink-0 px-3 py-1.5 bg-slate-900 border-b border-slate-800 flex items-center justify-between text-[11px]">
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-bold text-emerald-300">2D PIXEL AGENT OFFICE</span>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-slate-400 mr-1">이동 속도:</span>
          {[
            { label: '0.7x (여유)', val: 0.7 },
            { label: '1.0x (표준)', val: 1.0 },
            { label: '1.5x (빠름)', val: 1.5 },
          ].map((opt) => (
            <button
              key={opt.val}
              onClick={() => setSpeedMult(opt.val)}
              className={`px-2 py-0.5 rounded text-[10px] font-bold border transition ${
                speedMult === opt.val
                  ? 'bg-emerald-600 border-emerald-400 text-white'
                  : 'bg-slate-950 border-slate-700 text-slate-400 hover:text-slate-200'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 min-h-0 flex items-center justify-center p-2 bg-slate-950">
        <canvas
          ref={canvasRef}
          width={CW}
          height={CH}
          className="w-full h-full object-contain rounded-xl border border-slate-800 shadow-2xl bg-slate-900"
        />
      </div>

      <div className="shrink-0 h-28 bg-slate-950 border-t border-slate-800 flex flex-col overflow-hidden">
        <div className="shrink-0 px-3 py-1 bg-slate-900 border-b border-slate-800/80 flex items-center justify-between">
          <span className="text-amber-400 font-bold text-[10px]">
            ⚡ 실시간 에이전트 룸 이동 & 액션 이벤트 ({messages.length}건)
          </span>
          <span className="text-[9px] text-slate-400">마우스 휠 스크롤 가능 ↕</span>
        </div>

        <div
          ref={logContainerRef}
          className="flex-1 px-3 py-1.5 overflow-y-auto font-mono text-[10px] space-y-1.5"
        >
          {messages.length === 0 ? (
            <div className="text-slate-500 py-2">
              상단 [▶️ 업무 하달 실행]을 누르면 캐릭터들이 출입문과 복도를 따라 각 부서 방으로 이동합니다.
            </div>
          ) : (
            messages.map((m, idx) => (
              <div key={idx} className="flex items-start gap-2 leading-tight">
                <span className="text-slate-500 shrink-0">{m.timestamp}</span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[9px] font-bold shrink-0 ${
                    m.type === 'QC_REJECT'
                      ? 'bg-rose-900/80 text-rose-200'
                      : m.role === 'SUPERVISOR'
                      ? 'bg-indigo-900/80 text-indigo-200'
                      : 'bg-emerald-900/80 text-emerald-200'
                  }`}
                >
                  {m.agentName}
                </span>
                <span className="text-slate-300 break-all">
                  {(m.payload.text || m.payload.rejectReason || '').replace(/\s+/g, ' ')}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
'''

if __name__ == "__main__":
    with open("src/components/PixelRpgOffice.tsx", "w", encoding="utf-8") as f:
        f.write(PIXEL_FSM_FIXED)
    print("✅ 1. 단방향 워크플로우 FSM(핑퐁 방지) + 4방향 시선 + UI 레이어 분리 완료!")

    # 백엔드 workflow.py에서 캐릭터가 방으로 걸어갈 시간을 확보하도록 단계 전환 대기 시간을 0.6초 -> 1.8초로 자연스럽게 조정
    with open("backend/workflow.py", "r", encoding="utf-8") as f:
        wf = f.read()
    wf = wf.replace("await asyncio.sleep(0.6)", "await asyncio.sleep(1.8)")
    wf = wf.replace("await asyncio.sleep(0.4)", "await asyncio.sleep(1.5)")
    with open("backend/workflow.py", "w", encoding="utf-8") as f:
        f.write(wf)
    print("✅ 2. 백엔드 이벤트 호흡 조절 완료 (캐릭터 이동 시간 확보)")