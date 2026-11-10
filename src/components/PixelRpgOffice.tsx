'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useOfficeStore } from '@/store/useOfficeStore';

interface Point {
  x: number;
  y: number;
}

type DeptRoomKey = 'HR_ROOM' | 'DEV_ROOM' | 'QA_ROOM' | 'FIN_ROOM' | 'MEETING_ROOM' | 'MKT_ROOM';
type Direction = 'DOWN' | 'UP' | 'LEFT' | 'RIGHT';

interface StageItem {
  target: Point;
  via?: Point;
  workFrames: number;
  label: string;
  bubble: string;
  sitFacing: Direction;
  isShelfLookup?: boolean;
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  text?: string;
  color: string;
}

interface TrailPoint {
  x: number;
  y: number;
  life: number;
  maxLife: number;
  color: string;
  role: 'CEO' | 'SUPERVISOR' | 'WORKER1' | 'WORKER2';
}

interface OfficeStaff {
  id: string;
  name: string;
  deptTitle: string;
  roomKey: DeptRoomKey;
  role: 'CEO' | 'SUPERVISOR' | 'WORKER1' | 'WORKER2';
  homePos: Point;
  shelfPos: Point;
  x: number;
  y: number;
  vx: number;
  vy: number;
  waypoints: Point[];
  stageQueue: StageItem[];
  workTimer: number;
  maxWorkTimer: number;
  facing: Direction;
  hairColor: string;
  hairShade: string;
  shirtColor: string;
  accessory: 'GLASSES' | 'HEADSET' | 'CROWN_PIN' | 'SAFETY_BADGE' | 'NONE';
  isSelectedTeam: boolean;
  isShelfMode: boolean;
  carryingBook: boolean;
  taskLabel: string;
  activeBubble: string;
  lastBubbleText: string;
  bubbleAnim: number;
  progress: number;
  appliedPhase: number;
}

interface HoveredStaffInfo {
  name: string;
  deptTitle: string;
  role: string;
  taskLabel: string;
  progress: number;
  bubble: string;
  isSelected: boolean;
}

interface PixelRpgOfficeProps {
  onOpenReportModal?: () => void;
  onToggleLogDrawer?: () => void;
  unreadLogCount?: number;
  onAllGatheredChange?: (ready: boolean) => void;
}

const CW = 1120;
const CH = 640;
const CORRIDOR_Y = 305;

const ROOMS: Record<
  DeptRoomKey,
  {
    title: string;
    badgeColor: string;
    rx: number;
    ry: number;
    rw: number;
    rh: number;
    doorX: number;
    doorY: number;
    floorType: 'WOOD' | 'DARK_BLUE' | 'SLATE' | 'AMBER' | 'EMERALD';
    desks: Point[];
    shelf: Point;
  }
> = {
  HR_ROOM: {
    title: '🔍 리서치·인사팀',
    badgeColor: '#38bdf8',
    rx: 16,
    ry: 14,
    rw: 348,
    rh: 256,
    doorX: 190,
    doorY: 270,
    floorType: 'WOOD',
    desks: [
      { x: 95, y: 132 },
      { x: 205, y: 132 },
      { x: 285, y: 198 },
    ],
    shelf: { x: 145, y: 74 },
  },
  DEV_ROOM: {
    title: '💻 AI·SW개발팀',
    badgeColor: '#818cf8',
    rx: 386,
    ry: 14,
    rw: 348,
    rh: 256,
    doorX: 560,
    doorY: 270,
    floorType: 'DARK_BLUE',
    desks: [
      { x: 465, y: 132 },
      { x: 575, y: 132 },
      { x: 655, y: 198 },
    ],
    shelf: { x: 515, y: 74 },
  },
  QA_ROOM: {
    title: '🏭 품질·생산QA팀',
    badgeColor: '#34d399',
    rx: 756,
    ry: 14,
    rw: 348,
    rh: 256,
    doorX: 930,
    doorY: 270,
    floorType: 'SLATE',
    desks: [
      { x: 835, y: 132 },
      { x: 945, y: 132 },
      { x: 1025, y: 198 },
    ],
    shelf: { x: 885, y: 74 },
  },
  FIN_ROOM: {
    title: '📊 재무·데이터팀',
    badgeColor: '#fbbf24',
    rx: 16,
    ry: 342,
    rw: 348,
    rh: 280,
    doorX: 190,
    doorY: 342,
    floorType: 'EMERALD',
    desks: [
      { x: 95, y: 458 },
      { x: 205, y: 458 },
      { x: 285, y: 538 },
    ],
    shelf: { x: 145, y: 400 },
  },
  MEETING_ROOM: {
    title: '📋 중앙 결재·회의실',
    badgeColor: '#f59e0b',
    rx: 386,
    ry: 342,
    rw: 348,
    rh: 280,
    doorX: 560,
    doorY: 342,
    floorType: 'AMBER',
    desks: [],
    shelf: { x: 560, y: 390 },
  },
  MKT_ROOM: {
    title: '🛒 마케팅·전략팀',
    badgeColor: '#f472b6',
    rx: 756,
    ry: 342,
    rw: 348,
    rh: 280,
    doorX: 930,
    doorY: 342,
    floorType: 'WOOD',
    desks: [
      { x: 835, y: 458 },
      { x: 945, y: 458 },
      { x: 1025, y: 538 },
    ],
    shelf: { x: 885, y: 400 },
  },
};

const MEETING_TABLE_CENTER = { x: 560, y: 495 };
const MEETING_SEATS = {
  CEO: { x: 495, y: 445, facing: 'DOWN' as Direction },
  SUPERVISOR: { x: 625, y: 445, facing: 'DOWN' as Direction },
  WORKER1: { x: 495, y: 548, facing: 'UP' as Direction },
  WORKER2: { x: 625, y: 548, facing: 'UP' as Direction },
};

const INITIAL_ROSTER: Array<{
  id: string;
  name: string;
  deptTitle: string;
  roomKey: DeptRoomKey;
  role: 'CEO' | 'SUPERVISOR' | 'WORKER1' | 'WORKER2';
  deskIdx: number;
  hair: string;
  shade: string;
  shirt: string;
  accessory: 'GLASSES' | 'HEADSET' | 'CROWN_PIN' | 'SAFETY_BADGE' | 'NONE';
}> = [
  { id: 'ceo', name: '신영호 대표', deptTitle: '경영진', roomKey: 'MEETING_ROOM', role: 'CEO', deskIdx: 0, hair: '#f59e0b', shade: '#b45309', shirt: '#3730a3', accessory: 'CROWN_PIN' },
  { id: 'sup-hr-01', name: '윤지아 팀장', deptTitle: '인사·리서치팀', roomKey: 'HR_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#fb7185', shade: '#be123c', shirt: '#9f1239', accessory: 'GLASSES' },
  { id: 'wrk-hr-01', name: '박수아 수석', deptTitle: '인사·리서치팀', roomKey: 'HR_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#67e8f9', shade: '#0891b2', shirt: '#1e40af', accessory: 'HEADSET' },
  { id: 'wrk-hr-02', name: '한채원 책임', deptTitle: '인사·리서치팀', roomKey: 'HR_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#c084fc', shade: '#7e22ce', shirt: '#065f46', accessory: 'GLASSES' },
  { id: 'sup-dev-01', name: '임민서 팀장', deptTitle: 'SW개발팀', roomKey: 'DEV_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#38bdf8', shade: '#0284c7', shirt: '#1e3a8a', accessory: 'GLASSES' },
  { id: 'wrk-dev-01', name: '임지우 수석', deptTitle: 'SW개발팀', roomKey: 'DEV_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#a3e635', shade: '#4d7c0f', shirt: '#0f766e', accessory: 'HEADSET' },
  { id: 'wrk-dev-02', name: '임유진 책임', deptTitle: 'SW개발팀', roomKey: 'DEV_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#f472b6', shade: '#db2777', shirt: '#6b21a8', accessory: 'HEADSET' },
  { id: 'sup-qa-01', name: '임승현 팀장', deptTitle: '품질보증·QA팀', roomKey: 'QA_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#fb923c', shade: '#c2410c', shirt: '#047857', accessory: 'GLASSES' },
  { id: 'wrk-qa-01', name: '한도윤 수석', deptTitle: '품질보증·QA팀', roomKey: 'QA_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#2dd4bf', shade: '#0f766e', shirt: '#1d4ed8', accessory: 'SAFETY_BADGE' },
  { id: 'wrk-qa-02', name: '장지우 책임', deptTitle: '품질보증·QA팀', roomKey: 'QA_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#e879f9', shade: '#a21caf', shirt: '#4338ca', accessory: 'GLASSES' },
  { id: 'sup-fin-01', name: '정우성 팀장', deptTitle: '재무·데이터팀', roomKey: 'FIN_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#facc15', shade: '#a16207', shirt: '#1e40af', accessory: 'GLASSES' },
  { id: 'wrk-fin-01', name: '강현우 수석', deptTitle: '재무·데이터팀', roomKey: 'FIN_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#60a5fa', shade: '#2563eb', shirt: '#065f46', accessory: 'GLASSES' },
  { id: 'wrk-fin-02', name: '배수빈 책임', deptTitle: '재무·데이터팀', roomKey: 'FIN_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#f87171', shade: '#b91c1c', shirt: '#5b21b6', accessory: 'HEADSET' },
  { id: 'sup-mkt-01', name: '조다은 팀장', deptTitle: '마케팅·전략팀', roomKey: 'MKT_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#fb7185', shade: '#be123c', shirt: '#9f1239', accessory: 'GLASSES' },
  { id: 'wrk-mkt-01', name: '장건우 수석', deptTitle: '마케팅·전략팀', roomKey: 'MKT_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#38bdf8', shade: '#0369a1', shirt: '#1e40af', accessory: 'HEADSET' },
  { id: 'wrk-mkt-02', name: '권하윤 책임', deptTitle: '마케팅·전략팀', roomKey: 'MKT_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#c084fc', shade: '#6b21a8', shirt: '#047857', accessory: 'HEADSET' },
];

function detectRoomByPoint(x: number, y: number): DeptRoomKey | 'CORRIDOR' {
  for (const [k, r] of Object.entries(ROOMS) as Array<[DeptRoomKey, typeof ROOMS.HR_ROOM]>) {
    if (x >= r.rx && x <= r.rx + r.rw && y >= r.ry && y <= r.ry + r.rh) {
      return k;
    }
  }
  return 'CORRIDOR';
}

function buildSmartCorridorPath(curX: number, curY: number, target: Point, via?: Point): Point[] {
  const pts: Point[] = [];
  const startRoom = detectRoomByPoint(curX, curY);
  const destRoom = detectRoomByPoint(target.x, target.y);

  if (via) {
    pts.push({ x: via.x, y: via.y });
  }

  if (startRoom !== destRoom) {
    if (startRoom !== 'CORRIDOR') {
      const r1 = ROOMS[startRoom];
      pts.push({ x: r1.doorX, y: r1.doorY });
      pts.push({ x: r1.doorX, y: CORRIDOR_Y });
    } else {
      pts.push({ x: curX, y: CORRIDOR_Y });
    }

    if (destRoom !== 'CORRIDOR') {
      const r2 = ROOMS[destRoom];
      pts.push({ x: r2.doorX, y: CORRIDOR_Y });
      pts.push({ x: r2.doorX, y: r2.doorY });
    }
  }

  pts.push({ x: target.x, y: target.y });
  return pts;
}

function anyMatch(text: string, keywords: string[]): boolean {
  return keywords.some((k) => text.includes(k));
}

function mapDeptToRoom(deptName: string, agentId: string): DeptRoomKey {
  const d = (deptName + ' ' + agentId).toLowerCase();
  if (anyMatch(d, ['개발', 'sw', 'dev', '엔지니어'])) return 'DEV_ROOM';
  if (anyMatch(d, ['품질', 'qa', '생산', 'erp', '백오피스', 'iso', 'ppm', 'capa'])) return 'QA_ROOM';
  if (anyMatch(d, ['재무', '원가', 'fin', '데이터', 'dat'])) return 'FIN_ROOM';
  if (anyMatch(d, ['마케팅', '커머스', 'mkt', '글로벌', 'glb'])) return 'MKT_ROOM';
  return 'HR_ROOM';
}

