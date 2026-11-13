'use client';

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
    label: '🏥 ISO 13485·9001 품질문서 심사',
    prompt: '의료기기 제조 품질매뉴얼 및 작업표준서(SOP) 작성 시 ISO 13485:2016 및 ISO 9001:2015 인증 필수 요구사항 체크리스트와 주요 부적합(Gap) 방지 대책 보고서 작성해줘',
  },
  {
    label: '📉 월간 불량률(PPM)·CAPA 분석',
    prompt: '제조 라인 수입·공정검사 불량률(PPM) 데이터를 분석하여 핵심 불량 원인(Pareto)을 도출하고 협력사 시정조치요구서(CAPA) 및 8D 대책 보고서를 작성해줘',
  },
  {
    label: '🏭 제조 수입검사(CoA) 자동화',
    prompt: '제조업 수입검사 성적서(CoA) 엑셀 수기 입력 업무를 Python과 Vision AI로 자동화할 때의 기대 효과와 도입 로드맵 보고서를 작성해줘',
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
    label: '🛒 커머스 최저가·쿠폰 조사',
    prompt: '경쟁사 스마트워치 3종 최저가·쿠폰가 크롤링 후 비교 보고서 작성해줘',
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

// =====================================================================
// [전자결재 보고서 인포그래픽 렌더러]
// 줄글 불릿을 상태 배지(Pill) · 파레토 게이지 바 · LOT 감사추적 그리드 · SPC 공정능력 테이블로 자동 변환
// =====================================================================
type BulletTone = 'pass' | 'fail' | 'warn' | 'rawProv' | 'simProv' | 'webProv' | 'ceo' | 'neutral';

const TONE_STYLES: Record<BulletTone, { box: string; pill: string; label: string }> = {
  pass: { box: 'bg-emerald-50/70 border-emerald-300', pill: 'bg-emerald-600 text-white border-emerald-700', label: '✅ 적합' },
  fail: { box: 'bg-rose-50/80 border-rose-300', pill: 'bg-rose-600 text-white border-rose-700', label: '🚨 부적합/Gap' },
  warn: { box: 'bg-amber-50/90 border-amber-300', pill: 'bg-amber-500 text-slate-950 border-amber-600', label: '⚠️ 산포 경고' },
  rawProv: { box: 'bg-emerald-50/95 border-emerald-400', pill: 'bg-emerald-700 text-white border-emerald-800', label: '📊 실데이터' },
  simProv: { box: 'bg-sky-50/95 border-sky-400', pill: 'bg-sky-700 text-white border-sky-800', label: '🧪 표준 시뮬레이션' },
  webProv: { box: 'bg-indigo-50/95 border-indigo-400', pill: 'bg-indigo-700 text-white border-indigo-800', label: '🌐 실시간 지식수집' },
  ceo: { box: 'bg-amber-50/90 border-amber-300', pill: 'bg-slate-900 text-amber-200 border-slate-950', label: '⚡ 대표 지시' },
  neutral: { box: 'bg-slate-50/95 border-slate-200', pill: '', label: '' },
};

function classifyBullet(b: string): BulletTone {
  if (b.includes('📊 [데이터 출처:')) return 'rawProv';
  if (b.includes('🧪 [데이터 출처:')) return 'simProv';
  if (b.includes('🌐 [데이터 출처:')) return 'webProv';
  if (b.includes('⚠️')) return 'warn';
  if (b.includes('🚨')) return 'fail';
  if (b.includes('✅')) return 'pass';
  if (b.includes('⚡') || b.includes('↩️')) return 'ceo';
  return 'neutral';
}

function renderEmphasis(text: string, keyPrefix: string) {
  return text.split(/(\[[^\]]+\])/g).map((seg, i) =>
    seg.startsWith('[') && seg.endsWith(']') ? (
      <strong key={`${keyPrefix}-${i}`} className="font-bold text-slate-950">
        {seg}
      </strong>
    ) : (
      <React.Fragment key={`${keyPrefix}-${i}`}>{seg}</React.Fragment>
    )
  );
}

function StatusPill({ tone, label }: { tone: BulletTone; label?: string }) {
  const st = TONE_STYLES[tone];
  if (!st.pill) return null;
  return (
    <span className={`shrink-0 inline-flex items-center px-2.5 py-0.5 rounded-full text-[11.5px] font-extrabold border ${st.pill}`}>
      {label || st.label}
    </span>
  );
}

function GaugeBar({ pct, tone = 'neutral', height = 'h-2.5' }: { pct: number; tone?: 'good' | 'bad' | 'warn' | 'neutral'; height?: string }) {
  const safe = Math.max(0, Math.min(100, Number.isFinite(pct) ? pct : 0));
  const color =
    tone === 'good' ? 'bg-emerald-500' : tone === 'bad' ? 'bg-rose-500' : tone === 'warn' ? 'bg-amber-500' : 'bg-slate-700';
  return (
    <div className={`w-full ${height} rounded-full bg-slate-200 overflow-hidden`}>
      <div className={`${height} ${color} rounded-full transition-all duration-500`} style={{ width: `${safe}%` }} />
    </div>
  );
}

interface ParetoItem {
  rank: number;
  label: string;
  count: number;
  share: number;
  cum: number;
}

function parsePareto(b: string): ParetoItem[] | null {
  if (!/파레토|pareto/i.test(b)) return null;
  const items: ParetoItem[] = [];
  // 형식 A (첨부파일 엔진): "도금두께(고전압 커넥터 단자) 1건(비중 33.3%, 누적 33.3%)"
  Array.from(b.matchAll(/([^➔:]+?)\s(\d+)건\(비중 ([\d.]+)%, 누적 ([\d.]+)%\)/g)).forEach((m, i) => {
    items.push({ rank: i + 1, label: m[1].trim(), count: Number(m[2]), share: Number(m[3]), cum: Number(m[4]) });
  });
  // 형식 B (표준 시뮬레이션): "1위 치수·도금 두께 공차 이탈(19건, 45.2% / 누적 45.2%)"
  if (!items.length) {
    Array.from(b.matchAll(/(\d+)위\s([^(➔]+?)\((\d+)건,\s*([\d.]+)%\s*\/\s*누적\s*([\d.]+)%\)/g)).forEach((m) => {
      items.push({ rank: Number(m[1]), label: m[2].trim(), count: Number(m[3]), share: Number(m[4]), cum: Number(m[5]) });
    });
  }
  return items.length ? items : null;
}

interface SpcRow {
  label: string;
  n: number;
  limits: string;
  mean: string;
  sigma: string;
  cp: string;
  cpk: string;
  margin: number | null;
}

function parseSpc(b: string): SpcRow[] | null {
  if (!b.startsWith('[Real SPC')) return null;
  const body = b.replace(/^\[[^\]]+\]:\s*/, '').replace(/\.$/, '');
  const rows: SpcRow[] = [];
  body.split(' | ').forEach((part) => {
    const m = part.match(/^(.+?)\(n=(\d+), ([^)]*)\): (.*)$/);
    if (!m) return;
    const rest = m[4];
    const pick = (re: RegExp) => (rest.match(re)?.[1] ?? '-');
    const marginStr = rest.match(/여유도 (-?[\d.]+)%/)?.[1];
    rows.push({
      label: m[1].trim(),
      n: Number(m[2]),
      limits: m[3],
      mean: pick(/(?:평균|실측) ([\d.]+)/),
      sigma: pick(/σ=([\d.]+)/),
      cp: pick(/Cp=([\d.∞]+|N\/A)/),
      cpk: pick(/Cpk=([\d.∞]+|N\/A)/),
      margin: marginStr !== undefined ? Number(marginStr) : null,
    });
  });
  return rows.length ? rows : null;
}

