'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useOfficeStore, OfficeThemeId } from '@/store/useOfficeStore';

const THEME_BG_PATHS: Record<OfficeThemeId, string> = {
  classic: '/office_bg.png',
  space: '/office_space.png',
  factory: '/office_factory.png',
  quantum: '/office_quantum.png',
};

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
  lastSpokenFrame: number;
  progress: number;
  appliedPhase: number;
  stuckFrames: number;
  lastWaypointDist: number;
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
const SUPER_SAMPLE = 2; // 2x Super-sampling (2240x1280 물리 해상도 렌더링)
const CORRIDOR_Y = 304;
const FONT_FAMILY = "'Pretendard', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif";

// public/office_bg.png 픽셀 스캔 기반 6개 부서실 및 15개 책상·이름표 오차 0px 정밀 매칭 좌표
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
    bgFloorTone: string;
    bgFloorShadow: string;
    desks: Point[];
    shelf: Point;
  }
> = {
  HR_ROOM: {
    title: '🔍 리서치·인사팀',
    badgeColor: '#38bdf8',
    rx: 26,
    ry: 22,
    rw: 338,
    rh: 252,
    doorX: 195,
    doorY: 274,
    floorType: 'WOOD',
    bgFloorTone: '#834930',
    bgFloorShadow: '#6b3923',
    desks: [
      { x: 131, y: 146 },
      { x: 248, y: 146 },
      { x: 299, y: 213 },
    ],
    shelf: { x: 186, y: 84 },
  },
  DEV_ROOM: {
    title: '💻 AI·SW개발팀',
    badgeColor: '#818cf8',
    rx: 391,
    ry: 22,
    rw: 338,
    rh: 252,
    doorX: 560,
    doorY: 274,
    floorType: 'DARK_BLUE',
    bgFloorTone: '#2f4570',
    bgFloorShadow: '#1f3154',
    desks: [
      { x: 472, y: 146 },
      { x: 595, y: 146 },
      { x: 643, y: 213 },
    ],
    shelf: { x: 492, y: 84 },
  },
  QA_ROOM: {
    title: '🏭 품질·생산QA팀',
    badgeColor: '#34d399',
    rx: 756,
    ry: 22,
    rw: 338,
    rh: 252,
    doorX: 925,
    doorY: 274,
    floorType: 'SLATE',
    bgFloorTone: '#3d5f5b',
    bgFloorShadow: '#2c4745',
    desks: [
      { x: 830, y: 146 },
      { x: 947, y: 146 },
      { x: 1010, y: 213 },
    ],
    shelf: { x: 800, y: 84 },
  },
  FIN_ROOM: {
    title: '📊 재무·데이터팀',
    badgeColor: '#fbbf24',
    rx: 26,
    ry: 338,
    rw: 338,
    rh: 258,
    doorX: 195,
    doorY: 338,
    floorType: 'EMERALD',
    bgFloorTone: '#425e52',
    bgFloorShadow: '#2f473e',
    desks: [
      { x: 133, y: 458 },
      { x: 250, y: 458 },
      { x: 296, y: 531 },
    ],
    shelf: { x: 78, y: 405 },
  },
  MEETING_ROOM: {
    title: '📋 중앙 결재·회의실',
    badgeColor: '#f59e0b',
    rx: 391,
    ry: 338,
    rw: 338,
    rh: 258,
    doorX: 560,
    doorY: 338,
    floorType: 'AMBER',
    bgFloorTone: '#8e4e25',
    bgFloorShadow: '#6c3818',
    desks: [],
    shelf: { x: 432, y: 396 },
  },
  MKT_ROOM: {
    title: '🛒 마케팅·전략팀',
    badgeColor: '#f472b6',
    rx: 756,
    ry: 338,
    rw: 338,
    rh: 258,
    doorX: 925,
    doorY: 338,
    floorType: 'WOOD',
    bgFloorTone: '#72476d',
    bgFloorShadow: '#563352',
    desks: [
      { x: 834, y: 458 },
      { x: 951, y: 458 },
      { x: 1008, y: 531 },
    ],
    shelf: { x: 980, y: 400 },
  },
};

// 중앙 결재·회의실 타원형 테이블 중심 및 신영호 대표/전담팀 좌석 정밀 좌표
const MEETING_TABLE_CENTER = { x: 558, y: 500 };
const MEETING_SEATS = {
  CEO: { x: 556, y: 448, facing: 'DOWN' as Direction },
  SUPERVISOR: { x: 476, y: 472, facing: 'DOWN' as Direction },
  WORKER1: { x: 472, y: 522, facing: 'UP' as Direction },
  WORKER2: { x: 644, y: 522, facing: 'UP' as Direction },
};

// office_bg.png 일러스트 화풍과 완벽히 어우러지는 차분하고 고급스러운 애니메이션 톤 헤어/수트 팔레트
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
  { id: 'ceo', name: '신영호 대표', deptTitle: '경영진', roomKey: 'MEETING_ROOM', role: 'CEO', deskIdx: 0, hair: '#94a3b8', shade: '#475569', shirt: '#1e293b', accessory: 'CROWN_PIN' },
  { id: 'sup-hr-01', name: '윤지아 팀장', deptTitle: '인사·리서치팀', roomKey: 'HR_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#a85d63', shade: '#6e353a', shirt: '#475569', accessory: 'GLASSES' },
  { id: 'wrk-hr-01', name: '박수아 수석', deptTitle: '인사·리서치팀', roomKey: 'HR_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#3b4254', shade: '#1e2433', shirt: '#2b3954', accessory: 'GLASSES' },
  { id: 'wrk-hr-02', name: '한채원 책임', deptTitle: '인사·리서치팀', roomKey: 'HR_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#6d445c', shade: '#3f2234', shirt: '#3f2e56', accessory: 'HEADSET' },
  { id: 'sup-dev-01', name: '임민서 팀장', deptTitle: 'SW개발팀', roomKey: 'DEV_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#4a3731', shade: '#291d1a', shirt: '#283c5c', accessory: 'HEADSET' },
  { id: 'wrk-dev-01', name: '임지우 수석', deptTitle: 'SW개발팀', roomKey: 'DEV_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#5c7352', shade: '#384731', shirt: '#244b47', accessory: 'GLASSES' },
  { id: 'wrk-dev-02', name: '임유진 책임', deptTitle: 'SW개발팀', roomKey: 'DEV_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#c46d87', shade: '#823c52', shirt: '#4c3566', accessory: 'HEADSET' },
  { id: 'sup-qa-01', name: '임승현 팀장', deptTitle: '품질보증·QA팀', roomKey: 'QA_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#9c5a3c', shade: '#5e321e', shirt: '#284e46', accessory: 'GLASSES' },
  { id: 'wrk-qa-01', name: '한도윤 수석', deptTitle: '품질보증·QA팀', roomKey: 'QA_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#364156', shade: '#1e2536', shirt: '#283c5c', accessory: 'SAFETY_BADGE' },
  { id: 'wrk-qa-02', name: '장지우 책임', deptTitle: '품질보증·QA팀', roomKey: 'QA_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#69527a', shade: '#3e2d4c', shirt: '#38345e', accessory: 'HEADSET' },
  { id: 'sup-fin-01', name: '정우성 팀장', deptTitle: '재무·데이터팀', roomKey: 'FIN_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#b88b58', shade: '#78542d', shirt: '#2b3954', accessory: 'GLASSES' },
  { id: 'wrk-fin-01', name: '강현우 수석', deptTitle: '재무·데이터팀', roomKey: 'FIN_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#3d4654', shade: '#212730', shirt: '#254740', accessory: 'GLASSES' },
  { id: 'wrk-fin-02', name: '배수빈 책임', deptTitle: '재무·데이터팀', roomKey: 'FIN_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#7c4d42', shade: '#4a2a23', shirt: '#433154', accessory: 'HEADSET' },
  { id: 'sup-mkt-01', name: '조다은 팀장', deptTitle: '마케팅·전략팀', roomKey: 'MKT_ROOM', role: 'SUPERVISOR', deskIdx: 0, hair: '#8f4f45', shade: '#542923', shirt: '#523446', accessory: 'GLASSES' },
  { id: 'wrk-mkt-01', name: '장건우 수석', deptTitle: '마케팅·전략팀', roomKey: 'MKT_ROOM', role: 'WORKER1', deskIdx: 1, hair: '#353945', shade: '#1c1f26', shirt: '#2b3954', accessory: 'GLASSES' },
  { id: 'wrk-mkt-02', name: '권하윤 책임', deptTitle: '마케팅·전략팀', roomKey: 'MKT_ROOM', role: 'WORKER2', deskIdx: 2, hair: '#c98a4b', shade: '#855322', shirt: '#2d4a47', accessory: 'HEADSET' },
];

function detectRoomByPoint(x: number, y: number): DeptRoomKey | 'CORRIDOR' {
  for (const [k, r] of Object.entries(ROOMS) as Array<[DeptRoomKey, typeof ROOMS.HR_ROOM]>) {
    if (x >= r.rx && x <= r.rx + r.rw && y >= r.ry && y <= r.ry + r.rh) {
      return k;
    }
  }
  return 'CORRIDOR';
}

function getDoorwayApproachPoint(roomKey: DeptRoomKey): Point {
  const r = ROOMS[roomKey];
  const isTopRow = r.ry < CORRIDOR_Y;
  return {
    x: r.doorX,
    y: isTopRow ? r.ry + r.rh - 26 : r.ry + 28,
  };
}

function clampWalkablePosition(x: number, y: number): Point {
  // buildSmartCorridorPath가 이미 직각 복도·출입문 경로를 생성하므로,
  // 출입문 문턱 데드락을 원천 차단하기 위해 캔버스 외곽 안전 경계만 적용합니다.
  return {
    x: Math.max(16, Math.min(CW - 16, x)),
    y: Math.max(18, Math.min(CH - 16, y)),
  };
}

function pushOrthoPoint(pts: Point[], x: number, y: number) {
  const rx = Math.round(x);
  const ry = Math.round(y);
  const last = pts[pts.length - 1];
  if (!last || Math.hypot(last.x - rx, last.y - ry) > 1.5) {
    pts.push({ x: rx, y: ry });
  }
}

function appendCorridorSegment(pts: Point[], fromX: number, fromY: number, toX: number, toY: number) {
  const startRoom = detectRoomByPoint(fromX, fromY);
  const destRoom = detectRoomByPoint(toX, toY);

  if (startRoom === destRoom) {
    if (startRoom === 'MEETING_ROOM') {
      // 중앙 원형 회의 테이블(558, 525) 관통 방지 외곽 우회 경로
      const safeEdgeY = ROOMS.MEETING_ROOM.ry + 36;
      if (Math.abs(fromX - toX) > 40 && Math.max(fromY, toY) > 475) {
        pushOrthoPoint(pts, fromX, safeEdgeY);
        pushOrthoPoint(pts, toX, safeEdgeY);
      } else {
        pushOrthoPoint(pts, toX, fromY);
      }
      pushOrthoPoint(pts, toX, toY);
      return;
    }
    pushOrthoPoint(pts, toX, fromY);
    pushOrthoPoint(pts, toX, toY);
    return;
  }

  if (startRoom !== 'CORRIDOR') {
    const r1 = ROOMS[startRoom];
    const ap1 = getDoorwayApproachPoint(startRoom);
    // 방 내부 통로를 따라 출입문 직전(doorX, insideY)으로 직각 이동 후 복도로 진출
    if (startRoom === 'MEETING_ROOM' && fromY > 475) {
      pushOrthoPoint(pts, fromX, ap1.y);
      pushOrthoPoint(pts, ap1.x, ap1.y);
    } else {
      pushOrthoPoint(pts, ap1.x, fromY);
      pushOrthoPoint(pts, ap1.x, ap1.y);
    }
    pushOrthoPoint(pts, r1.doorX, r1.doorY);
    pushOrthoPoint(pts, r1.doorX, CORRIDOR_Y);
  } else {
    pushOrthoPoint(pts, fromX, CORRIDOR_Y);
  }

  if (destRoom !== 'CORRIDOR') {
    const r2 = ROOMS[destRoom];
    const ap2 = getDoorwayApproachPoint(destRoom);
    pushOrthoPoint(pts, r2.doorX, CORRIDOR_Y);
    pushOrthoPoint(pts, r2.doorX, r2.doorY);
    pushOrthoPoint(pts, ap2.x, ap2.y);

    if (destRoom === 'MEETING_ROOM') {
      // 회의실 중앙 테이블 충돌 방지: 상단 통로(y=452) 또는 좌/우 외곽에서 좌석으로 직각 진입
      const laneY = toY <= 488 ? toY : ROOMS.MEETING_ROOM.ry + 36;
      pushOrthoPoint(pts, ap2.x, laneY);
      pushOrthoPoint(pts, toX, laneY);
    } else {
      pushOrthoPoint(pts, toX, ap2.y);
    }
  } else {
    pushOrthoPoint(pts, toX, CORRIDOR_Y);
  }

  pushOrthoPoint(pts, toX, toY);
}

