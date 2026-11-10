import { NextRequest } from 'next/server';
import { buildReplayPart1, buildReplayPart2, ReplayTeamConfig } from '@/data/replayScenario';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const phase = searchParams.get('phase') || '1';
  const action = searchParams.get('action') || 'FORCE_APPROVE';
  const comment = searchParams.get('comment') || '';

  const cfg: ReplayTeamConfig = {
    supId: searchParams.get('supId') || 'sup-mkt-01',
    supName: searchParams.get('supName') || '김민준 팀장',
    supDept: searchParams.get('supDept') || '마케팅·커머스전략실',
    w1Id: searchParams.get('w1Id') || 'wrk-web-01',
    w1Name: searchParams.get('w1Name') || '이서연 수석',
    w1Dept: searchParams.get('w1Dept') || '웹데이터수집팀',
    w2Id: searchParams.get('w2Id') || 'wrk-doc-03',
    w2Name: searchParams.get('w2Name') || '박도윤 선임',
    w2Dept: searchParams.get('w2Dept') || '콘텐츠·리포트팀',
  };

  const sequence = phase === '1' ? buildReplayPart1(cfg) : buildReplayPart2(action, comment, cfg);
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      for (const item of sequence) {
        await new Promise((r) => setTimeout(r, item.delayMs));
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(item.event)}\n\n`));
      }
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'STREAM_END' })}\n\n`));
      controller.close();
    },
  });

  return new Response(stream, {
    headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive' },
  });
}
