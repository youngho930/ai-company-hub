import os

HIGH_QUALITY_PIXEL_OFFICE = r''''use client';

import React, { useEffect, useRef, useState } from 'react';
import { useOfficeStore } from '@/store/useOfficeStore';

interface Point {
  x: number;
  y: number;
}

type RoomId = 'RESEARCH' | 'DEV' | 'MEETING' | 'LOUNGE' | 'CORRIDOR';

interface SpriteAgent {
  id: string;
  name: string;
  dept: string;
  role: 'CEO' | 'SUPERVISOR' | 'WORKER1' | 'WORKER2';
  x: number;
  y: number;
  waypoints: Point[];
  finalTargetKey: string;
  facing: 'DOWN' | 'UP' | 'LEFT' | 'RIGHT';
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

// 각 방의 출입문(Doorway) 및 중앙 복도 교차점 정의
const DOORS: Record<RoomId, Point> = {
  RESEARCH: { x: 356, y: 145 },
  DEV: { x: 444, y: 145 },
  MEETING: { x: 356, y: 435 },
  LOUNGE: { x: 444, y: 435 },
  CORRIDOR: { x: 400, y: 280 },
};

// 주요 좌석 및 대기 위치 정의
const SPOTS: Record<string, { x: number; y: number; room: RoomId }> = {
  RESEARCH_DESK_1: { x: 115, y: 142, room: 'RESEARCH' },
  RESEARCH_DESK_2: { x: 245, y: 142, room: 'RESEARCH' },
  DEV_DESK_1: { x: 545, y: 142, room: 'DEV' },
  DEV_DESK_2: { x: 675, y: 142, room: 'DEV' },
  CEO_SEAT: { x: 145, y: 425, room: 'MEETING' },
  MEETING_SUP: { x: 235, y: 425, room: 'MEETING' },
  MEETING_W1: { x: 135, y: 495, room: 'MEETING' },
  MEETING_W2: { x: 245, y: 495, room: 'MEETING' },
  LOUNGE_SOFA_1: { x: 545, y: 435, room: 'LOUNGE' },
  LOUNGE_SOFA_2: { x: 655, y: 475, room: 'LOUNGE' },
  CORRIDOR_PATROL: { x: 400, y: 265, room: 'CORRIDOR' },
};

function getRoomAt(x: number, y: number): RoomId {
  if (x < 350 && y < 255) return 'RESEARCH';
  if (x > 450 && y < 255) return 'DEV';
  if (x < 350 && y > 320) return 'MEETING';
  if (x > 450 && y > 320) return 'LOUNGE';
  return 'CORRIDOR';
}

// 벽을 뚫지 않고 반드시 문과 복도를 거쳐 이동하는 웨이포인트 경로 생성기
function buildRoomPath(curX: number, curY: number, destSpot: { x: number; y: number; room: RoomId }): Point[] {
  const curRoom = getRoomAt(curX, curY);
  const targetRoom = destSpot.room;
  const pts: Point[] = [];

  if (curRoom === targetRoom) {
    pts.push({ x: destSpot.x, y: destSpot.y });
    return pts;
  }

  // 1) 현재 방에서 문으로 나가기
  if (curRoom !== 'CORRIDOR') {
    const exitDoor = DOORS[curRoom];
    pts.push({ x: exitDoor.x, y: exitDoor.y });
    pts.push({ x: 400, y: exitDoor.y });
  } else {
    pts.push({ x: 400, y: curY });
  }

  // 2) 복도를 따라 목표 방의 문 앞 높낮이로 이동
  if (targetRoom !== 'CORRIDOR') {
    const enterDoor = DOORS[targetRoom];
    pts.push({ x: 400, y: enterDoor.y });
    pts.push({ x: enterDoor.x, y: enterDoor.y });
  }

  // 3) 최종 목적지 좌석으로 이동
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

  const { nodes, messages, metrics } = useOfficeStore();

  useEffect(() => {
    speedRef.current = speedMult;
  }, [speedMult]);

  // 새 로그가 추가될 때마다 하단 이벤트 창 자동 스크롤
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [messages]);

  // Zustand 상태를 캐릭터 목표 지점 및 웨이포인트로 변환
  useEffect(() => {
    const currentMap = agentsRef.current;
    const latestMsgByAgent: Record<string, string> = {};
    messages.forEach((m) => {
      const txt = (m.payload?.text || m.payload?.rejectReason || '').replace(/\s+/g, ' ').trim();
      if (txt) latestMsgByAgent[m.agentId] = txt;
    });

    const lastEvent = messages[messages.length - 1];
    const isRejectMoment = lastEvent?.type === 'QC_REJECT';

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
      { hair: '#67e8f9', shade: '#0891b2', shirt: '#1e40af' }, // 실무자1 (민트 헤어)
      { hair: '#c084fc', shade: '#7e22ce', shirt: '#065f46' }, // 실무자2 (퍼플 헤어)
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

      let spotKey = 'LOUNGE_SOFA_1';
      let taskLabel = '대기 중';

      if (role === 'CEO') {
        spotKey = 'CEO_SEAT';
        taskLabel = '최종 결재·집무';
      } else if (role === 'SUPERVISOR') {
        if (isRejectMoment || status === 'REJECTED') {
          spotKey = 'MEETING_SUP';
          taskLabel = '🚨 QC 피드백 지시';
        } else if (status === 'WORKING') {
          spotKey = 'RESEARCH_DESK_2';
          taskLabel = '루브릭 품질 심사';
        } else if (status === 'DONE') {
          spotKey = 'MEETING_SUP';
          taskLabel = '최종 승인 완료';
        } else {
          spotKey = 'CORRIDOR_PATROL';
          taskLabel = '오피스 관제 중';
        }
      } else if (role === 'WORKER1') {
        if (isRejectMoment || status === 'REJECTED') {
          spotKey = 'MEETING_W1';
          taskLabel = 'QC 보완 회의 참석';
        } else if (status === 'WORKING' || status === 'REVIEWING') {
          spotKey = 'RESEARCH_DESK_1';
          taskLabel = '3단계 SoM 웹 탐색';
        } else if (status === 'DONE') {
          spotKey = 'LOUNGE_SOFA_1';
          taskLabel = '1차 팩트 수집 완료';
        } else {
          spotKey = 'LOUNGE_SOFA_1';
          taskLabel = '휴게실 대기';
        }
      } else {
        if (isRejectMoment) {
          spotKey = 'MEETING_W2';
          taskLabel = '보완 과제 인수';
        } else if (status === 'WORKING') {
          spotKey = 'DEV_DESK_1';
          taskLabel = '보고서 구조화·합성';
        } else if (status === 'DONE') {
          spotKey = 'DEV_DESK_2';
          taskLabel = '최종 보고서 완료';
        } else {
          spotKey = 'LOUNGE_SOFA_2';
          taskLabel = '휴게실 대기';
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
          facing: 'DOWN',
          status,
          hairColor: palettes[idx % palettes.length].hair,
          hairShade: palettes[idx % palettes.length].shade,
          shirtColor: palettes[idx % palettes.length].shirt,
          taskLabel,
          bubbleText: latestMsgByAgent[id] || '',
          progress: status === 'WORKING' ? 25 : status === 'DONE' ? 100 : 0,
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
        if (ag.finalTargetKey !== spotKey) {
          ag.finalTargetKey = spotKey;
          ag.waypoints = buildRoomPath(ag.x, ag.y, destSpot);
        }
        if (status === 'DONE') ag.progress = 100;
        else if (status === 'IDLE') ag.progress = 0;
      }
    });

    Object.keys(currentMap).forEach((k) => {
      if (!updatedIds.has(k)) delete currentMap[k];
    });
  }, [nodes, messages]);

  // 2. 고해상도 픽셀 아트 캔버스 렌더링 루프
  useEffect(() => {
    let animId: number;

    // 나무 마루 타일 (리서치실 & 회의실)
    const drawWoodRoom = (ctx: CanvasRenderingContext2D, rx: number, ry: number, rw: number, rh: number, base1: string, base2: string) => {
      const plankH = 16;
      const plankW = 48;
      for (let y = ry; y < ry + rh; y += plankH) {
        const rowIdx = Math.floor((y - ry) / plankH);
        for (let x = rx; x < rx + rw; x += plankW) {
          const colIdx = Math.floor((x - rx) / plankW);
          ctx.fillStyle = (rowIdx + colIdx) % 2 === 0 ? base1 : base2;
          const w = Math.min(plankW, rx + rw - x);
          const h = Math.min(plankH, ry + rh - y);
          ctx.fillRect(x, y, w, h);
          ctx.strokeStyle = 'rgba(0,0,0,0.18)';
          ctx.lineWidth = 1;
          ctx.strokeRect(x, y, w, h);
        }
      }
    };

    // 체크 타일 바닥 (복도, 개발실, 휴게실)
    const drawCheckTile = (ctx: CanvasRenderingContext2D, rx: number, ry: number, rw: number, rh: number, c1: string, c2: string, size = 24) => {
      for (let y = ry; y < ry + rh; y += size) {
        for (let x = rx; x < rx + rw; x += size) {
          const isEven = (Math.floor(x / size) + Math.floor(y / size)) % 2 === 0;
          ctx.fillStyle = isEven ? c1 : c2;
          ctx.fillRect(x, y, Math.min(size, rx + rw - x), Math.min(size, ry + rh - y));
        }
      }
    };

    // 출입구가 뚫려 있는 입체 벽면 그리기
    const drawRoomWalls = (
      ctx: CanvasRenderingContext2D,
      rx: number,
      ry: number,
      rw: number,
      rh: number,
      doorSide: 'RIGHT' | 'LEFT',
      doorY: number
    ) => {
      // 상단 벽면(두께감 표현)
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(rx, ry, rw, 14);
      ctx.fillStyle = '#334155';
      ctx.fillRect(rx + 2, ry + 2, rw - 4, 8);

      // 외곽 테두리
      ctx.strokeStyle = '#0f172a';
      ctx.lineWidth = 5;
      ctx.strokeRect(rx, ry, rw, rh);

      // 출입문 영역 터주기 (문지방)
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
        // 깜빡이는 서버 상태 LED
        ctx.fillStyle = (f + i * 15) % 40 < 20 ? '#34d399' : '#38bdf8';
        ctx.fillRect(sx + 8, sy + 9 + i * 12, 4, 3);
        ctx.fillStyle = '#f43f5e';
        ctx.fillRect(sx + 15, sy + 9 + i * 12, 3, 3);
      }
    };

    const drawOfficeDesk = (ctx: CanvasRenderingContext2D, dx: number, dy: number, isWorking: boolean, f: number) => {
      // 등받이 회전의자 (캐릭터 뒤편)
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(dx - 14, dy - 18, 28, 12);
      ctx.fillStyle = '#334155';
      ctx.fillRect(dx - 12, dy - 16, 24, 8);

      // 책상 그림자 및 본체
      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.fillRect(dx - 44, dy + 6, 88, 36);
      ctx.fillStyle = '#78350f';
      ctx.fillRect(dx - 42, dy + 2, 84, 32);
      ctx.fillStyle = '#b45309';
      ctx.fillRect(dx - 40, dy + 4, 80, 24);
      // 책상 전면 가림판
      ctx.fillStyle = '#451a03';
      ctx.fillRect(dx - 40, dy + 28, 80, 6);

      // 노트북 & 모니터 (책상 위)
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(dx - 18, dy - 2, 36, 18);
      ctx.fillStyle = isWorking ? (f % 36 < 18 ? '#38bdf8' : '#34d399') : '#475569';
      ctx.fillRect(dx - 15, dy, 30, 13);
      // 키보드 & 마우스패드
      ctx.fillStyle = '#cbd5e1';
      ctx.fillRect(dx - 12, dy + 18, 24, 5);
      // 머그컵
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(dx + 25, dy + 10, 7, 9);
      ctx.fillStyle = '#b45309';
      ctx.fillRect(dx + 26, dy + 11, 5, 3);
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

    // 귀여운 SD 도트 캐릭터 그리기 (머리 비율을 키워 인스타 영상 느낌 극대화)
    const drawChibiCharacter = (
      ctx: CanvasRenderingContext2D,
      ag: SpriteAgent,
      idx: number,
      isWalking: boolean,
      f: number
    ) => {
      // 걷기/타이핑 애니메이션 주기를 훨씬 차분하고 부드럽게 조절
      const walkCycle = isWalking ? Math.sin(f * 0.16 * speedRef.current + idx) : 0;
      const workBob = !isWalking && ag.status === 'WORKING' ? Math.sin(f * 0.12 + idx) * 1.0 : 0;
      const bounceY = isWalking ? Math.abs(walkCycle) * -3.2 : workBob;

      const cx = Math.round(ag.x);
      const cy = Math.round(ag.y + bounceY);

      // 1) 발밑 그림자 & 상태 링
      ctx.fillStyle =
        ag.status === 'REJECTED'
          ? 'rgba(244, 63, 94, 0.45)'
          : ag.status === 'WORKING'
          ? 'rgba(56, 189, 248, 0.38)'
          : 'rgba(0, 0, 0, 0.35)';
      ctx.beginPath();
      ctx.ellipse(cx, ag.y + 16, 14, 5.5, 0, 0, Math.PI * 2);
      ctx.fill();

      // 2) 신발 & 다리 (보행 시 교차)
      const leftLegY = isWalking ? Math.round(walkCycle * 3.5) : 0;
      const rightLegY = isWalking ? Math.round(-walkCycle * 3.5) : 0;
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(cx - 7, cy + 7 + leftLegY, 6, 8);
      ctx.fillRect(cx + 1, cy + 7 + rightLegY, 6, 8);

      // 3) 몸통 (정장/셔츠 + 넥타이/사원증 포인트)
      ctx.fillStyle = ag.shirtColor;
      ctx.fillRect(cx - 10, cy - 5, 20, 13);
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(cx - 2, cy - 4, 4, 7);
      ctx.fillStyle = ag.role === 'CEO' ? '#fbbf24' : '#38bdf8';
      ctx.fillRect(cx - 1, cy - 2, 2, 5);

      // 4) 양팔
      const armOffset = ag.status === 'WORKING' ? Math.round(Math.sin(f * 0.28 + idx) * 2) : Math.round(walkCycle * 2);
      ctx.fillStyle = ag.shirtColor;
      ctx.fillRect(cx - 14, cy - 4 + armOffset, 4, 10);
      ctx.fillRect(cx + 10, cy - 4 - armOffset, 4, 10);
      // 손
      ctx.fillStyle = '#fed7aa';
      ctx.fillRect(cx - 14, cy + 5 + armOffset, 4, 3);
      ctx.fillRect(cx + 10, cy + 5 - armOffset, 4, 3);

      // 5) 큼직한 SD 헤드 & 얼굴
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(cx - 14, cy - 28, 28, 24); // 외곽선
      ctx.fillStyle = '#ffedd5';
      ctx.fillRect(cx - 12, cy - 25, 24, 20); // 피부

      // 볼터치
      ctx.fillStyle = '#fda4af';
      ctx.fillRect(cx - 10, cy - 12, 3, 2);
      ctx.fillRect(cx + 7, cy - 12, 3, 2);

      // 눈 (자연스러운 깜빡임)
      if ((f + idx * 37) % 180 > 6) {
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(cx - 7, cy - 16, 3, 5);
        ctx.fillRect(cx + 4, cy - 16, 3, 5);
        // 눈동자 하이라이트
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(cx - 6, cy - 16, 1, 2);
        ctx.fillRect(cx + 5, cy - 16, 1, 2);
      } else {
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(cx - 7, cy - 14, 3, 1);
        ctx.fillRect(cx + 4, cy - 14, 3, 1);
      }

      // 6) 입체 도트 헤어스타일 (윗머리 + 앞머리 + 옆머리 + 하이라이트)
      ctx.fillStyle = ag.hairShade;
      ctx.fillRect(cx - 14, cy - 29, 28, 6);
      ctx.fillStyle = ag.hairColor;
      ctx.fillRect(cx - 13, cy - 28, 26, 8);
      // 앞머리 뱅
      ctx.fillRect(cx - 10, cy - 21, 6, 4);
      ctx.fillRect(cx - 1, cy - 21, 5, 3);
      ctx.fillRect(cx + 6, cy - 21, 5, 4);
      // 옆머리
      ctx.fillRect(cx - 14, cy - 23, 3, 12);
      ctx.fillRect(cx + 11, cy - 23, 3, 12);
      // 엔젤링 헤어 하이라이트
      ctx.fillStyle = 'rgba(255,255,255,0.45)';
      ctx.fillRect(cx - 8, cy - 26, 16, 2);

      // 7) 하단 이름표 & 프로그레스 바 (영상 속 깔끔한 다크 UI 카드 스타일)
      const labelY = ag.y + 20;
      ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
      ctx.fillRect(cx - 46, labelY, 92, 30);
      ctx.strokeStyle =
        ag.status === 'REJECTED' ? '#f43f5e' : ag.status === 'WORKING' ? '#38bdf8' : '#475569';
      ctx.lineWidth = 1.2;
      ctx.strokeRect(cx - 46, labelY, 92, 30);

      // 이름 텍스트
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(ag.name.replace(' (CEO)', ''), cx, labelY + 12);

      // 프로그레스 바 배경 및 게이지
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(cx - 42, labelY + 16, 84, 10);
      if (ag.progress > 0) {
        ctx.fillStyle = ag.status === 'DONE' ? '#10b981' : '#0ea5e9';
        ctx.fillRect(cx - 42, labelY + 16, Math.round((84 * ag.progress) / 100), 10);
      }
      ctx.fillStyle = '#e2e8f0';
      ctx.font = 'bold 8.5px sans-serif';
      ctx.fillText(ag.taskLabel.slice(0, 12), cx, labelY + 24);
    };

    const render = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      frameCountRef.current += 1;
      const f = frameCountRef.current;

      ctx.clearRect(0, 0, CW, CH);

      // 1) 중앙 십자 복도 바닥
      drawCheckTile(ctx, 0, 0, CW, CH, '#475569', '#3b4758', 24);

      // 2) 좌상단: 리서치실
      drawWoodRoom(ctx, 18, 16, 332, 236, '#854d0e', '#713f12');
      drawRoomWalls(ctx, 18, 16, 332, 236, 'RIGHT', DOORS.RESEARCH.y);
      drawBookshelf(ctx, 32, 24);
      drawBookshelf(ctx, 104, 24);
      drawBookshelf(ctx, 268, 24);
      drawPlant(ctx, 200, 48);

      // 3) 우상단: 개발·합성실
      drawCheckTile(ctx, 450, 16, 332, 236, '#1e3a5f', '#172554', 20);
      drawRoomWalls(ctx, 450, 16, 332, 236, 'LEFT', DOORS.DEV.y);
      drawServerRack(ctx, 468, 24, f);
      drawServerRack(ctx, 518, 24, f + 10);
      drawBookshelf(ctx, 698, 24);
      drawPlant(ctx, 610, 48);

      // 4) 좌하단: 결재·회의실
      drawWoodRoom(ctx, 18, 308, 332, 236, '#9a3412', '#7c2d12');
      drawRoomWalls(ctx, 18, 308, 332, 236, 'RIGHT', DOORS.MEETING.y);
      // 회의실 베이지 카펫 & 대형 원형 테이블
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
      // 테이블 위 결재 서류철
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(178, 448, 24, 16);
      drawPlant(ctx, 44, 350);

      // 5) 우하단: 휴게실
      drawCheckTile(ctx, 450, 308, 332, 236, '#334155', '#1e293b', 20);
      drawRoomWalls(ctx, 450, 308, 332, 236, 'LEFT', DOORS.LOUNGE.y);
      // 잔디색 라운지 러그
      ctx.fillStyle = '#065f46';
      ctx.fillRect(500, 390, 235, 125);
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 2;
      ctx.strokeRect(500, 390, 235, 125);
      // 소파 & 커피 스테이션
      ctx.fillStyle = '#2563eb';
      ctx.fillRect(520, 340, 115, 28);
      ctx.fillStyle = '#60a5fa';
      ctx.fillRect(524, 344, 107, 16);
      // 커피머신 테이블
      ctx.fillStyle = '#57534e';
      ctx.fillRect(675, 330, 55, 36);
      ctx.fillStyle = '#dc2626';
      ctx.fillRect(690, 322, 22, 24);
      drawPlant(ctx, 750, 355);
      drawPlant(ctx, 476, 515);

      const agentList = Object.values(agentsRef.current);
      const isDeskBusy = (sx: number, sy: number) =>
        agentList.some((a) => a.status === 'WORKING' && Math.hypot(a.x - sx, a.y - sy) < 32);

      // 6) 에이전트 이동 업데이트 (먼저 좌표를 갱신)
      const walkingMap: Record<string, boolean> = {};
      agentList.forEach((ag) => {
        let walking = false;
        if (ag.waypoints.length > 0) {
          const nextPt = ag.waypoints[0];
          const dx = nextPt.x - ag.x;
          const dy = nextPt.y - ag.y;
          const dist = Math.hypot(dx, dy);
          // 이전보다 훨씬 차분하고 자연스러운 보행 속도 (기본 1.65px/frame)
          const step = 1.65 * speedRef.current;

          if (dist <= step) {
            ag.x = nextPt.x;
            ag.y = nextPt.y;
            ag.waypoints.shift();
          } else {
            ag.x += (dx / dist) * step;
            ag.y += (dy / dist) * step;
            walking = true;
          }
        }
        walkingMap[ag.id] = walking;
        if (ag.status === 'WORKING' && !walking) {
          ag.progress = Math.min(96, ag.progress + 0.12 * speedRef.current);
        }
      });

      // 7) Y좌표 정렬(Depth Sorting)로 캐릭터와 책상의 앞뒤 입체감 표현
      agentList
        .slice()
        .sort((a, b) => a.y - b.y)
        .forEach((ag, idx) => {
          drawChibiCharacter(ctx, ag, idx, walkingMap[ag.id], f);
        });

      // 책상을 캐릭터 앞쪽에 배치하여 의자에 앉아 책상 앞에 있는 듯한 레이어 연출
      drawOfficeDesk(ctx, SPOTS.RESEARCH_DESK_1.x, SPOTS.RESEARCH_DESK_1.y + 8, isDeskBusy(SPOTS.RESEARCH_DESK_1.x, SPOTS.RESEARCH_DESK_1.y), f);
      drawOfficeDesk(ctx, SPOTS.RESEARCH_DESK_2.x, SPOTS.RESEARCH_DESK_2.y + 8, isDeskBusy(SPOTS.RESEARCH_DESK_2.x, SPOTS.RESEARCH_DESK_2.y), f);
      drawOfficeDesk(ctx, SPOTS.DEV_DESK_1.x, SPOTS.DEV_DESK_1.y + 8, isDeskBusy(SPOTS.DEV_DESK_1.x, SPOTS.DEV_DESK_1.y), f);
      drawOfficeDesk(ctx, SPOTS.DEV_DESK_2.x, SPOTS.DEV_DESK_2.y + 8, isDeskBusy(SPOTS.DEV_DESK_2.x, SPOTS.DEV_DESK_2.y), f);

      // 8) 방 이름 뱃지
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

      // 9) 말풍선 충돌 방지 렌더링 (근처에 다른 캐릭터가 있으면 위아래 스태거링)
      agentList.forEach((ag, idx) => {
        if (!ag.bubbleText) return;
        const bw = 152;
        const bh = 22;
        const bx = Math.max(12, Math.min(CW - bw - 12, ag.x - bw / 2));
        // 짝수/홀수 인덱스에 따라 말풍선 높이를 다르게 배치해 회의실에서도 절대 겹치지 않도록 처리
        const staggerOffset = (idx % 2) * 24;
        const by = Math.max(8, ag.y - 56 - staggerOffset);

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
      });

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, []);

  return (
    <div className="relative w-full h-full flex flex-col bg-slate-950 overflow-hidden select-none">
      {/* 상단 상태 & 애니메이션 배속 컨트롤 바 */}
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

      {/* 중앙 2D RPG 캔버스 */}
      <div className="flex-1 min-h-0 flex items-center justify-center p-2 bg-slate-950">
        <canvas
          ref={canvasRef}
          width={CW}
          height={CH}
          className="w-full h-full object-contain rounded-xl border border-slate-800 shadow-2xl bg-slate-900"
        />
      </div>

      {/* 하단 실시간 이벤트 패널 (고정 헤더와 스크롤 본문을 완전히 분리하여 글씨 겹침 원천 해결!) */}
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
        f.write(HIGH_QUALITY_PIXEL_OFFICE)
    print("✅ 고품질 2D 도트 오피스(복도 길찾기 + 속도 제어 + 로그 겹침 해결) 적용 완료!")