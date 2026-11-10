'use client';
import React, { useState } from 'react';
import { HitlPayload } from '@/types/agent';

interface Props {
  hitlData: HitlPayload | null;
  onDecision: (action: 'FORCE_APPROVE' | 'RETRY_WITH_GUIDE', comment: string) => void;
}

export default function CEOInterventionModal({ hitlData, onDecision }: Props) {
  const [comment, setComment] = useState('');
  if (!hitlData) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-6 select-none">
      <div className="bg-slate-900 border-2 border-rose-500 rounded-2xl w-full max-w-2xl overflow-hidden shadow-[0_0_40px_rgba(244,63,94,0.35)]">
        <div className="px-6 py-4 bg-rose-950/60 border-b border-rose-500/40 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="px-2.5 py-1 text-xs font-extrabold bg-rose-600 text-white rounded animate-pulse">🚨 HUMAN-IN-THE-LOOP</span>
            <h2 className="text-base font-bold text-rose-100">품질 검수 3회 연속 반려 — CEO 긴급 결재 요청</h2>
          </div>
          <span className="text-xs font-mono text-rose-300">WORKFLOW PAUSED ⏸️</span>
        </div>

        <div className="p-6 space-y-4">
          <div className="p-3.5 rounded-xl bg-rose-950/30 border border-rose-500/40">
            <div className="text-[11px] font-bold text-rose-400 mb-1">❌ {hitlData.supervisorName}의 3차 반려 사유 (대상: {hitlData.workerName})</div>
            <p className="text-xs text-rose-100">{hitlData.rejectReason}</p>
          </div>

          <div>
            <div className="text-[11px] font-semibold text-slate-400 mb-1">📄 {hitlData.workerName}의 현재 제출 초안</div>
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 max-h-32 overflow-y-auto whitespace-pre-wrap font-mono">
              {hitlData.latestDraft}
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-emerald-400 mb-1">✍️ CEO 특별 가이드라인 입력 (선택)</label>
            <textarea
              rows={2}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="예: 비회원 열람 불가 쿠폰가는 정가 기준으로 표기하고 바로 승인 진행해!"
              className="w-full p-3 text-xs bg-slate-950 border border-slate-700 rounded-xl text-slate-100 focus:outline-none focus:border-emerald-500"
            />
          </div>
        </div>

        <div className="px-6 py-4 bg-slate-950 border-t border-slate-800 flex justify-end gap-3">
          <button
            onClick={() => {
              onDecision('RETRY_WITH_GUIDE', comment || 'CEO 특별 가이드 반영 재수집');
              setComment('');
            }}
            className="px-4 py-2.5 text-xs font-bold bg-slate-800 hover:bg-slate-700 text-amber-300 border border-amber-500/40 rounded-xl"
          >
            🎯 가이드 주입 후 재작업 지시
          </button>
          <button
            onClick={() => {
              onDecision('FORCE_APPROVE', comment);
              setComment('');
            }}
            className="px-5 py-2.5 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl"
          >
            ⚡ 현재 초안으로 직권 강제 승인
          </button>
        </div>
      </div>
    </div>
  );
}
