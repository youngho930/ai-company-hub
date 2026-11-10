import { AgentEvent } from '@/types/agent';

const makeSoMSvg = (stepTitle: string, boxLabel: string, priceText: string) => {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="380" viewBox="0 0 640 380">
    <rect width="640" height="380" fill="#0f172a"/>
    <rect x="0" y="0" width="640" height="34" fill="#1e293b"/>
    <circle cx="18" cy="17" r="5" fill="#f43f5e"/><circle cx="34" cy="17" r="5" fill="#fbbf24"/><circle cx="50" cy="17" r="5" fill="#10b981"/>
    <text x="75" y="21" fill="#94a3b8" font-family="monospace" font-size="11">https://shopping.target-mall.kr/watch-pro-5</text>
    <text x="24" y="68" fill="#f8fafc" font-family="sans-serif" font-size="15" font-weight="bold">${stepTitle}</text>
    <rect x="24" y="88" width="592" height="48" rx="6" fill="rgba(244,63,94,0.12)" stroke="#f43f5e" stroke-width="2"/>
    <rect x="24" y="70" width="32" height="18" rx="3" fill="#e11d48"/>
    <text x="29" y="83" fill="#ffffff" font-family="monospace" font-size="11" font-weight="bold">#12</text>
    <text x="40" y="117" fill="#e2e8f0" font-family="sans-serif" font-size="13">${boxLabel}</text>
    <rect x="24" y="165" width="290" height="150" rx="8" fill="rgba(244,63,94,0.08)" stroke="#f43f5e" stroke-width="2"/>
    <rect x="24" y="147" width="32" height="18" rx="3" fill="#e11d48"/>
    <text x="29" y="160" fill="#ffffff" font-family="monospace" font-size="11" font-weight="bold">#18</text>
    <text x="42" y="200" fill="#94a3b8" font-family="sans-serif" font-size="12">경쟁사 스마트워치 5세대</text>
    <text x="42" y="240" fill="#34d399" font-family="sans-serif" font-size="21" font-weight="bold">${priceText}</text>
    <text x="42" y="275" fill="#f43f5e" font-family="sans-serif" font-size="11">※ 비회원 쿠폰 팝업 감지됨</text>
  </svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
};

export interface ReplayTeamConfig {
  supId: string;
  supName: string;
  supDept: string;
  w1Id: string;
  w1Name: string;
  w1Dept: string;
  w2Id: string;
  w2Name: string;
  w2Dept: string;
}