function buildSmartCorridorPath(curX: number, curY: number, target: Point, via?: Point): Point[] {
  const pts: Point[] = [];
  if (via) {
    appendCorridorSegment(pts, curX, curY, via.x, via.y);
    appendCorridorSegment(pts, via.x, via.y, target.x, target.y);
  } else {
    appendCorridorSegment(pts, curX, curY, target.x, target.y);
  }
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

  // 4대 테마 고해상도 일러스트 비동기 프리로드 레지스트리 (0초 실시간 전환용)
  const themeImagesRef = useRef<Partial<Record<OfficeThemeId, HTMLImageElement>>>({});
  const themeLoadedRef = useRef<Partial<Record<OfficeThemeId, boolean>>>({});

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

  const { missionRunId, officeTheme, nodes, messages, finalReport } = useOfficeStore();
  const officeThemeRef = useRef<OfficeThemeId>(officeTheme);
  const hasFinalReportRef = useRef<boolean>(false);
  const lastMissionRunIdRef = useRef<number>(missionRunId);

  useEffect(() => {
    officeThemeRef.current = officeTheme;
  }, [officeTheme]);

  // 4개 사옥 테마 배경 이미지 비동기 프리로드 + classic 폴백(/office_bg.jpg)
  useEffect(() => {
    (Object.entries(THEME_BG_PATHS) as Array<[OfficeThemeId, string]>).forEach(([themeKey, srcPath]) => {
      const img = new Image();
      img.decoding = 'async';
      img.onload = () => {
        themeImagesRef.current[themeKey] = img;
        themeLoadedRef.current[themeKey] = true;
      };
      img.onerror = () => {
        if (themeKey === 'classic') {
          const fallbackImg = new Image();
          fallbackImg.decoding = 'async';
          fallbackImg.onload = () => {
            themeImagesRef.current.classic = fallbackImg;
            themeLoadedRef.current.classic = true;
          };
          fallbackImg.onerror = () => {
            themeLoadedRef.current.classic = false;
          };
          fallbackImg.src = '/office_bg.jpg';
        } else {
          themeLoadedRef.current[themeKey] = false;
        }
      };
      img.src = srcPath;
    });
  }, []);

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
        taskLabel: item.role === 'CEO' ? '총괄 결재 대기' : '부서 일상 업무',
        activeBubble: '',
        lastBubbleText: '',
        bubbleAnim: 1,
        lastSpokenFrame: 0,
        progress: 0,
        appliedPhase: 0,
        stuckFrames: 0,
        lastWaypointDist: Infinity,
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
    const isNewMission = missionRunId !== lastMissionRunIdRef.current;
    const hasRejected = messages.some((m) => m.type === 'QC_REJECT');
    const isArchiveHit = messages.some(
      (m) => String(m.type) === 'ARCHIVE_HIT' || (m.payload?.text || '').includes('부서 책장(서가) 기존 기록 발견')
    );
    const hasLiveCeo = messages.some(
      (m) => String(m.type) === 'CEO_LIVE_INTERVENTION' || (m.payload?.text || '').includes('실시간 CEO 긴급 지침')
    );
    const isMissionFinished = Boolean(finalReport);
    hasFinalReportRef.current = isMissionFinished;

    if (isNewMission || !hasStarted) {
      lastMissionRunIdRef.current = missionRunId;
      trailsRef.current = [];
      particlesRef.current = [];
      archiveHitFlashRef.current = 0;
      ceoWaveFlashRef.current = 0;
      reportUnlockedRef.current = false;
      reportBannerAnimRef.current = 0;
      setReportUnlocked(false);
      onAllGatheredChange?.(false);

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
        st.facing = 'DOWN';
        st.workTimer = 0;
        st.maxWorkTimer = 120;
        st.progress = 0;
        st.activeBubble = '';
        st.lastBubbleText = '';
        st.bubbleAnim = 0;
        st.lastSpokenFrame = 0;
        st.taskLabel = st.role === 'CEO' ? '총괄 결재 대기' : '부서 일상 대기';
        st.appliedPhase = 0;
        st.stuckFrames = 0;
        st.lastWaypointDist = Infinity;
      });

      if (!hasStarted) {
        setPhaseBanner('🏢 전 부서(5개 팀 16명) 각자 사무실에서 일상 근무 대기 중');
        return;
      }
    }

    if (hasLiveCeo) {
      ceoWaveFlashRef.current = 120;
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
          ag.lastSpokenFrame = frameCountRef.current;
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
  }, [nodes, messages, finalReport, reportUnlocked, missionRunId]);

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
      cx >= MEETING_TABLE_CENTER.x - 52 &&
      cx <= MEETING_TABLE_CENTER.x + 52 &&
      cy >= MEETING_TABLE_CENTER.y - 38 &&
      cy <= MEETING_TABLE_CENTER.y + 38;
    setIsHoveringReport(hit);
    if (hit && isClick && onOpenReportModal) {
      onOpenReportModal();
    }
  };

  useEffect(() => {
    let animId: number;

    const drawHybridRoomSpotlight = (
      ctx: CanvasRenderingContext2D,
      rx: number,
      ry: number,
      rw: number,
      rh: number,
      badgeColor: string,
      isRoomActive: boolean,
      rKey: DeptRoomKey,
      f: number
    ) => {
      const centerX = rx + rw / 2;
      const centerY = ry + rh / 2 + 10;
      const lightRadius = Math.max(rw, rh) * 0.65;
      const pulse = 1 + Math.sin(f * 0.04) * 0.07;

      const roomGlow = ctx.createRadialGradient(
        centerX,
        centerY,
        10,
        centerX,
        centerY,
        lightRadius * pulse
      );

      if (isRoomActive) {
        roomGlow.addColorStop(0, 'rgba(52, 211, 153, 0.22)');
        roomGlow.addColorStop(0.5, 'rgba(56, 189, 248, 0.09)');
        roomGlow.addColorStop(1, 'rgba(15, 23, 42, 0)');
      } else if (rKey === 'MEETING_ROOM') {
        roomGlow.addColorStop(0, 'rgba(251, 191, 36, 0.16)');
        roomGlow.addColorStop(0.55, 'rgba(245, 158, 11, 0.05)');
        roomGlow.addColorStop(1, 'rgba(15, 23, 42, 0)');
      } else {
        roomGlow.addColorStop(0, `${badgeColor}14`);
        roomGlow.addColorStop(0.6, 'rgba(15, 23, 42, 0)');
        roomGlow.addColorStop(1, 'rgba(15, 23, 42, 0.14)');
      }

      ctx.save();
      ctx.fillStyle = roomGlow;
      ctx.beginPath();
      ctx.roundRect(rx, ry, rw, rh, 8);
      ctx.fill();

      if (isRoomActive) {
        ctx.strokeStyle = 'rgba(52, 211, 153, 0.85)';
        ctx.lineWidth = 2.5;
        ctx.shadowColor = 'rgba(16, 185, 129, 0.65)';
        ctx.shadowBlur = 12;
        ctx.beginPath();
        ctx.roundRect(rx + 2, ry + 2, rw - 4, rh - 4, 8);
        ctx.stroke();
      }
      ctx.restore();
    };

    const drawDeskInpaintMask = (
      ctx: CanvasRenderingContext2D,
      dx: number,
      dy: number,
      rKey: DeptRoomKey,
      isOccupiedAtDesk: boolean
    ) => {
      const room = ROOMS[rKey];
      ctx.save();

      const bgPatchGrad = ctx.createLinearGradient(dx, dy - 35, dx, dy + 4);
      bgPatchGrad.addColorStop(0, room.bgFloorShadow);
      bgPatchGrad.addColorStop(1, room.bgFloorTone);
      ctx.fillStyle = bgPatchGrad;
      ctx.beginPath();
      ctx.roundRect(dx - 23, dy - 34, 46, 38, 9);
      ctx.fill();

      ctx.strokeStyle = 'rgba(0, 0, 0, 0.14)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(dx - 21, dy - 22);
      ctx.lineTo(dx + 21, dy - 22);
      ctx.moveTo(dx - 21, dy - 12);
      ctx.lineTo(dx + 21, dy - 12);
      ctx.stroke();

      ctx.fillStyle = 'rgba(0, 0, 0, 0.32)';
      ctx.beginPath();
      ctx.ellipse(dx, dy - 4, 18, 7, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#141c2b';
      ctx.beginPath();
      ctx.roundRect(dx - 15.5, dy - 28.5, 31, 27, 7);
      ctx.fill();
      ctx.strokeStyle = '#475569';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      const chairGrad = ctx.createLinearGradient(dx, dy - 27, dx, dy - 3);
      chairGrad.addColorStop(0, '#334155');
      chairGrad.addColorStop(1, '#1e293b');
      ctx.fillStyle = chairGrad;
      ctx.beginPath();
      ctx.roundRect(dx - 12.5, dy - 25.5, 25, 21, 5);
      ctx.fill();

      ctx.fillStyle = '#475569';
      ctx.beginPath();
      ctx.roundRect(dx - 9, dy - 24, 18, 4.5, 2.2);
      ctx.fill();

      if (!isOccupiedAtDesk) {
        const tagY = dy + 25;
        ctx.fillStyle = room.bgFloorTone;
        ctx.beginPath();
        ctx.roundRect(dx - 57, tagY - 1, 114, 29, 7);
        ctx.fill();

        ctx.fillStyle = 'rgba(9, 13, 22, 0.88)';
        ctx.beginPath();
        ctx.roundRect(dx - 46, tagY + 3, 92, 20, 10);
        ctx.fill();
        ctx.strokeStyle = 'rgba(148, 163, 184, 0.5)';
        ctx.lineWidth = 1.1;
        ctx.stroke();
        ctx.fillStyle = '#e2e8f0';
        ctx.font = `700 9.5px ${FONT_FAMILY}`;
        ctx.textAlign = 'center';
        ctx.fillText('🪑 자리 이동 중', dx, tagY + 16.5);
      }

      ctx.restore();
    };

    const drawCeoInpaintMask = (ctx: CanvasRenderingContext2D) => {
      const cx = MEETING_SEATS.CEO.x;
      const cy = MEETING_SEATS.CEO.y;
      ctx.save();

      const wallGrad = ctx.createLinearGradient(cx, cy - 34, cx, cy + 8);
      wallGrad.addColorStop(0, '#8e4e25');
      wallGrad.addColorStop(1, '#6c3818');
      ctx.fillStyle = wallGrad;
      ctx.beginPath();
      ctx.roundRect(cx - 22, cy - 33, 44, 38, 8);
      ctx.fill();

      ctx.fillStyle = '#0f172a';
      ctx.beginPath();
      ctx.roundRect(cx - 16, cy - 29, 32, 27, 6);
      ctx.fill();
      ctx.strokeStyle = '#fbbf24';
      ctx.lineWidth = 1.2;
      ctx.stroke();
      ctx.fillStyle = '#1e293b';
      ctx.beginPath();
      ctx.roundRect(cx - 13, cy - 26, 26, 22, 4);
      ctx.fill();

      const tableMaskGrad = ctx.createLinearGradient(cx - 64, 469, cx + 64, 508);
      tableMaskGrad.addColorStop(0, '#92400e');
      tableMaskGrad.addColorStop(0.5, '#b45309');
      tableMaskGrad.addColorStop(1, '#92400e');
      ctx.fillStyle = tableMaskGrad;
      ctx.beginPath();
      ctx.roundRect(cx - 63, 469, 126, 38, 10);
      ctx.fill();

      ctx.strokeStyle = 'rgba(253, 224, 71, 0.45)';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(cx - 58, 504);
      ctx.quadraticCurveTo(cx, 496, cx + 58, 504);
      ctx.stroke();

      ctx.restore();
    };

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

      ctx.fillStyle = '#0f172a';
      ctx.fillRect(rx, ry, rw, 22);
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(rx, ry + 22, rw, 6);
      ctx.fillStyle = 'rgba(0,0,0,0.35)';
      ctx.fillRect(rx, ry + 28, rw, 7);

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
      ctx.strokeStyle = '#020617';
      ctx.lineWidth = 8;
      ctx.strokeRect(rx - 2, ry - 2, rw + 4, rh + 4);

      ctx.strokeStyle = isRoomActive ? '#10b981' : '#475569';
      ctx.lineWidth = 4.5;
      ctx.strokeRect(rx, ry, rw, rh);

      ctx.strokeStyle = isRoomActive ? '#6ee7b7' : `${badgeColor}88`;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(rx + 3, ry + 3, rw - 6, rh - 6);

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

      ctx.fillStyle = '#9a3412';
      ctx.fillRect(-7, 1, 14, 10);
      ctx.fillStyle = '#c2400c';
      ctx.fillRect(-9, -1, 18, 4);
      ctx.strokeStyle = '#431407';
      ctx.lineWidth = 1;
      ctx.strokeRect(-7, 1, 14, 10);

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

    const drawOfficeProps = (
      ctx: CanvasRenderingContext2D,
      rx: number,
      ry: number,
      rw: number,
      rh: number,
      rKey: DeptRoomKey,
      f: number
    ) => {
      drawLushPotPlant(ctx, rx + 24, ry + rh - 26, f, 0.95);

      if (rKey === 'HR_ROOM') {
        const bx = rx + rw - 78;
        const by = ry + 18;
        ctx.fillStyle = '#f8fafc';
        ctx.fillRect(bx, by, 62, 34);
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2;
        ctx.strokeRect(bx, by, 62, 34);
      } else if (rKey === 'DEV_ROOM') {
        const mx = rx + rw - 88;
        const my = ry + 16;
        ctx.fillStyle = '#090d16';
        ctx.fillRect(mx, my, 74, 38);
        ctx.strokeStyle = '#818cf8';
        ctx.lineWidth = 2;
        ctx.strokeRect(mx, my, 74, 38);
      } else if (rKey === 'QA_ROOM') {
        const cx = rx + 18;
        const cy = ry + 16;
        const cw = 98;
        const ch = 36;
        ctx.fillStyle = '#090d16';
        ctx.fillRect(cx, cy, cw, ch);
        ctx.strokeStyle = '#34d399';
        ctx.lineWidth = 2;
        ctx.strokeRect(cx, cy, cw, ch);
        for (let b = 0; b < 3; b++) {
          const bx = cx + 8 + ((b * 30 + Math.floor(f * 0.5)) % (cw - 24));
          ctx.fillStyle = b % 2 === 0 ? '#38bdf8' : '#fbbf24';
          ctx.fillRect(bx, cy + 12, 12, 11);
        }
      }
    };

    const drawBookshelf = (
      ctx: CanvasRenderingContext2D,
      bx: number,
      by: number,
      isGlowing: boolean,
      f: number,
      bgLoaded: boolean
    ) => {
      if (isGlowing) {
        const shelfGlow = ctx.createRadialGradient(bx, by - 5, 6, bx, by - 5, 56);
        shelfGlow.addColorStop(0, 'rgba(250, 204, 21, 0.55)');
        shelfGlow.addColorStop(0.5, 'rgba(56, 189, 248, 0.24)');
        shelfGlow.addColorStop(1, 'rgba(56, 189, 248, 0)');
        ctx.fillStyle = shelfGlow;
        ctx.beginPath();
        ctx.arc(bx, by - 5, 56, 0, Math.PI * 2);
        ctx.fill();
      }

      if (!bgLoaded) {
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
      }

      if (isGlowing) {
        ctx.save();
        ctx.strokeStyle = f % 16 < 8 ? '#fde047' : '#38bdf8';
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.roundRect(bx - 34, by - 24, 68, 38, 6);
        ctx.stroke();

        ctx.fillStyle = 'rgba(9, 13, 22, 0.94)';
        ctx.beginPath();
        ctx.roundRect(bx - 52, by - 44, 104, 19, 9);
        ctx.fill();
        ctx.fillStyle = '#fef08a';
        ctx.font = `800 10.5px ${FONT_FAMILY}`;
        ctx.textAlign = 'center';
        ctx.fillText('📚 기존 결재철 인출!', bx, by - 31);
        ctx.restore();
      }
    };

    const drawDesk = (
      ctx: CanvasRenderingContext2D,
      dx: number,
      dy: number,
      isWorking: boolean,
      isSelectedRoom: boolean,
      f: number,
      bgLoaded: boolean,
      activeTheme: OfficeThemeId = 'classic'
    ) => {
      if (bgLoaded && activeTheme === 'classic') {
        const woodGrad = ctx.createLinearGradient(dx - 38, dy + 11, dx + 38, dy + 24);
        woodGrad.addColorStop(0, '#d99b52');
        woodGrad.addColorStop(0.65, '#b8732e');
        woodGrad.addColorStop(1, '#7c4316');
        ctx.fillStyle = woodGrad;
        ctx.beginPath();
        ctx.roundRect(dx - 38, dy + 11, 76, 14, 3);
        ctx.fill();
        ctx.strokeStyle = '#451a03';
        ctx.lineWidth = 1;
        ctx.stroke();

        const lampGlow = ctx.createRadialGradient(dx - 26, dy + 6, 1, dx - 26, dy + 6, 16);
        lampGlow.addColorStop(0, 'rgba(253, 224, 71, 0.34)');
        lampGlow.addColorStop(1, 'rgba(253, 224, 71, 0)');
        ctx.fillStyle = lampGlow;
        ctx.beginPath();
        ctx.arc(dx - 26, dy + 6, 16, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#2563eb';
        ctx.fillRect(dx + 22, dy + 4, 6, 10);
        ctx.fillStyle = '#38bdf8';
        ctx.fillRect(dx + 29, dy + 4, 5, 10);

        if (isWorking || isSelectedRoom) {
          const bloomRadius = isWorking ? 42 + Math.sin(f * 0.14) * 5 : 26;
          const monitorBloom = ctx.createRadialGradient(dx, dy + 6, 2, dx, dy + 6, bloomRadius);
          if (isWorking) {
            monitorBloom.addColorStop(0, 'rgba(52, 211, 153, 0.55)');
            monitorBloom.addColorStop(0.45, 'rgba(56, 189, 248, 0.28)');
            monitorBloom.addColorStop(1, 'rgba(56, 189, 248, 0)');
          } else {
            monitorBloom.addColorStop(0, 'rgba(56, 189, 248, 0.22)');
            monitorBloom.addColorStop(1, 'rgba(56, 189, 248, 0)');
          }
          ctx.save();
          ctx.fillStyle = monitorBloom;
          ctx.beginPath();
          ctx.arc(dx, dy + 6, bloomRadius, 0, Math.PI * 2);
          ctx.fill();
          ctx.restore();
        }

        ctx.fillStyle = '#1e293b';
        ctx.beginPath();
        ctx.roundRect(dx - 16, dy - 1, 32, 15, 3);
        ctx.fill();
        ctx.strokeStyle = isWorking ? '#34d399' : '#0f172a';
        ctx.lineWidth = 1.3;
        ctx.stroke();

        // 듀얼 보조 모니터 (좌측)
        ctx.fillStyle = '#0f172a';
        ctx.beginPath();
        ctx.roundRect(dx - 34, dy + 2, 16, 11, 2);
        ctx.fill();
        ctx.fillStyle = isWorking ? '#1e3a5f' : '#334155';
        ctx.fillRect(dx - 32.5, dy + 3.5, 13, 8);

        ctx.fillStyle = '#334155';
        ctx.beginPath();
        ctx.roundRect(dx - 13, dy + 1.5, 26, 10, 2);
        ctx.fill();

        ctx.fillStyle = '#0f172a';
        ctx.fillRect(dx - 3, dy + 14, 6, 4);
        ctx.fillRect(dx - 9, dy + 17, 18, 2.5);

        // 책상 커피 머그컵 & 김 모락모락 애니메이션
        ctx.fillStyle = '#f8fafc';
        ctx.beginPath();
        ctx.roundRect(dx + 22, dy + 14, 6.5, 6, 1.5);
        ctx.fill();
        ctx.strokeStyle = '#64748b';
        ctx.lineWidth = 0.8;
        ctx.stroke();
        ctx.fillStyle = '#78350f';
        ctx.fillRect(dx + 23, dy + 14.5, 4.5, 1.8);
        if (isWorking || isSelectedRoom) {
          const steamShift = Math.sin(f * 0.09 + dx) * 1.6;
          const steamLift = (f * 0.25) % 6;
          ctx.strokeStyle = 'rgba(241, 245, 249, 0.55)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(dx + 25, dy + 13 - steamLift * 0.4);
          ctx.quadraticCurveTo(dx + 25 + steamShift, dy + 9 - steamLift * 0.5, dx + 25 - steamShift * 0.5, dy + 5 - steamLift);
          ctx.stroke();
        }

        if (isWorking) {
          // 실시간 코딩/차트 스크롤 애니메이션
          const scroll = Math.floor(f / 4) % 4;
          const barW1 = 10 + ((f + dx) % 11);
          const barW2 = 8 + ((f * 2 + dy) % 13);
          ctx.fillStyle = '#34d399';
          ctx.fillRect(dx - 11, dy + 3 + (scroll % 2) * 1.5, barW1, 1.8);
          ctx.fillStyle = '#38bdf8';
          ctx.fillRect(dx - 11, dy + 6.2, barW2, 1.8);
          ctx.fillStyle = '#facc15';
          ctx.fillRect(dx - 11, dy + 9.2, 6 + (f % 8), 1.5);

          // 보조 모니터 실시간 파형 바 차트
          ctx.fillStyle = '#38bdf8';
          ctx.fillRect(dx - 31, dy + 9 - ((f >> 2) % 4), 2.5, 2 + ((f >> 2) % 4));
          ctx.fillStyle = '#34d399';
          ctx.fillRect(dx - 27, dy + 9 - (((f + 5) >> 2) % 4), 2.5, 2 + (((f + 5) >> 2) % 4));
          ctx.fillStyle = '#f472b6';
          ctx.fillRect(dx - 23, dy + 9 - (((f + 9) >> 2) % 4), 2.5, 2 + (((f + 9) >> 2) % 4));
        }
        return;
      }

      // 하이테크 테마(space/factory/quantum)일 때는 배경 일러스트의 책상을 가리지 않고 콤팩트 홀로그램/콘솔 오버레이만 표시
      if (bgLoaded) {
        const accentHex =
          activeTheme === 'space'
            ? '#22d3ee'
            : activeTheme === 'factory'
            ? '#10b981'
            : '#c084fc';
        const secHex =
          activeTheme === 'space'
            ? '#38bdf8'
            : activeTheme === 'factory'
            ? '#facc15'
            : '#fbbf24';

        if (isWorking || isSelectedRoom) {
          const glowR = isWorking ? 28 + Math.sin(f * 0.14) * 4 : 18;
          const halo = ctx.createRadialGradient(dx, dy + 6, 1, dx, dy + 6, glowR);
          halo.addColorStop(0, activeTheme === 'space' ? 'rgba(34,211,238,0.42)' : activeTheme === 'factory' ? 'rgba(16,185,129,0.42)' : 'rgba(192,132,252,0.44)');
          halo.addColorStop(1, 'rgba(0,0,0,0)');
          ctx.fillStyle = halo;
          ctx.beginPath();
          ctx.arc(dx, dy + 6, glowR, 0, Math.PI * 2);
          ctx.fill();
        }

        // 콤팩트 홀로그래픽/클린룸 단말기
        ctx.fillStyle = activeTheme === 'space' ? 'rgba(8, 47, 73, 0.78)' : activeTheme === 'factory' ? 'rgba(15, 23, 42, 0.88)' : 'rgba(24, 12, 46, 0.84)';
        ctx.beginPath();
        ctx.roundRect(dx - 17, dy - 1, 34, 14, 3);
        ctx.fill();
        ctx.strokeStyle = isWorking ? accentHex : 'rgba(148, 163, 184, 0.55)';
        ctx.lineWidth = 1.25;
        ctx.stroke();

        // 하단 에미터 바
        ctx.fillStyle = accentHex;
        ctx.fillRect(dx - 11, dy + 14, 22, 2);

        if (isWorking) {
          const b1 = 8 + ((f + dx) % 12);
          const b2 = 6 + ((f * 2 + dy) % 14);
          ctx.fillStyle = accentHex;
          ctx.fillRect(dx - 13, dy + 3, b1, 1.8);
          ctx.fillStyle = secHex;
          ctx.fillRect(dx - 13, dy + 6.5, b2, 1.8);
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(dx - 13, dy + 9.8, 5 + (f % 10), 1.4);
        }
        return;
      }

      const deskTop =
        activeTheme === 'space'
          ? '#0e7490'
          : activeTheme === 'factory'
          ? '#475569'
          : activeTheme === 'quantum'
          ? '#4c1d95'
          : '#b45309';
      const deskEdge =
        activeTheme === 'space'
          ? '#155e75'
          : activeTheme === 'factory'
          ? '#1e293b'
          : activeTheme === 'quantum'
          ? '#2e1065'
          : '#78350f';

      ctx.fillStyle = '#0f172a';
      ctx.beginPath();
      ctx.roundRect(dx - 14, dy - 16, 28, 14, 4);
      ctx.fill();
      ctx.fillStyle = '#334155';
      ctx.beginPath();
      ctx.roundRect(dx - 11, dy - 14, 22, 10, 3);
      ctx.fill();

      ctx.fillStyle = 'rgba(0,0,0,0.4)';
      ctx.beginPath();
      ctx.roundRect(dx - 41, dy + 9, 82, 33, 4);
      ctx.fill();
      ctx.fillStyle = deskEdge;
      ctx.beginPath();
      ctx.roundRect(dx - 39, dy + 5, 78, 28, 4);
      ctx.fill();
      ctx.fillStyle = deskTop;
      ctx.fillRect(dx - 36, dy + 7, 72, 21);
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(dx - 36, dy + 28, 72, 5);

      ctx.fillStyle = '#0f172a';
      ctx.fillRect(dx - 22, dy, 34, 17);
      ctx.fillStyle = isWorking ? '#022c22' : isSelectedRoom ? '#1e293b' : '#334155';
      ctx.fillRect(dx - 20, dy + 2, 30, 13);
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
      const idleBreath = Math.sin(f * 0.075 + idx) * 0.65;
      const workBob = isWorkingDesk ? Math.sin(f * 0.28 + idx) * 1.35 : idleBreath;
      const bounceY = isWalking ? Math.abs(walkCycle) * -3.6 : workBob;

      const swayX = isWalking
        ? Math.sin(f * 0.22 * speedRef.current + idx) * 1.5
        : isWorkingDesk
        ? Math.sin(f * 0.15 + idx) * 0.5
        : 0;

      const squashPhase = isWalking
        ? Math.cos(f * 0.44 * speedRef.current + idx) * 0.055
        : isWorkingDesk
        ? Math.sin(f * 0.28 + idx) * 0.03
        : Math.sin(f * 0.075 + idx) * 0.02;
      const scaleX = 1 - squashPhase * 0.7;
      const scaleY = 1 + squashPhase;

      const cx = Math.round(ag.x + swayX);
      const cy = Math.round(ag.y + bounceY);

      if (ag.isSelectedTeam) {
        const shadowGlow = ctx.createRadialGradient(ag.x, ag.y + 12, 2, ag.x, ag.y + 12, 22);
        if (ag.taskLabel.includes('반려')) {
          shadowGlow.addColorStop(0, 'rgba(244, 63, 94, 0.65)');
          shadowGlow.addColorStop(1, 'rgba(244, 63, 94, 0)');
        } else if (ag.isShelfMode) {
          shadowGlow.addColorStop(0, 'rgba(250, 204, 21, 0.65)');
          shadowGlow.addColorStop(1, 'rgba(250, 204, 21, 0)');
        } else {
          shadowGlow.addColorStop(0, 'rgba(16, 185, 129, 0.52)');
          shadowGlow.addColorStop(1, 'rgba(16, 185, 129, 0)');
        }
        ctx.fillStyle = shadowGlow;
        ctx.beginPath();
        ctx.ellipse(ag.x, ag.y + 12, 20, 7.5, 0, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.fillStyle = 'rgba(0,0,0,0.28)';
        ctx.beginPath();
        ctx.ellipse(ag.x, ag.y + 12, 12, 4.5, 0, 0, Math.PI * 2);
        ctx.fill();
      }

      const pivotX = cx;
      const pivotY = ag.y + 11;
      ctx.save();
      ctx.translate(pivotX, pivotY);
      ctx.scale(scaleX, scaleY);
      ctx.translate(-pivotX, -pivotY);

      const leftLegY = isWalking ? Math.round(walkCycle * 3.5) : 0;
      const rightLegY = isWalking ? Math.round(-walkCycle * 3.5) : 0;
      ctx.fillStyle = '#1e293b';
      ctx.beginPath();
      ctx.roundRect(cx - 6.5, cy + 4 + leftLegY, 5, 7.5, 2.5);
      ctx.roundRect(cx + 1.5, cy + 4 + rightLegY, 5, 7.5, 2.5);
      ctx.fill();

      const suitGrad = ctx.createLinearGradient(cx, cy - 7, cx, cy + 7);
      suitGrad.addColorStop(0, ag.shirtColor);
      suitGrad.addColorStop(1, '#0f172a');
      ctx.fillStyle = suitGrad;
      ctx.beginPath();
      ctx.roundRect(cx - 11, cy - 6.5, 22, 12.5, 5.5);
      ctx.fill();
      ctx.strokeStyle = '#1e1b18';
      ctx.lineWidth = 1.3;
      ctx.stroke();

      ctx.fillStyle = '#f8fafc';
      ctx.beginPath();
      ctx.moveTo(cx - 3.5, cy - 6);
      ctx.lineTo(cx + 3.5, cy - 6);
      ctx.lineTo(cx, cy + 1.5);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = ag.role === 'CEO' ? '#dc2626' : ag.role === 'SUPERVISOR' ? '#d97706' : '#2563eb';
      ctx.fillRect(cx - 1.1, cy - 4.2, 2.2, 6);

      const armOffset = isWorkingDesk ? Math.round(Math.sin(f * 0.58 + idx) * 2.6) : Math.round(walkCycle * 2.2);
      ctx.fillStyle = ag.shirtColor;
      ctx.beginPath();
      ctx.roundRect(cx - 14.5, cy - 4.5 + armOffset, 4.5, 8.5, 2.5);
      ctx.roundRect(cx + 10.0, cy - 4.5 - armOffset, 4.5, 8.5, 2.5);
      ctx.fill();
      ctx.strokeStyle = '#1e1b18';
      ctx.lineWidth = 1;
      ctx.stroke();

      // 타자 치는 손목/손끝 모션 (책상 업무 중일 때 활발한 타이핑 표현)
      if (isWorkingDesk) {
        ctx.fillStyle = '#fde2c8';
        ctx.beginPath();
        ctx.arc(cx - 11.5, cy + 5.2 + armOffset, 2.1, 0, Math.PI * 2);
        ctx.arc(cx + 11.5, cy + 5.2 - armOffset, 2.1, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.fillStyle = '#fde2c8';
      ctx.beginPath();
      ctx.arc(cx - 12.2, cy + 4.8 + armOffset, 2.1, 0, Math.PI * 2);
      ctx.arc(cx + 12.2, cy + 4.8 - armOffset, 2.1, 0, Math.PI * 2);
      ctx.fill();

      if (idx % 3 === 1 && ag.role !== 'CEO') {
        ctx.fillStyle = ag.hairShade;
        ctx.beginPath();
        ctx.arc(cx, cy - 29.5, 5.8, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#231815';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      } else if (idx % 3 === 2 && ag.role !== 'CEO') {
        ctx.fillStyle = ag.hairShade;
        ctx.beginPath();
        ctx.ellipse(cx + 13.5, cy - 19.5, 4.2, 6.8, 0.3, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#231815';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }

      const hairGrad = ctx.createLinearGradient(cx, cy - 30, cx, cy - 7);
      hairGrad.addColorStop(0, ag.hairColor);
      hairGrad.addColorStop(1, ag.hairShade);

      ctx.fillStyle = hairGrad;
      ctx.beginPath();
      ctx.arc(cx, cy - 18.5, 14.8, Math.PI * 0.85, Math.PI * 2.15);
      ctx.quadraticCurveTo(cx + 15.2, cy - 9, cx + 11, cy - 6.5);
      ctx.lineTo(cx - 11, cy - 6.5);
      ctx.quadraticCurveTo(cx - 15.2, cy - 9, cx - 13.2, cy - 12);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = '#231815';
      ctx.lineWidth = 1.35;
      ctx.stroke();

      if (ag.facing === 'UP') {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.28)';
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        ctx.arc(cx, cy - 18, 9.5, Math.PI * 1.18, Math.PI * 1.82);
        ctx.stroke();
      } else {
        ctx.fillStyle = '#fbd8be';
        ctx.beginPath();
        ctx.ellipse(cx - 12.2, cy - 14.2, 2.2, 3.0, 0, 0, Math.PI * 2);
        ctx.ellipse(cx + 12.2, cy - 14.2, 2.2, 3.0, 0, 0, Math.PI * 2);
        ctx.fill();

        const skinGrad = ctx.createLinearGradient(cx, cy - 23, cx, cy - 6);
        skinGrad.addColorStop(0, '#fff3e6');
        skinGrad.addColorStop(1, '#fbd6b8');
        ctx.fillStyle = skinGrad;
        ctx.beginPath();
        ctx.moveTo(cx - 11.8, cy - 19.5);
        ctx.quadraticCurveTo(cx - 12.2, cy - 10.5, cx - 7.5, cy - 7.2);
        ctx.quadraticCurveTo(cx, cy - 4.8, cx + 7.5, cy - 7.2);
        ctx.quadraticCurveTo(cx + 12.2, cy - 10.5, cx + 11.8, cy - 19.5);
        ctx.quadraticCurveTo(cx, cy - 23.5, cx - 11.8, cy - 19.5);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = '#3b231a';
        ctx.lineWidth = 1.05;
        ctx.stroke();

        const eyeShiftX = ag.facing === 'LEFT' ? -1.8 : ag.facing === 'RIGHT' ? 1.8 : 0;

        ctx.fillStyle = 'rgba(244, 114, 130, 0.45)';
        ctx.beginPath();
        ctx.ellipse(cx - 7.8 + eyeShiftX, cy - 10.5, 2.6, 1.4, 0, 0, Math.PI * 2);
        ctx.ellipse(cx + 7.8 + eyeShiftX, cy - 10.5, 2.6, 1.4, 0, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = '#7c3f2c';
        ctx.lineWidth = 1.1;
        ctx.beginPath();
        ctx.arc(cx + eyeShiftX, cy - 9.6, 1.6, 0.15 * Math.PI, 0.85 * Math.PI);
        ctx.stroke();

        if ((f + idx * 31) % 160 > 5) {
          ctx.fillStyle = '#1e1b24';
          ctx.beginPath();
          ctx.ellipse(cx - 5.2 + eyeShiftX, cy - 13.8, 2.1, 2.6, 0, 0, Math.PI * 2);
          ctx.ellipse(cx + 5.2 + eyeShiftX, cy - 13.8, 2.1, 2.6, 0, 0, Math.PI * 2);
          ctx.fill();

          ctx.strokeStyle = '#141118';
          ctx.lineWidth = 1.3;
          ctx.beginPath();
          ctx.arc(cx - 5.2 + eyeShiftX, cy - 14.0, 2.4, Math.PI * 1.1, Math.PI * 1.9);
          ctx.stroke();
          ctx.beginPath();
          ctx.arc(cx + 5.2 + eyeShiftX, cy - 14.0, 2.4, Math.PI * 1.1, Math.PI * 1.9);
          ctx.stroke();

          ctx.fillStyle = ag.hairColor;
          ctx.beginPath();
          ctx.arc(cx - 5.2 + eyeShiftX, cy - 12.5, 1.1, 0, Math.PI * 2);
          ctx.arc(cx + 5.2 + eyeShiftX, cy - 12.5, 1.1, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = '#ffffff';
          ctx.beginPath();
          ctx.arc(cx - 5.8 + eyeShiftX, cy - 14.8, 0.95, 0, Math.PI * 2);
          ctx.arc(cx + 4.6 + eyeShiftX, cy - 14.8, 0.95, 0, Math.PI * 2);
          ctx.fill();
        } else {
          ctx.strokeStyle = '#1e1b24';
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.arc(cx - 5.2 + eyeShiftX, cy - 13.5, 2.2, 0.1 * Math.PI, 0.9 * Math.PI);
          ctx.stroke();
          ctx.beginPath();
          ctx.arc(cx + 5.2 + eyeShiftX, cy - 13.5, 2.2, 0.1 * Math.PI, 0.9 * Math.PI);
          ctx.stroke();
        }

        ctx.fillStyle = hairGrad;
        ctx.beginPath();
        ctx.arc(cx, cy - 18.8, 14.5, Math.PI * 0.96, Math.PI * 2.04);
        ctx.quadraticCurveTo(cx + 10, cy - 15.5, cx + 5.5, cy - 17.8);
        ctx.quadraticCurveTo(cx + 1.5, cy - 14.5, cx - 2.5, cy - 17.8);
        ctx.quadraticCurveTo(cx - 7.5, cy - 15.2, cx - 14.4, cy - 18.2);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = '#231815';
        ctx.lineWidth = 1.2;
        ctx.stroke();

        ctx.fillStyle = ag.hairColor;
        ctx.beginPath();
        ctx.moveTo(cx - 14.2, cy - 19.5);
        ctx.quadraticCurveTo(cx - 15.2, cy - 12.5, cx - 11.2, cy - 8.5);
        ctx.quadraticCurveTo(cx - 10.2, cy - 13.5, cx - 11.5, cy - 19.0);
        ctx.closePath();
        ctx.fill();

        ctx.beginPath();
        ctx.moveTo(cx + 14.2, cy - 19.5);
        ctx.quadraticCurveTo(cx + 15.2, cy - 12.5, cx + 11.2, cy - 8.5);
        ctx.quadraticCurveTo(cx + 10.2, cy - 13.5, cx + 11.5, cy - 19.0);
        ctx.closePath();
        ctx.fill();

        ctx.strokeStyle = 'rgba(255, 255, 255, 0.34)';
        ctx.lineWidth = 2.0;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.arc(cx, cy - 19.2, 10.8, Math.PI * 1.18, Math.PI * 1.82);
        ctx.stroke();

        if (ag.accessory === 'GLASSES') {
          ctx.strokeStyle = '#334155';
          ctx.lineWidth = 1.25;
          ctx.beginPath();
          ctx.roundRect(cx - 8.6 + eyeShiftX, cy - 16.5, 5.8, 4.8, 2.0);
          ctx.roundRect(cx + 2.8 + eyeShiftX, cy - 16.5, 5.8, 4.8, 2.0);
          ctx.stroke();
          ctx.fillStyle = 'rgba(255, 255, 255, 0.22)';
          ctx.beginPath();
          ctx.roundRect(cx - 8.2 + eyeShiftX, cy - 16.1, 5.0, 4.0, 1.6);
          ctx.roundRect(cx + 3.2 + eyeShiftX, cy - 16.1, 5.0, 4.0, 1.6);
          ctx.fill();
          ctx.beginPath();
          ctx.moveTo(cx - 2.8 + eyeShiftX, cy - 14.2);
          ctx.lineTo(cx + 2.8 + eyeShiftX, cy - 14.2);
          ctx.stroke();
        } else if (ag.accessory === 'HEADSET') {
          ctx.strokeStyle = '#475569';
          ctx.lineWidth = 2.0;
          ctx.beginPath();
          ctx.arc(cx, cy - 19.2, 14.8, Math.PI * 1.06, Math.PI * 1.94);
          ctx.stroke();
          ctx.fillStyle = '#334155';
          ctx.beginPath();
          ctx.roundRect(cx - 16.5, cy - 18.2, 3.6, 6.8, 1.8);
          ctx.roundRect(cx + 12.9, cy - 18.2, 3.6, 6.8, 1.8);
          ctx.fill();
          ctx.strokeStyle = '#1e293b';
          ctx.lineWidth = 1;
          ctx.stroke();
          ctx.fillStyle = '#38bdf8';
          ctx.beginPath();
          ctx.arc(cx - 14.7, cy - 14.8, 1.1, 0, Math.PI * 2);
          ctx.arc(cx + 14.7, cy - 14.8, 1.1, 0, Math.PI * 2);
          ctx.fill();
        } else if (ag.accessory === 'CROWN_PIN') {
          ctx.fillStyle = '#fbbf24';
          ctx.beginPath();
          ctx.arc(cx + 5.2, cy - 2.5, 2.0, 0, Math.PI * 2);
          ctx.fill();
        } else if (ag.accessory === 'SAFETY_BADGE') {
          ctx.fillStyle = '#10b981';
          ctx.beginPath();
          ctx.arc(cx + 5.2, cy - 2.5, 2.0, 0, Math.PI * 2);
          ctx.fill();
        }

        // 사옥 테마별 캐릭터 코스튬/장비 동기화 오버레이
        const activeTheme = officeThemeRef.current;
        if (activeTheme === 'space') {
          // 반투명 시안 스마트 바이저 + 궤도 사령부 숄더 견장
          ctx.fillStyle = 'rgba(34, 211, 238, 0.34)';
          ctx.beginPath();
          ctx.roundRect(cx - 9.5 + eyeShiftX, cy - 17.0, 19.0, 5.2, 2.2);
          ctx.fill();
          ctx.strokeStyle = '#22d3ee';
          ctx.lineWidth = 1.1;
          ctx.stroke();

          ctx.fillStyle = '#e2e8f0';
          ctx.fillRect(cx - 12.2, cy - 5.2, 4.4, 2.6);
          ctx.fillRect(cx + 7.8, cy - 5.2, 4.4, 2.6);
          ctx.fillStyle = '#06b6d4';
          ctx.fillRect(cx - 11.4, cy - 4.7, 2.8, 1.4);
          ctx.fillRect(cx + 8.6, cy - 4.7, 2.8, 1.4);
        } else if (activeTheme === 'factory') {
          // 스마트팩토리: QA팀 안전 헬멧 + 전 직원 클린룸 형광 안전 칼라 스트라이프
          if (ag.roomKey === 'QA_ROOM') {
            ctx.fillStyle = '#f8fafc';
            ctx.beginPath();
            ctx.arc(cx, cy - 22.8, 10.6, Math.PI, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#10b981';
            ctx.fillRect(cx - 11.5, cy - 23.2, 23, 2.4);
            ctx.strokeStyle = '#065f46';
            ctx.lineWidth = 1;
            ctx.strokeRect(cx - 11.5, cy - 23.2, 23, 2.4);
          }
          ctx.fillStyle = '#a3e635';
          ctx.fillRect(cx - 7.5, cy - 5.2, 2.5, 4.2);
          ctx.fillRect(cx + 5.0, cy - 5.2, 2.5, 4.2);
        } else if (activeTheme === 'quantum') {
          // 퀀텀 AI 코어: 네온 퍼플/골드 사이버네틱 이어셋 + 양자 코어 배지
          ctx.strokeStyle = '#c084fc';
          ctx.lineWidth = 1.6;
          ctx.beginPath();
          ctx.arc(cx - 12.6, cy - 15.2, 2.8, 0, Math.PI * 2);
          ctx.stroke();
          ctx.fillStyle = '#fbbf24';
          ctx.beginPath();
          ctx.arc(cx - 12.6, cy - 15.2, 1.3, 0, Math.PI * 2);
          ctx.arc(cx + 12.6, cy - 15.2, 1.3, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = '#f59e0b';
          ctx.lineWidth = 1.1;
          ctx.beginPath();
          ctx.arc(cx + 12.6, cy - 15.2, 2.8, 0, Math.PI * 2);
          ctx.stroke();
        }
      }

      const inMeetingRoom = detectRoomByPoint(ag.x, ag.y) === 'MEETING_ROOM' && !isWalking;
      const headingToMeeting =
        isWalking && ag.waypoints.some((wp) => wp.x >= 390 && wp.x <= 730 && wp.y >= 338);

      if (ag.carryingBook || headingToMeeting) {
        // 보고서 바인더 / 디지털 태블릿 운반 연출
        ctx.fillStyle = headingToMeeting ? '#1e3a8a' : '#fef08a';
        ctx.fillRect(cx + 8, cy - 7, 11, 13);
        ctx.strokeStyle = headingToMeeting ? '#60a5fa' : '#ca8a04';
        ctx.lineWidth = 1.4;
        ctx.strokeRect(cx + 8, cy - 7, 11, 13);
        if (headingToMeeting) {
          ctx.fillStyle = '#fbbf24';
          ctx.fillRect(cx + 10.5, cy - 4, 6, 2);
          ctx.fillStyle = '#e2e8f0';
          ctx.fillRect(cx + 10.5, cy - 0.5, 6, 1.5);
        }
      } else if (inMeetingRoom && ag.isSelectedTeam && ag.role !== 'CEO') {
        // 회의실 착석 시 브리핑 태블릿/서류 펼침 연출
        ctx.fillStyle = '#0f172a';
        ctx.beginPath();
        ctx.roundRect(cx - 8, cy + 5, 16, 8, 2);
        ctx.fill();
        ctx.fillStyle = '#38bdf8';
        ctx.fillRect(cx - 6, cy + 6.5, 12, 5);
      }

      ctx.restore();
    };

    // [초선명 HiDPI 2x Super-sampling 슬림 1줄 네임태그 & 단일 발언자 브리핑 토스트 시스템]
    const drawStaffOverlay = (
      ctx: CanvasRenderingContext2D,
      ag: OfficeStaff,
      isWalking: boolean,
      isWorkingDesk: boolean
    ) => {
      const cx = Math.round(ag.x);
      const cy = Math.round(ag.y);
      const isInMeeting = detectRoomByPoint(ag.x, ag.y) === 'MEETING_ROOM' && !isWalking;

      // 1) 신영호 대표 (CEO): 컴팩트 1줄 슬림 배지 (높이 18px)
      if (ag.role === 'CEO') {
        const capW = 104;
        const capH = 18;
        const capX = Math.round(cx - capW / 2);
        const labelY = Math.round(cy + 14);

        ctx.save();
        ctx.shadowColor = 'rgba(0, 0, 0, 0.72)';
        ctx.shadowBlur = 5;
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 1.5;

        ctx.fillStyle = '#090d16';
        ctx.beginPath();
        ctx.roundRect(capX, labelY, capW, capH, 9);
        ctx.fill();

        ctx.shadowBlur = 0;
        ctx.shadowColor = 'transparent';
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 0;
        ctx.strokeStyle = reportUnlockedRef.current ? '#fbbf24' : '#cbd5e1';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.fillStyle = reportUnlockedRef.current ? '#fef08a' : '#ffffff';
        ctx.font = `800 10.5px ${FONT_FAMILY}`;
        ctx.textAlign = 'center';
        ctx.fillText(`👑 ${ag.name}`, cx, Math.round(labelY + 12.5));
        ctx.restore();
        return;
      }

      // 2) 대기(비활성) 부서원: 슬림 1줄 배지 ("● 윤지아", 높이 18px)
      if (!ag.isSelectedTeam) {
        const shortName = ag.name.split(' ')[0];
        const pillW = 78;
        const pillH = 18;
        const pillX = Math.round(cx - pillW / 2);
        const labelY = Math.round(cy + 20);

        ctx.save();
        ctx.shadowColor = 'rgba(0, 0, 0, 0.6)';
        ctx.shadowBlur = 4;
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 1;

        ctx.fillStyle = 'rgba(11, 17, 32, 0.92)';
        ctx.beginPath();
        ctx.roundRect(pillX, labelY, pillW, pillH, 9);
        ctx.fill();

        ctx.shadowBlur = 0;
        ctx.shadowColor = 'transparent';
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 0;
        ctx.strokeStyle = 'rgba(148, 163, 184, 0.7)';
        ctx.lineWidth = 1.2;
        ctx.stroke();

        ctx.fillStyle = '#94a3b8';
        ctx.beginPath();
        ctx.arc(Math.round(pillX + 12), Math.round(labelY + 9), 2.8, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#e2e8f0';
        ctx.font = `700 10.5px ${FONT_FAMILY}`;
        ctx.textAlign = 'center';
        ctx.fillText(shortName, Math.round(cx + 4), Math.round(labelY + 12.5));
        ctx.restore();
        return;
      }

      // 3) 전담 투입 부서원: 슬림 1줄 배지 (높이 18px, 초록 상태점 + 전체 성명/직책 + 하단 진행선)
      const isReject = ag.taskLabel.includes('반려');
      const capW = 104;
      const capH = 18;
      const capX = Math.round(cx - capW / 2);
      const labelY = isInMeeting ? Math.round(cy + 15) : Math.round(cy + 20);
      const borderColor = isReject ? '#fb7185' : ag.isShelfMode ? '#fbbf24' : isWorkingDesk ? '#38bdf8' : '#10b981';

      ctx.save();
      ctx.shadowColor = 'rgba(0, 0, 0, 0.72)';
      ctx.shadowBlur = 5;
      ctx.shadowOffsetX = 0;
      ctx.shadowOffsetY = 1.5;

      ctx.fillStyle = '#090d16';
      ctx.beginPath();
      ctx.roundRect(capX, labelY, capW, capH, 9);
      ctx.fill();

      ctx.shadowBlur = 0;
      ctx.shadowColor = 'transparent';
      ctx.shadowOffsetX = 0;
      ctx.shadowOffsetY = 0;
      ctx.strokeStyle = borderColor;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (ag.progress > 0 && ag.progress < 100) {
        ctx.fillStyle = isReject ? '#f43f5e' : '#38bdf8';
        ctx.fillRect(Math.round(capX + 9), Math.round(labelY + capH - 2.5), Math.round(((capW - 18) * ag.progress) / 100), 1.8);
      }

      ctx.fillStyle = isReject ? '#fb7185' : '#10b981';
      ctx.beginPath();
      ctx.arc(Math.round(capX + 11), Math.round(labelY + 9), 3.0, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.font = `800 10.5px ${FONT_FAMILY}`;
      ctx.textAlign = 'center';
      ctx.fillText(ag.name, Math.round(cx + 5), Math.round(labelY + 12.5));
      ctx.restore();
    };

    // [단일 발언자(Single Active Speaker) 회의실 상단 고정 브리핑 토스트 배너]
    const drawSingleSpeakerBanner = (
      ctx: CanvasRenderingContext2D,
      staffList: OfficeStaff[],
      walkingMap: Record<string, boolean>
    ) => {
      const roleWeight = (role: OfficeStaff['role']) =>
        role === 'CEO' ? 3 : role === 'SUPERVISOR' ? 2 : role === 'WORKER1' ? 1 : 0;

      const spokenCandidates = staffList.filter((ag) => ag.isSelectedTeam && Boolean(ag.activeBubble));
      if (spokenCandidates.length === 0) return;

      const stationaryCandidates = spokenCandidates.filter((ag) => !walkingMap[ag.id]);
      const pool = stationaryCandidates.length > 0 ? stationaryCandidates : spokenCandidates;

      const activeSpeaker = pool
        .slice()
        .sort((a, b) => {
          const timeBucketA = Math.floor(a.lastSpokenFrame / 18);
          const timeBucketB = Math.floor(b.lastSpokenFrame / 18);
          if (timeBucketA !== timeBucketB) return timeBucketB - timeBucketA;
          return roleWeight(b.role) - roleWeight(a.role);
        })[0];

      if (!activeSpeaker) return;

      activeSpeaker.bubbleAnim = Math.min(1, activeSpeaker.bubbleAnim + 0.09);
      const bScale = activeSpeaker.bubbleAnim >= 0.99 ? 1 : easeOutBack(activeSpeaker.bubbleAnim);

      const isReject = activeSpeaker.taskLabel.includes('반려');
      const bw = 310;
      const bh = 34;
      const bx = Math.round(558 - bw / 2);
      const by = Math.round(368 - bh / 2);
      const centerBx = Math.round(bx + bw / 2);
      const centerBy = Math.round(by + bh / 2);

      ctx.save();
      if (bScale !== 1) {
        ctx.translate(centerBx, centerBy);
        ctx.scale(bScale, bScale);
        ctx.translate(-centerBx, -centerBy);
      }

      ctx.shadowColor = 'rgba(2, 6, 23, 0.55)';
      ctx.shadowBlur = 8;
      ctx.shadowOffsetX = 0;
      ctx.shadowOffsetY = 2;

      ctx.fillStyle = isReject ? '#881337' : activeSpeaker.isShelfMode ? '#fefce8' : '#f8fafc';
      ctx.beginPath();
      ctx.roundRect(bx, by, bw, bh, 10);
      ctx.fill();

      ctx.shadowBlur = 0;
      ctx.shadowColor = 'transparent';
      ctx.shadowOffsetX = 0;
      ctx.shadowOffsetY = 0;

      ctx.strokeStyle = isReject ? '#fda4af' : activeSpeaker.isShelfMode ? '#b45309' : '#0f172a';
      ctx.lineWidth = 1.8;
      ctx.stroke();

      // 좌측 발언자 뱃지
      const badgeLabel = activeSpeaker.role === 'CEO' ? `👑 ${activeSpeaker.name}` : activeSpeaker.name;
      const badgeW = 84;
      ctx.fillStyle = isReject ? '#be123c' : activeSpeaker.role === 'CEO' ? '#0f172a' : '#065f46';
      ctx.beginPath();
      ctx.roundRect(bx + 6, by + 6, badgeW, 22, 6);
      ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.font = `800 10px ${FONT_FAMILY}`;
      ctx.textAlign = 'center';
      ctx.fillText(badgeLabel, Math.round(bx + 6 + badgeW / 2), Math.round(by + 20.5));

      ctx.fillStyle = isReject ? '#ffffff' : '#0f172a';
      ctx.font = `800 11px ${FONT_FAMILY}`;
      ctx.textAlign = 'left';
      const cleanMsg = activeSpeaker.activeBubble.slice(0, 29);
      ctx.fillText(cleanMsg, Math.round(bx + 96), Math.round(by + 21));
      ctx.restore();
    };

    // 하이테크 3대 테마(우주 정거장 / 스마트팩토리 / 퀀텀 AI 코어)용 라이브 마이크로 VFX (바닥 패치·가림 현상 ZERO)
    const drawThemedLiveVfx = (
      ctx: CanvasRenderingContext2D,
      activeTheme: OfficeThemeId,
      f: number
    ) => {
      if (activeTheme === 'classic') return;

      ctx.save();
      if (activeTheme === 'space') {
        // 우주 정거장: 복도 광섬유 네온 펄스 + 회의실 은하 홀로그램 링 + 외곽 성운 반짝임
        const scanX = ((f * 3.2) % (CW - 80)) + 40;
        ctx.strokeStyle = 'rgba(34, 211, 238, 0.34)';
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.moveTo(28, CORRIDOR_Y - 1);
        ctx.lineTo(CW - 28, CORRIDOR_Y - 1);
        ctx.stroke();

        const pulseGrad = ctx.createLinearGradient(scanX - 45, 0, scanX + 45, 0);
        pulseGrad.addColorStop(0, 'rgba(34, 211, 238, 0)');
        pulseGrad.addColorStop(0.5, 'rgba(103, 232, 249, 0.95)');
        pulseGrad.addColorStop(1, 'rgba(34, 211, 238, 0)');
        ctx.strokeStyle = pulseGrad;
        ctx.lineWidth = 2.6;
        ctx.beginPath();
        ctx.moveTo(scanX - 45, CORRIDOR_Y - 1);
        ctx.lineTo(scanX + 45, CORRIDOR_Y - 1);
        ctx.stroke();

        // 중앙 회의실 은하 홀로그램 투영 링
        const rot = f * 0.025;
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.45)';
        ctx.lineWidth = 1.4;
        ctx.setLineDash([8, 6]);
        ctx.lineDashOffset = -f * 0.5;
        ctx.beginPath();
        ctx.ellipse(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 70, 38, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);

        // 미세 별빛 반짝임 (상단 관측창/모서리 영역)
        for (let i = 0; i < 8; i++) {
          const sx = 88 + i * 134;
          const sy = 16 + ((i * 19) % 18);
          const alpha = 0.25 + 0.55 * Math.abs(Math.sin(f * 0.05 + i + rot));
          ctx.fillStyle = `rgba(186, 230, 253, ${alpha.toFixed(2)})`;
          ctx.beginPath();
          ctx.arc(sx, sy, 1.4, 0, Math.PI * 2);
          ctx.fill();
        }
      } else if (activeTheme === 'factory') {
        // 스마트팩토리: 에메랄드/시안 안전 동선 펄스 + QA/RA 실 미세 로봇 암 & 컨베이어 텔레메트리
        const ledShift = (f * 2.4) % 40;
        ctx.strokeStyle = 'rgba(16, 185, 129, 0.32)';
        ctx.lineWidth = 1.8;
        ctx.setLineDash([12, 12]);
        ctx.lineDashOffset = -ledShift;
        ctx.beginPath();
        ctx.moveTo(32, CORRIDOR_Y);
        ctx.lineTo(CW - 32, CORRIDOR_Y);
        ctx.stroke();
        ctx.setLineDash([]);

        // QA_ROOM 상단 우측(로봇 암 관절 마이크로 모션)
        const qa = ROOMS.QA_ROOM;
        const armX = qa.rx + qa.rw - 56;
        const armY = qa.ry + 54;
        const swing = Math.sin(f * 0.06) * 0.35;
        ctx.save();
        ctx.translate(armX, armY);
        ctx.fillStyle = '#334155';
        ctx.beginPath();
        ctx.arc(0, 0, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.rotate(-0.4 + swing);
        ctx.fillStyle = '#facc15';
        ctx.fillRect(-2, -16, 4, 16);
        ctx.translate(0, -16);
        ctx.rotate(0.75 - swing * 0.6);
        ctx.fillStyle = '#10b981';
        ctx.fillRect(-1.5, -12, 3, 12);
        ctx.fillStyle = '#34d399';
        ctx.beginPath();
        ctx.arc(0, -12, 2.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      } else if (activeTheme === 'quantum') {
        // 퀀텀 AI 코어: 퍼플/골드 양자 회로 노드 + 회의실 부유 와이어프레임 큐브
        ctx.strokeStyle = 'rgba(168, 85, 247, 0.35)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(30, CORRIDOR_Y);
        ctx.lineTo(CW - 30, CORRIDOR_Y);
        ctx.stroke();

        const nodeXs = [190, 375, 560, 745, 930];
        nodeXs.forEach((nx, i) => {
          const glow = 0.4 + 0.5 * Math.sin(f * 0.08 + i * 1.1);
          ctx.fillStyle = `rgba(251, 191, 36, ${glow.toFixed(2)})`;
          ctx.beginPath();
          ctx.arc(nx, CORRIDOR_Y, 2.6, 0, Math.PI * 2);
          ctx.fill();
        });

        // 중앙 회의실 양자 공명 링 & 회전 다이아몬드 큐브
        const angle = f * 0.03;
        const qx = MEETING_TABLE_CENTER.x;
        const qy = MEETING_TABLE_CENTER.y - 2 + Math.sin(f * 0.07) * 2.5;
        const rx = Math.cos(angle) * 11;
        ctx.strokeStyle = 'rgba(251, 191, 36, 0.72)';
        ctx.lineWidth = 1.3;
        ctx.beginPath();
        ctx.moveTo(qx, qy - 11);
        ctx.lineTo(qx + rx, qy);
        ctx.lineTo(qx, qy + 11);
        ctx.lineTo(qx - rx, qy);
        ctx.closePath();
        ctx.stroke();
      }
      ctx.restore();
    };

    // 4대 테마 고밀도 프로시저럴 폴백 엔진 (이미지 미로드/실패 시에도 정확한 3x2 그리드 + 테마별 사옥 완벽 구현)
    const drawThemedProceduralScene = (
      ctx: CanvasRenderingContext2D,
      activeTheme: OfficeThemeId,
      staffList: OfficeStaff[],
      f: number
    ) => {
      const tileA =
        activeTheme === 'space'
          ? '#0b1526'
          : activeTheme === 'factory'
          ? '#182230'
          : activeTheme === 'quantum'
          ? '#070514'
          : '#334155';
      const tileB =
        activeTheme === 'space'
          ? '#0f1e36'
          : activeTheme === 'factory'
          ? '#1f2c3d'
          : activeTheme === 'quantum'
          ? '#110a24'
          : '#293548';

      for (let y = 0; y < CH; y += 24) {
        for (let x = 0; x < CW; x += 24) {
          ctx.fillStyle = (Math.floor(x / 24) + Math.floor(y / 24)) % 2 === 0 ? tileA : tileB;
          ctx.fillRect(x, y, 24, 24);
        }
      }

      // 복도 배경 및 테마별 가이드 라인
      ctx.fillStyle =
        activeTheme === 'quantum'
          ? 'rgba(24, 10, 48, 0.85)'
          : activeTheme === 'space'
          ? 'rgba(8, 30, 54, 0.82)'
          : 'rgba(15, 23, 42, 0.72)';
      ctx.fillRect(20, CORRIDOR_Y - 20, CW - 40, 40);
      ctx.strokeStyle =
        activeTheme === 'space'
          ? 'rgba(34, 211, 238, 0.5)'
          : activeTheme === 'factory'
          ? 'rgba(16, 185, 129, 0.45)'
          : activeTheme === 'quantum'
          ? 'rgba(192, 132, 252, 0.5)'
          : 'rgba(56, 189, 248, 0.25)';
      ctx.lineWidth = 1.2;
      ctx.strokeRect(20, CORRIDOR_Y - 20, CW - 40, 40);

      if (activeTheme === 'classic') {
        drawLushPotPlant(ctx, 375, CORRIDOR_Y - 12, f, 1.0);
        drawLushPotPlant(ctx, 745, CORRIDOR_Y - 12, f, 1.0);
        drawLushPotPlant(ctx, 34, CORRIDOR_Y - 12, f, 0.9);
        drawLushPotPlant(ctx, 1086, CORRIDOR_Y - 12, f, 0.9);
      }

      (Object.entries(ROOMS) as Array<[DeptRoomKey, typeof ROOMS.HR_ROOM]>).forEach(([rKey, r]) => {
        const isRoomActive = staffList.some((s) => s.roomKey === rKey && s.isSelectedTeam && rKey !== 'MEETING_ROOM');

        if (activeTheme === 'classic') {
          drawRoomFloor(ctx, r.rx, r.ry, r.rw, r.rh, r.floorType, r.badgeColor, isRoomActive, f);
          if (r.ry < 100 && rKey !== 'QA_ROOM') {
            drawWindowAndSunbeam(ctx, r.rx + 145, r.ry + 2, f);
            drawWindowAndSunbeam(ctx, r.rx + 230, r.ry + 2, f);
          }
        } else {
          // 하이테크 방 바닥 타일 + 메탈릭 상단 벽면 + 관측창/모니터
          const roomBg =
            activeTheme === 'space'
              ? rKey === 'MEETING_ROOM'
                ? '#0d2238'
                : '#10223a'
              : activeTheme === 'factory'
              ? rKey === 'QA_ROOM'
                ? '#1e293b'
                : '#172332'
              : rKey === 'MEETING_ROOM'
              ? '#1b0d33'
              : '#120b24';
          ctx.fillStyle = roomBg;
          ctx.fillRect(r.rx, r.ry, r.rw, r.rh);

          // 미세 그리드 라인
          ctx.strokeStyle =
            activeTheme === 'space'
              ? 'rgba(56, 189, 248, 0.14)'
              : activeTheme === 'factory'
              ? 'rgba(16, 185, 129, 0.14)'
              : 'rgba(168, 85, 247, 0.16)';
          ctx.lineWidth = 1;
          for (let gx = r.rx + 28; gx < r.rx + r.rw; gx += 28) {
            ctx.beginPath();
            ctx.moveTo(gx, r.ry + 28);
            ctx.lineTo(gx, r.ry + r.rh);
            ctx.stroke();
          }

          // 상단 메탈릭 벽면
          ctx.fillStyle = activeTheme === 'quantum' ? '#1e1038' : '#0f172a';
          ctx.fillRect(r.rx, r.ry, r.rw, 28);

          // 우주 테마: 상단 방 성운 관측창
          if (activeTheme === 'space' && r.ry < 100) {
            ctx.fillStyle = '#020617';
            ctx.fillRect(r.rx + 150, r.ry + 5, 150, 20);
            ctx.strokeStyle = '#22d3ee';
            ctx.lineWidth = 1;
            ctx.strokeRect(r.rx + 150, r.ry + 5, 150, 20);
            ctx.fillStyle = '#e0f2fe';
            for (let s = 0; s < 5; s++) {
              ctx.fillRect(r.rx + 162 + s * 28, r.ry + 10 + (s % 2) * 6, 2, 2);
            }
          }
          // 스마트팩토리: 벽면 디지털 트윈 KPI 패널
          if (activeTheme === 'factory') {
            ctx.fillStyle = '#052e16';
            ctx.fillRect(r.rx + 155, r.ry + 6, 95, 16);
            ctx.strokeStyle = '#10b981';
            ctx.lineWidth = 1;
            ctx.strokeRect(r.rx + 155, r.ry + 6, 95, 16);
            ctx.fillStyle = '#34d399';
            ctx.fillRect(r.rx + 162, r.ry + 11, 25 + (f % 18), 4);
          }
        }

        drawMetalMoldingFrame(ctx, r.rx, r.ry, r.rw, r.rh, r.badgeColor, isRoomActive, r.doorX, r.doorY);

        if (rKey !== 'MEETING_ROOM') {
          const isShelfGlowing =
            isRoomActive &&
            (archiveHitFlashRef.current > 0 ||
              staffList.some((s) => s.roomKey === rKey && Math.hypot(s.x - r.shelf.x, s.y - r.shelf.y) < 35));
          drawBookshelf(ctx, r.shelf.x, r.shelf.y, isShelfGlowing, f, false);
          drawBookshelf(ctx, r.shelf.x + 88, r.shelf.y, false, f, false);
          if (activeTheme === 'classic') {
            drawOfficeProps(ctx, r.rx, r.ry, r.rw, r.rh, rKey, f);
          }
        } else {
          // 테마별 회의실 카펫 & 테이블
          const carpetColor =
            activeTheme === 'space'
              ? 'rgba(14, 116, 144, 0.25)'
              : activeTheme === 'factory'
              ? 'rgba(6, 95, 70, 0.25)'
              : activeTheme === 'quantum'
              ? 'rgba(126, 34, 206, 0.28)'
              : '#fef3c7';
          const carpetBorder =
            activeTheme === 'space'
              ? '#22d3ee'
              : activeTheme === 'factory'
              ? '#10b981'
              : activeTheme === 'quantum'
              ? '#fbbf24'
              : '#d97706';

          ctx.fillStyle = carpetColor;
          ctx.beginPath();
          ctx.roundRect(r.rx + 46, r.ry + 66, r.rw - 92, r.rh - 98, 8);
          ctx.fill();
          ctx.strokeStyle = carpetBorder;
          ctx.lineWidth = 2;
          ctx.strokeRect(r.rx + 50, r.ry + 70, r.rw - 100, r.rh - 106);

          ctx.fillStyle =
            activeTheme === 'space'
              ? '#083344'
              : activeTheme === 'factory'
              ? '#1e293b'
              : activeTheme === 'quantum'
              ? '#2e1065'
              : '#78350f';
          ctx.beginPath();
          ctx.ellipse(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 66, 36, 0, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle =
            activeTheme === 'space'
              ? '#0e7490'
              : activeTheme === 'factory'
              ? '#065f46'
              : activeTheme === 'quantum'
              ? '#6b21a8'
              : '#b45309';
          ctx.beginPath();
          ctx.ellipse(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 56, 28, 0, 0, Math.PI * 2);
          ctx.fill();
        }
      });

      drawThemedLiveVfx(ctx, activeTheme, f);
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

      // 2x Super-sampling (2240x1280 물리 픽셀 스케일링) 적용
      ctx.setTransform(SUPER_SAMPLE, 0, 0, SUPER_SAMPLE, 0, 0);
      ctx.clearRect(0, 0, CW, CH);

      const activeTheme = officeThemeRef.current;
      const activeImg = themeImagesRef.current[activeTheme];
      const bgLoaded = Boolean(themeLoadedRef.current[activeTheme] && activeImg);
      const staffList = Object.values(staffRef.current);

      if (bgLoaded && activeImg) {
        ctx.save();
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(activeImg, 0, 0, CW, CH);
        ctx.restore();

        (Object.entries(ROOMS) as Array<[DeptRoomKey, typeof ROOMS.HR_ROOM]>).forEach(([rKey, r]) => {
          const isRoomActive = staffList.some((s) => s.roomKey === rKey && s.isSelectedTeam && rKey !== 'MEETING_ROOM');
          drawHybridRoomSpotlight(ctx, r.rx, r.ry, r.rw, r.rh, r.badgeColor, isRoomActive, rKey, f);

          if (rKey !== 'MEETING_ROOM') {
            const isShelfGlowing =
              isRoomActive &&
              (archiveHitFlashRef.current > 0 ||
                staffList.some((s) => s.roomKey === rKey && Math.hypot(s.x - r.shelf.x, s.y - r.shelf.y) < 35));
            drawBookshelf(ctx, r.shelf.x, r.shelf.y, isShelfGlowing, f, true);

            // 클래식 오피스(/office_bg.png)에서만 책상 마스킹 인페인트 적용 (신규 하이테크 바닥 보호)
            if (activeTheme === 'classic') {
              r.desks.forEach((d) => {
                const isOccupiedAtDesk = staffList.some(
                  (s) => Math.hypot(s.x - d.x, s.y - d.y) < 16
                );
                drawDeskInpaintMask(ctx, d.x, d.y, rKey, isOccupiedAtDesk);
              });
            }
          } else {
            // 클래식 오피스에서만 대표 자리 마스킹 인페인트 적용
            if (activeTheme === 'classic') {
              drawCeoInpaintMask(ctx);
            }

            const tableGlow = ctx.createRadialGradient(
              MEETING_TABLE_CENTER.x,
              MEETING_TABLE_CENTER.y,
              8,
              MEETING_TABLE_CENTER.x,
              MEETING_TABLE_CENTER.y,
              88
            );
            const glowRgba =
              activeTheme === 'space'
                ? 'rgba(34, 211, 238, 0.24)'
                : activeTheme === 'factory'
                ? 'rgba(16, 185, 129, 0.22)'
                : activeTheme === 'quantum'
                ? 'rgba(192, 132, 252, 0.26)'
                : 'rgba(251, 191, 36, 0.22)';
            tableGlow.addColorStop(0, glowRgba);
            tableGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');
            ctx.fillStyle = tableGlow;
            ctx.beginPath();
            ctx.arc(MEETING_TABLE_CENTER.x, MEETING_TABLE_CENTER.y, 88, 0, Math.PI * 2);
            ctx.fill();

            if (ceoWaveFlashRef.current > 0) {
              const radius = 50 + ((120 - ceoWaveFlashRef.current) % 45) * 2.2;
              ctx.strokeStyle = 'rgba(56, 189, 248, 0.78)';
              ctx.lineWidth = 3;
              ctx.beginPath();
              ctx.arc(MEETING_SEATS.CEO.x, MEETING_SEATS.CEO.y, radius, 0, Math.PI * 2);
              ctx.stroke();
            }
          }
        });

        drawThemedLiveVfx(ctx, activeTheme, f);
      } else {
        drawThemedProceduralScene(ctx, activeTheme, staffList, f);
      }

      const walkingMap: Record<string, boolean> = {};
      const workingDeskMap: Record<string, boolean> = {};

      staffList.forEach((ag) => {
        let walking = false;

        if (ag.isSelectedTeam && ag.waypoints.length === 0 && ag.workTimer <= 0 && ag.stageQueue.length > 0) {
          const nextSt = ag.stageQueue.shift()!;
          ag.taskLabel = nextSt.label;
          ag.activeBubble = nextSt.bubble;
          ag.bubbleAnim = 0;
          ag.lastSpokenFrame = f;
          ag.workTimer = nextSt.workFrames;
          ag.maxWorkTimer = Math.max(1, nextSt.workFrames);
          ag.progress = nextSt.workFrames > 0 ? 15 : 100;
          if (nextSt.isShelfLookup) {
            ag.carryingBook = true;
          }
          ag.stuckFrames = 0;
          ag.lastWaypointDist = Infinity;
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

          if (ag.lastWaypointDist - dist < 0.15) {
            ag.stuckFrames += 1;
          } else {
            ag.stuckFrames = 0;
          }
          ag.lastWaypointDist = dist;

          if (Math.abs(dx) > Math.abs(dy)) {
            ag.facing = dx < 0 ? 'LEFT' : 'RIGHT';
          } else {
            ag.facing = dy < 0 ? 'UP' : 'DOWN';
          }

          if (dist <= Math.max(2.2, desiredSpeed + 0.6) || ag.stuckFrames >= 45) {
            ag.x = nextPt.x;
            ag.y = nextPt.y;
            ag.vx = 0;
            ag.vy = 0;
            ag.stuckFrames = 0;
            ag.lastWaypointDist = Infinity;
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
            ag.vx = ag.vx * 0.22 + targetVx * 0.78;
            ag.vy = ag.vy * 0.22 + targetVy * 0.78;
            const clamped = clampWalkablePosition(ag.x + ag.vx, ag.y + ag.vy);
            ag.x = clamped.x;
            ag.y = clamped.y;
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
          drawDesk(ctx, d.x, d.y, busy, isSelectedRoom, f, bgLoaded, activeTheme);
        });

        if (!bgLoaded) {
          ctx.fillStyle = 'rgba(9, 13, 22, 0.95)';
          ctx.beginPath();
          ctx.roundRect(r.rx + 10, r.ry + 8, 138, 23, 6);
          ctx.fill();
          ctx.strokeStyle = r.badgeColor;
          ctx.lineWidth = 1.6;
          ctx.stroke();
          ctx.fillStyle = '#ffffff';
          ctx.font = `800 11.5px ${FONT_FAMILY}`;
          ctx.textAlign = 'center';
          ctx.fillText(r.title, r.rx + 79, r.ry + 23.5);
        }
      });

      particlesRef.current = particlesRef.current.filter((pt) => pt.life > 0);
      particlesRef.current.forEach((pt) => {
        pt.x += pt.vx;
        pt.y += pt.vy;
        pt.life -= 1;
        ctx.globalAlpha = Math.max(0, pt.life / pt.maxLife);
        if (pt.text) {
          ctx.fillStyle = pt.color;
          ctx.font = `800 11px ${FONT_FAMILY}`;
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
        const bannerScale = reportBannerAnimRef.current >= 0.99 ? 1 : easeOutBack(reportBannerAnimRef.current);
        const bounceDoc = Math.round(Math.sin(f * 0.12) * 2.5);
        const tx = Math.round(MEETING_TABLE_CENTER.x);
        const ty = Math.round(MEETING_TABLE_CENTER.y + bounceDoc);

        ctx.save();
        if (bannerScale !== 1) {
          ctx.translate(tx, ty);
          ctx.scale(bannerScale, bannerScale);
          ctx.translate(-tx, -ty);
        }

        const docGlow = ctx.createRadialGradient(tx, MEETING_TABLE_CENTER.y, 4, tx, MEETING_TABLE_CENTER.y, 34);
        if (f % 30 < 15) {
          docGlow.addColorStop(0, 'rgba(251, 191, 36, 0.72)');
          docGlow.addColorStop(1, 'rgba(251, 191, 36, 0)');
        } else {
          docGlow.addColorStop(0, 'rgba(16, 185, 129, 0.68)');
          docGlow.addColorStop(1, 'rgba(16, 185, 129, 0)');
        }
        ctx.fillStyle = docGlow;
        ctx.beginPath();
        ctx.arc(tx, MEETING_TABLE_CENTER.y, 34, 0, Math.PI * 2);
        ctx.fill();

        // 테이블 정중앙 고급 골드 결재판 아이콘 (24x28 컴팩트 벡터 렌더)
        ctx.fillStyle = '#0f172a';
        ctx.beginPath();
        ctx.roundRect(Math.round(tx - 12), Math.round(ty - 14), 24, 28, 4);
        ctx.fill();
        ctx.strokeStyle = '#fbbf24';
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.fillStyle = '#fffbeb';
        ctx.beginPath();
        ctx.roundRect(Math.round(tx - 9), Math.round(ty - 9), 18, 20, 2);
        ctx.fill();

        // 상단 골드 클립 바
        ctx.fillStyle = '#f59e0b';
        ctx.beginPath();
        ctx.roundRect(Math.round(tx - 5), Math.round(ty - 15), 10, 5, 2);
        ctx.fill();

        // 본문 미니 문서 라인 & 에메랄드 직인 도장
        ctx.fillStyle = '#334155';
        ctx.fillRect(Math.round(tx - 6), Math.round(ty - 5), 12, 1.8);
        ctx.fillRect(Math.round(tx - 6), Math.round(ty - 1), 9, 1.8);
        ctx.fillRect(Math.round(tx - 6), Math.round(ty + 3), 11, 1.8);

        ctx.fillStyle = '#10b981';
        ctx.beginPath();
        ctx.arc(Math.round(tx + 4), Math.round(ty + 7.5), 3.2, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();
      }

      staffList
        .slice()
        .sort((a, b) => Number(a.isSelectedTeam) - Number(b.isSelectedTeam))
        .forEach((ag) => {
          drawStaffOverlay(ctx, ag, walkingMap[ag.id], Boolean(workingDeskMap[ag.id]));
        });

      // 화면 전체에서 단 1명의 활성 발언자 말풍선만 회의실 상단 여백(558, 368)에 깔끔하게 표시
      drawSingleSpeakerBanner(ctx, staffList, walkingMap);

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, []);

  return (
    <div className="relative w-full h-full flex flex-col bg-slate-950 overflow-hidden select-none">
      <div className="shrink-0 px-5 py-2 bg-slate-900/90 backdrop-blur-md border-b border-slate-800/80 flex items-center justify-between text-xs shadow-lg">
        <div className="flex items-center gap-3">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
          </span>
          <span className="font-bold text-slate-200 tracking-tight">{phaseBanner}</span>
          {reportUnlocked && (
            <button
              onClick={onOpenReportModal}
              className="px-3 py-1 text-[11px] font-extrabold bg-emerald-950/90 hover:bg-emerald-900 text-emerald-200 border border-emerald-500/60 rounded-lg shadow-[0_0_12px_rgba(16,185,129,0.25)] hover:scale-105 active:scale-95 transition-all duration-200 antialiased"
            >
              📋 보고서 열람
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
              className={`px-2.5 py-1 rounded-lg text-[10px] font-bold border backdrop-blur-md transition-all duration-200 ${
                speedMult === opt.val
                  ? 'bg-emerald-600/90 border-emerald-400/80 text-white shadow-[0_0_12px_rgba(16,185,129,0.35)]'
                  : 'bg-slate-950/75 border-slate-800/80 text-slate-400 hover:text-slate-100 hover:border-slate-700 hover:bg-slate-900/90'
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
          width={CW * SUPER_SAMPLE}
          height={CH * SUPER_SAMPLE}
          onClick={(e) => handleCanvasPos(e, true)}
          onMouseMove={(e) => handleCanvasPos(e, false)}
          onMouseLeave={() => setHoveredStaff(null)}
          className={`w-full h-full object-contain rounded-2xl border border-slate-800/80 shadow-[0_0_50px_rgba(0,0,0,0.8)] bg-slate-900 transition-all duration-300 ease-out ${
            isHoveringReport ? 'cursor-pointer ring-2 ring-amber-400/90 shadow-[0_0_35px_rgba(251,191,36,0.3)]' : ''
          }`}
        />

        {hoveredStaff && (
          <div className="absolute bottom-4 right-5 z-30 w-72 p-3.5 rounded-2xl bg-slate-900/90 backdrop-blur-xl border border-emerald-500/40 shadow-[0_8px_32px_rgba(0,0,0,0.65)] pointer-events-none transition-all duration-200">
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
      </div>

      {/* 캔버스 외부 하단 전용 HUD 액션 바 (캔버스 내부 좌석/이름표 겹침 0%) */}
      {reportUnlocked && (
        <div className="shrink-0 px-5 py-2.5 bg-gradient-to-r from-emerald-950/90 via-slate-900/95 to-emerald-950/90 border-t border-emerald-500/40 flex items-center justify-between gap-4 shadow-[0_-8px_28px_rgba(6,78,59,0.35)]">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="shrink-0 px-2.5 py-0.5 rounded-full text-[10.5px] font-extrabold bg-emerald-500/20 text-emerald-300 border border-emerald-400/50">
              결재 완료
            </span>
            <span className="text-xs font-bold text-slate-100 truncate">
              📄 최종 전자결재 보고서 승인 대기 — 클릭하여 인포그래픽 보고서 열람 및 Excel·Word·PDF 다운로드
            </span>
          </div>
          <button
            onClick={() => onOpenReportModal && onOpenReportModal()}
            className="shrink-0 px-4 py-1.5 rounded-xl text-xs font-extrabold bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 shadow-[0_4px_16px_rgba(16,185,129,0.4)] hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 cursor-pointer"
          >
            📋 인포그래픽 보고서 열람 ➔
          </button>
        </div>
      )}
    </div>
  );
}
