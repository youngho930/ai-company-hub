import os

FILES = {
    # 1. 2.5D 도트 오피스: 마우스 호버 시 직원 상세 상태 인스펙터(HUD 카드) + 앰비언트 조명/네온 테두리 업그레이드
    "src/components/PixelRpgOffice.tsx": r"""'use client';

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

export default function PixelRpgOffice({
  onOpenReportModal,
  onToggleLogDrawer,
  unreadLogCount = 0,
  onAllGatheredChange,
}: PixelRpgOfficeProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const staffRef = useRef<Record<string, OfficeStaff>>({});
  const particlesRef = useRef<Particle[]>([]);
  const frameCountRef = useRef<number>(0);

  const [speedMult, setSpeedMult] = useState<number>(1.0);
  const [isHoveringReport, setIsHoveringReport] = useState<boolean>(false);
  const [reportUnlocked, setReportUnlocked] = useState<boolean>(false);
  const [phaseBanner, setPhaseBanner] = useState<string>('5개 부서 16명 상시 근무 중');
  const [hoveredStaff, setHoveredStaff] = useState<HoveredStaffInfo | null>(null);

  const speedRef = useRef<number>(1.0);
  const reportUnlockedRef = useRef<boolean>(false);
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
      (m) => m.type === 'ARCHIVE_HIT' || (m.payload?.text || '').includes('부서 책장(서가) 기존 기록 발견')
    );
    const hasLiveCeo = messages.some(
      (m) => m.type === 'CEO_LIVE_INTERVENTION' || (m.payload?.text || '').includes('실시간 CEO 긴급 지침')
    );
    const isMissionFinished = Boolean(finalReport);

    if (hasLiveCeo) {
      ceoWaveFlashRef.current = 120;
    }

    if (!hasStarted) {
      setPhaseBanner('🏢 전 부서(5개 팀 16명) 각자 사무실에서 일상 근무 대기 중');
      Object.values(map).forEach((st) => {
        st.isSelectedTeam = st.role === 'CEO';
        st.isShelfMode = false;
        st.carryingBook = false;
        st.stageQueue = [];
        st.waypoints = [];
        st.x = st.homePos.x;
        st.y = st.homePos.y;
        st.workTimer = 0;
        st.progress = 0;
        st.activeBubble = '';
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
        st.workTimer = 0;
        st.progress = 0;
        st.activeBubble = '';
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
      floorType: 'WOOD' | 'DARK_BLUE' | 'SLATE' | 'AMBER' | 'EMERALD'
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
      const bounceY = isWalking ? Math.abs(walkCycle) * -3.5 : workBob;

      const cx = Math.round(ag.x);
      const cy = Math.round(ag.y + bounceY);

      if (ag.isSelectedTeam) {
        ctx.fillStyle = ag.taskLabel.includes('반려')
          ? 'rgba(244, 63, 94, 0.55)'
          : ag.isShelfMode
          ? 'rgba(250, 204, 21, 0.55)'
          : 'rgba(16, 185, 129, 0.45)';
        ctx.beginPath();
        ctx.ellipse(cx, ag.y + 14, 17, 6.5, 0, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.fillStyle = 'rgba(0,0,0,0.32)';
        ctx.beginPath();
        ctx.ellipse(cx, ag.y + 14, 12, 4.5, 0, 0, Math.PI * 2);
        ctx.fill();
      }

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

        ctx.fillStyle = isReject ? '#881337' : ag.isShelfMode ? '#fef3c7' : '#ffffff';
        ctx.fillRect(bx, by, bw, bh);
        ctx.strokeStyle = isReject ? '#fb7185' : ag.isShelfMode ? '#d97706' : '#0f172a';
        ctx.lineWidth = 1.8;
        ctx.strokeRect(bx, by, bw, bh);

        ctx.fillStyle = isReject ? '#ffe4e6' : '#0f172a';
        ctx.font = 'bold 9px sans-serif';
        ctx.textAlign = 'center';
        const l1 = ag.activeBubble.slice(0, 23);
        const l2 = ag.activeBubble.slice(23, 45);
        ctx.fillText(l1, bx + bw / 2, by + (l2 ? 13 : 19));
        if (l2) ctx.fillText(l2, bx + bw / 2, by + 25);
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
        drawRoomFloor(ctx, r.rx, r.ry, r.rw, r.rh, r.floorType);

        if (r.ry < 100) {
          drawWindowAndSunbeam(ctx, r.rx + 140, r.ry + 1, f);
          drawWindowAndSunbeam(ctx, r.rx + 235, r.ry + 1, f);
        }

        const isRoomActive = staffList.some((s) => s.roomKey === rKey && s.isSelectedTeam && rKey !== 'MEETING_ROOM');
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
          const step = 2.6 * speedRef.current * catchUpBoost;

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
              ag.facing =
                ag.y > MEETING_TABLE_CENTER.y && detectRoomByPoint(ag.x, ag.y) === 'MEETING_ROOM'
                  ? 'UP'
                  : Math.hypot(ag.x - ag.shelfPos.x, ag.y - ag.shelfPos.y) < 20
                  ? 'UP'
                  : 'DOWN';
            }
          } else {
            ag.x += (dx / dist) * step;
            ag.y += (dy / dist) * step;
            walking = true;
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
        const bounceDoc = Math.sin(f * 0.12) * 3;
        const tx = MEETING_TABLE_CENTER.x;
        const ty = MEETING_TABLE_CENTER.y + bounceDoc;

        ctx.fillStyle = f % 30 < 15 ? 'rgba(250, 204, 21, 0.55)' : 'rgba(16, 185, 129, 0.55)';
        ctx.beginPath();
        ctx.arc(tx, MEETING_TABLE_CENTER.y, 34, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#fef08a';
        ctx.fillRect(tx - 15, ty - 12, 30, 22);
        ctx.strokeStyle = '#ca8a04';
        ctx.lineWidth = 2;
        ctx.strokeRect(tx - 15, ty - 12, 30, 22);

        ctx.fillStyle = '#059669';
        ctx.fillRect(tx - 68, ty - 34, 136, 20);
        ctx.strokeStyle = '#fde047';
        ctx.lineWidth = 1.8;
        ctx.strokeRect(tx - 68, ty - 34, 136, 20);
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 10px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('📋 최종 보고서 (클릭)', tx, ty - 21);
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
      <div className="shrink-0 px-5 py-2 bg-slate-900/90 backdrop-blur-md border-b border-slate-800/80 flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
          </span>
          <span className="font-bold text-slate-200 tracking-tight">{phaseBanner}</span>
          {reportUnlocked && (
            <button
              onClick={onOpenReportModal}
              className="px-3.5 py-1 text-[11px] font-extrabold bg-gradient-to-r from-amber-400 to-yellow-300 hover:from-amber-300 hover:to-yellow-200 text-slate-950 rounded-lg shadow-[0_0_15px_rgba(251,191,36,0.5)] animate-bounce transition"
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
              className={`px-2.5 py-1 rounded-md text-[10px] font-bold border transition ${
                speedMult === opt.val
                  ? 'bg-emerald-600 border-emerald-400 text-white shadow'
                  : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
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
          className={`w-full h-full object-contain rounded-2xl border border-slate-800/90 shadow-[0_0_50px_rgba(0,0,0,0.75)] bg-slate-900 ${
            isHoveringReport ? 'cursor-pointer ring-2 ring-amber-400' : ''
          }`}
        />

        {hoveredStaff && (
          <div className="absolute bottom-5 right-6 z-30 w-72 p-3.5 rounded-2xl bg-slate-950/95 backdrop-blur-md border border-emerald-500/50 shadow-2xl pointer-events-none transition-all">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2">
              <div>
                <span className="text-xs font-extrabold text-white block">{hoveredStaff.name}</span>
                <span className="text-[10px] text-emerald-400 font-semibold">{hoveredStaff.deptTitle}</span>
              </div>
              <span
                className={`px-2 py-0.5 text-[9px] font-bold rounded-full border ${
                  hoveredStaff.isSelected
                    ? 'bg-emerald-950 text-emerald-300 border-emerald-500/50'
                    : 'bg-slate-900 text-slate-400 border-slate-700'
                }`}
              >
                {hoveredStaff.isSelected ? '🟢 전담 투입 중' : '⚪ 부서 대기'}
              </span>
            </div>
            <div className="space-y-1.5 text-[11px]">
              <div className="flex justify-between text-slate-300">
                <span className="text-slate-500">현재 태스크:</span>
                <span className="font-bold text-sky-300">{hoveredStaff.taskLabel}</span>
              </div>
              <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-gradient-to-r from-emerald-500 to-sky-400 h-full transition-all"
                  style={{ width: `${hoveredStaff.progress}%` }}
                />
              </div>
              <p className="text-[10px] text-slate-400 italic pt-1 leading-snug">
                &ldquo;{hoveredStaff.bubble}&rdquo;
              </p>
            </div>
          </div>
        )}

        {reportUnlocked && (
          <button
            onClick={() => onOpenReportModal && onOpenReportModal()}
            className="absolute bottom-6 left-1/2 -translate-x-1/2 z-30 px-6 py-3 text-xs font-extrabold bg-gradient-to-r from-amber-400 via-yellow-300 to-amber-400 hover:brightness-110 text-slate-950 rounded-2xl shadow-[0_0_30px_rgba(251,191,36,0.9)] border-2 border-white flex items-center gap-2.5 animate-bounce cursor-pointer transition"
          >
            <span>📋 중앙 회의실 최종 전자결재 보고서 도착! (클릭하여 결재문서 열람 및 Word·Excel·PDF 저장)</span>
          </button>
        )}
      </div>
    </div>
  );
}
""",

    # 2. 메인 페이지(page.tsx): 전자결재 도장(Stamp) 테이블 헤더 + 카드형 리치 보고서 렌더러 + 뷰 스위처(2.5D 사옥 vs LangGraph 노드)
    "src/app/page.tsx": r"""'use client';

import React, { useState, useEffect, useRef } from 'react';
import { ReactFlow, Background, Controls } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useOfficeStore } from '@/store/useOfficeStore';
import AgentCustomNode from '@/components/AgentCustomNode';
import PixelRpgOffice from '@/components/PixelRpgOffice';
import EmployeeDirectoryModal from '@/components/EmployeeDirectoryModal';
import CEOInterventionModal from '@/components/CEOInterventionModal';
import { EmployeeProfile } from '@/types/agent';

const nodeTypes = { agentNode: AgentCustomNode };

const PRESET_SCENARIOS = [
  {
    label: '🛒 커머스 최저가·쿠폰 조사',
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
    label: '🏭 제조 수입검사(CoA) 자동화',
    prompt: '제조업 수입검사 성적서(CoA) 엑셀 수기 입력 업무를 Python과 Vision AI로 자동화할 때의 기대 효과와 도입 로드맵 보고서를 작성해줘',
  },
];

function cleanReportText(raw: string) {
  return raw
    .replace(/<br\s*\/?>/gi, '\n   ')
    .replace(/#{1,4}\s/g, '📌 ')
    .replace(/\*\*/g, '');
}

interface ParsedSection {
  title: string;
  bullets: string[];
}

function parseReportIntoCards(raw: string): { bannerNote: string; sections: ParsedSection[] } {
  const cleaned = cleanReportText(raw);
  const lines = cleaned.split('\n');
  let bannerNote = '';
  const sections: ParsedSection[] = [];
  let currentSec: ParsedSection | null = null;

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;
    if (line.startsWith('📚 [')) {
      bannerNote = line;
      continue;
    }
    if (line.startsWith('📌')) {
      if (currentSec) sections.push(currentSec);
      currentSec = { title: line.replace(/^📌\s*/, ''), bullets: [] };
    } else {
      const cleanBullet = line.replace(/^[•\-\*]\s*/, '');
      if (!currentSec) {
        currentSec = { title: '1. 핵심 요약 및 종합 결론', bullets: [] };
      }
      currentSec.bullets.push(cleanBullet);
    }
  }
  if (currentSec) sections.push(currentSec);
  return { bannerNote, sections };
}

export default function MissionControlPage() {
  const [prompt, setPrompt] = useState(PRESET_SCENARIOS[1].prompt);
  const [liveWhisper, setLiveWhisper] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [copiedToast, setCopiedToast] = useState(false);

  const [isReplayMode] = useState(false);
  const [leftViewMode, setLeftViewMode] = useState<'PIXEL' | 'GRAPH'>('PIXEL');
  const [isDirOpen, setIsDirOpen] = useState(false);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [isLogDrawerOpen, setIsLogDrawerOpen] = useState(false);
  const [isBrowserDrawerOpen, setIsBrowserDrawerOpen] = useState(false);
  const [isOAuthModalOpen, setIsOAuthModalOpen] = useState(false);
  const [isArchiveModalOpen, setIsArchiveModalOpen] = useState(false);
  const [isWebhookModalOpen, setIsWebhookModalOpen] = useState(false);
  const [isCostModalOpen, setIsCostModalOpen] = useState(false);
  const [, setIsAllGathered] = useState(false);

  const [archiveList, setArchiveList] = useState<any[]>([]);
  const [costMetrics, setCostMetrics] = useState<any>({
    prompt_tokens: 0,
    completion_tokens: 0,
    total_tokens: 0,
    total_cost_usd: 0.0,
    saved_cost_usd: 0.0,
    cache_hits: 0,
    budget_limit_usd: 1.0,
    pii_masked_count: 0,
  });
  const [webhookConfigs, setWebhookConfigs] = useState<any>({});
  const [webhookPreview, setWebhookPreview] = useState<string>('');

  const [sessionId] = useState(() => 'sess-' + Math.random().toString(36).slice(2, 10));
  const [uploadedFileName, setUploadedFileName] = useState<string>('');
  const [, setUploadedPreview] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [gptConnected, setGptConnected] = useState<boolean>(false);
  const [, setGptMaskedToken] = useState<string>('');
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
    dispatchEvent,
    clearHitl,
    resetMission,
  } = useOfficeStore();

  const refreshArchiveList = () => {
    fetch(`${apiBase}/api/mission/history`)
      .then((r) => r.json())
      .then((d) => {
        if (d.records) setArchiveList(d.records);
      })
      .catch(() => {});
  };

  const refreshCostMetrics = () => {
    fetch(`${apiBase}/api/metrics/cost`)
      .then((r) => r.json())
      .then((d) => {
        if (d && typeof d.total_tokens === 'number') setCostMetrics(d);
      })
      .catch(() => {});
  };

  const refreshWebhookConfigs = () => {
    fetch(`${apiBase}/api/integrations/webhooks`)
      .then((r) => r.json())
      .then((d) => setWebhookConfigs(d || {}))
      .catch(() => {});
  };

  const handleDeleteArchive = async (id: number) => {
    await fetch(`${apiBase}/api/mission/history/${id}`, { method: 'DELETE' });
    refreshArchiveList();
  };

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
    refreshArchiveList();
    refreshCostMetrics();
    refreshWebhookConfigs();
    return () => {
      esRef.current?.close();
    };
  }, []);

  const handleSendLiveWhisper = async () => {
    if (!liveWhisper.trim()) return;
    const msg = liveWhisper.trim();
    setLiveWhisper('');
    try {
      await fetch(`${apiBase}/api/mission/intervene`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, instruction: msg }),
      });
      dispatchEvent({
        type: 'MESSAGE',
        agentId: 'ceo',
        agentName: '신영호 대표 (실시간 개입)',
        role: 'SUPERVISOR',
        timestamp: '방금 전',
        payload: {
          status: 'WORKING',
          text: `⚡ [CEO 실시간 지시 전송 완료]: "${msg}" ➔ 작업 중인 에이전트가 즉시 반영합니다.`,
        },
      });
    } catch {
      alert('백엔드 서버 연결을 확인해 주세요.');
    }
  };

  const handleTestWebhook = async (targetSystem: string) => {
    try {
      const res = await fetch(`${apiBase}/api/integrations/test-dispatch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_system: targetSystem,
          prompt,
          report_markdown: finalReport || '샘플 5단 결재 보고서 데이터 정합 완료',
        }),
      });
      const data = await res.json();
      setWebhookPreview(JSON.stringify(data, null, 2));
    } catch {
      alert('백엔드 연결을 확인해 주세요.');
    }
  };

  const handleSaveWebhooks = async () => {
    await fetch(`${apiBase}/api/integrations/webhooks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ configs: webhookConfigs }),
    });
    alert('외부 시스템(ERP·Jira·Slack) 연동 설정이 저장되었습니다.');
  };

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
          body: JSON.stringify({ filename: file.name, content_base64: base64Content, session_id: sessionId }),
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

  const handleDownloadReportFile = async (format: 'docx' | 'xlsx' | 'md' | 'pdf') => {
    if (!finalReport) return;
    if (format === 'pdf') {
      const printWin = window.open('', '_blank', 'width=900,height=800');
      if (!printWin) return;
      const htmlContent = `
        <html>
          <head>
            <title>${prompt.slice(0, 30)} - 최종 결재 보고서</title>
            <style>
              body { font-family: 'Malgun Gothic', sans-serif; padding: 40px; color: #0f172a; line-height: 1.7; }
              h1 { color: #1e3a5f; border-bottom: 2px solid #1e3a5f; padding-bottom: 10px; font-size: 20px; }
              pre { white-space: pre-wrap; font-family: 'Malgun Gothic', sans-serif; font-size: 13px; }
            </style>
          </head>
          <body>
            <h1>📋 AI Company Hub 최종 승인 결재 보고서</h1>
            <pre>${cleanReportText(finalReport)}</pre>
            <script>window.onload = () => { window.print(); };</script>
          </body>
        </html>`;
      printWin.document.write(htmlContent);
      printWin.document.close();
      return;
    }

    try {
      const res = await fetch(`${apiBase}/api/mission/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: uploadedFileName ? `${uploadedFileName} 정밀 분석 및 결재 보고서` : prompt.slice(0, 60),
          report_markdown: cleanReportText(finalReport),
          format,
          session_id: sessionId,
        }),
      });
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'docx' ? 'docx' : format === 'xlsx' ? 'xlsx' : 'md';
      a.download = `AI_결재보고서_${new Date().toISOString().slice(0, 10)}.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      alert('파일 생성 중 오류가 발생했습니다.');
    }
  };

  const handleCopyReport = () => {
    if (!finalReport) return;
    navigator.clipboard.writeText(cleanReportText(finalReport));
    setCopiedToast(true);
    setTimeout(() => setCopiedToast(false), 2000);
  };

  const handleClearUpload = async () => {
    setUploadedFileName('');
    setUploadedPreview('');
    if (fileInputRef.current) fileInputRef.current.value = '';
    try {
      await fetch(`${apiBase}/api/mission/clear-upload?session_id=${sessionId}`, { method: 'POST' });
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
        alert('로그인 시간이 초과되었거나 취소되었습니다. 직접 입력 방식으로 시도해 주세요.');
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
    setIsStreaming(true);
    const es = new EventSource(url);
    esRef.current = es;
    es.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      if (ev.type === 'COST_UPDATE') {
        setCostMetrics(ev.payload);
      } else if (ev.type === 'ARCHIVE_SAVED') {
        refreshArchiveList();
        refreshCostMetrics();
      } else if (ev.type === 'ARCHIVE_HIT') {
        refreshCostMetrics();
        dispatchEvent({
          type: 'MESSAGE',
          agentId: ev.agentId,
          agentName: ev.agentName,
          role: ev.role,
          timestamp: ev.timestamp,
          payload: ev.payload,
        });
      } else if (ev.type === 'CEO_LIVE_INTERVENTION' || ev.type === 'FORCE_REFRESH_START') {
        dispatchEvent({
          type: 'MESSAGE',
          agentId: ev.agentId,
          agentName: ev.agentName,
          role: ev.role,
          timestamp: ev.timestamp,
          payload: ev.payload,
        });
      } else if (ev.type === 'STREAM_END') {
        setIsStreaming(false);
        refreshCostMetrics();
        es.close();
        esRef.current = null;
      } else {
        dispatchEvent(ev);
      }
    };
    es.onerror = () => {
      setIsStreaming(false);
      es.close();
      esRef.current = null;
    };
  };

  const startMission = (customPrompt?: string) => {
    const targetPrompt = customPrompt ?? prompt;
    if (customPrompt) setPrompt(customPrompt);
    resetMission(Boolean(manualTeam));
    setExpandedLogs({});
    setSelectedFrameIdx(-1);
    setIsAllGathered(false);
    if (isReplayMode) {
      const q1 = buildReplayQuery({ phase: '1' });
      streamSSE('/api/mission/replay?' + q1);
    } else {
      const params = new URLSearchParams({ prompt: targetPrompt, session_id: sessionId });
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
      const q2 = buildReplayQuery({ phase: '2', action, comment });
      streamSSE('/api/mission/replay?' + q2);
    } else {
      await fetch(`${apiBase}/api/mission/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, comment, session_id: sessionId }),
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

  const parsedReport = finalReport ? parseReportIntoCards(finalReport) : { bannerNote: '', sections: [] };
  const activeSupNode = nodes.find((n) => n.id !== 'ceo' && n.id.startsWith('sup-'));
  const activeWorkerNodes = nodes.filter((n) => n.id.startsWith('wrk-'));

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-950 text-slate-100 select-none">
      <header className="shrink-0 px-5 py-2.5 bg-slate-900/95 backdrop-blur-md border-b border-slate-800 space-y-2 shadow-lg">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-base">🏢</span>
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-extrabold tracking-tight bg-gradient-to-r from-emerald-400 to-sky-400 bg-clip-text text-transparent">
                    AI COMPANY HUB
                  </span>
                  <span className="px-1.5 py-0.2 text-[9px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-500/40 rounded">
                    v3.5 Enterprise
                  </span>
                </div>
                <span className="text-[9px] text-slate-400 block">Multi-Agent Orchestration & CoA Analytics</span>
              </div>
            </div>

            <div className="flex bg-slate-950 p-1 rounded-xl border border-slate-800">
              <button
                onClick={() => setLeftViewMode('PIXEL')}
                className={`px-2.5 py-1 text-[11px] font-bold rounded-lg transition ${
                  leftViewMode === 'PIXEL'
                    ? 'bg-emerald-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                🎮 2.5D 사옥 관제
              </button>
              <button
                onClick={() => setLeftViewMode('GRAPH')}
                className={`px-2.5 py-1 text-[11px] font-bold rounded-lg transition ${
                  leftViewMode === 'GRAPH'
                    ? 'bg-indigo-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                🕸️ LangGraph 토폴로지
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-1 max-w-3xl">
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv,.pdf,.txt,.md,.json"
              onChange={handleFileUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className={`px-3 py-2 text-xs font-bold rounded-xl border transition shrink-0 ${
                uploadedFileName
                  ? 'bg-sky-500/20 border-sky-400 text-sky-300 shadow-[0_0_12px_rgba(56,189,248,0.3)]'
                  : 'bg-slate-950 border-slate-700 text-slate-300 hover:border-sky-500/60'
              }`}
            >
              {uploadedFileName ? `📎 ${uploadedFileName.slice(0, 14)}` : '📎 파일 첨부'}
            </button>
            {uploadedFileName && (
              <button
                onClick={handleClearUpload}
                className="px-2 py-1.5 text-[10px] font-bold bg-rose-950 border border-rose-700 text-rose-300 rounded-lg"
                title="첨부 해제"
              >
                ✕
              </button>
            )}

            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && startMission()}
              placeholder="업무 지시 입력 (동일 질문은 뒤쪽 책장에서 즉시 인출하며, '다시 찾아줘' 입력 시 새로 크롤링합니다)"
              className="w-full px-3.5 py-2 text-xs bg-slate-950 border border-slate-700/90 rounded-xl text-slate-100 focus:outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400/40"
            />
            <button
              onClick={() => startMission()}
              disabled={isStreaming}
              className="px-4 py-2 text-xs font-extrabold bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white rounded-xl shrink-0 shadow-lg transition"
            >
              {isStreaming ? '⏳ 수행 중' : '▶️ 업무 하달'}
            </button>
            <button
              onClick={() => {
                const cleanBase = prompt.replace(/다시\s*찾아줘|새로\s*찾아줘/g, '').trim();
                startMission(`${cleanBase} 다시 찾아줘`);
              }}
              title="서가(책장) 캐시를 무시하고 웹에서 새로 크롤링합니다"
              className="px-3 py-2 text-xs font-bold bg-indigo-600/90 hover:bg-indigo-500 text-white rounded-xl shrink-0 border border-indigo-400/40 transition"
            >
              🔄 다시 찾아줘
            </button>
          </div>

          <div className="flex items-center gap-1.5 text-xs shrink-0">
            <button
              onClick={() => {
                refreshCostMetrics();
                setIsCostModalOpen(true);
              }}
              className="px-2.5 py-1.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-cyan-400 text-left transition"
            >
              <span className="text-[9px] block text-slate-400">
                비용 방어 (캐시 {costMetrics.cache_hits}회)
              </span>
              <span className="text-[11px] font-bold text-cyan-400">
                💰 ${Number(costMetrics.total_cost_usd || 0).toFixed(4)}
              </span>
            </button>

            <button
              onClick={() => {
                refreshWebhookConfigs();
                setIsWebhookModalOpen(true);
              }}
              className="px-2.5 py-1.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-violet-400 text-left transition"
            >
              <span className="text-[9px] block text-slate-400">외부 연동</span>
              <span className="text-[11px] font-bold text-violet-400">🔌 ERP·Jira</span>
            </button>

            <button
              onClick={() => {
                refreshArchiveList();
                setIsArchiveModalOpen(true);
              }}
              className="px-2.5 py-1.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-emerald-400 text-left transition"
            >
              <span className="text-[9px] block text-slate-400">서가(책장) DB</span>
              <span className="text-[11px] font-bold text-emerald-400">🗂️ 보관함 ({archiveList.length})</span>
            </button>

            <button
              onClick={() => setIsBrowserDrawerOpen(true)}
              className="px-2.5 py-1.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-sky-400 text-left transition"
            >
              <span className="text-[9px] block text-slate-400">SoM 비전</span>
              <span className="text-[11px] font-bold text-sky-400">🌐 웹 ({browserHistory.length})</span>
            </button>

            <button
              onClick={() => setIsLogDrawerOpen(true)}
              className="px-2.5 py-1.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-amber-400 text-left transition"
            >
              <span className="text-[9px] block text-slate-400">검수 기록</span>
              <span className="text-[11px] font-bold text-amber-400">📜 로그 ({messages.length})</span>
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 pt-0.5">
          <div className="flex items-center gap-1.5 overflow-x-auto">
            <span className="text-[11px] font-bold text-slate-400 shrink-0">💡 원클릭 시나리오:</span>
            {PRESET_SCENARIOS.map((item, idx) => (
              <button
                key={idx}
                onClick={() => setPrompt(item.prompt)}
                className={`px-2.5 py-1 text-[11px] rounded-lg border transition shrink-0 ${
                  prompt === item.prompt
                    ? 'bg-emerald-950/60 border-emerald-500/60 text-emerald-300 font-bold'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                {item.label}
              </button>
            ))}
            <button
              onClick={() => setIsDirOpen(true)}
              className="px-2.5 py-1 text-[11px] rounded-lg bg-slate-950 border border-slate-800 hover:border-amber-400 text-amber-300 font-semibold shrink-0"
            >
              👥 사원 명부·수동 차출
            </button>
          </div>

          <div className="flex items-center gap-1.5 shrink-0 bg-slate-950 px-3 py-1 rounded-xl border border-sky-500/40 shadow-inner">
            <span className="text-[11px] font-bold text-sky-400">💬 실시간 CEO 개입:</span>
            <input
              value={liveWhisper}
              onChange={(e) => setLiveWhisper(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendLiveWhisper()}
              placeholder="작업 중 추가 지시 입력 (예: 불량 원인 더 자세히 써줘)"
              className="w-64 px-2 py-0.5 text-[11px] bg-slate-900 border border-slate-700 rounded-md text-slate-100 focus:outline-none focus:border-sky-400"
            />
            <button
              onClick={handleSendLiveWhisper}
              className="px-2.5 py-0.5 text-[11px] font-bold bg-sky-600 hover:bg-sky-500 text-white rounded-md transition"
            >
              ⚡ 지시 투입
            </button>
          </div>
        </div>
      </header>

      <main className="relative flex-1 min-h-0 overflow-hidden flex flex-col">
        <div className="flex-1 min-h-0 overflow-hidden relative">
          {leftViewMode === 'PIXEL' ? (
            <PixelRpgOffice
              onOpenReportModal={() => setIsReportModalOpen(true)}
              onToggleLogDrawer={() => setIsLogDrawerOpen(!isLogDrawerOpen)}
              unreadLogCount={messages.length}
              onAllGatheredChange={setIsAllGathered}
            />
          ) : (
            <div className="w-full h-full bg-slate-950 relative">
              <div className="absolute top-4 left-5 z-20 px-4 py-2 rounded-xl bg-slate-900/90 border border-indigo-500/40 text-xs">
                <span className="font-bold text-indigo-300 block">🕸️ LangGraph StateGraph 실시간 노드 토폴로지</span>
                <span className="text-[11px] text-slate-400">
                  CEO ➔ 팀장(Supervisor QC Gate) ➔ 실무 에이전트(Worker 1·2) 간 조건부 엣지(Conditional Edge) 상태 전이
                </span>
              </div>
              <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView colorMode="dark">
                <Background color="#334155" gap={16} />
                <Controls />
              </ReactFlow>
            </div>
          )}
        </div>

        {isBrowserDrawerOpen && (
          <aside className="absolute right-0 top-0 bottom-0 w-[500px] z-40 bg-slate-950/95 backdrop-blur-md border-l border-slate-700 flex flex-col shadow-2xl">
            <div className="shrink-0 px-4 py-3 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
              <span className="text-xs font-bold text-sky-400">🌐 실시간 웹 탐색 (SoM Vision 캡처)</span>
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
                      <span className="text-[10px] font-bold text-slate-400 mr-1">🎬 탐색 단계:</span>
                      {browserHistory.map((item, idx) => {
                        const isSelected = (selectedFrameIdx === -1 ? browserHistory.length - 1 : selectedFrameIdx) === idx;
                        return (
                          <button
                            key={idx}
                            onClick={() => setSelectedFrameIdx(idx)}
                            className={`px-2.5 py-1 text-[10px] font-bold rounded-lg border transition ${
                              isSelected
                                ? 'bg-emerald-600 border-emerald-400 text-white shadow'
                                : 'bg-slate-950 border-slate-700 text-slate-300'
                            }`}
                          >
                            {item.step}
                          </button>
                        );
                      })}
                    </div>
                  )}
                  <div className="rounded-xl overflow-hidden border border-slate-700 shadow-lg">
                    <img src={displayedFrameUrl} alt="SoM View" className="w-full object-contain" />
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-500 text-center mt-32">
                  업무 하달 시 웹사이트 스캔 및 빨간 번호표(SoM) 캡처 화면이 이곳에 표시됩니다.
                </p>
              )}
            </div>
          </aside>
        )}

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
                        className="mt-2 px-2.5 py-1 text-[10px] font-bold bg-slate-800 hover:bg-slate-700 text-emerald-300 rounded"
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

      {isCostModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-6">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-2xl p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-cyan-400">
                  💰 LLM 토큰 사용량 및 비용·보안 거버넌스 대시보드
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  실시간 Input/Output 토큰 과금 추이, 서가 캐시 비용 절감액, PII 개인정보 마스킹 현황을 관제합니다.
                </p>
              </div>
              <button
                onClick={() => setIsCostModalOpen(false)}
                className="px-2.5 py-1 text-xs font-bold bg-slate-800 rounded-lg"
              >
                ✕ 닫기
              </button>
            </div>

            <div className="grid grid-cols-4 gap-3 text-center">
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-[10px] text-slate-400 block">총 누적 토큰</span>
                <span className="text-base font-extrabold text-slate-100">
                  {costMetrics.total_tokens || 0} T
                </span>
                <span className="text-[9px] text-slate-500 block mt-1">
                  In {costMetrics.prompt_tokens || 0} / Out {costMetrics.completion_tokens || 0}
                </span>
              </div>
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-[10px] text-slate-400 block">누적 API 비용</span>
                <span className="text-base font-extrabold text-cyan-400">
                  ${Number(costMetrics.total_cost_usd || 0).toFixed(5)}
                </span>
                <span className="text-[9px] text-slate-500 block mt-1">
                  상한: ${costMetrics.budget_limit_usd || 1.0}
                </span>
              </div>
              <div className="p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-500/40">
                <span className="text-[10px] text-emerald-300 block">서가 캐시 절감액</span>
                <span className="text-base font-extrabold text-emerald-400">
                  ${Number(costMetrics.saved_cost_usd || 0).toFixed(4)}
                </span>
                <span className="text-[9px] text-emerald-300/80 block mt-1">
                  캐시 히트: {costMetrics.cache_hits || 0}회
                </span>
              </div>
              <div className="p-3.5 rounded-xl bg-rose-950/30 border border-rose-500/40">
                <span className="text-[10px] text-rose-300 block">PII 보안 마스킹</span>
                <span className="text-base font-extrabold text-rose-400">
                  {costMetrics.pii_masked_count || 0} 건
                </span>
                <span className="text-[9px] text-rose-300/80 block mt-1">DLP 가드레일 작동</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {isWebhookModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-6">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-4xl max-h-[88vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 bg-slate-950 border-b border-slate-800">
              <div>
                <h3 className="text-sm font-bold text-violet-400">
                  🔌 엔터프라이즈 외부 시스템(Ecount ERP · Jira · Slack) 연동 센터
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  현재는 [시뮬레이션 프리뷰 모드]로 작동하며, 실무 투입 시 API URL만 입력하면 코드 수정 없이 즉시 실서버로 전송됩니다.
                </p>
              </div>
              <button
                onClick={() => setIsWebhookModalOpen(false)}
                className="px-3 py-1.5 text-xs font-bold bg-slate-800 rounded-lg"
              >
                ✕ 닫기
              </button>
            </div>

            <div className="flex-1 p-6 overflow-y-auto grid grid-cols-12 gap-5 text-xs">
              <div className="col-span-7 space-y-4">
                {['ecount_erp', 'jira_cloud', 'slack_webhook'].map((sysKey) => {
                  const item = webhookConfigs[sysKey] || {};
                  return (
                    <div key={sysKey} className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-100">{item.name || sysKey}</span>
                        <button
                          onClick={() => handleTestWebhook(sysKey)}
                          className="px-2.5 py-1 text-[11px] font-bold bg-violet-600 hover:bg-violet-500 text-white rounded-lg transition"
                        >
                          ⚡ 연동 페이로드 생성 테스트
                        </button>
                      </div>
                      <input
                        value={item.endpoint_url || ''}
                        onChange={(e) =>
                          setWebhookConfigs({
                            ...webhookConfigs,
                            [sysKey]: { ...item, endpoint_url: e.target.value },
                          })
                        }
                        placeholder="실무 투입 시 Endpoint URL 입력 (비워두면 안전한 시뮬레이션 모드로 작동)"
                        className="w-full px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded text-slate-200"
                      />
                    </div>
                  );
                })}
                <button
                  onClick={handleSaveWebhooks}
                  className="w-full py-2.5 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl shadow"
                >
                  💾 연동 설정 저장하기
                </button>
              </div>

              <div className="col-span-5 flex flex-col bg-slate-950 border border-slate-800 rounded-xl p-4">
                <span className="font-bold text-emerald-400 mb-2">
                  📡 실시간 생성 API Payload (JSON 규격 미리보기)
                </span>
                <pre className="flex-1 text-[11px] text-slate-300 overflow-auto whitespace-pre-wrap font-mono bg-slate-900 p-3 rounded-lg border border-slate-800">
                  {webhookPreview ||
                    '좌측에서 [⚡ 연동 페이로드 생성 테스트] 버튼을 누르면 현업 ERP·Jira·Slack으로 전송되는 표준 JSON 전문이 이곳에 표시됩니다.'}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}

      {isArchiveModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-6">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 bg-slate-950 border-b border-slate-800">
              <div>
                <h3 className="text-sm font-bold text-emerald-400">
                  🗂️ 사옥 책장(서가) 결재 문서 영구 보관함 (총 {archiveList.length}건)
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  동일한 질문을 입력하면 에이전트가 뒤쪽 책장에서 이 문서를 꺼내 즉시 보고하며, &quot;다시 찾아줘&quot;를 붙이면 새로 크롤링합니다.
                </p>
              </div>
              <button
                onClick={() => setIsArchiveModalOpen(false)}
                className="px-3 py-1.5 text-xs font-bold bg-slate-800 hover:bg-slate-700 rounded-lg"
              >
                ✕ 닫기
              </button>
            </div>

            <div className="flex-1 p-5 overflow-y-auto space-y-3">
              {archiveList.map((rec) => (
                <div
                  key={rec.id}
                  className="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-slate-700 flex items-center justify-between gap-4"
                >
                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-700/50 rounded">
                        {rec.doc_trace_id || `#${rec.id}`} | {rec.dept}
                      </span>
                      <span className="text-[11px] text-slate-400">
                        검수: {rec.supervisor_name} | 실무: {rec.worker_names}
                      </span>
                      <span className="text-[10px] text-slate-500 ml-auto">{rec.created_at}</span>
                    </div>
                    <p className="text-xs font-bold text-slate-100 truncate">{rec.prompt}</p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => {
                        setIsArchiveModalOpen(false);
                        startMission(rec.prompt);
                      }}
                      className="px-2.5 py-1.5 text-xs font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg transition"
                    >
                      📚 책장에서 꺼내 보고시키기
                    </button>
                    <button
                      onClick={() => {
                        dispatchEvent({
                          type: 'FINAL_REPORT',
                          agentId: 'ceo',
                          agentName: rec.supervisor_name,
                          role: 'SUPERVISOR',
                          timestamp: rec.created_at,
                          payload: { status: 'DONE', reportMarkdown: rec.report_markdown },
                        });
                        setPrompt(rec.prompt);
                        setIsArchiveModalOpen(false);
                        setIsReportModalOpen(true);
                      }}
                      className="px-3 py-1.5 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition"
                    >
                      📖 바로 열람
                    </button>
                    <button
                      onClick={() => handleDeleteArchive(rec.id)}
                      className="px-2.5 py-1.5 text-xs font-bold bg-rose-950 hover:bg-rose-900 text-rose-300 rounded-lg transition"
                    >
                      삭제
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {isReportModalOpen && finalReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-6">
          <div className="bg-slate-900 border border-slate-700/90 rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.9)]">
            <div className="flex flex-wrap items-center justify-between gap-2 px-6 py-4 bg-slate-950 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <span className="px-2.5 py-1 text-[10px] font-extrabold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 rounded-lg">
                  최종 승인 완료
                </span>
                <h3 className="text-sm font-extrabold text-white tracking-tight">
                  📋 엔터프라이즈 전자결재 5단 심층 분석 보고서
                </h3>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleCopyReport}
                  className="px-3 py-1.5 text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl border border-slate-700 transition"
                >
                  {copiedToast ? '✅ 복사됨!' : '📋 전문 복사'}
                </button>
                <button
                  onClick={() => handleDownloadReportFile('docx')}
                  className="px-3.5 py-1.5 text-xs font-bold bg-gradient-to-r from-blue-600 to-indigo-600 hover:brightness-110 text-white rounded-xl shadow transition"
                >
                  📘 Word (.docx)
                </button>
                <button
                  onClick={() => handleDownloadReportFile('xlsx')}
                  className="px-3.5 py-1.5 text-xs font-bold bg-gradient-to-r from-emerald-600 to-teal-600 hover:brightness-110 text-white rounded-xl shadow transition"
                >
                  📗 2-Sheet Excel (.xlsx)
                </button>
                <button
                  onClick={() => handleDownloadReportFile('pdf')}
                  className="px-3.5 py-1.5 text-xs font-bold bg-gradient-to-r from-rose-600 to-pink-600 hover:brightness-110 text-white rounded-xl shadow transition"
                >
                  📕 PDF 인쇄·저장
                </button>
                <button
                  onClick={() => {
                    setIsReportModalOpen(false);
                    setIsWebhookModalOpen(true);
                  }}
                  className="px-3.5 py-1.5 text-xs font-bold bg-violet-600 hover:bg-violet-500 text-white rounded-xl shadow transition"
                >
                  🔌 ERP·Jira 전송
                </button>
                <button
                  onClick={() => setIsReportModalOpen(false)}
                  className="ml-1 px-3 py-1.5 text-xs font-bold bg-slate-800 hover:bg-slate-700 rounded-xl"
                >
                  ✕
                </button>
              </div>
            </div>

            <div className="flex-1 p-6 overflow-y-auto space-y-5 bg-gradient-to-b from-slate-900 to-slate-950 select-text">
              <div className="p-4 rounded-2xl bg-slate-950/90 border border-slate-800 flex flex-wrap items-center justify-between gap-4 shadow-inner">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                      DOC-{new Date().toISOString().slice(0, 10).replace(/-/g, '')}-VERIFIED
                    </span>
                    <span className="text-[11px] font-bold text-emerald-400">
                      • QC 루브릭 정량 검수 통과 (기준 85점 이상)
                    </span>
                  </div>
                  <p className="text-xs font-bold text-slate-200">
                    안건: {prompt}
                  </p>
                </div>

                <div className="flex items-center gap-2 text-center">
                  <div className="w-24 p-2 rounded-xl bg-slate-900 border border-slate-800">
                    <span className="text-[9px] text-slate-400 block">실무 기안</span>
                    <span className="text-[11px] font-bold text-sky-300 block my-0.5">
                      {activeWorkerNodes[0]?.data?.name ? String(activeWorkerNodes[0].data.name).split(' ')[0] : '전담 연구원'}
                    </span>
                    <span className="inline-block px-1.5 py-0.2 text-[9px] font-extrabold text-sky-400 border border-sky-500/40 rounded">
                      기안완료(印)
                    </span>
                  </div>
                  <div className="w-24 p-2 rounded-xl bg-slate-900 border border-slate-800">
                    <span className="text-[9px] text-slate-400 block">부서장 검수</span>
                    <span className="text-[11px] font-bold text-emerald-300 block my-0.5">
                      {activeSupNode?.data?.name ? String(activeSupNode.data.name).split(' ')[0] : '전담 팀장'}
                    </span>
                    <span className="inline-block px-1.5 py-0.2 text-[9px] font-extrabold text-emerald-400 border border-emerald-500/40 rounded">
                      검수승인(印)
                    </span>
                  </div>
                  <div className="w-24 p-2 rounded-xl bg-amber-950/20 border border-amber-500/40">
                    <span className="text-[9px] text-amber-300 block">최종 결재</span>
                    <span className="text-[11px] font-bold text-amber-400 block my-0.5">신영호 대표</span>
                    <span className="inline-block px-1.5 py-0.2 text-[9px] font-extrabold text-rose-400 border border-rose-500/50 bg-rose-950/40 rounded">
                      결재완료(印)
                    </span>
                  </div>
                </div>
              </div>

              {parsedReport.bannerNote && (
                <div className="px-4 py-2.5 rounded-xl bg-amber-500/15 border border-amber-400/50 text-amber-200 text-xs font-bold flex items-center gap-2">
                  <span>{parsedReport.bannerNote}</span>
                </div>
              )}

              <div className="space-y-4">
                {parsedReport.sections.map((sec, sIdx) => (
                  <div
                    key={sIdx}
                    className="p-5 rounded-2xl bg-slate-950/85 border border-slate-800/90 hover:border-slate-700 transition shadow-lg space-y-3"
                  >
                    <div className="flex items-center gap-2.5 border-b border-slate-800/80 pb-2.5">
                      <span className="px-2.5 py-0.5 text-xs font-extrabold rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                        SECTION 0{sIdx + 1}
                      </span>
                      <h4 className="text-sm font-extrabold text-white tracking-tight">{sec.title}</h4>
                    </div>

                    <div className="space-y-2">
                      {sec.bullets.map((b, bIdx) => {
                        const isFail = b.includes('🚨') || b.includes('불합격') || b.includes('부적합');
                        const isPass = b.includes('✅') || b.includes('적격(합격)');
                        const isCeoNote = b.includes('⚡');

                        return (
                          <div
                            key={bIdx}
                            className={`p-3 rounded-xl text-xs leading-relaxed border flex items-start gap-2.5 ${
                              isFail
                                ? 'bg-rose-950/35 border-rose-500/50 text-rose-100 font-semibold'
                                : isPass
                                ? 'bg-emerald-950/25 border-emerald-500/40 text-emerald-100'
                                : isCeoNote
                                ? 'bg-sky-950/40 border-sky-400/50 text-sky-100 font-semibold'
                                : 'bg-slate-900/70 border-slate-800/70 text-slate-200'
                            }`}
                          >
                            <span className="text-emerald-400 font-bold shrink-0 mt-0.5">•</span>
                            <span className="flex-1 break-words">{b}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
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
""",
}

for path, content in FILES.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ 엔터프라이즈 UI/UX 마스터피스 디자인 패치 완료: {path}")
