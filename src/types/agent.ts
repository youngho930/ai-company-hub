export type AgentStatus = 'IDLE' | 'WORKING' | 'REVIEWING' | 'REJECTED' | 'DONE';

export interface EmployeeProfile {
  id: string;
  name: string;
  role: 'SUPERVISOR' | 'WORKER';
  dept: string;
  persona: string;
  skills: string[];
  summary: string;
  system_prompt: string;
  qc_criteria: string[];
  tools: string[];
}

export interface HitlPayload {
  supervisorName: string;
  workerName: string;
  rejectReason: string;
  latestDraft: string;
}

export interface AgentEvent {
  type: 'TEAM_ASSEMBLED' | 'STATUS_CHANGE' | 'MESSAGE' | 'QC_REJECT' | 'BROWSER_FRAME' | 'FINAL_REPORT' | 'HITL_REQUIRED' | 'STREAM_END';
  agentId: string;
  agentName: string;
  role: 'SUPERVISOR' | 'WORKER';
  timestamp: string;
  payload: {
    status?: AgentStatus;
    text?: string;
    rejectReason?: string;
    targetWorkerId?: string;
    screenshotUrl?: string;
    tokensUsed?: number;
    reportMarkdown?: string;
    nodes?: any[];
    edges?: any[];
    workerId?: string;
    workerName?: string;
    latestDraft?: string;
  };
}
