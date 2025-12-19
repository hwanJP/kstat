// src/components/progress/ProgressPanel.tsx

'use client';

import { useSurveyStore } from '@/stores/survey-store';
import {
  Target,
  Database,
  LayoutGrid,
  ListChecks,
  Palette,
  FileText,
  Check,
  Circle,
} from 'lucide-react';

const stepIcons = [Target, Database, LayoutGrid, ListChecks, Palette, FileText];

export default function ProgressPanel() {
  const { currentStep, steps, isComplete } = useSurveyStore();

  return (
    <div className="h-full p-6">
      <h2 className="font-semibold text-lg mb-6 text-white flex items-center gap-2">
        <Circle className="w-5 h-5 text-orange-400" />
        진행 상황
      </h2>
      
      <div className="space-y-1">
        {steps.map((step, index) => {
          const Icon = stepIcons[index];
          const stepNumber = index + 1;
          const isCompleted = stepNumber < currentStep || isComplete;
          const isCurrent = stepNumber === currentStep && !isComplete;

          return (
            <div key={step.id} className="relative">
              {/* 연결선 - 개선됨 */}
              {index < steps.length - 1 && (
                <div
                  className={`absolute left-5 top-12 w-0.5 h-8 transition-all duration-300 ${
                    isCompleted 
                      ? 'bg-gradient-to-b from-emerald-500 to-emerald-600' 
                      : 'bg-slate-700/50'
                  }`}
                />
              )}
              
              <div
                className={`relative flex items-center gap-3 p-3 rounded-xl transition-all duration-300 ${
                  isCurrent
                    ? 'glass border border-orange-500/50 glow-orange'
                    : isCompleted
                    ? 'bg-emerald-500/10 border border-emerald-500/30'
                    : 'bg-slate-800/30 border border-white/5'
                }`}
              >
                {/* 아이콘 - 개선됨 */}
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
                    isCompleted
                      ? 'bg-gradient-to-br from-emerald-500 to-emerald-600 text-white shadow-lg'
                      : isCurrent
                      ? 'gradient-primary text-white shadow-lg animate-pulse'
                      : 'bg-slate-700/50 text-slate-400'
                  }`}
                >
                  {isCompleted ? (
                    <Check className="w-5 h-5" />
                  ) : (
                    <Icon className="w-5 h-5" />
                  )}
                </div>
                
                {/* 텍스트 */}
                <div className="flex-1 min-w-0">
                  <p
                    className={`text-sm font-medium truncate transition-colors duration-300 ${
                      isCompleted
                        ? 'text-emerald-400'
                        : isCurrent
                        ? 'text-orange-300'
                        : 'text-slate-400'
                    }`}
                  >
                    {step.name}
                  </p>
                  {step.description && (
                    <p className="text-xs text-slate-500 truncate mt-0.5">
                      {step.description}
                    </p>
                  )}
                </div>
                
                {/* 상태 뱃지 - 개선됨 */}
                {isCurrent && (
                  <span className="text-xs bg-orange-500/20 text-orange-400 px-2.5 py-1 rounded-full font-medium border border-orange-500/30">
                    진행중
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
      
      {/* 완료 표시 - 개선됨 */}
      {isComplete && (
        <div className="mt-6 p-4 bg-gradient-to-br from-emerald-500/20 to-emerald-600/20 rounded-xl border border-emerald-500/30 shadow-lg">
          <div className="flex items-center gap-3 text-emerald-400">
            <div className="w-10 h-10 bg-emerald-500 rounded-full flex items-center justify-center shadow-lg">
              <Check className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="font-semibold">설문 작성 완료!</p>
              <p className="text-xs text-emerald-300">파일을 내보내실 수 있습니다</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}