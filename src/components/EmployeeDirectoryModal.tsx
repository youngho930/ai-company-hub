'use client';
import React, { useState, useMemo } from 'react';
import { EmployeeProfile } from '@/types/agent';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  employees: EmployeeProfile[];
  activeAgentIds: string[];
  onConfirmManualTeam: (supervisor: EmployeeProfile, workers: EmployeeProfile[]) => void;
}

export default function EmployeeDirectoryModal({ isOpen, onClose, employees, activeAgentIds, onConfirmManualTeam }: Props) {
  const [selectedDept, setSelectedDept] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [pickedSup, setPickedSup] = useState<EmployeeProfile | null>(null);
  const [pickedWorkers, setPickedWorkers] = useState<EmployeeProfile[]>([]);

  const departments = useMemo(() => ['ALL', ...Array.from(new Set(employees.map((e) => e.dept)))], [employees]);

  const filtered = useMemo(() => {
    return employees.filter((e) => {
      const mDept = selectedDept === 'ALL' || e.dept === selectedDept;
      const mSearch = !searchQuery.trim() || e.name.includes(searchQuery) || e.summary.includes(searchQuery) || e.skills.some((s) => s.includes(searchQuery));
      return mDept && mSearch;
    });
  }, [employees, selectedDept, searchQuery]);

  if (!isOpen) return null;

  const togglePick = (emp: EmployeeProfile) => {
    if (emp.role === 'SUPERVISOR') {
      setPickedSup((prev) => (prev?.id === emp.id ? null : emp));
    } else {
      setPickedWorkers((prev) => {
        if (prev.some((w) => w.id === emp.id)) return prev.filter((w) => w.id !== emp.id);
        if (prev.length >= 4) return prev;
        return [...prev, emp];
      });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-6 select-none">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-6xl h-[86vh] flex flex-col overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 bg-slate-950 border-b border-slate-800">
          <h2 className="text-base font-bold text-slate-100">📋 전사 AI 에이전트 100명 인사 기록부 (클릭하여 수동 차출 가능)</h2>
          <button onClick={onClose} className="px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 rounded-lg">✕ 닫기</button>
        </div>

        <div className="p-4 bg-slate-900 border-b border-slate-800 space-y-2.5">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="이름, 부서, 보유 스킬(#크롤링, #통계) 검색..."
            className="w-full px-4 py-2 text-xs bg-slate-950 border border-slate-700 rounded-lg text-slate-100"
          />
          <div className="flex gap-2 overflow-x-auto pb-1">
            {departments.map((d) => (
              <button
                key={d}
                onClick={() => setSelectedDept(d)}
                className={`px-3 py-1 text-xs rounded-full shrink-0 border ${
                  selectedDept === d ? 'bg-emerald-600/20 border-emerald-500 text-emerald-300' : 'bg-slate-950 border-slate-800 text-slate-400'
                }`}
              >
                {d === 'ALL' ? '전체 부서 (100명)' : d}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 p-5 overflow-y-auto grid grid-cols-1 md:grid-cols-3 gap-3.5 auto-rows-max">
          {filtered.map((emp) => {
            const isPicked = pickedSup?.id === emp.id || pickedWorkers.some((w) => w.id === emp.id);
            const isActive = activeAgentIds.includes(emp.id);
            return (
              <div
                key={emp.id}
                onClick={() => togglePick(emp)}
                className={`p-4 rounded-xl border transition cursor-pointer flex flex-col justify-between ${
                  isPicked ? 'border-amber-400 bg-amber-950/25' : isActive ? 'border-emerald-500 bg-emerald-950/20' : 'border-slate-800 bg-slate-950/70 hover:border-slate-600'
                }`}
              >
                <div>
                  <div className="flex justify-between text-[11px] mb-1.5">
                    <span className="text-slate-400">{emp.dept}</span>
                    <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${isPicked ? 'bg-amber-400 text-slate-950' : 'bg-slate-800 text-slate-300'}`}>
                      {isPicked ? '✓ 차출 선택됨' : emp.role === 'SUPERVISOR' ? '+ 팀장 지정' : '+ 실무자 추가'}
                    </span>
                  </div>
                  <div className="font-bold text-sm text-white mb-1">{emp.name} <span className="text-[11px] font-normal text-sky-400">({emp.persona})</span></div>
                  <p className="text-xs text-slate-300 line-clamp-2 mb-2.5">{emp.summary}</p>
                </div>
                <div className="flex flex-wrap gap-1">
                  {emp.skills.map((s) => (
                    <span key={s} className="px-2 py-0.5 text-[10px] bg-slate-900 border border-slate-700 text-slate-300 rounded">#{s}</span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        <div className="px-6 py-3.5 bg-slate-950 border-t border-slate-800 flex items-center justify-between">
          <div className="text-xs flex items-center gap-4">
            <span>👑 팀장: <strong className="text-indigo-400">{pickedSup ? pickedSup.name : '미선택'}</strong></span>
            <span>🛠️ 실무자({pickedWorkers.length}/4): <strong className="text-emerald-400">{pickedWorkers.map((w) => w.name).join(', ') || '미선택'}</strong></span>
          </div>
          <button
            disabled={!pickedSup || pickedWorkers.length === 0}
            onClick={() => { if (pickedSup) { onConfirmManualTeam(pickedSup, pickedWorkers); onClose(); } }}
            className="px-5 py-2 text-xs font-bold bg-amber-500 hover:bg-amber-400 disabled:bg-slate-800 disabled:text-slate-600 text-slate-950 rounded-lg"
          >
            ⚡ 이 구성으로 즉시 팀 편성
          </button>
        </div>
      </div>
    </div>
  );
}