function CpkBadge({ value }: { value: string }) {
  const num = value === '∞' ? Infinity : Number(value);
  if (!Number.isFinite(num) && value !== '∞') {
    return <span className="text-slate-500 font-semibold">{value}</span>;
  }
  const cls =
    num >= 1.33
      ? 'bg-emerald-100 text-emerald-900 border-emerald-400'
      : num >= 1.0
      ? 'bg-amber-100 text-amber-900 border-amber-400'
      : 'bg-rose-100 text-rose-900 border-rose-400';
  return <span className={`inline-block px-2 py-0.5 rounded-md border font-extrabold tabular-nums ${cls}`}>{value}</span>;
}

function ReportBulletView({ text, idx }: { text: string; idx: number }) {
  const tone = classifyBullet(text);
  const st = TONE_STYLES[tone];
  const baseBox = `p-3.5 rounded-xl border text-[14.5px] leading-relaxed font-medium text-[#0f172a] antialiased ${st.box}`;

  // 1) 파레토(Pareto) 빈도 분석 ➔ 순위별 게이지 바
  const pareto = parsePareto(text);
  if (pareto) {
    const head = text.match(/^\[([^\]]+)\]/)?.[1] || '파레토(Pareto) 우선순위 분석';
    return (
      <div className={`${baseBox} space-y-2.5`}>
        <div className="flex items-center justify-between gap-2">
          <strong className="font-extrabold text-slate-950">📊 {head}</strong>
          <span className="text-[11.5px] font-bold text-slate-600">막대 = 비중 % · 점선 = 누적 %</span>
        </div>
        <div className="space-y-2">
          {pareto.map((p) => {
            const isVital = p.cum - p.share < 80;
            return (
              <div key={`${idx}-p-${p.rank}`} className="grid grid-cols-[28px_minmax(0,1fr)_120px] items-center gap-3">
                <span
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-black ${
                    isVital ? 'bg-rose-600 text-white' : 'bg-slate-300 text-slate-800'
                  }`}
                >
                  {p.rank}
                </span>
                <div className="space-y-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 text-[13.5px]">
                    <span className="font-bold text-slate-900 truncate">{p.label}</span>
                    <span className="shrink-0 font-semibold text-slate-700 tabular-nums">{p.count}건</span>
                  </div>
                  <div className="relative">
                    <GaugeBar pct={p.share} tone={isVital ? 'bad' : 'neutral'} />
                    <div className="absolute top-[-2px] h-[14px] border-l-2 border-dashed border-slate-900/70" style={{ left: `${Math.min(100, p.cum)}%` }} />
                  </div>
                </div>
                <div className="text-right tabular-nums">
                  <div className="text-[14px] font-extrabold text-slate-950">{p.share}%</div>
                  <div className="text-[11.5px] font-semibold text-slate-600">누적 {p.cum}%</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // 2) Real SPC 공정능력(σ·Cp·Cpk) ➔ 구조화 테이블
  const spc = parseSpc(text);
  if (spc) {
    return (
      <div className={`${baseBox} space-y-2`}>
        <strong className="font-extrabold text-slate-950">📐 Real SPC 공정능력 분석 (σ · Cp · Cpk · 규격 여유도)</strong>
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-[13px]">
            <thead className="bg-slate-900 text-white">
              <tr>
                {['검사항목', 'n', '규격 한계', '평균', 'σ', 'Cp', 'Cpk', '최소 여유도'].map((h) => (
                  <th key={h} className="px-2.5 py-1.5 text-left font-bold whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {spc.map((r, i) => (
                <tr key={`${idx}-spc-${i}`} className="border-t border-slate-200 odd:bg-slate-50/70">
                  <td className="px-2.5 py-1.5 font-bold text-slate-900">{r.label}</td>
                  <td className="px-2.5 py-1.5 tabular-nums">{r.n}</td>
                  <td className="px-2.5 py-1.5 whitespace-nowrap text-slate-700">{r.limits}</td>
                  <td className="px-2.5 py-1.5 tabular-nums">{r.mean}</td>
                  <td className="px-2.5 py-1.5 tabular-nums">{r.sigma}</td>
                  <td className="px-2.5 py-1.5"><CpkBadge value={r.cp} /></td>
                  <td className="px-2.5 py-1.5"><CpkBadge value={r.cpk} /></td>
                  <td className="px-2.5 py-1.5 min-w-[120px]">
                    {r.margin === null ? (
                      <span className="text-slate-500">-</span>
                    ) : (
                      <div className="flex items-center gap-2">
                        <GaugeBar pct={Math.max(0, r.margin) * 2} tone={r.margin < 0 ? 'bad' : r.margin <= 15 ? 'warn' : 'good'} height="h-2" />
                        <span className={`tabular-nums font-extrabold ${r.margin < 0 ? 'text-rose-700' : r.margin <= 15 ? 'text-amber-700' : 'text-emerald-700'}`}>
                          {r.margin}%
                        </span>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // 3) LOT별 1:1 감사추적(Audit Trail) ➔ 구조화 그리드 카드
  const lot = text.match(/^\[원본 #(\d+)행 \| ([^|]+) \| ([^\]]+)\]\s*(.+)$/);
  if (lot) {
    const detail = lot[4].match(/^(.+?): 기준규격\(Spec\) '([^']*)' 대비 실측값 '([^']*)' (?:검출|확인) ➔ 판정: (.+?)(?: \((.+)\))?$/);
    const cells = detail
      ? [
          ['원본 행', `#${lot[1]}`],
          ['LOT', lot[2].trim()],
          ['품목(협력사)', lot[3].trim()],
          ['검사항목', detail[1]],
          ['기준규격', detail[2]],
          ['실측값', detail[3]],
          ['편차', (detail[5] || '-').replace(/^.*?:\s*/, '')],
        ]
      : null;
    return (
      <div className={`${baseBox} space-y-2`}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-[12px] font-extrabold text-slate-600 tracking-wide">1:1 AUDIT TRAIL</span>
          <StatusPill tone={tone} label={tone === 'fail' ? '🚨 부적합' : tone === 'pass' ? '✅ 적격(합격)' : undefined} />
        </div>
        {cells ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-1.5">
            {cells.map(([k, v]) => (
              <div key={`${idx}-${k}`} className="rounded-lg bg-white border border-slate-200 px-2 py-1.5">
                <div className="text-[10.5px] font-bold text-slate-500">{k}</div>
                <div className={`text-[13px] font-extrabold break-words ${k === '실측값' && tone === 'fail' ? 'text-rose-700' : 'text-slate-950'}`}>{v}</div>
              </div>
            ))}
          </div>
        ) : (
          <div>{renderEmphasis(text, `lot-${idx}`)}</div>
        )}
      </div>
    );
  }

  // 4) 조항별 심사 결과 "[조항 — 상태]: 내용" ➔ 상태 배지 카드
  const clause = text.match(/^\[([^\]]+?) — ([^\]]+)\](?::\s*|\s*➔\s*)(.*)$/);
  if (clause && (tone === 'pass' || tone === 'fail' || tone === 'warn')) {
    const extra = clause[2].includes(' — ') ? clause[2].split(' — ').slice(1).join(' — ') : '';
    return (
      <div className={`${baseBox} space-y-1.5`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <strong className="font-extrabold text-slate-950 text-[14px]">{clause[1]}</strong>
          <div className="flex items-center gap-1.5">
            {extra && <span className="px-2 py-0.5 rounded-full text-[11px] font-extrabold bg-rose-100 text-rose-900 border border-rose-300">{extra}</span>}
            <StatusPill tone={tone} />
          </div>
        </div>
        <div className="text-[13.5px] text-slate-800">{renderEmphasis(clause[3], `cl-${idx}`)}</div>
      </div>
    );
  }

  // 5) 일반 불릿 ➔ 상태 배지 + 순위 원형 배지 + 핵심 수치 칩 + 부합도/합격률 게이지
  const rank = text.match(/\[(\d+)위/)?.[1];
  const ppmChips = Array.from(text.matchAll(/([\d,]+(?:\.\d+)?)\s?PPM/g)).map((m) => `${m[1]} PPM`);
  const pctChips = Array.from(text.matchAll(/(\d+(?:\.\d+)?)%/g)).map((m) => `${m[1]}%`);
  const chips = Array.from(new Set([...ppmChips, ...pctChips])).slice(0, 3);
  const scoreMatch = text.match(/부합도 ([\d.]+)%/) || text.match(/합격 \d+건 \(([\d.]+)%\)/);
  const scorePct = scoreMatch ? Number(scoreMatch[1]) : null;

  return (
    <div className={`${baseBox} space-y-2`}>
      <div className="flex items-start gap-2.5">
        {rank ? (
          <span className="shrink-0 mt-0.5 w-7 h-7 rounded-full bg-slate-900 text-white flex items-center justify-center text-[12px] font-black">{rank}</span>
        ) : (
          <span className="text-slate-900 font-extrabold shrink-0 mt-0.5">•</span>
        )}
        <span className="flex-1 break-words">{renderEmphasis(text, `b-${idx}`)}</span>
        <div className="shrink-0 flex flex-col items-end gap-1">
          <StatusPill tone={tone} />
          {tone === 'neutral' &&
            chips.map((c) => (
              <span key={`${idx}-${c}`} className="px-2 py-0.5 rounded-md bg-slate-900 text-white text-[11.5px] font-extrabold tabular-nums whitespace-nowrap">
                {c}
              </span>
            ))}
        </div>
      </div>
      {scorePct !== null && (
        <div className="flex items-center gap-2 pl-5">
          <GaugeBar pct={scorePct} tone={scorePct >= 85 ? 'good' : scorePct >= 60 ? 'warn' : 'bad'} />
          <span className="shrink-0 text-[12.5px] font-extrabold tabular-nums text-slate-900">{scorePct}%</span>
        </div>
      )}
    </div>
  );
}

const CEO_REJECT_TAG_RE = /\s*\[↩️ 대표 결재 반려 보완지시(?:\s*#\d+)?:\s*([^\]]+)\]/g;

function splitRejectDirectives(p: string): { core: string; reasons: string[] } {
  const reasons = Array.from(p.matchAll(CEO_REJECT_TAG_RE)).map((m) => m[1].trim());
  return { core: p.replace(CEO_REJECT_TAG_RE, '').trim(), reasons };
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
  const [approvalStatus, setApprovalStatus] = useState<'PENDING' | 'APPROVED'>('PENDING');
  const [approvedAt, setApprovedAt] = useState<string>('');
  const [ceoRejectReason, setCeoRejectReason] = useState<string>('');
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

  // 새 보고서가 도착하면 결재 상태를 '대표 결재 대기'로 초기화
  useEffect(() => {
    setApprovalStatus('PENDING');
    setApprovedAt('');
  }, [finalReport]);

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

  const buildDynamicExportFilename = (ext: string): string => {
    const dateStr = new Date().toISOString().slice(0, 10);
    const cleanPart = (raw: string, maxLen: number) =>
      raw
        .replace(/[\\/:*?"<>|\r\n]+/g, '_')
        .replace(/\s+/g, '_')
        .replace(/_+/g, '_')
        .replace(/^[_-]+|[_-]+$/g, '')
        .slice(0, maxLen)
        .replace(/^[_-]+|[_-]+$/g, '') || '핵심안건';

    if (uploadedFileName) {
      const baseNoExt = uploadedFileName.replace(/\.[^/.]+$/, '');
      return `[결재보고서]_${cleanPart(baseNoExt, 40)}_분석_${dateStr}.${ext}`;
    }
    const cleanTopic = prompt
      .replace(/\[↩️[^\]]*\]/g, '')
      .replace(/\(첨부파일[^)]*\)/g, '')
      .replace(/(?:정밀\s*분석\s*및\s*결재\s*보고서|최종\s*승인\s*결재\s*보고서|결재\s*보고서|심층\s*보고서|보고서)\s*$/g, '')
      .replace(/(?:조사해줘|작성해줘|분석해줘|검토해줘|정리해줘|알려줘|해줘)\s*$/g, '')
      .trim();
    return `[결재보고서]_${cleanPart(cleanTopic, 32)}_${dateStr}.${ext}`;
  };

  const handleDownloadReportFile = async (format: 'docx' | 'xlsx' | 'md' | 'pdf') => {
    if (!finalReport) return;
    if (format === 'pdf') {
      const printWin = window.open('', '_blank', 'width=900,height=800');
      if (!printWin) return;
      const pdfTitle = buildDynamicExportFilename('pdf').replace(/\.pdf$/i, '');
      const htmlContent = `
        <html>
          <head>
            <title>${pdfTitle}</title>
            <style>
              body { font-family: 'Malgun Gothic', sans-serif; padding: 40px; color: #0f172a; line-height: 1.7; }
              h1 { color: #1e3a5f; border-bottom: 2px solid #1e3a5f; padding-bottom: 10px; font-size: 20px; }
              pre { white-space: pre-wrap; font-family: 'Malgun Gothic', sans-serif; font-size: 13px; }
            </style>
          </head>
          <body>
            <h1>📋 ${pdfTitle}</h1>
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
          attached_filename: uploadedFileName || '',
        }),
      });
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'docx' ? 'docx' : format === 'xlsx' ? 'xlsx' : 'md';
      let downloadName = buildDynamicExportFilename(ext);
      const disp = res.headers.get('Content-Disposition') || '';
      const utfMatch = disp.match(/filename\*\=UTF-8''([^;\n]+)/i);
      const plainMatch = disp.match(/filename="?([^";\n]+)"?/i);
      if (utfMatch?.[1]) {
        try {
          downloadName = decodeURIComponent(utfMatch[1].trim());
        } catch {
          // keep fallback
        }
      } else if (plainMatch?.[1]) {
        downloadName = plainMatch[1].trim();
      }
      a.download = downloadName;
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

  // [전자결재 양방향 워크플로우] 최종 승인 확정
  const handleCeoApprove = () => {
    setApprovalStatus('APPROVED');
    setApprovedAt(new Date().toLocaleString('ko-KR', { hour12: false }));
  };

  // [전자결재 양방향 워크플로우] 반려 사유를 원 안건에 결합하여 전담팀 즉시 재가동(Re-run)
  const handleCeoReject = () => {
    const reason = ceoRejectReason.replace(/[\[\]]/g, '').trim();
    if (!reason) return;
    const nextNo = splitRejectDirectives(prompt).reasons.length + 1;
    const nextPrompt = `${prompt.trim()} [↩️ 대표 결재 반려 보완지시 #${nextNo}: ${reason}]`;
    setIsReportModalOpen(false);
    setCeoRejectReason('');
    setApprovalStatus('PENDING');
    setApprovedAt('');
    startMission(nextPrompt);
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
  const agendaInfo = splitRejectDirectives(prompt);
  const activeSupNode = nodes.find((n) => n.id !== 'ceo' && n.id.startsWith('sup-'));
  const activeWorkerNodes = nodes.filter((n) => n.id.startsWith('wrk-'));

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-950 text-slate-100 select-none">
      <header className="shrink-0 px-5 py-2.5 bg-slate-900/75 backdrop-blur-2xl border-b border-white/10 space-y-2 shadow-[0_8px_30px_rgba(0,0,0,0.5)] z-30">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-950/75 backdrop-blur-md border border-white/10 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)]">
              <span className="text-base">🏢</span>
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-extrabold tracking-tight bg-gradient-to-r from-emerald-400 to-sky-400 bg-clip-text text-transparent">
                    AI COMPANY HUB
                  </span>
                  <span className="px-1.5 py-0.2 text-[9px] font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-500/40 rounded">
                    v3.5 Enterprise
                  </span>
                </div>
                <span className="text-[9px] text-slate-400 block">Multi-Agent Orchestration & CoA Analytics</span>
              </div>
            </div>

            <div className="flex bg-slate-950/75 backdrop-blur-md p-1 rounded-xl border border-white/10 shadow-inner">
              <button
                onClick={() => setLeftViewMode('PIXEL')}
                className={`px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all duration-300 ease-out ${
                  leftViewMode === 'PIXEL'
                    ? 'bg-gradient-to-r from-emerald-600 to-teal-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.4)]'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-white/5'
                }`}
              >
                🎮 2.5D 사옥 관제
              </button>
              <button
                onClick={() => setLeftViewMode('GRAPH')}
                className={`px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all duration-300 ease-out ${
                  leftViewMode === 'GRAPH'
                    ? 'bg-gradient-to-r from-indigo-600 to-violet-500 text-white shadow-[0_0_15px_rgba(99,102,241,0.4)]'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-white/5'
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
              className={`px-3 py-2 text-xs font-bold rounded-xl border backdrop-blur-md transition-all duration-300 ease-out shrink-0 ${
                uploadedFileName
                  ? 'bg-sky-500/20 border-sky-400/80 text-sky-300 shadow-[0_0_15px_rgba(56,189,248,0.3)] hover:bg-sky-500/30'
                  : 'bg-slate-950/70 border-white/15 text-slate-300 hover:border-sky-400/60 hover:bg-slate-900/80 hover:-translate-y-0.5'
              }`}
            >
              {uploadedFileName ? `📎 ${uploadedFileName.slice(0, 14)}` : '📎 파일 첨부'}
            </button>
            {uploadedFileName && (
              <button
                onClick={handleClearUpload}
                className="px-2 py-1.5 text-[10px] font-bold bg-rose-950/80 backdrop-blur-md border border-rose-500/50 text-rose-300 rounded-lg hover:bg-rose-900/80 transition-all duration-300 ease-out"
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
              className="w-full px-3.5 py-2 text-xs bg-slate-950/80 backdrop-blur-md border border-white/15 rounded-xl text-slate-100 focus:outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-400/30 transition-all duration-300 ease-out"
            />
            <button
              onClick={() => startMission()}
              disabled={isStreaming}
              className="px-4 py-2 text-xs font-extrabold bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 hover:-translate-y-0.5 active:translate-y-0 text-white rounded-xl shrink-0 shadow-[0_4px_20px_rgba(16,185,129,0.35)] hover:shadow-[0_6px_25px_rgba(16,185,129,0.55)] transition-all duration-300 ease-out"
            >
              {isStreaming ? '⏳ 수행 중' : '▶️ 업무 하달'}
            </button>
            <button
              onClick={() => {
                const cleanBase = prompt.replace(/다시\s*찾아줘|새로\s*찾아줘/g, '').trim();
                startMission(`${cleanBase} 다시 찾아줘`);
              }}
              title="서가(책장) 캐시를 무시하고 웹에서 새로 크롤링합니다"
              className="px-3 py-2 text-xs font-bold bg-indigo-600/85 hover:bg-indigo-500 hover:-translate-y-0.5 active:translate-y-0 backdrop-blur-md text-white rounded-xl shrink-0 border border-indigo-400/40 shadow-[0_4px_15px_rgba(99,102,241,0.3)] transition-all duration-300 ease-out"
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
              className="px-2.5 py-1.5 rounded-xl bg-slate-950/70 backdrop-blur-md border border-white/10 hover:border-cyan-400/70 hover:bg-slate-900/80 hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(34,211,238,0.2)] text-left transition-all duration-300 ease-out"
            >
              <span className="text-[9px] block text-slate-400">
                비용 방어 (캐시 {costMetrics.cache_hits}회)
              </span>
              <span className="text-[11px] font-bold text-cyan-400">
                💰 ${Number(costMetrics.total_cost_usd || 0).toFixed(4)}
              </span>
            </button>

            <button
              onClick={() => setIsOAuthModalOpen(true)}
              className="px-2.5 py-1.5 rounded-xl bg-slate-950/70 backdrop-blur-md border border-white/10 hover:border-teal-400/70 hover:bg-slate-900/80 hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(45,212,191,0.2)] text-left transition-all duration-300 ease-out"
            >
              <span className="text-[9px] block text-slate-400">
                {gptConnected ? 'OpenAI 연결됨' : 'LLM 엔진'}
              </span>
              <span className="text-[11px] font-bold text-teal-400">🔗 LLM 연동</span>
            </button>

            <button
              onClick={() => {
                refreshWebhookConfigs();
                setIsWebhookModalOpen(true);
              }}
              className="px-2.5 py-1.5 rounded-xl bg-slate-950/70 backdrop-blur-md border border-white/10 hover:border-violet-400/70 hover:bg-slate-900/80 hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(167,139,250,0.2)] text-left transition-all duration-300 ease-out"
            >
              <span className="text-[9px] block text-slate-400">외부 연동</span>
              <span className="text-[11px] font-bold text-violet-400">🔌 ERP·Jira</span>
            </button>

            <button
              onClick={() => {
                refreshArchiveList();
                setIsArchiveModalOpen(true);
              }}
              className="px-2.5 py-1.5 rounded-xl bg-slate-950/70 backdrop-blur-md border border-white/10 hover:border-emerald-400/70 hover:bg-slate-900/80 hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(52,211,153,0.2)] text-left transition-all duration-300 ease-out"
            >
              <span className="text-[9px] block text-slate-400">서가(책장) DB</span>
              <span className="text-[11px] font-bold text-emerald-400">🗂️ 보관함 ({archiveList.length})</span>
            </button>

            <button
              onClick={() => setIsBrowserDrawerOpen(true)}
              className="px-2.5 py-1.5 rounded-xl bg-slate-950/70 backdrop-blur-md border border-white/10 hover:border-sky-400/70 hover:bg-slate-900/80 hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(56,189,248,0.2)] text-left transition-all duration-300 ease-out"
            >
              <span className="text-[9px] block text-slate-400">SoM 비전</span>
              <span className="text-[11px] font-bold text-sky-400">🌐 웹 ({browserHistory.length})</span>
            </button>

            <button
              onClick={() => setIsLogDrawerOpen(true)}
              className="px-2.5 py-1.5 rounded-xl bg-slate-950/70 backdrop-blur-md border border-white/10 hover:border-amber-400/70 hover:bg-slate-900/80 hover:-translate-y-0.5 hover:shadow-[0_4px_16px_rgba(251,191,36,0.2)] text-left transition-all duration-300 ease-out"
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
                className={`px-2.5 py-1 text-[11px] rounded-lg border backdrop-blur-md transition-all duration-300 ease-out shrink-0 ${
                  prompt === item.prompt
                    ? 'bg-emerald-950/70 border-emerald-500/70 text-emerald-300 font-bold shadow-[0_0_12px_rgba(16,185,129,0.25)]'
                    : 'bg-slate-950/60 border-white/10 text-slate-400 hover:text-slate-100 hover:border-white/25 hover:bg-slate-900/70'
                }`}
              >
                {item.label}
              </button>
            ))}
            <button
              onClick={() => setIsDirOpen(true)}
              className="px-2.5 py-1 text-[11px] rounded-lg bg-slate-950/70 backdrop-blur-md border border-white/10 hover:border-amber-400/70 hover:bg-slate-900/80 text-amber-300 font-semibold shrink-0 transition-all duration-300 ease-out"
            >
              👥 사원 명부·수동 차출
            </button>
          </div>

          <div className="flex items-center gap-1.5 shrink-0 bg-slate-950/75 backdrop-blur-md px-3 py-1 rounded-xl border border-sky-500/40 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)]">
            <span className="text-[11px] font-bold text-sky-400">💬 실시간 CEO 개입:</span>
            <input
              value={liveWhisper}
              onChange={(e) => setLiveWhisper(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendLiveWhisper()}
              placeholder="작업 중 추가 지시 입력 (예: 불량 원인 더 자세히 써줘)"
              className="w-64 px-2 py-0.5 text-[11px] bg-slate-900/80 border border-white/15 rounded-md text-slate-100 focus:outline-none focus:border-sky-400 transition-all duration-300 ease-out"
            />
            <button
              onClick={handleSendLiveWhisper}
              className="px-2.5 py-0.5 text-[11px] font-bold bg-sky-600 hover:bg-sky-500 hover:shadow-[0_0_12px_rgba(56,189,248,0.4)] text-white rounded-md transition-all duration-300 ease-out"
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
              <div className="absolute top-4 left-5 z-20 px-4 py-2 rounded-xl bg-slate-900/80 backdrop-blur-xl border border-indigo-500/40 shadow-xl text-xs">
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
          <aside className="absolute right-0 top-0 bottom-0 w-[500px] z-40 bg-slate-900/80 backdrop-blur-2xl border-l border-white/15 flex flex-col shadow-[0_0_50px_rgba(0,0,0,0.85)] transition-all duration-300 ease-out">
            <div className="shrink-0 px-4 py-3 bg-slate-950/70 border-b border-white/10 flex items-center justify-between">
              <span className="text-xs font-bold text-sky-400">🌐 실시간 웹 탐색 (SoM Vision 캡처)</span>
              <button
                onClick={() => setIsBrowserDrawerOpen(false)}
                className="px-2.5 py-1 text-xs font-bold bg-slate-800/80 hover:bg-slate-700 border border-white/10 rounded-lg text-slate-200 transition-all duration-300 ease-out"
              >
                ✕ 닫기
              </button>
            </div>
            <div className="flex-1 p-4 overflow-y-auto space-y-3">
              {displayedFrameUrl ? (
                <div className="space-y-2.5">
                  {browserHistory.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap bg-slate-950/70 backdrop-blur-md p-2 rounded-xl border border-white/10">
                      <span className="text-[10px] font-bold text-slate-400 mr-1">🎬 탐색 단계:</span>
                      {browserHistory.map((item, idx) => {
                        const isSelected = (selectedFrameIdx === -1 ? browserHistory.length - 1 : selectedFrameIdx) === idx;
                        return (
                          <button
                            key={idx}
                            onClick={() => setSelectedFrameIdx(idx)}
                            className={`px-2.5 py-1 text-[10px] font-bold rounded-lg border transition-all duration-300 ease-out ${
                              isSelected
                                ? 'bg-emerald-600 border-emerald-400 text-white shadow-[0_0_12px_rgba(16,185,129,0.4)]'
                                : 'bg-slate-950/80 border-white/10 text-slate-300 hover:border-white/30'
                            }`}
                          >
                            {item.step}
                          </button>
                        );
                      })}
                    </div>
                  )}
                  <div className="rounded-xl overflow-hidden border border-white/15 shadow-2xl">
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
          <aside className="absolute right-0 top-0 bottom-0 w-[460px] z-40 bg-slate-900/80 backdrop-blur-2xl border-l border-white/15 flex flex-col shadow-[0_0_50px_rgba(0,0,0,0.85)] transition-all duration-300 ease-out">
            <div className="shrink-0 px-4 py-3 bg-slate-950/70 border-b border-white/10 flex items-center justify-between">
              <span className="text-xs font-bold text-amber-400">
                📜 AGENT WORKSPACE & QC 상세 로그 ({messages.length}건)
              </span>
              <button
                onClick={() => setIsLogDrawerOpen(false)}
                className="px-2.5 py-1 text-xs font-bold bg-slate-800/80 hover:bg-slate-700 border border-white/10 rounded-lg text-slate-200 transition-all duration-300 ease-out"
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
                    className={`p-3.5 rounded-xl border backdrop-blur-md text-xs leading-relaxed transition-all duration-300 ease-out ${
                      m.type === 'QC_REJECT'
                        ? 'bg-rose-950/45 border-rose-500/60 text-rose-200'
                        : m.role === 'SUPERVISOR'
                        ? 'bg-indigo-950/35 border-indigo-500/40'
                        : 'bg-slate-950/70 border-white/10'
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
                        className="mt-2 px-2.5 py-1 text-[10px] font-bold bg-slate-800/80 hover:bg-slate-700 text-emerald-300 rounded transition-all duration-300 ease-out"
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

      {isOAuthModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 backdrop-blur-md p-6 transition-all duration-300 ease-out">
          <div className="bg-slate-900/80 backdrop-blur-2xl border border-white/15 rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-[0_20px_70px_rgba(0,0,0,0.85)]">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-sm font-bold text-emerald-400">🔗 ChatGPT 모델 및 계정 연동하기</h3>
              <button
                onClick={() => setIsOAuthModalOpen(false)}
                className="px-2.5 py-1 text-xs font-bold bg-slate-800/80 hover:bg-slate-700 border border-white/10 rounded-lg transition-all duration-300 ease-out"
              >
                ✕ 닫기
              </button>
            </div>
            <div className="space-y-3 pt-1">
              <button
                onClick={handleAutoBrowserConnect}
                disabled={isAutoConnecting}
                className="w-full py-3 text-xs font-bold bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 hover:-translate-y-0.5 text-white rounded-xl shadow-[0_4px_20px_rgba(16,185,129,0.35)] transition-all duration-300 ease-out"
              >
                {isAutoConnecting
                  ? '⏳ 열린 창에서 ChatGPT 로그인을 완료해 주세요...'
                  : '⚡ 방법 1: 원클릭 브라우저 로그인으로 자동 연동하기'}
              </button>
              <div className="pt-2 border-t border-white/10 space-y-1.5">
                <label className="text-[11px] font-bold text-slate-400 block">
                  🔑 방법 2: OpenAI API Key (`sk-...`) 직접 입력:
                </label>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={oauthInputToken}
                    onChange={(e) => setOauthInputToken(e.target.value)}
                    placeholder="sk-proj-..."
                    className="flex-1 px-3 py-2 text-xs bg-slate-950/80 border border-white/15 rounded-lg text-slate-100 focus:outline-none focus:border-sky-400 transition-all duration-300 ease-out"
                  />
                  <button
                    onClick={handleSaveOAuthToken}
                    className="px-4 py-2 text-xs font-bold bg-sky-600 hover:bg-sky-500 hover:-translate-y-0.5 text-white rounded-lg shrink-0 transition-all duration-300 ease-out"
                  >
                    연동 저장
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {isCostModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 backdrop-blur-md p-6 transition-all duration-300 ease-out">
          <div className="bg-slate-900/80 backdrop-blur-2xl border border-white/15 rounded-2xl w-full max-w-2xl p-6 space-y-4 shadow-[0_20px_70px_rgba(0,0,0,0.85)]">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
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
                className="px-2.5 py-1 text-xs font-bold bg-slate-800/80 hover:bg-slate-700 border border-white/10 rounded-lg transition-all duration-300 ease-out"
              >
                ✕ 닫기
              </button>
            </div>

            <div className="grid grid-cols-4 gap-3 text-center">
              <div className="p-3.5 rounded-xl bg-slate-950/75 backdrop-blur-md border border-white/10 hover:border-white/25 transition-all duration-300 ease-out">
                <span className="text-[10px] text-slate-400 block">총 누적 토큰</span>
                <span className="text-base font-extrabold text-slate-100">
                  {costMetrics.total_tokens || 0} T
                </span>
                <span className="text-[9px] text-slate-500 block mt-1">
                  In {costMetrics.prompt_tokens || 0} / Out {costMetrics.completion_tokens || 0}
                </span>
              </div>
              <div className="p-3.5 rounded-xl bg-slate-950/75 backdrop-blur-md border border-white/10 hover:border-cyan-500/40 transition-all duration-300 ease-out">
                <span className="text-[10px] text-slate-400 block">누적 API 비용</span>
                <span className="text-base font-extrabold text-cyan-400">
                  ${Number(costMetrics.total_cost_usd || 0).toFixed(5)}
                </span>
                <span className="text-[9px] text-slate-500 block mt-1">
                  상한: ${costMetrics.budget_limit_usd || 1.0}
                </span>
              </div>
              <div className="p-3.5 rounded-xl bg-emerald-950/35 backdrop-blur-md border border-emerald-500/40 hover:border-emerald-400/70 transition-all duration-300 ease-out">
                <span className="text-[10px] text-emerald-300 block">서가 캐시 절감액</span>
                <span className="text-base font-extrabold text-emerald-400">
                  ${Number(costMetrics.saved_cost_usd || 0).toFixed(4)}
                </span>
                <span className="text-[9px] text-emerald-300/80 block mt-1">
                  캐시 히트: {costMetrics.cache_hits || 0}회
                </span>
              </div>
              <div className="p-3.5 rounded-xl bg-rose-950/35 backdrop-blur-md border border-rose-500/40 hover:border-rose-400/70 transition-all duration-300 ease-out">
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 backdrop-blur-md p-6 transition-all duration-300 ease-out">
          <div className="bg-slate-900/80 backdrop-blur-2xl border border-white/15 rounded-2xl w-full max-w-4xl max-h-[88vh] flex flex-col overflow-hidden shadow-[0_20px_70px_rgba(0,0,0,0.85)]">
            <div className="flex items-center justify-between px-6 py-4 bg-slate-950/75 border-b border-white/10">
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
                className="px-3 py-1.5 text-xs font-bold bg-slate-800/80 hover:bg-slate-700 border border-white/10 rounded-lg transition-all duration-300 ease-out"
              >
                ✕ 닫기
              </button>
            </div>

            <div className="flex-1 p-6 overflow-y-auto grid grid-cols-12 gap-5 text-xs">
              <div className="col-span-7 space-y-4">
                {['ecount_erp', 'jira_cloud', 'slack_webhook'].map((sysKey) => {
                  const item = webhookConfigs[sysKey] || {};
                  return (
                    <div key={sysKey} className="p-4 rounded-xl bg-slate-950/75 backdrop-blur-md border border-white/10 hover:border-violet-500/40 transition-all duration-300 ease-out space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-100">{item.name || sysKey}</span>
                        <button
                          onClick={() => handleTestWebhook(sysKey)}
                          className="px-2.5 py-1 text-[11px] font-bold bg-violet-600 hover:bg-violet-500 hover:-translate-y-0.5 text-white rounded-lg shadow-[0_4px_12px_rgba(139,92,246,0.3)] transition-all duration-300 ease-out"
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
                        className="w-full px-3 py-1.5 text-xs bg-slate-900/80 border border-white/15 rounded-lg text-slate-200 focus:outline-none focus:border-violet-400 transition-all duration-300 ease-out"
                      />
                    </div>
                  );
                })}
                <button
                  onClick={handleSaveWebhooks}
                  className="w-full py-2.5 text-xs font-bold bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 hover:-translate-y-0.5 text-white rounded-xl shadow-[0_4px_20px_rgba(16,185,129,0.35)] transition-all duration-300 ease-out"
                >
                  💾 연동 설정 저장하기
                </button>
              </div>

              <div className="col-span-5 flex flex-col bg-slate-950/75 backdrop-blur-md border border-white/10 rounded-xl p-4">
                <span className="font-bold text-emerald-400 mb-2">
                  📡 실시간 생성 API Payload (JSON 규격 미리보기)
                </span>
                <pre className="flex-1 text-[11px] text-slate-300 overflow-auto whitespace-pre-wrap font-mono bg-slate-900/80 p-3 rounded-lg border border-white/10">
                  {webhookPreview ||
                    '좌측에서 [⚡ 연동 페이로드 생성 테스트] 버튼을 누르면 현업 ERP·Jira·Slack으로 전송되는 표준 JSON 전문이 이곳에 표시됩니다.'}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}

      {isArchiveModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 backdrop-blur-md p-6 transition-all duration-300 ease-out">
          <div className="bg-slate-900/80 backdrop-blur-2xl border border-white/15 rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden shadow-[0_20px_70px_rgba(0,0,0,0.85)]">
            <div className="flex items-center justify-between px-6 py-4 bg-slate-950/75 border-b border-white/10">
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
                className="px-3 py-1.5 text-xs font-bold bg-slate-800/80 hover:bg-slate-700 border border-white/10 rounded-lg transition-all duration-300 ease-out"
              >
                ✕ 닫기
              </button>
            </div>

            <div className="flex-1 p-5 overflow-y-auto space-y-3">
              {archiveList.map((rec) => (
                <div
                  key={rec.id}
                  className="p-4 rounded-xl bg-slate-950/75 backdrop-blur-md border border-white/10 hover:border-emerald-500/40 flex items-center justify-between gap-4 transition-all duration-300 ease-out"
                >
                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 text-[10px] font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-700/50 rounded">
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
                      className="px-2.5 py-1.5 text-xs font-bold bg-amber-500 hover:bg-amber-400 hover:-translate-y-0.5 text-slate-950 rounded-lg shadow-[0_4px_12px_rgba(245,158,11,0.3)] transition-all duration-300 ease-out"
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
                        setUploadedFileName(rec.attached_file || '');
                        setIsArchiveModalOpen(false);
                        setIsReportModalOpen(true);
                      }}
                      className="px-3 py-1.5 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 hover:-translate-y-0.5 text-white rounded-lg shadow-[0_4px_12px_rgba(16,185,129,0.3)] transition-all duration-300 ease-out"
                    >
                      📖 바로 열람
                    </button>
                    <button
                      onClick={() => handleDeleteArchive(rec.id)}
                      className="px-2.5 py-1.5 text-xs font-bold bg-rose-950/80 hover:bg-rose-900 border border-rose-500/30 text-rose-300 rounded-lg transition-all duration-300 ease-out"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-xl p-6 transition-all duration-300 ease-out">
          <div className="bg-slate-900/85 backdrop-blur-2xl border border-white/15 rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden shadow-[0_25px_80px_rgba(0,0,0,0.9)]">
            <div className="flex flex-wrap items-center justify-between gap-2 px-6 py-4 bg-slate-950/80 border-b border-white/10">
              <div className="flex items-center gap-2.5">
                <span
                  className={`px-2.5 py-1 text-[10px] font-extrabold rounded-lg border ${
                    approvalStatus === 'APPROVED'
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-[0_0_12px_rgba(16,185,129,0.2)]'
                      : 'bg-amber-500/20 text-amber-200 border-amber-400/50'
                  }`}
                >
                  {approvalStatus === 'APPROVED' ? '최종 승인 완료' : '대표 결재 대기'}
                </span>
                <h3 className="text-sm font-extrabold text-white tracking-tight">
                  📋 엔터프라이즈 전자결재 5단 심층 분석 보고서
                </h3>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleCopyReport}
                  className="px-3 py-1.5 text-xs font-bold bg-slate-800/80 hover:bg-slate-700 hover:-translate-y-0.5 text-slate-200 rounded-xl border border-white/15 transition-all duration-300 ease-out"
                >
                  {copiedToast ? '✅ 복사됨!' : '📋 전문 복사'}
                </button>
                <button
                  onClick={() => handleDownloadReportFile('docx')}
                  className="px-3.5 py-1.5 text-xs font-bold bg-gradient-to-r from-blue-600 to-indigo-600 hover:brightness-110 hover:-translate-y-0.5 text-white rounded-xl shadow-[0_4px_15px_rgba(37,99,235,0.35)] transition-all duration-300 ease-out"
                >
                  📘 Word (.docx)
                </button>
                <button
                  onClick={() => handleDownloadReportFile('xlsx')}
                  className="px-3.5 py-1.5 text-xs font-bold bg-gradient-to-r from-emerald-600 to-teal-600 hover:brightness-110 hover:-translate-y-0.5 text-white rounded-xl shadow-[0_4px_15px_rgba(16,185,129,0.35)] transition-all duration-300 ease-out"
                >
                  📗 2-Sheet Excel (.xlsx)
                </button>
                <button
                  onClick={() => handleDownloadReportFile('pdf')}
                  className="px-3.5 py-1.5 text-xs font-bold bg-gradient-to-r from-rose-600 to-pink-600 hover:brightness-110 hover:-translate-y-0.5 text-white rounded-xl shadow-[0_4px_15px_rgba(225,29,72,0.35)] transition-all duration-300 ease-out"
                >
                  📕 PDF 인쇄·저장
                </button>
                <button
                  onClick={() => {
                    setIsReportModalOpen(false);
                    setIsWebhookModalOpen(true);
                  }}
                  className="px-3.5 py-1.5 text-xs font-bold bg-violet-600 hover:bg-violet-500 hover:-translate-y-0.5 text-white rounded-xl shadow-[0_4px_15px_rgba(139,92,246,0.35)] transition-all duration-300 ease-out"
                >
                  🔌 ERP·Jira 전송
                </button>
                <button
                  onClick={() => setIsReportModalOpen(false)}
                  className="ml-1 px-3 py-1.5 text-xs font-bold bg-slate-800/80 hover:bg-slate-700 border border-white/10 rounded-xl transition-all duration-300 ease-out"
                >
                  ✕
                </button>
              </div>
            </div>

            <div
              className="flex-1 p-6 overflow-y-auto space-y-5 bg-[#fcfcfd] text-slate-900 antialiased select-text"
              style={{ WebkitFontSmoothing: 'antialiased' }}
            >
              <div className="p-4 rounded-2xl bg-slate-50/95 border border-slate-300 flex flex-wrap items-center justify-between gap-4 shadow-sm">
                <div className="space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[11px] font-mono font-bold text-slate-800 bg-white px-2.5 py-0.5 rounded border border-slate-300">
                      DOC-{new Date().toISOString().slice(0, 10).replace(/-/g, '')}-VERIFIED
                    </span>
                    {Boolean(uploadedFileName) ||
                    finalReport.includes('실데이터 전수 검증 모드') ||
                    finalReport.includes('Verified Raw Data') ||
                    finalReport.includes('[전수 품질 판정 통계]') ? (
                      <span className="px-2.5 py-0.5 text-[11px] font-extrabold bg-emerald-100 text-emerald-950 border border-emerald-400 rounded">
                        [🟢 실데이터 전수연산 검증됨]
                      </span>
                    ) : finalReport.includes('실시간 멀티 소스 지식 수집 모드') ||
                      finalReport.includes('Live Web & Knowledge Synthesis') ? (
                      <span className="px-2.5 py-0.5 text-[11px] font-extrabold bg-indigo-100 text-indigo-950 border border-indigo-400 rounded">
                        [🌐 실시간 멀티소스 지식 수집·교차검증됨]
                      </span>
                    ) : (
                      <span className="px-2.5 py-0.5 text-[11px] font-extrabold bg-sky-100 text-sky-950 border border-sky-400 rounded">
                        [🔵 표준 레퍼런스 표본 시뮬레이션]
                      </span>
                    )}
                    <span className="text-xs font-extrabold text-emerald-800">
                      • QC 루브릭 정량 검수 통과 (기준 85점 이상)
                    </span>
                  </div>
                  <p className="text-[14.5px] font-extrabold text-slate-950 leading-snug">
                    안건: {agendaInfo.core}
                  </p>
                  {agendaInfo.reasons.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-0.5">
                      {agendaInfo.reasons.map((r, i) => (
                        <span
                          key={`rej-${i}`}
                          className="px-2 py-0.5 text-[11.5px] font-bold rounded-md bg-rose-50 text-rose-900 border border-rose-300"
                        >
                          ↩️ 반려 #{i + 1}: {r}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2 text-center">
                  <div className="w-24 p-2 rounded-xl bg-white border border-slate-300 shadow-2xs">
                    <span className="text-[10px] font-semibold text-slate-600 block">실무 기안</span>
                    <span className="text-xs font-extrabold text-slate-950 block my-0.5">
                      {activeWorkerNodes[0]?.data?.name ? String(activeWorkerNodes[0].data.name).split(' ')[0] : '전담 연구원'}
                    </span>
                    <span className="inline-block px-1.5 py-0.5 text-[9.5px] font-extrabold text-sky-900 bg-sky-100 border border-sky-400 rounded">
                      기안완료(印)
                    </span>
                  </div>
                  <div className="w-24 p-2 rounded-xl bg-white border border-slate-300 shadow-2xs">
                    <span className="text-[10px] font-semibold text-slate-600 block">부서장 검수</span>
                    <span className="text-xs font-extrabold text-slate-950 block my-0.5">
                      {activeSupNode?.data?.name ? String(activeSupNode.data.name).split(' ')[0] : '전담 팀장'}
                    </span>
                    <span className="inline-block px-1.5 py-0.5 text-[9.5px] font-extrabold text-emerald-900 bg-emerald-100 border border-emerald-400 rounded">
                      검수승인(印)
                    </span>
                  </div>
                  <div
                    className={`w-72 p-2.5 rounded-xl border shadow-2xs text-left space-y-2 ${
                      approvalStatus === 'APPROVED' ? 'bg-emerald-50 border-emerald-400' : 'bg-amber-50 border-amber-400'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-[10px] font-bold text-amber-900 block">최종 결재</span>
                        <span className="text-xs font-extrabold text-slate-950 block">신영호 대표</span>
                      </div>
                      {approvalStatus === 'APPROVED' ? (
                        <span className="px-2 py-1 text-[10.5px] font-black text-rose-700 border-2 border-rose-600 rounded-md rotate-[-6deg] bg-white">
                          결재완료(印)
                          <span className="block text-[8.5px] font-bold text-rose-600/90">{approvedAt}</span>
                        </span>
                      ) : (
                        <span className="px-1.5 py-0.5 text-[10px] font-extrabold text-amber-900 bg-amber-100 border border-amber-400 rounded">
                          ⏳ 결재 대기
                        </span>
                      )}
                    </div>
                    {approvalStatus !== 'APPROVED' && (
                      <>
                        <button
                          onClick={handleCeoApprove}
                          className="w-full px-2.5 py-1.5 text-[12px] font-extrabold bg-emerald-700 hover:bg-emerald-600 text-white rounded-lg border border-emerald-800 transition-all duration-200"
                        >
                          ✍️ 최종 결재 승인 확정
                        </button>
                        <div className="flex items-center gap-1.5">
                          <input
                            value={ceoRejectReason}
                            onChange={(e) => setCeoRejectReason(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !e.nativeEvent.isComposing) handleCeoReject();
                            }}
                            placeholder="반려 사유 (예: 협력사 Cpk 개선 대책 구체화)"
                            className="flex-1 min-w-0 px-2 py-1.5 text-[11.5px] font-medium text-slate-900 placeholder:text-slate-400 bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-rose-400"
                          />
                          <button
                            onClick={handleCeoReject}
                            disabled={!ceoRejectReason.trim()}
                            className="shrink-0 px-2 py-1.5 text-[11.5px] font-extrabold bg-rose-600 hover:bg-rose-500 disabled:bg-slate-300 disabled:text-slate-500 disabled:cursor-not-allowed text-white rounded-lg border border-rose-700 transition-all duration-200"
                          >
                            ↩️ 결재 반려
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {parsedReport.bannerNote && (
                <div className="px-4 py-3 rounded-xl bg-amber-50 border border-amber-400 text-slate-950 text-[13.5px] font-bold flex items-center gap-2">
                  <span>{parsedReport.bannerNote}</span>
                </div>
              )}

              <div className="space-y-4">
                {parsedReport.sections.map((sec, sIdx) => (
                  <div
                    key={sIdx}
                    className="p-5 rounded-2xl bg-[#fcfcfd] border border-slate-300 shadow-sm space-y-3.5"
                  >
                    <div className="flex items-center gap-2.5 border-b border-slate-200 pb-2.5">
                      <span className="px-2.5 py-0.5 text-xs font-extrabold rounded-lg bg-slate-900 text-white border border-slate-800">
                        SECTION 0{sIdx + 1}
                      </span>
                      <h4 className="text-[15.5px] font-extrabold text-slate-950 tracking-tight">{sec.title}</h4>
                    </div>

                    <div className="space-y-2.5">
                      {sec.bullets.map((b, bIdx) => (
                        <ReportBulletView key={`${sIdx}-${bIdx}`} text={b} idx={sIdx * 100 + bIdx} />
                      ))}
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