function easeOutBack(t: number): number {
  const c1 = 2.1;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
}

export default function PixelRpgOffice({
  onOpenReportModal,
  onToggleLogDrawer,
  unreadLogCount = 0,
  onAllGatheredChange,
}: PixelRpgOfficeProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const staffRef = useRef<Record<string, OfficeStaff>>({});
  const particlesRef = useRef<Particle[]>([]);
  const trailsRef = useRef<TrailPoint[]>([]);
  const frameCountRef = useRef<number>(0);

  const [speedMult, setSpeedMult] = useState<number>(1.0);
  const [isHoveringReport, setIsHoveringReport] = useState<boolean>(false);
  const [reportUnlocked, setReportUnlocked] = useState<boolean>(false);
  const [phaseBanner, setPhaseBanner] = useState<string>('5개 부서 16명 상시 근무 중');
  const [hoveredStaff, setHoveredStaff] = useState<HoveredStaffInfo | null>(null);

  const speedRef = useRef<number>(1.0);
  const reportUnlockedRef = useRef<boolean>(false);
  const reportBannerAnimRef = useRef<number>(0);
  const archiveHitFlashRef = useRef<number>(0);
  const ceoWaveFlashRef = useRef<number>(0);

  const { nodes, messages, finalReport } = useOfficeStore();
  const hasFinalReportRef = useRef<boolean>(false);

  useEffect(() => {
    const map: Record<string, OfficeStaff> = {};
    INITIAL_ROSTER.forEach((item) => {
      const room = ROOMS[item.roomKey];
      const home =
        item.role === 'CEO'
          ? { x: MEETING_SEATS.CEO.x, y: MEETING_SEATS.CEO.y }
          : room.desks[item.deskIdx] || room.desks[0];

      map[item.id] = {
        id: item.id,
        name: item.name,
        deptTitle: item.deptTitle,
        roomKey: item.roomKey,
        role: item.role,
        homePos: { x: home.x, y: home.y },
        shelfPos: { x: room.shelf.x, y: room.shelf.y },
        x: home.x,
        y: home.y,
        vx: 0,
        vy: 0,
        waypoints: [],
        stageQueue: [],
        workTimer: 0,
        maxWorkTimer: 120,
        facing: 'DOWN',
        hairColor: item.hair,
        hairShade: item.shade,
        shirtColor: item.shirt,
        accessory: item.accessory,
        isSelectedTeam: item.role === 'CEO',
        isShelfMode: false,
        carryingBook: false,
        taskLabel: item.role === 'CEO' ? '총괄 집무 대기' : '부서 일상 업무',
        activeBubble: '',
        lastBubbleText: '',
        bubbleAnim: 1,
        progress: 0,
        appliedPhase: 0,
      };
    });
    staffRef.current = map;
  }, []);

  useEffect(() => {
    speedRef.current = speedMult;
  }, [speedMult]);

  useEffect(() => {
    hasFinalReportRef.current = Boolean(finalReport);
    if (!finalReport) {
      reportUnlockedRef.current = false;
      reportBannerAnimRef.current = 0;
      setReportUnlocked(false);
      onAllGatheredChange?.(false);
    }
  }, [finalReport]);

  useEffect(() => {
    const map = staffRef.current;
    if (Object.keys(map).length === 0) return;

    const hasStarted = messages.length > 0;
    const hasRejected = messages.some((m) => m.type === 'QC_REJECT');
    const isArchiveHit = messages.some(
      (m) => String(m.type) === 'ARCHIVE_HIT' || (m.payload?.text || '').includes('부서 책장(서가) 기존 기록 발견')
    );
    const hasLiveCeo = messages.some(
      (m) => String(m.type) === 'CEO_LIVE_INTERVENTION' || (m.payload?.text || '').includes('실시간 CEO 긴급 지침')
    );
    const isMissionFinished = Boolean(finalReport);

    if (hasLiveCeo) {
      ceoWaveFlashRef.current = 120;
    }

    if (!hasStarted) {
      setPhaseBanner('🏢 전 부서(5개 팀 16명) 각자 사무실에서 일상 근무 대기 중');
      trailsRef.current = [];
      Object.values(map).forEach((st) => {
        st.isSelectedTeam = st.role === 'CEO';
        st.isShelfMode = false;
        st.carryingBook = false;
        st.stageQueue = [];
        st.waypoints = [];
        st.x = st.homePos.x;
        st.y = st.homePos.y;
        st.vx = 0;
        st.vy = 0;
        st.workTimer = 0;
        st.progress = 0;
        st.activeBubble = '';
        st.lastBubbleText = '';
        st.bubbleAnim = 0;
        st.taskLabel = st.role === 'CEO' ? '총괄 집무 대기' : '부서 일상 대기';
        st.appliedPhase = 0;
      });
      return;
    }

    const activeNonCeo = nodes.filter((n) => n.id !== 'ceo');
    let targetRoomKey: DeptRoomKey = 'HR_ROOM';
    if (activeNonCeo.length > 0) {
      targetRoomKey = mapDeptToRoom(String(activeNonCeo[0].data?.dept || ''), activeNonCeo[0].id);
    }

    const roomStaff = Object.values(map).filter((s) => s.roomKey === targetRoomKey);
    activeNonCeo.slice(0, 3).forEach((n, idx) => {
      const targetChar = roomStaff[idx];
      if (targetChar) {
        targetChar.name = String(n.data?.name || targetChar.name);
        targetChar.deptTitle = String(n.data?.dept || targetChar.deptTitle);
      }
    });

    Object.values(map).forEach((st) => {
      const isTarget = st.role === 'CEO' || st.roomKey === targetRoomKey;
      st.isSelectedTeam = isTarget;
      if (!isTarget) {
        st.stageQueue = [];
        st.waypoints = [];
        st.x = st.homePos.x;
        st.y = st.homePos.y;
        st.vx = 0;
        st.vy = 0;
        st.workTimer = 0;
        st.progress = 0;
        st.activeBubble = '';
        st.lastBubbleText = '';
        st.bubbleAnim = 0;
        st.taskLabel = '자리에 남아 대기 중';
      }
    });

    const deptTitle = ROOMS[targetRoomKey].title;

    if (isArchiveHit) {
      archiveHitFlashRef.current = 180;
      setPhaseBanner(`📚 [${deptTitle} 서가 메모리 히트!] 뒤쪽 책장에서 기존 결재 문서를 꺼내 즉시 회의실로 보고합니다 ($0)`);
      Object.values(map)
        .filter((s) => s.isSelectedTeam)
        .forEach((ag) => {
          if (ag.appliedPhase < 10) {
            ag.appliedPhase = 10;
            ag.stageQueue = [];
            ag.isShelfMode = true;
            if (ag.role === 'CEO') {
              ag.stageQueue.push({
                target: MEETING_SEATS.CEO,
                workFrames: 0,
                label: '📚 서가 기록 즉시 결재',
                bubble: '📚 이전에 결재했던 기록이군요! 책장에서 바로 가져오세요!',
                sitFacing: 'DOWN',
              });
            } else if (ag.role === 'WORKER1') {
              ag.stageQueue.push({
                target: ag.shelfPos,
                workFrames: 65,
                label: '📚 뒤쪽 책장 기록 탐색',
                bubble: '📚 뒤쪽 책장(서가)에서 이전 결재 보고서철을 찾았습니다!',
                sitFacing: 'UP',
                isShelfLookup: true,
              });
              ag.stageQueue.push({
                target: MEETING_SEATS.WORKER1,
                workFrames: 0,
                label: '📚 서가 기록 즉시 상신',
                bubble: '📚 책장에서 꺼내온 기존 결재 문서를 회의실에 즉시 보고합니다!',
                sitFacing: 'UP',
              });
            } else if (ag.role === 'SUPERVISOR') {
              ag.stageQueue.push({
                target: MEETING_SEATS.SUPERVISOR,
                workFrames: 0,
                label: '📚 아카이브 무결성 확인',
                bubble: '✅ 서가 보관본 일치 확인 완료! (재조사 원하시면 "다시 찾아줘" 입력)',
                sitFacing: 'DOWN',
              });
            } else {
              ag.stageQueue.push({
                target: MEETING_SEATS.WORKER2,
                workFrames: 0,
                label: '📚 서가 문서 동석 보고',
                bubble: '📚 API 비용 $0으로 기존 검증 보고서를 즉시 복원했습니다!',
                sitFacing: 'UP',
              });
            }
          }
        });
      return;
    }

    if (reportUnlocked) {
      setPhaseBanner(`✅ [${deptTitle}] 중앙 회의실 최종 결재 완료 (타 부서 12명은 각자 자리 대기)`);
    } else if (hasLiveCeo) {
      setPhaseBanner(`⚡ [실시간 CEO 긴급 지침 수신!] ${deptTitle} 에이전트들이 대표님 추가 지시를 즉시 반영 중입니다!`);
    } else if (hasRejected) {
      setPhaseBanner(`🔄 [${deptTitle}] 팀장 QC 반려 ➔ 담당 부서실로 복귀하여 2차 심층 재크롤링 수행 중`);
    } else {
      setPhaseBanner(`🚀 [${deptTitle} 3명 차출 가동] 부서 컴퓨터 집중 조사 중 (타 부서 12명은 자리 대기)`);
    }

    Object.values(map)
      .filter((s) => s.isSelectedTeam)
      .forEach((ag) => {
        if (hasLiveCeo && ag.role !== 'CEO') {
          ag.activeBubble = '⚡ 대표님 실시간 추가 지시 수신! 즉시 반영 중!';
          ag.bubbleAnim = 0;
        }

        if (hasStarted && ag.appliedPhase < 1) {
          ag.appliedPhase = 1;
          if (ag.role === 'CEO') {
            ag.stageQueue.push({
              target: MEETING_SEATS.CEO,
              workFrames: 0,
              label: '총괄 결재 대기',
              bubble: `🎯 ${deptTitle} 전담팀 업무 하달!`,
              sitFacing: 'DOWN',
            });
          } else if (ag.role === 'SUPERVISOR') {
            ag.stageQueue.push({
              target: ag.homePos,
              workFrames: 85,
              label: '🔎 부서 1차 조사 지휘',
              bubble: '🔎 우리 부서에서 1차 정밀 조사를 시작합니다!',
              sitFacing: 'DOWN',
            });
          } else if (ag.role === 'WORKER1') {
            ag.stageQueue.push({
              target: ag.homePos,
              via: ag.shelfPos,
              workFrames: 115,
              label: '🔍 1차 공식 문서 탐색',
              bubble: '🔍 서가 스캔 후 PC에서 공식 문서 팩트 수집 중!',
              sitFacing: 'DOWN',
            });
          } else {
            ag.stageQueue.push({
              target: ag.homePos,
              via: ag.shelfPos,
              workFrames: 105,
              label: '💻 1차 데이터 구조화',
              bubble: '💻 수집 데이터 및 첨부 문서 파싱 중!',
              sitFacing: 'DOWN',
            });
          }
        }

        if (hasRejected && ag.appliedPhase < 2) {
          ag.appliedPhase = 2;
          if (ag.role === 'SUPERVISOR') {
            ag.stageQueue.push({
              target: MEETING_SEATS.SUPERVISOR,
              workFrames: 60,
              label: '🚨 중앙회의실 QC 반려',
              bubble: '🚨 [QC 반려] 2차 심화 재크롤링 및 5단 보고서로 보완하세요!',
              sitFacing: 'DOWN',
            });
            ag.stageQueue.push({
              target: ag.homePos,
              workFrames: 85,
              label: '🔎 부서 복귀·2차 감독',
              bubble: '🔎 부서실로 돌아와 2차 심층 재조사를 감독합니다.',
              sitFacing: 'DOWN',
            });
          } else if (ag.role === 'WORKER1') {
            ag.stageQueue.push({
              target: MEETING_SEATS.WORKER1,
              workFrames: 55,
              label: '🚨 반려 피드백 수령',
              bubble: '📋 즉시 부서실 PC로 돌아가 2차 재크롤링을 수행하겠습니다!',
              sitFacing: 'UP',
            });
            ag.stageQueue.push({
              target: ag.homePos,
              via: ag.shelfPos,
              workFrames: 120,
              label: '🔄 부서 복귀·2차 재조사',
              bubble: '🔄 [2차 심층 재조사] 심화 쿼리로 추가 근거 크롤링 중!',
              sitFacing: 'DOWN',
            });
          } else if (ag.role === 'WORKER2') {
            ag.stageQueue.push({
              target: MEETING_SEATS.WORKER2,
              workFrames: 55,
              label: '🚨 5단 보고서 보완 지시',
              bubble: '📋 부서실로 복귀해 5단 심층 보고서로 확장하겠습니다!',
              sitFacing: 'UP',
            });
            ag.stageQueue.push({
              target: ag.homePos,
              via: ag.shelfPos,
              workFrames: 120,
              label: '💻 5단 심층 보고서 작성',
              bubble: '💻 [2차 보완] 5단 장문 보고서 및 정량 지표 합성 중!',
              sitFacing: 'DOWN',
            });
          }
        }

        if (isMissionFinished && ag.appliedPhase < 3) {
          ag.appliedPhase = 3;
          if (ag.role === 'CEO') {
            ag.stageQueue.push({
              target: MEETING_SEATS.CEO,
              workFrames: 0,
              label: '✅ 최종 결재 완료',
              bubble: '✅ [최종 승인] 회의실 테이블의 보고서를 클릭하세요!',
              sitFacing: 'DOWN',
            });
          } else if (ag.role === 'SUPERVISOR') {
            ag.stageQueue.push({
              target: MEETING_SEATS.SUPERVISOR,
              workFrames: 0,
              label: '✅ QC 100점 승인 완료',
              bubble: '✅ [검수 완료] 5단 심층 보고서를 결재 상신합니다!',
              sitFacing: 'DOWN',
            });
          } else if (ag.role === 'WORKER1') {
            ag.stageQueue.push({
              target: MEETING_SEATS.WORKER1,
              workFrames: 0,
              label: '✅ 2차 재조사 완료',
              bubble: '✅ 공식 출처 팩트 검증 완료! 회의실 집결!',
              sitFacing: 'UP',
            });
          } else {
            ag.stageQueue.push({
              target: MEETING_SEATS.WORKER2,
              workFrames: 0,
              label: '✅ 5단 보고서 상신 완료',
              bubble: '✅ Word·Excel·PDF 변환 및 ERP 연동 준비 완료!',
              sitFacing: 'UP',
            });
          }
        }
      });
  }, [nodes, messages, finalReport, reportUnlocked]);

  const handleCanvasPos = (e: React.MouseEvent<HTMLCanvasElement>, isClick: boolean) => {
    if (!canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const scale = Math.min(rect.width / CW, rect.height / CH);
    const renderedW = CW * scale;
    const renderedH = CH * scale;
    const offsetX = (rect.width - renderedW) / 2;
    const offsetY = (rect.height - renderedH) / 2;

    const cx = (e.clientX - rect.left - offsetX) / scale;
    const cy = (e.clientY - rect.top - offsetY) / scale;

    const foundStaff = Object.values(staffRef.current).find(
      (ag) => Math.hypot(cx - ag.x, cy - ag.y) < 48
    );
    if (foundStaff) {
      setHoveredStaff({
        name: foundStaff.name,
        deptTitle: foundStaff.deptTitle,
        role: foundStaff.role,
        taskLabel: foundStaff.taskLabel,
        progress: foundStaff.progress,
        bubble: foundStaff.activeBubble || '현재 배정된 부서 업무 수행 중',
        isSelected: foundStaff.isSelectedTeam,
      });
    } else {
      setHoveredStaff(null);
    }

    if (!reportUnlockedRef.current) {
      setIsHoveringReport(false);
      return;
    }
    const hit =
      cx >= MEETING_TABLE_CENTER.x - 85 &&
      cx <= MEETING_TABLE_CENTER.x + 85 &&
      cy >= MEETING_TABLE_CENTER.y - 60 &&
      cy <= MEETING_TABLE_CENTER.y + 50;
    setIsHoveringReport(hit);
    if (hit && isClick && onOpenReportModal) {
      onOpenReportModal();
    }
  };

  useEffect(() => {
    let animId: number;

    const drawRoomFloor = (
      ctx: CanvasRenderingContext2D,
      rx: number,
      ry: number,
      rw: number,
      rh: number,
      floorType: 'WOOD' | 'DARK_BLUE' | 'SLATE' | 'AMBER' | 'EMERALD',
      badgeColor: string,
      isRoomActive: boolean,
      f: number
    ) => {
      const palette: Record<typeof floorType, [string, string]> = {
        WOOD: ['#78350f', '#652b0d'],
        DARK_BLUE: ['#1e3a5f', '#172554'],
        SLATE: ['#334155', '#1e293b'],
        AMBER: ['#9a3412', '#7c2d12'],
        EMERALD: ['#064e3b', '#022c22'],
      };
      const [c1, c2] = palette[floorType];
      const size = 22;
      for (let y = ry; y < ry + rh; y += size) {
        for (let x = rx; x < rx + rw; x += size) {
          const isEven = (Math.floor(x / size) + Math.floor(y / size)) % 2 === 0;
          ctx.fillStyle = isEven ? c1 : c2;
          ctx.fillRect(x, y, Math.min(size, rx + rw - x), Math.min(size, ry + rh - y));
        }
      }

      // 부서실 상단 벽면 패널
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(rx, ry, rw, 22);
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(rx, ry + 22, rw, 6);
      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.fillRect(rx, ry + 28, rw, 7);

      // 중앙 조명 은은한 네온/앰비언트 글로우 (createRadialGradient)
      const centerX = rx + rw / 2;
      const centerY = ry + rh / 2 + 12;
      const lightRadius = Math.max(rw, rh) * 0.64;
      const pulse = 1 + Math.sin(f * 0.035) * 0.08;
      const roomGlow = ctx.createRadialGradient(
        centerX,
        centerY,
        12,
        centerX,
        centerY,
        lightRadius * pulse
      );

      if (isRoomActive) {
        roomGlow.addColorStop(0, 'rgba(52, 211, 153, 0.26)');
        roomGlow.addColorStop(0.45, 'rgba(56, 189, 248, 0.12)');
        roomGlow.addColorStop(1, 'rgba(15, 23, 42, 0)');
      } else if (floorType === 'AMBER') {
        roomGlow.addColorStop(0, 'rgba(251, 191, 36, 0.25)');
        roomGlow.addColorStop(0.55, 'rgba(245, 158, 11, 0.09)');
        roomGlow.addColorStop(1, 'rgba(15, 23, 42, 0)');
      } else {
        roomGlow.addColorStop(0, `${badgeColor}26`);
        roomGlow.addColorStop(0.55, `${badgeColor}0e`);
        roomGlow.addColorStop(1, 'rgba(15, 23, 42, 0)');
      }

      ctx.save();
      ctx.fillStyle = roomGlow;
      ctx.fillRect(rx, ry, rw, rh);
      ctx.restore();
    };

    // 입체적인 메탈 몰딩 프레임과 4방 코너 볼트
    const drawMetalMoldingFrame = (
      ctx: CanvasRenderingContext2D,
      rx: number,
      ry: number,
      rw: number,
      rh: number,
      badgeColor: string,
      isRoomActive: boolean,
      doorX: number,
      doorY: number
    ) => {
      // 외곽 다크 베벨
      ctx.strokeStyle = '#020617';
      ctx.lineWidth = 8;
      ctx.strokeRect(rx - 2, ry - 2, rw + 4, rh + 4);

      // 스틸 메탈 몰딩 바디
      ctx.strokeStyle = isRoomActive ? '#10b981' : '#475569';
      ctx.lineWidth = 4.5;
      ctx.strokeRect(rx, ry, rw, rh);

      // 인라인 네온/하이라이트 트림
      ctx.strokeStyle = isRoomActive ? '#6ee7b7' : `${badgeColor}88`;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(rx + 3, ry + 3, rw - 6, rh - 6);

      // 코너 메탈 브래킷 & 볼트 (4개 코너)
      const corners = [
        { cx: rx + 5, cy: ry + 5 },
        { cx: rx + rw - 5, cy: ry + 5 },
        { cx: rx + 5, cy: ry + rh - 5 },
        { cx: rx + rw - 5, cy: ry + rh - 5 },
      ];
      corners.forEach(({ cx, cy }) => {
        ctx.fillStyle = '#334155';
        ctx.fillRect(cx - 5, cy - 5, 10, 10);
        ctx.strokeStyle = '#94a3b8';
        ctx.lineWidth = 1;
        ctx.strokeRect(cx - 5, cy - 5, 10, 10);
        ctx.fillStyle = '#e2e8f0';
        ctx.beginPath();
        ctx.arc(cx, cy, 2.3, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(cx - 1.5, cy - 0.5, 3, 1);
      });

      // 출입구 슬라이딩 메탈 도어 매트
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(doorX - 28, doorY - 5, 56, 10);
      ctx.fillStyle = isRoomActive ? '#34d399' : '#94a3b8';
      ctx.fillRect(doorX - 24, doorY - 3, 48, 6);
    };

    const drawLushPotPlant = (ctx: CanvasRenderingContext2D, px: number, py: number, f: number, scale = 1.0) => {
      ctx.save();
      ctx.translate(px, py);
      ctx.scale(scale, scale);

      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.beginPath();
      ctx.ellipse(0, 11, 11, 4.5, 0, 0, Math.PI * 2);
      ctx.fill();

      // 화분 몸체
      ctx.fillStyle = '#9a3412';
      ctx.fillRect(-7, 1, 14, 10);
      ctx.fillStyle = '#c2410c';
      ctx.fillRect(-9, -1, 18, 4);
      ctx.strokeStyle = '#431407';
      ctx.lineWidth = 1;
      ctx.strokeRect(-7, 1, 14, 10);

      // 잎사귀 볼륨
      const sway = Math.sin(f * 0.04 + px) * 1.2;
      ctx.fillStyle = '#14532d';
      ctx.beginPath();
      ctx.arc(0, -7, 11, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#16a34a';
      ctx.beginPath();
      ctx.arc(-4 + sway * 0.5, -9, 7, 0, Math.PI * 2);
      ctx.arc(5 + sway * 0.5, -8, 6.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#4ade80';
      ctx.beginPath();
      ctx.arc(-2 + sway, -12, 4.5, 0, Math.PI * 2);
      ctx.arc(3 + sway, -10, 3.5, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    };

    const drawWindowAndSunbeam = (ctx: CanvasRenderingContext2D, wx: number, wy: number, f: number) => {
      ctx.fillStyle = '#0284c7';
      ctx.fillRect(wx, wy, 68, 14);
      ctx.fillStyle = '#38bdf8';
      ctx.fillRect(wx + 4, wy + 2, 27, 10);
      ctx.fillRect(wx + 36, wy + 2, 27, 10);
      const alpha = 0.07 + Math.sin(f * 0.03) * 0.02;
      ctx.fillStyle = `rgba(186, 230, 253, ${alpha})`;
      ctx.beginPath();
      ctx.moveTo(wx, wy + 14);
      ctx.lineTo(wx + 68, wy + 14);
      ctx.lineTo(wx + 86, wy + 70);
      ctx.lineTo(wx - 18, wy + 70);
      ctx.closePath();
      ctx.fill();
    };

    // 부서별 특화 아케이드 배경 디테일 렌더링
    const drawOfficeProps = (
      ctx: CanvasRenderingContext2D,
      rx: number,
      ry: number,
      rw: number,
      rh: number,
      rKey: DeptRoomKey,
      f: number
    ) => {
      // 실내 화분
      drawLushPotPlant(ctx, rx + 24, ry + rh - 26, f, 0.95);

      if (rKey === 'HR_ROOM') {
        // 1) 리서치·인사팀: 원형 차트(파이 차트) 보드 & 소파
        const bx = rx + rw - 78;
        const by = ry + 18;
        ctx.fillStyle = '#f8fafc';
        ctx.fillRect(bx, by, 62, 34);
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2;
        ctx.strokeRect(bx, by, 62, 34);

        // 원형 파이 차트
        const pcx = bx + 18;
        const pcy = by + 17;
        ctx.fillStyle = '#38bdf8';
        ctx.beginPath();
        ctx.arc(pcx, pcy, 10, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#f43f5e';
        ctx.beginPath();
        ctx.moveTo(pcx, pcy);
        ctx.arc(pcx, pcy, 10, -0.5, 1.3);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = '#fbbf24';
        ctx.beginPath();
        ctx.moveTo(pcx, pcy);
        ctx.arc(pcx, pcy, 10, 1.3, 2.5);
        ctx.closePath();
        ctx.fill();

        // 보드 우측 막대 지표
        ctx.fillStyle = '#0ea5e9';
        ctx.fillRect(bx + 34, by + 7, 20, 4);
        ctx.fillStyle = '#10b981';
        ctx.fillRect(bx + 34, by + 15, 15, 4);
        ctx.fillStyle = '#f59e0b';
        ctx.fillRect(bx + 34, by + 23, 22, 4);

        // 리서치팀 라운지 소파 (하단 좌측)
        const sx = rx + 62;
        const sy = ry + rh - 42;
        ctx.fillStyle = 'rgba(0,0,0,0.35)';
        ctx.fillRect(sx - 2, sy + 4, 68, 24);
        ctx.fillStyle = '#0369a1';
        ctx.beginPath();
        ctx.roundRect(sx, sy, 64, 22, 6);
        ctx.fill();
        ctx.fillStyle = '#0ea5e9';
        ctx.beginPath();
        ctx.roundRect(sx + 5, sy + 5, 25, 14, 4);
        ctx.roundRect(sx + 34, sy + 5, 25, 14, 4);
        ctx.fill();
      } else if (rKey === 'DEV_ROOM') {
        // 2) AI·SW개발팀: 대형 코드 모니터, 홀로그램 큐브, AI 로봇
        const mx = rx + rw - 88;
        const my = ry + 16;
        ctx.fillStyle = '#090d16';
        ctx.fillRect(mx, my, 74, 38);
        ctx.strokeStyle = '#818cf8';
        ctx.lineWidth = 2;
        ctx.strokeRect(mx, my, 74, 38);
        const codeColors = ['#34d399', '#38bdf8', '#f472b6', '#fbbf24', '#a78bfa'];
        for (let i = 0; i < 5; i++) {
          ctx.fillStyle = codeColors[(i + Math.floor(f / 10)) % codeColors.length];
          const w = 16 + ((i * 13 + Math.floor(f / 6)) % 36);
          ctx.fillRect(mx + 6 + (i % 2) * 6, my + 6 + i * 6, w, 3);
        }

        // 홀로그램 큐브 & 페데스탈 (좌측 상단)
        const hx = rx + 36;
        const hy = ry + 56;
        ctx.fillStyle = '#1e293b';
        ctx.fillRect(hx - 12, hy + 10, 24, 10);
        ctx.fillStyle = '#38bdf8';
        ctx.beginPath();
        ctx.ellipse(hx, hy + 10, 12, 4, 0, 0, Math.PI * 2);
        ctx.fill();

        const floatY = hy - 4 + Math.sin(f * 0.08) * 3.5;
        const holoGlow = ctx.createRadialGradient(hx, floatY, 2, hx, floatY, 20);
        holoGlow.addColorStop(0, 'rgba(56, 189, 248, 0.7)');
        holoGlow.addColorStop(1, 'rgba(56, 189, 248, 0)');
        ctx.fillStyle = holoGlow;
        ctx.beginPath();
        ctx.arc(hx, floatY, 20, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = '#67e8f9';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(hx - 7, floatY - 7, 12, 12);
        ctx.strokeStyle = '#c084fc';
        ctx.strokeRect(hx - 3, floatY - 11, 12, 12);

        // 귀여운 개발팀 AI 로봇 (좌측 하단)
        const rbx = rx + 82 + Math.sin(f * 0.03) * 8;
        const rby = ry + rh - 34;
        ctx.fillStyle = '#cbd5e1';
        ctx.beginPath();
        ctx.roundRect(rbx - 9, rby - 12, 18, 16, 5);
        ctx.fill();
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(rbx - 6, rby - 9, 12, 6);
        ctx.fillStyle = '#38bdf8';
        ctx.fillRect(rbx - 4, rby - 7, 3, 2);
        ctx.fillRect(rbx + 1, rby - 7, 3, 2);
        ctx.strokeStyle = '#38bdf8';
        ctx.beginPath();
        ctx.moveTo(rbx, rby - 12);
        ctx.lineTo(rbx, rby - 17);
        ctx.stroke();
        ctx.fillStyle = '#f43f5e';
        ctx.beginPath();
        ctx.arc(rbx, rby - 18, 2, 0, Math.PI * 2);
        ctx.fill();
      } else if (rKey === 'QA_ROOM') {
        // 3) 품질·생산QA팀: 유리창 너머 컨베이어 벨트, 안전모, QA 체크리스트 보드, 원형 테이블
        const cx = rx + 18;
        const cy = ry + 16;
        const cw = 98;
        const ch = 36;
        // 유리창 프레임
        ctx.fillStyle = '#090d16';
        ctx.fillRect(cx, cy, cw, ch);
        ctx.strokeStyle = '#34d399';
        ctx.lineWidth = 2;
        ctx.strokeRect(cx, cy, cw, ch);

        // 컨베이어 벨트 트랙 및 롤러
        ctx.fillStyle = '#334155';
        ctx.fillRect(cx + 4, cy + 23, cw - 8, 7);
        for (let r = 0; r < 6; r++) {
          ctx.fillStyle = '#94a3b8';
          ctx.beginPath();
          ctx.arc(cx + 10 + r * 15, cy + 26.5, 2, 0, Math.PI * 2);
          ctx.fill();
        }
        // 이동하는 의료기기/제품 패키지 박스들
        for (let b = 0; b < 3; b++) {
          const bx = cx + 8 + ((b * 30 + Math.floor(f * 0.5)) % (cw - 24));
          ctx.fillStyle = b % 2 === 0 ? '#38bdf8' : '#fbbf24';
          ctx.fillRect(bx, cy + 12, 12, 11);
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(bx + 3, cy + 14, 6, 3);
        }
        // 비전 스캐너 레이저
        ctx.fillStyle = 'rgba(52, 211, 153, 0.45)';
        ctx.fillRect(cx + cw / 2 - 2, cy + 3, 4, 20);

        // QA 체크리스트 보드 (우측 상단)
        const qbx = rx + rw - 68;
        const qby = ry + 18;
        ctx.fillStyle = '#f8fafc';
        ctx.fillRect(qbx, qby, 54, 34);
        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 2;
        ctx.strokeRect(qbx, qby, 54, 34);
        for (let i = 0; i < 3; i++) {
          ctx.fillStyle = '#10b981';
          ctx.fillRect(qbx + 5, qby + 6 + i * 9, 6, 6);
          ctx.fillStyle = '#334155';
          ctx.fillRect(qbx + 15, qby + 8 + i * 9, 32, 3);
        }

        // 원형 QA 분임조 테이블 & 안전모 (하단 좌측)
        const tx = rx + 95;
        const ty = ry + rh - 36;
        ctx.fillStyle = 'rgba(0,0,0,0.35)';
        ctx.beginPath();
        ctx.ellipse(tx, ty + 4, 24, 14, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#1e293b';
        ctx.beginPath();
        ctx.ellipse(tx, ty, 22, 13, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // 노란 안전모 (Safety Helmet) 2개
        const drawHelmet = (hx: number, hy: number) => {
          ctx.fillStyle = '#facc15';
          ctx.beginPath();
          ctx.arc(hx, hy, 6, Math.PI, 0);
          ctx.fill();
          ctx.fillStyle = '#eab308';
          ctx.fillRect(hx - 7, hy - 1, 14, 2.5);
        };
        drawHelmet(tx - 7, ty - 2);
        drawHelmet(tx + 8, ty + 2);
      } else if (rKey === 'FIN_ROOM') {
        // 4) 재무·데이터팀: 대형 상승 차트 보드 & 서버랙
        const fbx = rx + rw - 82;
        const fby = ry + 18;
        ctx.fillStyle = '#090d16';
        ctx.fillRect(fbx, fby, 68, 36);
        ctx.strokeStyle = '#fbbf24';
        ctx.lineWidth = 2;
        ctx.strokeRect(fbx, fby, 68, 36);

        // 상승 막대 & 꺾은선 차트
        const bars = [10, 15, 13, 21, 27];
        bars.forEach((bh, idx) => {
          ctx.fillStyle = idx === 4 ? '#34d399' : '#0ea5e9';
          ctx.fillRect(fbx + 8 + idx * 11, fby + 31 - bh, 7, bh);
        });
        ctx.strokeStyle = '#fde047';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(fbx + 10, fby + 24);
        ctx.lineTo(fbx + 22, fby + 18);
        ctx.lineTo(fbx + 34, fby + 20);
        ctx.lineTo(fbx + 46, fby + 11);
        ctx.lineTo(fbx + 56, fby + 6);
        ctx.stroke();

        // 좌측 금융 데이터 서버랙
        const sx = rx + 20;
        const sy = ry + 26;
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(sx, sy, 34, 38);
        ctx.strokeStyle = '#fbbf24';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(sx, sy, 34, 38);
        for (let i = 0; i < 3; i++) {
          ctx.fillStyle = (f + i * 12) % 30 < 15 ? '#34d399' : '#fbbf24';
          ctx.fillRect(sx + 5, sy + 6 + i * 10, 5, 3);
        }
      } else if (rKey === 'MKT_ROOM') {
        // 6) 마케팅·전략팀: 세계지도, 아이디어 전구 보드, 핑크 소파
        // 세계지도 보드 (상단 좌측)
        const mx = rx + 20;
        const my = ry + 22;
        ctx.fillStyle = '#0c4a6e';
        ctx.fillRect(mx, my, 76, 36);
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(mx, my, 76, 36);
        // 대륙 실루엣
        ctx.fillStyle = '#34d399';
        ctx.beginPath();
        ctx.ellipse(mx + 18, my + 14, 9, 6, 0.2, 0, Math.PI * 2);
        ctx.ellipse(mx + 24, my + 25, 5, 6, -0.2, 0, Math.PI * 2);
        ctx.ellipse(mx + 46, my + 13, 14, 7, 0, 0, Math.PI * 2);
        ctx.ellipse(mx + 58, my + 26, 6, 4, 0, 0, Math.PI * 2);
        ctx.fill();
        // 글로벌 거점 핀
        ctx.fillStyle = '#f43f5e';
        ctx.beginPath();
        ctx.arc(mx + 18, my + 13, 2.2, 0, Math.PI * 2);
        ctx.arc(mx + 52, my + 14, 2.2, 0, Math.PI * 2);
        ctx.fill();

        // 아이디어 전구 보드 (우측 상단)
        const ibx = rx + rw - 72;
        const iby = ry + 20;
        ctx.fillStyle = '#f8fafc';
        ctx.fillRect(ibx, iby, 56, 34);
        ctx.strokeStyle = '#f472b6';
        ctx.lineWidth = 2;
        ctx.strokeRect(ibx, iby, 56, 34);
        // 반짝이는 전구 아이콘
        ctx.fillStyle = '#facc15';
        ctx.beginPath();
        ctx.arc(ibx + 16, iby + 15, 7, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#64748b';
        ctx.fillRect(ibx + 13, iby + 21, 6, 4);
        // 컬러 포스트잇
        ctx.fillStyle = '#f43f5e';
        ctx.fillRect(ibx + 30, iby + 7, 9, 8);
        ctx.fillStyle = '#38bdf8';
        ctx.fillRect(ibx + 41, iby + 7, 9, 8);
        ctx.fillStyle = '#a855f7';
        ctx.fillRect(ibx + 35, iby + 18, 10, 8);

        // 핑크 디자이너 소파 (하단 좌측)
        const psx = rx + 62;
        const psy = ry + rh - 44;
        ctx.fillStyle = 'rgba(0,0,0,0.35)';
        ctx.fillRect(psx - 2, psy + 4, 68, 24);
        ctx.fillStyle = '#db2777';
        ctx.beginPath();
        ctx.roundRect(psx, psy, 64, 22, 7);
        ctx.fill();
        ctx.fillStyle = '#f472b6';
        ctx.beginPath();
        ctx.roundRect(psx + 5, psy + 5, 25, 14, 4);
        ctx.roundRect(psx + 34, psy + 5, 25, 14, 4);
        ctx.fill();
      }
    };

    const drawBookshelf = (ctx: CanvasRenderingContext2D, bx: number, by: number, isGlowing: boolean, f: number) => {
      if (isGlowing) {
        const shelfGlow = ctx.createRadialGradient(bx, by - 5, 6, bx, by - 5, 52);
        shelfGlow.addColorStop(0, 'rgba(250, 204, 21, 0.45)');
        shelfGlow.addColorStop(0.5, 'rgba(56, 189, 248, 0.2)');
        shelfGlow.addColorStop(1, 'rgba(56, 189, 248, 0)');
        ctx.fillStyle = shelfGlow;
        ctx.beginPath();
        ctx.arc(bx, by - 5, 52, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.fillRect(bx - 30, by - 18, 64, 36);
      ctx.fillStyle = '#451a03';
      ctx.fillRect(bx - 32, by - 22, 64, 34);
      ctx.fillStyle = '#78350f';
      ctx.fillRect(bx - 29, by - 19, 58, 28);
      const colors = ['#f43f5e', '#38bdf8', '#10b981', '#fbbf24', '#a855f7', '#fb923c'];
      for (let r = 0; r < 2; r++) {
        for (let i = 0; i < 6; i++) {
          ctx.fillStyle = colors[(i + r * 2) % colors.length];
          ctx.fillRect(bx - 25 + i * 8, by - 16 + r * 13, 6, 10);
        }
      }
      if (isGlowing) {
        ctx.strokeStyle = f % 16 < 8 ? '#fde047' : '#38bdf8';
        ctx.lineWidth = 3;
        ctx.strokeRect(bx - 35, by - 25, 70, 40);
        ctx.fillStyle = '#fef08a';
        ctx.font = 'bold 9.5px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('📚 기존 결재철 인출!', bx, by - 28);
      }
    };

    const drawDesk = (ctx: CanvasRenderingContext2D, dx: number, dy: number, isWorking: boolean, isSelectedRoom: boolean, f: number) => {
      // 체어 등받이
      ctx.fillStyle = '#0f172a';
      ctx.beginPath();
      ctx.roundRect(dx - 14, dy - 16, 28, 14, 4);
      ctx.fill();
      ctx.fillStyle = '#334155';
      ctx.beginPath();
      ctx.roundRect(dx - 11, dy - 14, 22, 10, 3);
      ctx.fill();

      // 데스크 그림자 및 우드 상판
      ctx.fillStyle = 'rgba(0,0,0,0.4)';
      ctx.beginPath();
      ctx.roundRect(dx - 41, dy + 9, 82, 33, 4);
      ctx.fill();
      ctx.fillStyle = '#78350f';
      ctx.beginPath();
      ctx.roundRect(dx - 39, dy + 5, 78, 28, 4);
      ctx.fill();
      ctx.fillStyle = '#b45309';
      ctx.fillRect(dx - 36, dy + 7, 72, 21);
      ctx.fillStyle = '#451a03';
      ctx.fillRect(dx - 36, dy + 28, 72, 5);

      // 책상 스탠드 조명 (Desk Lamp) + 따뜻한 광원 효과
      const lx = dx - 31;
      const ly = dy + 8;
      ctx.fillStyle = '#475569';
      ctx.fillRect(lx - 3, ly + 8, 6, 3);
      ctx.strokeStyle = '#94a3b8';
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.moveTo(lx, ly + 8);
      ctx.lineTo(lx - 2, ly + 1);
      ctx.lineTo(lx + 4, ly - 2);
      ctx.stroke();
      ctx.fillStyle = '#fbbf24';
      ctx.beginPath();
      ctx.arc(lx + 5, ly - 1, 3.2, Math.PI * 0.8, Math.PI * 2.2);
      ctx.fill();

      const lampGlow = ctx.createRadialGradient(lx + 6, ly + 6, 1, lx + 6, ly + 6, 18);
      lampGlow.addColorStop(0, 'rgba(253, 224, 71, 0.38)');
      lampGlow.addColorStop(1, 'rgba(253, 224, 71, 0)');
      ctx.fillStyle = lampGlow;
      ctx.beginPath();
      ctx.arc(lx + 6, ly + 6, 18, 0, Math.PI * 2);
      ctx.fill();

      // 작업 중인 모니터 화면 은은한 네온 글로우(Bloom) 효과 (createRadialGradient)
      if (isWorking || isSelectedRoom) {
        const bloomRadius = isWorking ? 38 + Math.sin(f * 0.14) * 4 : 24;
        const monitorBloom = ctx.createRadialGradient(dx - 4, dy + 8, 2, dx - 4, dy + 8, bloomRadius);
        if (isWorking) {
          monitorBloom.addColorStop(0, 'rgba(52, 211, 153, 0.5)');
          monitorBloom.addColorStop(0.45, 'rgba(56, 189, 248, 0.25)');
          monitorBloom.addColorStop(1, 'rgba(56, 189, 248, 0)');
        } else {
          monitorBloom.addColorStop(0, 'rgba(56, 189, 248, 0.18)');
          monitorBloom.addColorStop(1, 'rgba(56, 189, 248, 0)');
        }
        ctx.save();
        ctx.fillStyle = monitorBloom;
        ctx.beginPath();
        ctx.arc(dx - 4, dy + 8, bloomRadius, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      // 메인 모니터 & 서브 모니터
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(dx - 22, dy, 34, 17);
      ctx.fillStyle = isWorking ? '#022c22' : isSelectedRoom ? '#1e293b' : '#334155';
      ctx.fillRect(dx - 20, dy + 2, 30, 13);

      ctx.fillStyle = '#0f172a';
      ctx.fillRect(dx + 14, dy + 2, 16, 14);
      ctx.fillStyle = isWorking ? '#0c4a6e' : '#1e293b';
      ctx.fillRect(dx + 16, dy + 4, 12, 10);

      // 키보드 & 머그컵
      ctx.fillStyle = '#cbd5e1';
      ctx.fillRect(dx - 12, dy + 19, 20, 4);
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(dx + 26, dy + 17, 6, 7);
      ctx.fillStyle = '#d97706';
      ctx.fillRect(dx + 27, dy + 18, 4, 3);

      if (isWorking) {
        const lineY = f % 8;
        ctx.fillStyle = '#34d399';
        ctx.fillRect(dx - 18, dy + 4 + (lineY % 5), 18, 2);
        ctx.fillStyle = '#38bdf8';
        ctx.fillRect(dx - 18, dy + 9, 24, 2);
        ctx.fillStyle = '#67e8f9';
        ctx.fillRect(dx + 18, dy + 6 + (lineY % 4), 8, 1.5);
      }
    };

    // 2.5등신 SD(Chibi) 아케이드 스타일 캐릭터 렌더링
    const drawStaffCharacter = (
      ctx: CanvasRenderingContext2D,
      ag: OfficeStaff,
      idx: number,
      isWalking: boolean,
      isWorkingDesk: boolean,
      f: number
    ) => {
      const walkCycle = isWalking ? Math.sin(f * 0.22 * speedRef.current + idx) : 0;
      const idleBreath = Math.sin(f * 0.08 + idx) * 0.8;
      const workBob = isWorkingDesk ? Math.sin(f * 0.32 + idx) * 1.6 : idleBreath;
      const bounceY = isWalking ? Math.abs(walkCycle) * -3.8 : workBob;

      // 보행 시 미세한 좌우 스웨이(Sway)
      const swayX = isWalking
        ? Math.sin(f * 0.22 * speedRef.current + idx) * 1.8
        : isWorkingDesk
        ? Math.sin(f * 0.16 + idx) * 0.6
        : 0;

      // 숨쉬기 탄성 및 보행 탄성 (Squash & Stretch)
      const squashPhase = isWalking
        ? Math.cos(f * 0.44 * speedRef.current + idx) * 0.065
        : isWorkingDesk
        ? Math.sin(f * 0.32 + idx) * 0.038
        : Math.sin(f * 0.08 + idx) * 0.028;
      const scaleX = 1 - squashPhase * 0.75;
      const scaleY = 1 + squashPhase;

      const cx = Math.round(ag.x + swayX);
      const cy = Math.round(ag.y + bounceY);

      // 바닥 그림자 & 선택된 팀 오라
      if (ag.isSelectedTeam) {
        const shadowGlow = ctx.createRadialGradient(ag.x, ag.y + 14, 2, ag.x, ag.y + 14, 23);
        if (ag.taskLabel.includes('반려')) {
          shadowGlow.addColorStop(0, 'rgba(244, 63, 94, 0.68)');
          shadowGlow.addColorStop(1, 'rgba(244, 63, 94, 0)');
        } else if (ag.isShelfMode) {
          shadowGlow.addColorStop(0, 'rgba(250, 204, 21, 0.68)');
          shadowGlow.addColorStop(1, 'rgba(250, 204, 21, 0)');
        } else {
          shadowGlow.addColorStop(0, 'rgba(16, 185, 129, 0.6)');
          shadowGlow.addColorStop(1, 'rgba(16, 185, 129, 0)');
        }
        ctx.fillStyle = shadowGlow;
        ctx.beginPath();
        ctx.ellipse(ag.x, ag.y + 14, 21, 8.5, 0, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.fillStyle = 'rgba(0,0,0,0.35)';
        ctx.beginPath();
        ctx.ellipse(ag.x, ag.y + 14, 13, 5, 0, 0, Math.PI * 2);
        ctx.fill();
      }

      const pivotX = cx;
      const pivotY = ag.y + 13;
      ctx.save();
      ctx.translate(pivotX, pivotY);
      ctx.scale(scaleX, scaleY);
      ctx.translate(-pivotX, -pivotY);

      // SD 다리 & 신발
      const leftLegY = isWalking ? Math.round(walkCycle * 3.5) : 0;
      const rightLegY = isWalking ? Math.round(-walkCycle * 3.5) : 0;
      ctx.fillStyle = '#0f172a';
      ctx.beginPath();
      ctx.roundRect(cx - 7, cy + 5 + leftLegY, 5.5, 8, 2);
      ctx.roundRect(cx + 1.5, cy + 5 + rightLegY, 5.5, 8, 2);
      ctx.fill();

      // SD 상체 자켓 & 셔츠/넥타이
      ctx.fillStyle = ag.shirtColor;
      ctx.beginPath();
      ctx.roundRect(cx - 11, cy - 6, 22, 13, 4);
      ctx.fill();
      ctx.strokeStyle = '#0f172a';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(cx - 2.5, cy - 5, 5, 7);
      ctx.fillStyle = ag.role === 'CEO' ? '#fbbf24' : ag.role === 'SUPERVISOR' ? '#f43f5e' : '#38bdf8';
      ctx.fillRect(cx - 1, cy - 3, 2, 6);

      // SD 팔과 손
      const armOffset = isWorkingDesk ? Math.round(Math.sin(f * 0.5 + idx) * 2.8) : Math.round(walkCycle * 2.2);
      ctx.fillStyle = ag.shirtColor;
      ctx.beginPath();
      ctx.roundRect(cx - 15, cy - 4 + armOffset, 4.5, 9, 2);
      ctx.roundRect(cx + 10.5, cy - 4 - armOffset, 4.5, 9, 2);
      ctx.fill();
      ctx.fillStyle = '#fed7aa';
      ctx.beginPath();
      ctx.arc(cx - 12.8, cy + 5.5 + armOffset, 2.2, 0, Math.PI * 2);
      ctx.arc(cx + 12.8, cy + 5.5 - armOffset, 2.2, 0, Math.PI * 2);
      ctx.fill();

      // 2.5등신 SD 헤드 아웃라인 & 풍성한 헤어 볼륨
      ctx.fillStyle = '#0f172a';
      ctx.beginPath();
      ctx.roundRect(cx - 15, cy - 29, 30, 25, 8);
      ctx.fill();

      if (ag.facing === 'UP') {
        ctx.fillStyle = ag.hairColor;
        ctx.beginPath();
        ctx.roundRect(cx - 14, cy - 28, 28, 23, 7);
        ctx.fill();
        ctx.fillStyle = ag.hairShade;
        ctx.fillRect(cx - 13, cy - 11, 26, 6);
        // 헤어 엔젤링 하이라이트
        ctx.fillStyle = 'rgba(255,255,255,0.45)';
        ctx.beginPath();
        ctx.ellipse(cx, cy - 22, 9, 2.5, 0, 0, Math.PI * 2);
        ctx.fill();
      } else {
        // 얼굴 피부
        ctx.fillStyle = '#ffedd5';
        ctx.beginPath();
        ctx.roundRect(cx - 12.5, cy - 24, 25, 19, 6);
        ctx.fill();

        const eyeShiftX = ag.facing === 'LEFT' ? -2 : ag.facing === 'RIGHT' ? 2 : 0;

        // 발그레한 볼터치
        ctx.fillStyle = 'rgba(251, 113, 133, 0.65)';
        ctx.beginPath();
        ctx.ellipse(cx - 8.5 + eyeShiftX, cy - 10.5, 2.8, 1.6, 0, 0, Math.PI * 2);
        ctx.ellipse(cx + 8.5 + eyeShiftX, cy - 10.5, 2.8, 1.6, 0, 0, Math.PI * 2);
        ctx.fill();

        // 반짝이는 큰 아케이드 눈동자 (듀얼 하이라이트)
        if ((f + idx * 31) % 160 > 5) {
          // 눈동자 베이스
          ctx.fillStyle = '#0f172a';
          ctx.beginPath();
          ctx.roundRect(cx - 7.5 + eyeShiftX, cy - 16.5, 4.2, 5.2, 1.5);
          ctx.roundRect(cx + 3.3 + eyeShiftX, cy - 16.5, 4.2, 5.2, 1.5);
          ctx.fill();
          // 눈동자 하단 컬러 반사광
          ctx.fillStyle = ag.hairColor;
          ctx.fillRect(cx - 6.8 + eyeShiftX, cy - 13, 2.8, 1.4);
          ctx.fillRect(cx + 4.0 + eyeShiftX, cy - 13, 2.8, 1.4);
          // 메인 화이트 별빛 하이라이트
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(cx - 7.0 + eyeShiftX, cy - 16.0, 2.0, 2.0);
          ctx.fillRect(cx + 3.8 + eyeShiftX, cy - 16.0, 2.0, 2.0);
          ctx.fillRect(cx - 4.5 + eyeShiftX, cy - 13.0, 1.0, 1.0);
          ctx.fillRect(cx + 6.3 + eyeShiftX, cy - 13.0, 1.0, 1.0);
        } else {
          // 눈 깜빡임
          ctx.fillStyle = '#0f172a';
          ctx.fillRect(cx - 7 + eyeShiftX, cy - 14, 4, 1.5);
          ctx.fillRect(cx + 3 + eyeShiftX, cy - 14, 4, 1.5);
        }

        // 풍성한 앞머리 & 옆머리 볼륨
        ctx.fillStyle = ag.hairShade;
        ctx.beginPath();
        ctx.roundRect(cx - 14.5, cy - 30, 29, 7, 5);
        ctx.fill();

        ctx.fillStyle = ag.hairColor;
        ctx.beginPath();
        ctx.roundRect(cx - 14, cy - 28.5, 28, 8.5, 5);
        ctx.fill();
        // 옆머리 락(Locks)
        ctx.beginPath();
        ctx.roundRect(cx - 14.5, cy - 22, 4, 13, 2);
        ctx.roundRect(cx + 10.5, cy - 22, 4, 13, 2);
        ctx.fill();
        // 정수리 바보털(아호게) 볼륨 포인트
        ctx.beginPath();
        ctx.ellipse(cx + 2, cy - 30.5, 4, 2, -0.3, 0, Math.PI * 2);
        ctx.fill();

        // 헤어 하이라이트 (광택)
        ctx.fillStyle = 'rgba(255,255,255,0.52)';
        ctx.beginPath();
        ctx.roundRect(cx - 9, cy - 27, 16, 2.5, 1.2);
        ctx.fill();

        // 액세서리 디테일 (안경 / 헤드셋 / 대표 배지)
        if (ag.accessory === 'GLASSES') {
          ctx.strokeStyle = '#e2e8f0';
          ctx.lineWidth = 1.2;
          ctx.strokeRect(cx - 8.5 + eyeShiftX, cy - 17, 5.8, 5.2);
          ctx.strokeRect(cx + 2.5 + eyeShiftX, cy - 17, 5.8, 5.2);
          ctx.beginPath();
          ctx.moveTo(cx - 2.7 + eyeShiftX, cy - 14.5);
          ctx.lineTo(cx + 2.5 + eyeShiftX, cy - 14.5);
          ctx.stroke();
        } else if (ag.accessory === 'HEADSET') {
          ctx.strokeStyle = '#38bdf8';
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(cx, cy - 20, 14.5, Math.PI * 1.05, Math.PI * 1.95);
          ctx.stroke();
          ctx.fillStyle = '#0284c7';
          ctx.beginPath();
          ctx.roundRect(cx - 16.5, cy - 19, 3.5, 7, 1.5);
          ctx.roundRect(cx + 13, cy - 19, 3.5, 7, 1.5);
          ctx.fill();
        } else if (ag.accessory === 'CROWN_PIN') {
          ctx.fillStyle = '#fbbf24';
          ctx.beginPath();
          ctx.arc(cx, cy - 29.5, 3, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      if (ag.carryingBook) {
        ctx.fillStyle = '#fef08a';
        ctx.fillRect(cx + 8, cy - 8, 12, 14);
        ctx.strokeStyle = '#ca8a04';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(cx + 8, cy - 8, 12, 14);
      }

      ctx.restore();
    };

    const drawStaffOverlay = (
      ctx: CanvasRenderingContext2D,
      ag: OfficeStaff,
      isWalking: boolean,
      isWorkingDesk: boolean
    ) => {
      const cx = Math.round(ag.x);
      const isInMeeting = detectRoomByPoint(ag.x, ag.y) === 'MEETING_ROOM' && !isWalking;
      const labelY = isInMeeting ? Math.round(ag.y + 18) : Math.round(ag.y + 38);

      // 비활성(대기) 부서원: 알약 형태의 둥근 다크 네임태그 [이름 (대기)]
      if (!ag.isSelectedTeam) {
        const pillW = 78;
        const pillH = 19;
        const pillX = cx - pillW / 2;
        ctx.fillStyle = 'rgba(15, 23, 42, 0.86)';
        ctx.beginPath();
        ctx.roundRect(pillX, labelY, pillW, pillH, 9.5);
        ctx.fill();
        ctx.strokeStyle = 'rgba(100, 116, 139, 0.65)';
        ctx.lineWidth = 1.2;
        ctx.stroke();

        ctx.fillStyle = '#64748b';
        ctx.beginPath();
        ctx.arc(pillX + 10, labelY + 9.5, 2.5, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#cbd5e1';
        ctx.font = 'bold 9px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${ag.name.split(' ')[0]} (대기)`, cx + 3, labelY + 12.5);
        return;
      }

      // 전담 투입 부서원: 둥근 아케이드 상태 배지 + 프로그레스 바
      const isReject = ag.taskLabel.includes('반려');
      ctx.fillStyle = 'rgba(15, 23, 42, 0.94)';
      ctx.beginPath();
      ctx.roundRect(cx - 54, labelY, 108, 29, 8);
      ctx.fill();
      ctx.strokeStyle = isReject ? '#f43f5e' : ag.isShelfMode ? '#fbbf24' : isWorkingDesk ? '#38bdf8' : '#10b981';
      ctx.lineWidth = 1.6;
      ctx.stroke();

      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(ag.name, cx, labelY + 11.5);

      ctx.fillStyle = '#1e293b';
      ctx.beginPath();
      ctx.roundRect(cx - 48, labelY + 15.5, 96, 9, 4.5);
      ctx.fill();
      if (ag.progress > 0) {
        ctx.fillStyle = isReject ? '#f43f5e' : ag.isShelfMode ? '#f59e0b' : ag.progress >= 100 ? '#10b981' : '#0ea5e9';
        ctx.beginPath();
        ctx.roundRect(cx - 48, labelY + 15.5, Math.max(8, Math.round((96 * ag.progress) / 100)), 9, 4.5);
        ctx.fill();
      }
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 8px sans-serif';
      ctx.fillText(isWalking ? '🚶 이동 중..' : ag.taskLabel.slice(0, 14), cx, labelY + 23);

      if (!isWalking && ag.activeBubble) {
        if (ag.lastBubbleText !== ag.activeBubble) {
          ag.lastBubbleText = ag.activeBubble;
          ag.bubbleAnim = 0;
        }
        ag.bubbleAnim = Math.min(1, ag.bubbleAnim + 0.085);
        const bScale = easeOutBack(ag.bubbleAnim);

        const bw = 196;
        const bh = 32;
        let bx = cx - bw / 2;
        let by = Math.round(ag.y - 66);

        if (isInMeeting) {
          if (ag.role === 'CEO') {
            bx = cx - bw + 20;
            by = Math.round(ag.y - 68);
          } else if (ag.role === 'SUPERVISOR') {
            bx = cx - 20;
            by = Math.round(ag.y - 68);
          } else if (ag.role === 'WORKER1') {
            bx = cx - bw + 20;
            by = Math.round(ag.y + 48);
          } else {
            bx = cx - 20;
            by = Math.round(ag.y + 48);
          }
        }

        bx = Math.max(8, Math.min(CW - bw - 8, bx));
        by = Math.max(6, Math.min(CH - bh - 6, by));

        const centerBx = bx + bw / 2;
        const centerBy = by + bh / 2;

        ctx.save();
        ctx.translate(centerBx, centerBy);
        ctx.scale(bScale, bScale);
        ctx.translate(-centerBx, -centerBy);

        ctx.fillStyle = isReject ? '#881337' : ag.isShelfMode ? '#fef3c7' : '#ffffff';
        ctx.beginPath();
        ctx.roundRect(bx, by, bw, bh, 8);
        ctx.fill();
        ctx.strokeStyle = isReject ? '#fb7185' : ag.isShelfMode ? '#d97706' : '#0f172a';
        ctx.lineWidth = 1.8;
        ctx.stroke();

        ctx.fillStyle = isReject ? '#ffe4e6' : '#0f172a';
        ctx.font = 'bold 9px sans-serif';
        ctx.textAlign = 'center';
        const l1 = ag.activeBubble.slice(0, 23);
        const l2 = ag.activeBubble.slice(23, 45);
        ctx.fillText(l1, bx + bw / 2, by + (l2 ? 13 : 19));
        if (l2) ctx.fillText(l2, bx + bw / 2, by + 25);

        ctx.restore();
      }
    };

    const render = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      frameCountRef.current += 1;
      const f = frameCountRef.current;
      if (archiveHitFlashRef.current > 0) archiveHitFlashRef.current -= 1;
      if (ceoWaveFlashRef.current > 0) ceoWaveFlashRef.current -= 1;

      ctx.clearRect(0, 0, CW, CH);

      // 복도 바닥 타일
      for (let y = 0; y < CH; y += 24) {
        for (let x = 0; x < CW; x += 24) {
          ctx.fillStyle = (Math.floor(x / 24) + Math.floor(y / 24)) % 2 === 0 ? '#334155' : '#293548';
          ctx.fillRect(x, y, 24, 24);
        }
      }
      // 중앙 복도 가이드 카펫 트랙
      ctx.fillStyle = 'rgba(15, 23, 42, 0.65)';
      ctx.fillRect(20, CORRIDOR_Y - 20, CW - 40, 40);
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.25)';
      ctx.lineWidth = 1;
      ctx.strokeRect(20, CORRIDOR_Y - 20, CW - 40, 40);

      // 복도 화분 디테일 (방 사이 복도 포인트)
      drawLushPotPlant(ctx, 375, CORRIDOR_Y - 12, f, 1.0);
      drawLushPotPlant(ctx, 745, CORRIDOR_Y - 12, f, 1.0);
      drawLushPotPlant(ctx, 34, CORRIDOR_Y - 12, f, 0.9);
      drawLushPotPlant(ctx, 1086, CORRIDOR_Y - 12, f, 0.9);

      const staffList = Object.values(staffRef.current);

      (Object.entries(ROOMS) as Array<[DeptRoomKey, typeof ROOMS.HR_ROOM]>).forEach(([rKey, r]) => {
        const isRoomActive = staffList.some((s) => s.roomKey === rKey && s.isSelectedTeam && rKey !== 'MEETING_ROOM');
        drawRoomFloor(ctx, r.rx, r.ry, r.rw, r.rh, r.floorType, r.badgeColor, isRoomActive, f);

        if (r.ry < 100 && rKey !== 'QA_ROOM') {
          drawWindowAndSunbeam(ctx, r.rx + 145, r.ry + 2, f);
          drawWindowAndSunbeam(ctx, r.rx + 230, r.ry + 2, f);
        }

        drawMetalMoldingFrame(ctx, r.rx, r.ry, r.rw, r.rh, r.badgeColor, isRoomActive, r.doorX, r.doorY);

        if (rKey !== 'MEETING_ROOM') {
          const isShelfGlowing =
            isRoomActive &&
            (archiveHitFlashRef.current > 0 ||
              staffList.some((s) => s.roomKey === rKey && Math.hypot(s.x - r.shelf.x, s.y - r.shelf.y) < 35));
          drawBookshelf(ctx, r.shelf.x, r.shelf.y, isShelfGlowing, f);
          drawBookshelf(ctx, r.shelf.x + 88, r.shelf.y, false, f);
          drawOfficeProps(ctx, r.rx, r.ry, r.rw, r.rh, rKey, f);
        } else {
          // 5) 중앙 회의실: 골드 월계관 엠블럼, 국기/사기, 의자 6개, 원형 회의 테이블
          // VIP 레드/골드 카펫
          ctx.fillStyle = '#78350f';
          ctx.beginPath();
          ctx.roundRect(r.rx + 42, r.ry + 62, r.rw - 84, r.rh - 90, 8);
          ctx.fill();
          ctx.fillStyle = '#fef3c7';
          ctx.beginPath();
          ctx.roundRect(r.rx + 46, r.ry + 66, r.rw - 92, r.rh - 98, 6);
          ctx.fill();
          ctx.strokeStyle = '#d97706';
          ctx.lineWidth = 2.5;
          ctx.strokeRect(r.rx + 50, r.ry + 70, r.rw - 100, r.rh - 106);

          // 상단 벽면 골드 월계관 엠블럼 & 태극기/사기(국기)
          const emX = MEETING_TABLE_CENTER.x;
          const emY = r.ry + 38;
          ctx.fillStyle = '#0f172a';
          ctx.beginPath();
          ctx.arc(emX, emY, 16, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = '#fbbf24';
          ctx.lineWidth = 2;
          ctx.stroke();
          // 월계관 아치
          ctx.strokeStyle = '#fde047';
          ctx.lineWidth = 1.8;
          ctx.beginPath();
          ctx.arc(emX, emY, 11, Math.PI * 0.2, Math.PI * 0.8);
          ctx.stroke();
          ctx.beginPath();
          ctx.arc(emX, emY, 11, Math.PI * 1.2, Math.PI * 1.8);
          ctx.stroke();
          ctx.fillStyle = '#fbbf24';
          ctx.font = 'bold 9px sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText('VIP', emX, emY + 3);

          // 좌·우 의전 국기/사기 스탠드
          const drawFlag = (fx: number, fy: number, flagColor: string) => {
            ctx.fillStyle = '#fbbf24';
            ctx.fillRect(fx - 4, fy + 16, 8, 3);
            ctx.strokeStyle = '#fde047';
            ctx.lineWidth = 1.8;
            ctx.beginPath();
            ctx.moveTo(fx, fy + 16);
            ctx.lineTo(fx, fy - 12);
            ctx.stroke();
            ctx.fillStyle = flagColor;
            ctx.beginPath();
            ctx.moveTo(fx, fy - 11);
            ctx.lineTo(fx + 16, fy - 6);
            ctx.lineTo(fx, fy);
            ctx.closePath();
            ctx.fill();
          };
          drawFlag(emX - 42, emY, '#3b82f6');
          drawFlag(emX + 34, emY, '#10b981');

          // 회의실 중앙 테이블 조명 글로우
          const tableGlow = ctx.createRadialGradient(
            MEETING_TABLE_CENTER.x,
            MEETING_TABLE_CENTER.y,
            8,
            MEETING_TABLE_CENTER.x,
            MEETING_TABLE_CENTER.y,
            84
          );
          tableGlow.addColorStop(0, 'rgba(251, 191, 36, 0.38)');
          tableGlow.addColorStop(1, 'rgba(251, 191, 36, 0)');
          ctx.fillStyle = tableGlow;
          ctx.beginPath();
          ctx.arc(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 84, 0, Math.PI * 2);
          ctx.fill();

          // 원형 테이블 주변 6개 임원용 가죽 의자
          for (let ci = 0; ci < 6; ci++) {
            const ang = (ci * Math.PI) / 3;
            const chX = MEETING_TABLE_CENTER.x + Math.cos(ang) * 58;
            const chY = MEETING_TABLE_CENTER.y + Math.sin(ang) * 52;
            ctx.fillStyle = '#1e293b';
            ctx.beginPath();
            ctx.arc(chX, chY, 10, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#fbbf24';
            ctx.lineWidth = 1.5;
            ctx.stroke();
          }

          // 원형 회의 테이블 본체 + 골드 엠블럼 링
          ctx.fillStyle = 'rgba(0,0,0,0.4)';
          ctx.beginPath();
          ctx.arc(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y + 5, 50, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = '#78350f';
          ctx.beginPath();
          ctx.arc(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 49, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = '#b45309';
          ctx.beginPath();
          ctx.arc(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 41, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = '#fde047';
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 26, 0, Math.PI * 2);
          ctx.stroke();

          if (ceoWaveFlashRef.current > 0) {
            const radius = 50 + ((120 - ceoWaveFlashRef.current) % 45) * 2.2;
            ctx.strokeStyle = 'rgba(56, 189, 248, 0.75)';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(MEETING_SEATS.CEO.x, MEETING_SEATS.CEO.y, radius, 0, Math.PI * 2);
            ctx.stroke();
          }
        }
      });

      const walkingMap: Record<string, boolean> = {};
      const workingDeskMap: Record<string, boolean> = {};

      staffList.forEach((ag) => {
        let walking = false;

        if (ag.isSelectedTeam && ag.waypoints.length === 0 && ag.workTimer <= 0 && ag.stageQueue.length > 0) {
          const nextSt = ag.stageQueue.shift()!;
          ag.taskLabel = nextSt.label;
          ag.activeBubble = nextSt.bubble;
          ag.bubbleAnim = 0;
          ag.workTimer = nextSt.workFrames;
          ag.maxWorkTimer = Math.max(1, nextSt.workFrames);
          ag.progress = nextSt.workFrames > 0 ? 15 : 100;
          if (nextSt.isShelfLookup) {
            ag.carryingBook = true;
          }
          ag.waypoints = buildSmartCorridorPath(ag.x, ag.y, nextSt.target, nextSt.via);
        }

        if (ag.waypoints.length > 0) {
          const nextPt = ag.waypoints[0];
          const dx = nextPt.x - ag.x;
          const dy = nextPt.y - ag.y;
          const dist = Math.hypot(dx, dy);
          const catchUpBoost = hasFinalReportRef.current ? 1.85 : 1.0;
          const baseMaxSpeed = 2.75 * speedRef.current * catchUpBoost;

          const isFinalWaypoint = ag.waypoints.length === 1;
          const decelFactor = isFinalWaypoint ? Math.min(1, Math.max(0.32, dist / 34)) : Math.min(1, Math.max(0.55, dist / 18));
          const desiredSpeed = baseMaxSpeed * decelFactor;

          if (Math.abs(dx) > Math.abs(dy)) {
            ag.facing = dx < 0 ? 'LEFT' : 'RIGHT';
          } else {
            ag.facing = dy < 0 ? 'UP' : 'DOWN';
          }

          if (dist <= Math.max(1.2, desiredSpeed)) {
            ag.x = nextPt.x;
            ag.y = nextPt.y;
            ag.vx = 0;
            ag.vy = 0;
            ag.waypoints.shift();
            if (ag.waypoints.length === 0) {
              ag.facing =
                ag.y > MEETING_TABLE_CENTER.y && detectRoomByPoint(ag.x, ag.y) === 'MEETING_ROOM'
                  ? 'UP'
                  : Math.hypot(ag.x - ag.shelfPos.x, ag.y - ag.shelfPos.y) < 20
                  ? 'UP'
                  : 'DOWN';
            }
          } else {
            const targetVx = (dx / dist) * desiredSpeed;
            const targetVy = (dy / dist) * desiredSpeed;
            ag.vx = ag.vx * 0.65 + targetVx * 0.35;
            ag.vy = ag.vy * 0.65 + targetVy * 0.35;
            ag.x += ag.vx;
            ag.y += ag.vy;
            walking = true;

            if (ag.isSelectedTeam && f % 3 === 0) {
              const trailColor = ag.taskLabel.includes('반려')
                ? '244, 63, 94'
                : ag.isShelfMode
                ? '250, 204, 21'
                : ag.role === 'SUPERVISOR'
                ? '56, 189, 248'
                : '52, 211, 153';
              trailsRef.current.push({
                x: ag.x,
                y: ag.y + 13,
                life: 38,
                maxLife: 38,
                color: trailColor,
                role: ag.role,
              });
            }

            if (f % 7 === 0) {
              particlesRef.current.push({
                x: ag.x,
                y: ag.y + 14,
                vx: (Math.random() - 0.5) * 0.5,
                vy: -0.3,
                life: 18,
                maxLife: 18,
                color: 'rgba(203, 213, 225, 0.5)',
              });
            }
          }
        } else if (ag.workTimer > 0) {
          const timerBoost = hasFinalReportRef.current ? 2.2 : 1.0;
          ag.workTimer = Math.max(0, ag.workTimer - speedRef.current * timerBoost);
          ag.progress = Math.min(99, Math.round(((ag.maxWorkTimer - ag.workTimer) / ag.maxWorkTimer) * 100));

          const isAtShelf = Math.hypot(ag.x - ag.shelfPos.x, ag.y - ag.shelfPos.y) < 25;
          if (!isAtShelf && detectRoomByPoint(ag.x, ag.y) !== 'MEETING_ROOM') {
            workingDeskMap[ag.id] = true;
            if (f % 12 === 0) {
              const tokens = ['0', '1', '🔍', '📊', '⚡'];
              particlesRef.current.push({
                x: ag.x + (Math.random() - 0.5) * 24,
                y: ag.y - 18,
                vx: 0,
                vy: -0.65,
                life: 28,
                maxLife: 28,
                text: tokens[Math.floor(Math.random() * tokens.length)],
                color: '#38bdf8',
              });
            }
          } else if (isAtShelf && f % 10 === 0) {
            particlesRef.current.push({
              x: ag.x + (Math.random() - 0.5) * 20,
              y: ag.y - 24,
              vx: 0,
              vy: -0.6,
              life: 26,
              maxLife: 26,
              text: '📖',
              color: '#fde047',
            });
          }

          if (ag.workTimer <= 0) {
            ag.progress = 100;
          }
        }

        walkingMap[ag.id] = walking;
      });

      // 바닥 잔상 트레일(Path Trail) 렌더링
      trailsRef.current = trailsRef.current.filter((tr) => tr.life > 0);
      trailsRef.current.forEach((tr) => {
        tr.life -= 1;
        const ratio = Math.max(0, tr.life / tr.maxLife);
        const radius = 3.5 + ratio * 5.5;
        const trailGrad = ctx.createRadialGradient(tr.x, tr.y, 0.5, tr.x, tr.y, radius * 1.6);
        trailGrad.addColorStop(0, `rgba(${tr.color}, ${ratio * 0.55})`);
        trailGrad.addColorStop(0.6, `rgba(${tr.color}, ${ratio * 0.22})`);
        trailGrad.addColorStop(1, `rgba(${tr.color}, 0)`);
        ctx.fillStyle = trailGrad;
        ctx.beginPath();
        ctx.ellipse(tr.x, tr.y, radius * 1.35, radius * 0.65, 0, 0, Math.PI * 2);
        ctx.fill();
      });

      const selectedMembers = staffList.filter((s) => s.isSelectedTeam);
      if (hasFinalReportRef.current && !reportUnlockedRef.current && selectedMembers.length > 0) {
        const allSelectedInMeeting = selectedMembers.every(
          (ag) =>
            ag.stageQueue.length === 0 &&
            ag.waypoints.length === 0 &&
            ag.workTimer <= 0 &&
            detectRoomByPoint(ag.x, ag.y) === 'MEETING_ROOM'
        );
        if (allSelectedInMeeting) {
          reportUnlockedRef.current = true;
          reportBannerAnimRef.current = 0;
          setReportUnlocked(true);
          onAllGatheredChange?.(true);
        }
      }

      staffList
        .slice()
        .sort((a, b) => a.y - b.y)
        .forEach((ag, idx) => {
          drawStaffCharacter(ctx, ag, idx, walkingMap[ag.id], Boolean(workingDeskMap[ag.id]), f);
        });

      (Object.entries(ROOMS) as Array<[DeptRoomKey, typeof ROOMS.HR_ROOM]>).forEach(([rKey, r]) => {
        const isSelectedRoom = staffList.some((s) => s.roomKey === rKey && s.isSelectedTeam);
        r.desks.forEach((d) => {
          const busy = staffList.some(
            (s) => s.isSelectedTeam && !walkingMap[s.id] && Math.hypot(s.x - d.x, s.y - d.y) < 26
          );
          drawDesk(ctx, d.x, d.y, busy, isSelectedRoom, f);
        });

        // 알약형/메탈 부서 명패 배지
        ctx.fillStyle = 'rgba(15, 23, 42, 0.94)';
        ctx.beginPath();
        ctx.roundRect(r.rx + 10, r.ry + 8, 134, 22, 6);
        ctx.fill();
        ctx.strokeStyle = r.badgeColor;
        ctx.lineWidth = 1.6;
        ctx.stroke();
        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 10.5px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(r.title, r.rx + 77, r.ry + 23);
      });

      particlesRef.current = particlesRef.current.filter((pt) => pt.life > 0);
      particlesRef.current.forEach((pt) => {
        pt.x += pt.vx;
        pt.y += pt.vy;
        pt.life -= 1;
        ctx.globalAlpha = Math.max(0, pt.life / pt.maxLife);
        if (pt.text) {
          ctx.fillStyle = pt.color;
          ctx.font = 'bold 10px sans-serif';
          ctx.fillText(pt.text, pt.x, pt.y);
        } else {
          ctx.fillStyle = pt.color;
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2);
          ctx.fill();
        }
      });
      ctx.globalAlpha = 1.0;

      if (reportUnlockedRef.current) {
        reportBannerAnimRef.current = Math.min(1, reportBannerAnimRef.current + 0.065);
        const bannerScale = easeOutBack(reportBannerAnimRef.current);
        const bounceDoc = Math.sin(f * 0.12) * 3;
        const tx = MEETING_TABLE_CENTER.x;
        const ty = MEETING_TABLE_CENTER.y + bounceDoc;

        ctx.save();
        ctx.translate(tx, ty);
        ctx.scale(bannerScale, bannerScale);
        ctx.translate(-tx, -ty);

        const docGlow = ctx.createRadialGradient(tx, MEETING_TABLE_CENTER.y, 4, tx, MEETING_TABLE_CENTER.y, 42);
        if (f % 30 < 15) {
          docGlow.addColorStop(0, 'rgba(250, 204, 21, 0.72)');
          docGlow.addColorStop(1, 'rgba(250, 204, 21, 0)');
        } else {
          docGlow.addColorStop(0, 'rgba(16, 185, 129, 0.72)');
          docGlow.addColorStop(1, 'rgba(16, 185, 129, 0)');
        }
        ctx.fillStyle = docGlow;
        ctx.beginPath();
        ctx.arc(tx, MEETING_TABLE_CENTER.y, 42, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#fef08a';
        ctx.fillRect(tx - 15, ty - 12, 30, 22);
        ctx.strokeStyle = '#ca8a04';
        ctx.lineWidth = 2;
        ctx.strokeRect(tx - 15, ty - 12, 30, 22);

        ctx.fillStyle = '#059669';
        ctx.beginPath();
        ctx.roundRect(tx - 72, ty - 36, 144, 22, 6);
        ctx.fill();
        ctx.strokeStyle = '#fde047';
        ctx.lineWidth = 1.8;
        ctx.stroke();
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 10px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('📋 최종 보고서 (클릭)', tx, ty - 21);

        ctx.restore();
      }

      staffList
        .slice()
        .sort((a, b) => Number(a.isSelectedTeam) - Number(b.isSelectedTeam))
        .forEach((ag) => {
          drawStaffOverlay(ctx, ag, walkingMap[ag.id], Boolean(workingDeskMap[ag.id]));
        });

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, []);

  return (
    <div className="relative w-full h-full flex flex-col bg-slate-950 overflow-hidden select-none">
      <div className="shrink-0 px-5 py-2 bg-slate-900/80 backdrop-blur-xl border-b border-white/10 flex items-center justify-between text-xs shadow-lg">
        <div className="flex items-center gap-3">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
          </span>
          <span className="font-bold text-slate-200 tracking-tight">{phaseBanner}</span>
          {reportUnlocked && (
            <button
              onClick={onOpenReportModal}
              className="px-3.5 py-1 text-[11px] font-extrabold bg-gradient-to-r from-amber-400 to-yellow-300 hover:from-amber-300 hover:to-yellow-200 text-slate-950 rounded-lg shadow-[0_0_18px_rgba(251,191,36,0.55)] hover:scale-105 active:scale-95 transition-all duration-300 ease-out animate-bounce"
            >
              📋 전자결재 보고서 열람 & 다운로드
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-400 font-medium">시뮬레이션 배속:</span>
          {[
            { label: '0.7x', val: 0.7 },
            { label: '1.0x', val: 1.0 },
            { label: '1.8x', val: 1.8 },
          ].map((opt) => (
            <button
              key={opt.val}
              onClick={() => setSpeedMult(opt.val)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-bold border backdrop-blur-md transition-all duration-300 ease-out ${
                speedMult === opt.val
                  ? 'bg-emerald-600/90 border-emerald-400/80 text-white shadow-[0_0_12px_rgba(16,185,129,0.4)] scale-105'
                  : 'bg-slate-950/70 border-white/10 text-slate-400 hover:text-slate-100 hover:border-white/25 hover:bg-slate-900/80'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="relative flex-1 min-h-0 flex items-center justify-center p-2.5 bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950">
        <canvas
          ref={canvasRef}
          width={CW}
          height={CH}
          onClick={(e) => handleCanvasPos(e, true)}
          onMouseMove={(e) => handleCanvasPos(e, false)}
          onMouseLeave={() => setHoveredStaff(null)}
          className={`w-full h-full object-contain rounded-2xl border border-white/10 shadow-[0_0_50px_rgba(0,0,0,0.8)] bg-slate-900 transition-all duration-300 ease-out ${
            isHoveringReport ? 'cursor-pointer ring-2 ring-amber-400/90 shadow-[0_0_35px_rgba(251,191,36,0.3)]' : ''
          }`}
        />

        {hoveredStaff && (
          <div className="absolute bottom-5 right-6 z-30 w-72 p-3.5 rounded-2xl bg-slate-900/85 backdrop-blur-xl border border-emerald-500/40 shadow-[0_8px_32px_rgba(0,0,0,0.65)] pointer-events-none transition-all duration-300 ease-out">
            <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-2">
              <div>
                <span className="text-xs font-extrabold text-white block">{hoveredStaff.name}</span>
                <span className="text-[10px] text-emerald-400 font-semibold">{hoveredStaff.deptTitle}</span>
              </div>
              <span
                className={`px-2 py-0.5 text-[9px] font-bold rounded-full border ${
                  hoveredStaff.isSelected
                    ? 'bg-emerald-950/80 text-emerald-300 border-emerald-500/50 shadow-[0_0_10px_rgba(16,185,129,0.25)]'
                    : 'bg-slate-900/80 text-slate-400 border-white/10'
                }`}
              >
                {hoveredStaff.isSelected ? '🟢 전담 투입 중' : '⚪ 부서 대기'}
              </span>
            </div>
            <div className="space-y-1.5 text-[11px]">
              <div className="flex justify-between text-slate-300">
                <span className="text-slate-400">현재 태스크:</span>
                <span className="font-bold text-sky-300">{hoveredStaff.taskLabel}</span>
              </div>
              <div className="w-full bg-slate-800/80 h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-gradient-to-r from-emerald-500 to-sky-400 h-full transition-all duration-300 ease-out"
                  style={{ width: `${hoveredStaff.progress}%` }}
                />
              </div>
              <p className="text-[10px] text-slate-300 italic pt-1 leading-snug">
                &ldquo;{hoveredStaff.bubble}&rdquo;
              </p>
            </div>
          </div>
        )}

        {reportUnlocked && (
          <button
            onClick={() => onOpenReportModal && onOpenReportModal()}
            style={{
              animation: 'bounce 1.2s infinite, pulse 2.4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
            }}
            className="absolute bottom-6 left-1/2 -translate-x-1/2 z-30 px-6 py-3 text-xs font-extrabold bg-gradient-to-r from-amber-400 via-yellow-300 to-amber-400 hover:brightness-110 hover:scale-105 active:scale-95 text-slate-950 rounded-2xl shadow-[0_0_35px_rgba(251,191,36,0.85)] border-2 border-white/90 backdrop-blur-md flex items-center gap-2.5 cursor-pointer transition-all duration-300 ease-out"
          >
            <span>📋 중앙 회의실 최종 전자결재 보고서 도착! (클릭하여 결재문서 열람 및 Word·Excel·PDF 저장)</span>
          </button>
        )}
      </div>
    </div>
  );
}
