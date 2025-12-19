// src/app/page.tsx

'use client';

import Link from 'next/link';
import { ClipboardList, History, Plus, Sparkles, Network } from 'lucide-react';
import { useSurveyStore } from '@/stores/survey-store';
import ProgressPanel from '@/components/progress/ProgressPanel';
import ChatPanel from '@/components/chat/ChatPanel';
import PreviewPanel from '@/components/preview/PreviewPanel';
import { resetSurvey as resetSurveyAPI } from '@/lib/api';

export default function Home() {
  const { sessionId, reset } = useSurveyStore();

  const handleNewSurvey = async () => {
    if (sessionId) {
      try {
        await resetSurveyAPI(sessionId);
      } catch (error) {
        console.error('리셋 오류:', error);
      }
    }
    reset();
    window.location.reload();
  };

  return (
    <div className="flex flex-col h-screen gradient-bg">
      {/* 헤더 */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-white/10 bg-slate-900/80 backdrop-blur-lg flex-shrink-0">
        <div className="flex items-center gap-3">
          {/* 로고 */}
          <div className="flex items-center justify-center w-10 h-10 rounded-xl gradient-primary shadow-lg">
            <ClipboardList className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-white tracking-tight">
                Survey Builder AI
              </h1>
              <Sparkles className="w-4 h-4 text-orange-400 animate-pulse" />
            </div>
            <p className="text-xs text-slate-400">
              RAG 기반 설문지 생성 시스템
            </p>
          </div>
        </div>
        
        {/* 헤더 버튼 */}
        <div className="flex gap-2">
          {/* 챗봇 버튼 (현재 페이지) */}
          <Link href="/">
            <button className="flex items-center gap-2 px-4 py-2 text-sm text-white gradient-primary rounded-lg shadow-lg">
              💬 챗봇
            </button>
          </Link>
          
          {/* GraphRAG 버튼 */}
          <Link href="/graph-explorer">
            <button className="flex items-center gap-2 px-4 py-2 text-sm text-slate-300 border border-slate-600 rounded-lg hover:bg-slate-800/50 hover:border-orange-500 transition-all duration-200">
              <Network className="w-4 h-4" />
              GraphRAG
            </button>
          </Link>
          
          {/* 히스토리 버튼 */}
          <button className="flex items-center gap-2 px-4 py-2 text-sm text-slate-300 border border-slate-600 rounded-lg hover:bg-slate-800/50 hover:border-slate-500 transition-all duration-200">
            <History className="w-4 h-4" />
            히스토리
          </button>
          
          {/* 새 설문 버튼 */}
          <button
            onClick={handleNewSurvey}
            className="flex items-center gap-2 px-4 py-2 text-sm text-white gradient-primary rounded-lg hover:opacity-90 transition-all duration-200 shadow-lg hover:shadow-orange-500/50"
          >
            <Plus className="w-4 h-4" />
            새 설문
          </button>
        </div>
      </header>

      {/* 메인 콘텐츠 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 좌측: 진행 패널 */}
        <aside className="w-72 border-r border-white/10 bg-slate-900/30 backdrop-blur-sm overflow-y-auto flex-shrink-0">
          <ProgressPanel />
        </aside>

        {/* 중앙: 챗봇 패널 */}
        <main className="flex-1 flex flex-col bg-slate-800/20 min-w-0 overflow-hidden">
          <ChatPanel />
        </main>

        {/* 우측: 미리보기 패널 - 너비 1.2배 확대 (w-96=384px → w-[460px]) */}
        <aside className="w-[460px] border-l border-white/10 bg-slate-900/30 backdrop-blur-sm overflow-y-auto flex-shrink-0">
          <PreviewPanel />
        </aside>
      </div>
    </div>
  );
}