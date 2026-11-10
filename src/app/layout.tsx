import './globals.css';
import React from 'react';

export const metadata = {
  title: 'AI Company Mission Control | 신영호 포트폴리오',
  description: '100명의 가상 직원과 팀장 QC 반려 루프를 갖춘 멀티 에이전트 오케스트레이션 시스템',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="dark">
      <body className="antialiased bg-slate-950 text-slate-100">{children}</body>
    </html>
  );
}
