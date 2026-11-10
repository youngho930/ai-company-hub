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
}> = [
  { id: 'ceo', name: '신영호 대표', deptTitle: '경영진', roomKey: 'MEETING_ROOM', role: 'CEO', deskIdx: 0, hair: '#f59e0b', shade: '#b45309', shirt: '#3730a3' },
  { id: 'sup-hr-01', name: '윤지아 팀장', deptTitle: '인사·리서치팀', roomKey: 'HR_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#fb7185', shade: '#be123c', shirt: '#9f1239' },
  { id: 'wrk-hr-01', name: '박수아 수석', deptTitle: '인사·리서치팀', roomKey: 'HR_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#67e8f9', shade: '#0891b2', shirt: '#1e40af' },
  { id: 'wrk-hr-02', name: '한채원 책임', deptTitle: '인사·리서치팀', roomKey: 'HR_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#c084fc', shade: '#7e22ce', shirt: '#065f46' },
  { id: 'sup-dev-01', name: '임민서 팀장', deptTitle: 'SW개발팀', roomKey: 'DEV_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#38bdf8', shade: '#0284c7', shirt: '#1e3a8a' },
  { id: 'wrk-dev-01', name: '임지우 수석', deptTitle: 'SW개발팀', roomKey: 'DEV_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#a3e635', shade: '#4d7c0f', shirt: '#0f766e' },
  { id: 'wrk-dev-02', name: '임유진 책임', deptTitle: 'SW개발팀', roomKey: 'DEV_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#f472b6', shade: '#db2777', shirt: '#6b21a8' },
  { id: 'sup-qa-01', name: '임승현 팀장', deptTitle: '품질보증·QA팀', roomKey: 'QA_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#fb923c', shade: '#c2410c', shirt: '#047857' },
  { id: 'wrk-qa-01', name: '한도윤 수석', deptTitle: '품질보증·QA팀', roomKey: 'QA_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#2dd4bf', shade: '#0f766e', shirt: '#1d4ed8' },
  { id: 'wrk-qa-02', name: '장지우 책임', deptTitle: '품질보증·QA팀', roomKey: 'QA_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#e879f9', shade: '#a21caf', shirt: '#4338ca' },
  { id: 'sup-fin-01', name: '정우성 팀장', deptTitle: '재무·데이터팀', roomKey: 'FIN_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#facc15', shade: '#a16207', shirt: '#1e40af' },
  { id: 'wrk-fin-01', name: '강현우 수석', deptTitle: '재무·데이터팀', roomKey: 'FIN_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#60a5fa', shade: '#2563eb', shirt: '#065f46' },
  { id: 'wrk-fin-02', name: '배수빈 책임', deptTitle: '재무·데이터팀', roomKey: 'FIN_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#f87171', shade: '#b91c1c', shirt: '#5b21b6' },
  { id: 'sup-mkt-01', name: '조다은 팀장', deptTitle: '마케팅·전략팀', roomKey: 'MKT_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#fb7185', shade: '#be123c', shirt: '#9f1239' },
  { id: 'wrk-mkt-01', name: '장건우 수석', deptTitle: '마케팅·전략팀', roomKey: 'MKT_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#38bdf8', shade: '#0369a1', shirt: '#1e40af' },
  { id: 'wrk-mkt-02', name: '권하윤 책임', deptTitle: '마케팅·전략팀', roomKey: 'MKT_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#c084fc', shade: '#6b21a8', shirt: '#047857' },
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
  if (anyMatch(d, ['품질', 'qa', '생산', 'erp', '백오피스'])) return 'QA_ROOM';
  if (anyMatch(d, ['재무', '원가', 'fin', '데이터', 'dat'])) return 'FIN_ROOM';
  if (anyMatch(d, ['마케팅', '커머스', 'mkt', '글로벌', 'glb'])) return 'MKT_ROOM';
  return 'HR_ROOM';
}

