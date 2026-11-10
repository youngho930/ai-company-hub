import { Handle, Position } from '@xyflow/react';
import { AgentStatus } from '@/types/agent';

const statusStyles: Record<AgentStatus, string> = {
  IDLE: 'border-slate-700 bg-slate-900/90 text-slate-400',
  WORKING: 'border-emerald-500 bg-emerald-950/60 text-emerald-300 shadow-[0_0_15px_rgba(16,185,129,0.35)] animate-pulse',
  REVIEWING: 'border-amber-500 bg-amber-950/50 text-amber-300',
  REJECTED: 'border-rose-500 bg-rose-950/60 text-rose-300 shadow-[0_0_15px_rgba(244,63,94,0.45)]',
  DONE: 'border-sky-500 bg-sky-950/40 text-sky-300',
};

export default function AgentCustomNode({ data }: { data: { name: string; dept: string; status: AgentStatus } }) {
  const st = data.status || 'IDLE';
  return (
    <div className={`px-4 py-2.5 rounded-xl border-2 transition-all duration-300 min-w-[155px] ${statusStyles[st]}`}>
      <Handle type="target" position={Position.Top} className="!bg-slate-400" />
      <div className="text-[10px] uppercase tracking-wider opacity-75">{data.dept}</div>
      <div className="font-bold text-sm mt-0.5">{data.name}</div>
      <div className="mt-1.5 inline-block px-2 py-0.5 text-[10px] rounded bg-black/40 font-mono">● {st}</div>
      <Handle type="source" position={Position.Bottom} className="!bg-slate-400" />
    </div>
  );
}