export const buildReplayPart1 = (cfg: ReplayTeamConfig): { delayMs: number; event: AgentEvent }[] => {
  const isSingleWorker = cfg.w1Id === cfg.w2Id;
  const workerNodes = isSingleWorker
    ? [{ id: cfg.w1Id, type: 'agentNode', position: { x: 250, y: 300 }, data: { name: cfg.w1Name, dept: cfg.w1Dept, status: 'WORKING' } }]
    : [
        { id: cfg.w1Id, type: 'agentNode', position: { x: 130, y: 300 }, data: { name: cfg.w1Name, dept: cfg.w1Dept, status: 'WORKING' } },
        { id: cfg.w2Id, type: 'agentNode', position: { x: 370, y: 300 }, data: { name: cfg.w2Name, dept: cfg.w2Dept, status: 'IDLE' } },
      ];

  const workerEdges = isSingleWorker
    ? [{ id: 'e-2', source: cfg.supId, target: cfg.w1Id, animated: true }]
    : [
        { id: 'e-2', source: cfg.supId, target: cfg.w1Id, animated: true },
        { id: 'e-3', source: cfg.supId, target: cfg.w2Id, animated: false },
      ];

  return [
    {
      delayMs: 300,
      event: {
        type: 'TEAM_ASSEMBLED', agentId: cfg.supId, agentName: cfg.supName, role: 'SUPERVISOR', timestamp: '14:00:01',
        payload: {
          tokensUsed: 280,
          nodes: [
            { id: 'ceo', type: 'agentNode', position: { x: 250, y: 20 }, data: { name: '신영호 대표 (CEO)', dept: '경영진', status: 'DONE' } },
            { id: cfg.supId, type: 'agentNode', position: { x: 250, y: 150 }, data: { name: cfg.supName, dept: cfg.supDept, status: 'WORKING' } },
            ...workerNodes,
          ],
          edges: [{ id: 'e-1', source: 'ceo', target: cfg.supId, animated: true }, ...workerEdges],
        },
      },
    },
    {
      delayMs: 850,
      event: {
        type: 'MESSAGE', agentId: cfg.supId, agentName: cfg.supName, role: 'SUPERVISOR', timestamp: '14:00:02',
        payload: { status: 'WORKING', text: `🎯 [업무 하달] ${cfg.w1Name}님은 3사 스마트워치 정가·쿠폰가를 수집하고, ${cfg.w2Name}님은 비교 보고서를 작성하세요.`, tokensUsed: 190 },
      },
    },
    {
      delayMs: 950,
      event: {
        type: 'BROWSER_FRAME', agentId: cfg.w1Id, agentName: cfg.w1Name, role: 'WORKER', timestamp: 'Step 1/3',
        payload: { status: 'WORKING', screenshotUrl: makeSoMSvg('Step 1. 쇼핑몰 접속 및 검색창(#12) 타깃팅', '🔍 검색어 타이핑: 스마트워치 5세대 최저가', '정가 359,000원') },
      },
    },
    {
      delayMs: 950,
      event: {
        type: 'MESSAGE', agentId: cfg.w1Id, agentName: cfg.w1Name, role: 'WORKER', timestamp: '14:00:04',
        payload: { status: 'REVIEWING', text: '📄 [1차 결재 상신] 3사 공식 정가 수집 완료했습니다. 결재 부탁드립니다.', tokensUsed: 320 },
      },
    },
    {
      delayMs: 1050,
      event: {
        type: 'QC_REJECT', agentId: cfg.supId, agentName: cfg.supName, role: 'SUPERVISOR', timestamp: '14:00:05',
        payload: { status: 'REJECTED', targetWorkerId: cfg.w1Id, rejectReason: '[1차 반려 (1/3회)] 정가만 수집되었고 쿠폰 즉시할인가와 출처 URL이 누락되었습니다. 재탐색하세요.', tokensUsed: 260 },
      },
    },
    {
      delayMs: 950,
      event: {
        type: 'BROWSER_FRAME', agentId: cfg.w1Id, agentName: cfg.w1Name, role: 'WORKER', timestamp: 'Step 2/3',
        payload: { status: 'WORKING', screenshotUrl: makeSoMSvg('Step 2. 상세페이지 쿠폰함(#18) 재타깃팅', '🏷️ #18 쿠폰 적용가 추출 시도', '쿠폰가 329,000원 (A사)') },
      },
    },
    {
      delayMs: 950,
      event: {
        type: 'MESSAGE', agentId: cfg.w1Id, agentName: cfg.w1Name, role: 'WORKER', timestamp: '14:00:07',
        payload: { status: 'REVIEWING', text: '📄 [2차 결재 상신] A사(329,000원), C사(298,000원) 쿠폰가 및 URL 보완하여 재상신합니다.', tokensUsed: 340 },
      },
    },
    {
      delayMs: 1050,
      event: {
        type: 'QC_REJECT', agentId: cfg.supId, agentName: cfg.supName, role: 'SUPERVISOR', timestamp: '14:00:08',
        payload: { status: 'REJECTED', targetWorkerId: cfg.w1Id, rejectReason: '[2차 반려 (2/3회)] B사 오픈마켓 할인가가 여전히 빈값(Null)입니다. 다시 확인하세요.', tokensUsed: 290 },
      },
    },
    {
      delayMs: 950,
      event: {
        type: 'MESSAGE', agentId: cfg.w1Id, agentName: cfg.w1Name, role: 'WORKER', timestamp: '14:00:09',
        payload: { status: 'REVIEWING', text: '📄 [3차 결재 상신] B사는 회원 로그인 전용 쿠폰 팝업에 가려져 정가(340,000원)로만 제출합니다.', tokensUsed: 280 },
      },
    },
    {
      delayMs: 1050,
      event: {
        type: 'QC_REJECT', agentId: cfg.supId, agentName: cfg.supName, role: 'SUPERVISOR', timestamp: '14:00:10',
        payload: { status: 'REJECTED', targetWorkerId: cfg.w1Id, rejectReason: '[3차 반려 (3/3회)] B사 회원 전용 쿠폰 팝업에 막혀 또 수집에 실패했습니다. 기준 미달 반려합니다.', tokensUsed: 310 },
      },
    },
    {
      delayMs: 550,
      event: {
        type: 'HITL_REQUIRED', agentId: cfg.supId, agentName: cfg.supName, role: 'SUPERVISOR', timestamp: '14:00:11',
        payload: {
          status: 'REJECTED', workerId: cfg.w1Id, workerName: cfg.w1Name,
          rejectReason: 'B사 오픈마켓의 회원 전용 쿠폰가는 비로그인 상태에서 열람이 불가하여 3회 연속 수집에 실패했습니다.',
          latestDraft: '• A사 공식몰: 정가 359,000원 / 쿠폰가 329,000원\n• B사 오픈마켓: 정가 340,000원 / 쿠폰가 [로그인필요]\n• C사 직영몰: 정가 330,000원 / 쿠폰가 298,000원 (최저가)',
        },
      },
    },
  ];
};