// Elastic easeOutBack curve for scale bounce animations
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

      // 중앙 조명 은은한 네온/앰비언트 글로우 (createRadialGradient)
      const centerX = rx + rw / 2;
      const centerY = ry + rh / 2 + 10;
      const lightRadius = Math.max(rw, rh) * 0.62;
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
        roomGlow.addColorStop(0, 'rgba(52, 211, 153, 0.24)');
        roomGlow.addColorStop(0.45, 'rgba(56, 189, 248, 0.11)');
        roomGlow.addColorStop(1, 'rgba(15, 23, 42, 0)');
      } else if (floorType === 'AMBER') {
        roomGlow.addColorStop(0, 'rgba(251, 191, 36, 0.22)');
        roomGlow.addColorStop(0.55, 'rgba(245, 158, 11, 0.08)');
        roomGlow.addColorStop(1, 'rgba(15, 23, 42, 0)');
      } else {
        roomGlow.addColorStop(0, `${badgeColor}24`);
        roomGlow.addColorStop(0.55, `${badgeColor}0c`);
        roomGlow.addColorStop(1, 'rgba(15, 23, 42, 0)');
      }

      ctx.save();
      ctx.fillStyle = roomGlow;
      ctx.fillRect(rx, ry, rw, rh);
      ctx.restore();

      ctx.fillStyle = '#0f172a';
      ctx.fillRect(rx, ry, rw, 14);
      ctx.fillStyle = 'rgba(0,0,0,0.32)';
      ctx.fillRect(rx, ry + 14, rw, 8);
    };

    const drawWindowAndSunbeam = (ctx: CanvasRenderingContext2D, wx: number, wy: number, f: number) => {
      ctx.fillStyle = '#0284c7';
      ctx.fillRect(wx, wy, 72, 12);
      ctx.fillStyle = '#38bdf8';
      ctx.fillRect(wx + 4, wy + 2, 28, 8);
      ctx.fillRect(wx + 38, wy + 2, 28, 8);
      const alpha = 0.07 + Math.sin(f * 0.03) * 0.02;
      ctx.fillStyle = `rgba(186, 230, 253, ${alpha})`;
      ctx.beginPath();
      ctx.moveTo(wx, wy + 12);
      ctx.lineTo(wx + 72, wy + 12);
      ctx.lineTo(wx + 92, wy + 72);
      ctx.lineTo(wx - 20, wy + 72);
      ctx.closePath();
      ctx.fill();
    };

    const drawOfficeProps = (ctx: CanvasRenderingContext2D, rx: number, ry: number, rw: number, rh: number, rKey: DeptRoomKey, f: number) => {
      const wbx = rx + rw - 64;
      const wby = ry + 20;
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(wbx, wby, 48, 26);
      ctx.strokeStyle = '#64748b';
      ctx.lineWidth = 2;
      ctx.strokeRect(wbx, wby, 48, 26);
      ctx.fillStyle = '#fbbf24';
      ctx.fillRect(wbx + 5, wby + 5, 8, 7);
      ctx.fillStyle = '#38bdf8';
      ctx.fillRect(wbx + 16, wby + 5, 8, 7);
      ctx.fillStyle = '#f43f5e';
      ctx.fillRect(wbx + 27, wby + 12, 8, 7);

      const px = rx + 26;
      const py = ry + rh - 32;
      ctx.fillStyle = 'rgba(0,0,0,0.3)';
      ctx.beginPath();
      ctx.ellipse(px, py + 10, 10, 4, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#c2410c';
      ctx.fillRect(px - 6, py, 12, 10);
      ctx.fillStyle = '#15803d';
      ctx.beginPath();
      ctx.arc(px, py - 5, 10, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#4ade80';
      ctx.beginPath();
      ctx.arc(px - 3 + Math.sin(f * 0.05), py - 8, 5, 0, Math.PI * 2);
      ctx.fill();

      if (rKey === 'DEV_ROOM' || rKey === 'FIN_ROOM') {
        const sx = rx + 20;
        const sy = ry + 22;
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(sx, sy, 34, 38);
        ctx.strokeStyle = '#475569';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(sx, sy, 34, 38);
        for (let i = 0; i < 3; i++) {
          ctx.fillStyle = (f + i * 12) % 30 < 15 ? '#34d399' : '#38bdf8';
          ctx.fillRect(sx + 5, sy + 6 + i * 10, 4, 3);
          ctx.fillStyle = '#f43f5e';
          ctx.fillRect(sx + 12, sy + 6 + i * 10, 3, 3);
        }
      } else if (rKey !== 'MEETING_ROOM') {
        const cx = rx + 22;
        const cy = ry + 26;
        ctx.fillStyle = '#e2e8f0';
        ctx.fillRect(cx, cy, 18, 28);
        ctx.fillStyle = '#38bdf8';
        ctx.fillRect(cx + 3, cy - 10, 12, 10);
        ctx.fillStyle = '#ef4444';
        ctx.fillRect(cx + 4, cy + 8, 3, 4);
        ctx.fillStyle = '#3b82f6';
        ctx.fillRect(cx + 10, cy + 8, 3, 4);
      }
    };

    const drawBookshelf = (ctx: CanvasRenderingContext2D, bx: number, by: number, isGlowing: boolean, f: number) => {
      if (isGlowing) {
        const shelfGlow = ctx.createRadialGradient(bx, by - 5, 6, bx, by - 5, 52);
        shelfGlow.addColorStop(0, 'rgba(250, 204, 21, 0.42)');
        shelfGlow.addColorStop(0.5, 'rgba(56, 189, 248, 0.18)');
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
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(dx - 13, dy - 15, 26, 13);
      ctx.fillStyle = '#334155';
      ctx.fillRect(dx - 11, dy - 13, 22, 9);

      ctx.fillStyle = 'rgba(0,0,0,0.38)';
      ctx.fillRect(dx - 40, dy + 9, 80, 32);
      ctx.fillStyle = '#78350f';
      ctx.fillRect(dx - 38, dy + 5, 76, 28);
      ctx.fillStyle = '#b45309';
      ctx.fillRect(dx - 36, dy + 7, 72, 21);
      ctx.fillStyle = '#451a03';
      ctx.fillRect(dx - 36, dy + 28, 72, 5);

      // 작업 중인 모니터 화면 은은한 네온 글로우(Bloom) 효과 (createRadialGradient)
      if (isWorking || isSelectedRoom) {
        const bloomRadius = isWorking ? 38 + Math.sin(f * 0.14) * 4 : 24;
        const monitorBloom = ctx.createRadialGradient(dx - 4, dy + 8, 2, dx - 4, dy + 8, bloomRadius);
        if (isWorking) {
          monitorBloom.addColorStop(0, 'rgba(52, 211, 153, 0.48)');
          monitorBloom.addColorStop(0.45, 'rgba(56, 189, 248, 0.24)');
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

      ctx.fillStyle = '#0f172a';
      ctx.fillRect(dx - 22, dy, 34, 17);
      ctx.fillStyle = isWorking ? '#022c22' : isSelectedRoom ? '#1e293b' : '#334155';
      ctx.fillRect(dx - 20, dy + 2, 30, 13);

      ctx.fillStyle = '#0f172a';
      ctx.fillRect(dx + 14, dy + 2, 16, 14);
      ctx.fillStyle = isWorking ? '#0c4a6e' : '#1e293b';
      ctx.fillRect(dx + 16, dy + 4, 12, 10);

      ctx.fillStyle = '#cbd5e1';
      ctx.fillRect(dx - 12, dy + 19, 20, 4);
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(dx - 30, dy + 14, 6, 7);
      ctx.fillStyle = '#d97706';
      ctx.fillRect(dx - 29, dy + 15, 4, 3);

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

      // 바닥 그림자
      if (ag.isSelectedTeam) {
        const shadowGlow = ctx.createRadialGradient(ag.x, ag.y + 14, 2, ag.x, ag.y + 14, 22);
        if (ag.taskLabel.includes('반려')) {
          shadowGlow.addColorStop(0, 'rgba(244, 63, 94, 0.65)');
          shadowGlow.addColorStop(1, 'rgba(244, 63, 94, 0)');
        } else if (ag.isShelfMode) {
          shadowGlow.addColorStop(0, 'rgba(250, 204, 21, 0.65)');
          shadowGlow.addColorStop(1, 'rgba(250, 204, 21, 0)');
        } else {
          shadowGlow.addColorStop(0, 'rgba(16, 185, 129, 0.58)');
          shadowGlow.addColorStop(1, 'rgba(16, 185, 129, 0)');
        }
        ctx.fillStyle = shadowGlow;
        ctx.beginPath();
        ctx.ellipse(ag.x, ag.y + 14, 20, 8, 0, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.fillStyle = 'rgba(0,0,0,0.32)';
        ctx.beginPath();
        ctx.ellipse(ag.x, ag.y + 14, 12, 4.5, 0, 0, Math.PI * 2);
        ctx.fill();
      }

      // Squash & Stretch 변환 적용 (발 끝 기준점)
      const pivotX = cx;
      const pivotY = ag.y + 13;
      ctx.save();
      ctx.translate(pivotX, pivotY);
      ctx.scale(scaleX, scaleY);
      ctx.translate(-pivotX, -pivotY);

      const leftLegY = isWalking ? Math.round(walkCycle * 3.5) : 0;
      const rightLegY = isWalking ? Math.round(-walkCycle * 3.5) : 0;
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(cx - 6, cy + 5 + leftLegY, 5, 8);
      ctx.fillRect(cx + 1, cy + 5 + rightLegY, 5, 8);

      ctx.fillStyle = ag.shirtColor;
      ctx.fillRect(cx - 10, cy - 5, 20, 12);
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(cx - 2, cy - 4, 4, 6);
      ctx.fillStyle = ag.role === 'CEO' ? '#fbbf24' : ag.role === 'SUPERVISOR' ? '#f43f5e' : '#38bdf8';
      ctx.fillRect(cx - 1, cy - 2, 2, 5);

      const armOffset = isWorkingDesk ? Math.round(Math.sin(f * 0.5 + idx) * 2.8) : Math.round(walkCycle * 2.2);
      ctx.fillStyle = ag.shirtColor;
      ctx.fillRect(cx - 14, cy - 4 + armOffset, 4, 9);
      ctx.fillRect(cx + 10, cy - 4 - armOffset, 4, 9);
      ctx.fillStyle = '#fed7aa';
      ctx.fillRect(cx - 14, cy + 4 + armOffset, 4, 3);
      ctx.fillRect(cx + 10, cy + 4 - armOffset, 4, 3);

      ctx.fillStyle = '#0f172a';
      ctx.fillRect(cx - 13, cy - 26, 26, 22);

      if (ag.facing === 'UP') {
        ctx.fillStyle = ag.hairColor;
        ctx.fillRect(cx - 12, cy - 25, 24, 20);
        ctx.fillStyle = ag.hairShade;
        ctx.fillRect(cx - 12, cy - 10, 24, 5);
      } else {
        ctx.fillStyle = '#ffedd5';
        ctx.fillRect(cx - 11, cy - 23, 22, 18);

        const eyeShiftX = ag.facing === 'LEFT' ? -2 : ag.facing === 'RIGHT' ? 2 : 0;
        ctx.fillStyle = '#fda4af';
        ctx.fillRect(cx - 9 + eyeShiftX, cy - 11, 3, 2);
        ctx.fillRect(cx + 6 + eyeShiftX, cy - 11, 3, 2);

        if ((f + idx * 31) % 160 > 5) {
          ctx.fillStyle = '#0f172a';
          ctx.fillRect(cx - 6 + eyeShiftX, cy - 15, 3, 4);
          ctx.fillRect(cx + 3 + eyeShiftX, cy - 15, 3, 4);
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(cx - 5 + eyeShiftX, cy - 15, 1, 2);
          ctx.fillRect(cx + 4 + eyeShiftX, cy - 15, 1, 2);
        } else {
          ctx.fillStyle = '#0f172a';
          ctx.fillRect(cx - 6 + eyeShiftX, cy - 13, 3, 1);
          ctx.fillRect(cx + 3 + eyeShiftX, cy - 13, 3, 1);
        }

        ctx.fillStyle = ag.hairShade;
        ctx.fillRect(cx - 13, cy - 27, 26, 5);
        ctx.fillStyle = ag.hairColor;
        ctx.fillRect(cx - 12, cy - 26, 24, 7);
        ctx.fillRect(cx - 13, cy - 21, 3, 11);
        ctx.fillRect(cx + 10, cy - 21, 3, 11);
        ctx.fillStyle = 'rgba(255,255,255,0.45)';
        ctx.fillRect(cx - 8, cy - 25, 14, 2);
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

      if (!ag.isSelectedTeam) {
        ctx.fillStyle = 'rgba(15, 23, 42, 0.78)';
        ctx.fillRect(cx - 36, labelY, 72, 18);
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 1;
        ctx.strokeRect(cx - 36, labelY, 72, 18);
        ctx.fillStyle = '#94a3b8';
        ctx.font = 'bold 9px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${ag.name.split(' ')[0]} (대기)`, cx, labelY + 12);
        return;
      }

      const isReject = ag.taskLabel.includes('반려');
      ctx.fillStyle = 'rgba(15, 23, 42, 0.95)';
      ctx.fillRect(cx - 52, labelY, 104, 28);
      ctx.strokeStyle = isReject ? '#f43f5e' : ag.isShelfMode ? '#fbbf24' : isWorkingDesk ? '#38bdf8' : '#10b981';
      ctx.lineWidth = 1.5;
      ctx.strokeRect(cx - 52, labelY, 104, 28);

      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(ag.name, cx, labelY + 11);

      ctx.fillStyle = '#1e293b';
      ctx.fillRect(cx - 48, labelY + 15, 96, 9);
      if (ag.progress > 0) {
        ctx.fillStyle = isReject ? '#f43f5e' : ag.isShelfMode ? '#f59e0b' : ag.progress >= 100 ? '#10b981' : '#0ea5e9';
        ctx.fillRect(cx - 48, labelY + 15, Math.round((96 * ag.progress) / 100), 9);
      }
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 8px sans-serif';
      ctx.fillText(isWalking ? '🚶 이동 중..' : ag.taskLabel.slice(0, 14), cx, labelY + 22.5);

      if (!isWalking && ag.activeBubble) {
        if (ag.lastBubbleText !== ag.activeBubble) {
          ag.lastBubbleText = ag.activeBubble;
          ag.bubbleAnim = 0;
        }
        ag.bubbleAnim = Math.min(1, ag.bubbleAnim + 0.085);
        const bScale = easeOutBack(ag.bubbleAnim);

        const bw = 194;
        const bh = 32;
        let bx = cx - bw / 2;
        let by = Math.round(ag.y - 64);

        if (isInMeeting) {
          if (ag.role === 'CEO') {
            bx = cx - bw + 20;
            by = Math.round(ag.y - 66);
          } else if (ag.role === 'SUPERVISOR') {
            bx = cx - 20;
            by = Math.round(ag.y - 66);
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
        ctx.roundRect(bx, by, bw, bh, 7);
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

      for (let y = 0; y < CH; y += 24) {
        for (let x = 0; x < CW; x += 24) {
          ctx.fillStyle = (Math.floor(x / 24) + Math.floor(y / 24)) % 2 === 0 ? '#475569' : '#3b4758';
          ctx.fillRect(x, y, 24, 24);
        }
      }
      ctx.fillStyle = 'rgba(30, 41, 59, 0.55)';
      ctx.fillRect(24, CORRIDOR_Y - 18, CW - 48, 36);

      const staffList = Object.values(staffRef.current);

      (Object.entries(ROOMS) as Array<[DeptRoomKey, typeof ROOMS.HR_ROOM]>).forEach(([rKey, r]) => {
        const isRoomActive = staffList.some((s) => s.roomKey === rKey && s.isSelectedTeam && rKey !== 'MEETING_ROOM');
        drawRoomFloor(ctx, r.rx, r.ry, r.rw, r.rh, r.floorType, r.badgeColor, isRoomActive, f);

        if (r.ry < 100) {
          drawWindowAndSunbeam(ctx, r.rx + 140, r.ry + 1, f);
          drawWindowAndSunbeam(ctx, r.rx + 235, r.ry + 1, f);
        }

        ctx.strokeStyle = isRoomActive ? '#10b981' : '#0f172a';
        ctx.lineWidth = isRoomActive ? 5 : 4;
        ctx.strokeRect(r.rx, r.ry, r.rw, r.rh);

        ctx.fillStyle = '#cbd5e1';
        ctx.fillRect(r.doorX - 24, r.doorY - 4, 48, 8);

        if (rKey !== 'MEETING_ROOM') {
          const isShelfGlowing =
            isRoomActive &&
            (archiveHitFlashRef.current > 0 ||
              staffList.some((s) => s.roomKey === rKey && Math.hypot(s.x - r.shelf.x, s.y - r.shelf.y) < 35));
          drawBookshelf(ctx, r.shelf.x, r.shelf.y, isShelfGlowing, f);
          drawBookshelf(ctx, r.shelf.x + 92, r.shelf.y, false, f);
          drawOfficeProps(ctx, r.rx, r.ry, r.rw, r.rh, rKey, f);
        } else {
          ctx.fillStyle = '#fde68a';
          ctx.fillRect(r.rx + 45, r.ry + 65, r.rw - 90, r.rh - 95);
          ctx.strokeStyle = '#d97706';
          ctx.lineWidth = 2;
          ctx.strokeRect(r.rx + 45, r.ry + 65, r.rw - 90, r.rh - 95);

          // 회의실 중앙 테이블 조명 글로우
          const tableGlow = ctx.createRadialGradient(
            MEETING_TABLE_CENTER.x,
            MEETING_TABLE_CENTER.y,
            8,
            MEETING_TABLE_CENTER.x,
            MEETING_TABLE_CENTER.y,
            78
          );
          tableGlow.addColorStop(0, 'rgba(251, 191, 36, 0.35)');
          tableGlow.addColorStop(1, 'rgba(251, 191, 36, 0)');
          ctx.fillStyle = tableGlow;
          ctx.beginPath();
          ctx.arc(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 78, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = '#78350f';
          ctx.beginPath();
          ctx.arc(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 48, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = '#b45309';
          ctx.beginPath();
          ctx.arc(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 40, 0, Math.PI * 2);
          ctx.fill();

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

          // 부드러운 감속 보간 (목표 지점 접근 시 자연스러운 감속 및 코너링)
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

            // 전담팀 캐릭터 이동 시 바닥 잔상 트레일(Path Trail) 생성
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

      // 바닥 잔상 트레일(Path Trail) 렌더링 (부드러운 페이드아웃)
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

        ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
        ctx.fillRect(r.rx + 10, r.ry + 8, 128, 22);
        ctx.strokeStyle = r.badgeColor;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(r.rx + 10, r.ry + 8, 128, 22);
        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 10.5px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(r.title, r.rx + 74, r.ry + 23);
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
