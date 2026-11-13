import { create } from 'zustand';
import { Node, Edge } from '@xyflow/react';
import { AgentEvent, HitlPayload } from '@/types/agent';

export type OfficeThemeId = 'classic' | 'space' | 'factory' | 'quantum';

export interface BrowserFrameItem {
  step: string;
  url: string;
}

interface OfficeState {
  missionRunId: number;
  officeTheme: OfficeThemeId;
  nodes: Node[];
  edges: Edge[];
  messages: AgentEvent[];
  currentFrame: string | null;
  browserHistory: BrowserFrameItem[];
  finalReport: string | null;
  hitlData: HitlPayload | null;
  metrics: { activeAgents: number; tokens: number; cost: number; rejections: number };
  setOfficeTheme: (theme: OfficeThemeId) => void;
  dispatchEvent: (event: AgentEvent) => void;
  clearHitl: () => void;
  resetMission: (preserveTeam?: boolean) => void;
}

export const useOfficeStore = create<OfficeState>((set) => ({
  missionRunId: 0,
  officeTheme: 'classic',
  nodes: [],
  edges: [],
  messages: [],
  currentFrame: null,
  browserHistory: [],
  finalReport: null,
  hitlData: null,
  metrics: { activeAgents: 0, tokens: 0, cost: 0, rejections: 0 },

  setOfficeTheme: (theme) => set({ officeTheme: theme }),

  clearHitl: () => set({ hitlData: null }),
  resetMission: (preserveTeam = false) =>
    set((state) => ({
      missionRunId: state.missionRunId + 1,
      nodes: preserveTeam
        ? state.nodes.map((n) => ({ ...n, data: { ...n.data, status: n.id === 'ceo' ? 'DONE' : 'IDLE' } }))
        : [],
      edges: preserveTeam ? state.edges : [],
      messages: [],
      currentFrame: null,
      browserHistory: [],
      finalReport: null,
      hitlData: null,
      metrics: {
        activeAgents: preserveTeam ? Math.max(0, state.nodes.length - 1) : 0,
        tokens: 0,
        cost: 0,
        rejections: 0,
      },
    })),

  dispatchEvent: (event) =>
    set((state) => {
      const addedTokens = event.payload?.tokensUsed || 0;
      const newMetrics = {
        ...state.metrics,
        tokens: state.metrics.tokens + addedTokens,
        cost: state.metrics.cost + addedTokens * 0.000003,
        rejections: event.type === 'QC_REJECT' ? state.metrics.rejections + 1 : state.metrics.rejections,
      };

      if (event.type === 'TEAM_ASSEMBLED') {
        return {
          ...state,
          nodes: event.payload.nodes || [],
          edges: event.payload.edges || [],
          metrics: { ...newMetrics, activeAgents: Math.max(0, (event.payload.nodes?.length || 1) - 1) },
        };
      }

      if (event.type === 'HITL_REQUIRED') {
        return {
          ...state,
          metrics: { ...newMetrics, rejections: 3 },
          hitlData: {
            supervisorName: event.agentName,
            workerName: event.payload.workerName || '실무자',
            rejectReason: event.payload.rejectReason || '',
            latestDraft: event.payload.latestDraft || '',
          },
        };
      }

      const targetRejectedWorker = event.payload?.targetWorkerId;
      const updatedNodes = state.nodes.map((node) => {
        if (event.type === 'QC_REJECT' && targetRejectedWorker && node.id === targetRejectedWorker) {
          return { ...node, data: { ...node.data, status: 'REJECTED' } };
        }
        if (node.id === event.agentId && event.payload?.status) {
          return { ...node, data: { ...node.data, status: event.payload.status } };
        }
        return node;
      });

      const nextHistory =
        event.type === 'BROWSER_FRAME' && event.payload.screenshotUrl
          ? [...state.browserHistory, { step: event.timestamp || `Step ${state.browserHistory.length + 1}`, url: event.payload.screenshotUrl }]
          : state.browserHistory;

      return {
        ...state,
        nodes: updatedNodes,
        messages: ['MESSAGE', 'QC_REJECT'].includes(event.type) ? [...state.messages, event] : state.messages,
        currentFrame: event.type === 'BROWSER_FRAME' ? event.payload.screenshotUrl! : state.currentFrame,
        browserHistory: nextHistory,
        finalReport: event.type === 'FINAL_REPORT' ? event.payload.reportMarkdown! : state.finalReport,
        metrics: newMetrics,
      };
    }),
}));