export const buildReplayPart2 = (action: string, comment: string, cfg: ReplayTeamConfig): { delayMs: number; event: AgentEvent }[] => [
  {
    delayMs: 300,
    event: {
      type: 'MESSAGE', agentId: 'ceo', agentName: '신영호 대표 (CEO 직권)', role: 'SUPERVISOR', timestamp: '14:00:15',
      payload: { status: 'DONE', text: `⚡ [CEO 직권 결재 완료] (${action}) ${comment || '비회원 열람 불가 항목은 정가 기준으로 표기하고 즉시 보고서 작성할 것.'}`, tokensUsed: 120 },
    },
  },
  {
    delayMs: 750,
    event: {
      type: 'STATUS_CHANGE', agentId: cfg.w1Id, agentName: cfg.w1Name, role: 'WORKER', timestamp: '14:00:16',
      payload: { status: 'DONE' },
    },
  },
  {
    delayMs: 850,
    event: {
      type: 'MESSAGE', agentId: cfg.w2Id, agentName: cfg.w2Name, role: 'WORKER', timestamp: '14:00:17',
      payload: { status: 'DONE', text: '📄 [최종 보고서 상신] CEO 결재 지침을 반영하여 3사 비교 마크다운 보고서 작성을 완료했습니다.', tokensUsed: 410 },
    },
  },
  {
    delayMs: 850,
    event: {
      type: 'FINAL_REPORT', agentId: cfg.supId, agentName: cfg.supName, role: 'SUPERVISOR', timestamp: '14:00:18',
      payload: {
        status: 'DONE', tokensUsed: 420,
        reportMarkdown: `### 📊 스마트워치 3사 가격·스펙 비교 최종 결재서\n\n- **검수 책임자:** ${cfg.supName} (${cfg.supDept})\n- **수행 실무자:** ${cfg.w1Name}, ${cfg.w2Name}\n- **검수 이력:** 팀장 3회 반려 후 **CEO Human-in-the-loop 직권 결재 완료**\n\n• **A사 공식몰:** 정가 359,000원 → 쿠폰가 **329,000원**\n• **B사 오픈마켓:** 정가 **340,000원** (CEO 지침에 의거 비회원 정가 기준 반영)\n• **C사 직영몰:** 정가 330,000원 → 쿠폰가 **298,000원 (최저가)**`,
      },
    },
  },
];
