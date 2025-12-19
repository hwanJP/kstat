// src/stores/survey-store.ts

/**
 * Survey Builder의 전역 상태를 관리하는 Zustand Store.
 * 
 * 주요 역할:
 * 1. LangGraph 기반 설문 생성 프로세스의 현재 상태 관리
 * 2. 대화형 메시지 관리 (ChatPanel)
 * 3. 단계(ProgressPanel) 및 미리보기(PreviewPanel) 관리
 * 4. 서버(LangGraph) 응답과 프론트 상태를 동기화하는 핵심 엔진 역할
 */

import { create } from 'zustand';
import { STEPS } from '@/lib/constants';
import type { Message, StepInfo, PreviewData } from '@/types/survey';

/**
 * Zustand Store의 타입 정의
 * - sessionId: 서버 세션과 연결
 * - currentStep: LangGraph의 진행 단계
 * - messages: 사용자/AI 대화 리스트
 * - surveyState: LangGraph의 내부 상태(JSON)
 * - activePreview: 최근 수정된 Preview 항목
 * - allFields: 모든 Preview 필드 (추후 확장 가능)
 */

interface SurveyStore {
  // 세션
  sessionId: string | null;
  
  // 단계
  currentStep: number;
  steps: StepInfo[];
  
  // 메시지
  messages: Message[];
  
  // 상태
  isProcessing: boolean;
  isComplete: boolean;
  surveyState: Record<string, unknown>;
  
  // 미리보기
  activePreview: PreviewData | null;
  allFields: Record<string, string>;
  
  // 생성된 설문
  generatedSurvey: {
    questions: any[];
    metadata?: any;
  } | null;
  
  /**
   * 상태 업데이트 액션들
   */
  setSessionId: (id: string) => void;
  setCurrentStep: (step: number) => void;
  setMessages: (messages: Message[]) => void;
  addMessage: (role: 'user' | 'assistant', content: string) => void;
  setIsProcessing: (processing: boolean) => void;
  setIsComplete: (complete: boolean) => void;
  setSurveyState: (state: Record<string, unknown>) => void;
  updateSurveyState: (updates: Partial<Record<string, unknown>>) => void;  // 🆕 추가
  setActivePreview: (preview: PreviewData | null) => void;
  setAllFields: (fields: Record<string, string>) => void;
  
  // 생성된 설문 설정
  setGeneratedSurvey: (survey: { questions: any[]; metadata?: any } | null) => void;

  /**
   * 서버 응답(API → LangGraph)을 받아
   * 프론트 전체 상태를 갱신하는 핵심 동기화 함수
   */
  updateFromResponse: (response: {
    session_id: string;
    messages: { role: string; content: string }[];
    state: Record<string, unknown>;
    current_step: number;
    is_complete: boolean;
    changed_field?: string;
    changed_value?: string;
  }) => void;
  
  // 전체 Store 초기화
  reset: () => void;
}

/**
 * 초기 상태 정의
 */
const initialState = {
  sessionId: null,
  currentStep: 1,
  steps: STEPS,
  messages: [],
  isProcessing: false,
  isComplete: false,
  surveyState: {},
  activePreview: null,
  allFields: {},
  generatedSurvey: null,
};

/**
 * Zustand Store 생성
 */
export const useSurveyStore = create<SurveyStore>((set, get) => ({
  // ----- 초기 상태 로드 -----
  ...initialState,

  // ----- Setter 함수들 -----

  // 서버 세션 ID 설정
  setSessionId: (id) => set({ sessionId: id }),

  // LangGraph 단계 설정
  setCurrentStep: (step) => set({ currentStep: step }),

  // 메시지 전체를 덮어쓰기 (주로 서버 응답 시 사용)
  setMessages: (messages) => set({ messages }),

  // 메시지 추가 (사용자 입력 시 화면에 먼저 표시)
  addMessage: (role, content) =>
    set((state) => ({
      messages: [...state.messages, { 
        id: `msg_${Date.now()}`,
        role, 
        content,
        timestamp: new Date()
      }],
    })),

  // 로딩 상태 설정
  setIsProcessing: (processing) => set({ isProcessing: processing }),

  // 전체 완료 여부 설정
  setIsComplete: (complete) => set({ isComplete: complete }),

  // LangGraph 전체 상태 저장 (전체 교체)
  setSurveyState: (surveyState) => set({ surveyState }),

  // 🆕 LangGraph 상태 부분 업데이트 (미리보기에서 수정 시 사용)
  updateSurveyState: (updates) =>
    set((state) => ({
      surveyState: { ...state.surveyState, ...updates },
    })),

  // 특정 Preview 항목 활성화
  setActivePreview: (preview) => set({ activePreview: preview }),

  // Preview 전체 필드 저장(추후 편집 기능 등에서 사용 가능)
  setAllFields: (fields) => set({ allFields: fields }),

  // 생성된 설문 설정
  setGeneratedSurvey: (survey) => set({ generatedSurvey: survey }),

  /**
   * ★ 핵심 기능:
   * API 응답을 받아 프론트 전체 상태를 갱신하는 함수
   *
   * ChatPanel, ProgressPanel, PreviewPanel이
   * 모두 이 함수로부터 업데이트를 받는다.
   */
  updateFromResponse: (response) => {
    // 1) 메시지 포맷 정리: 서버 role → 클라이언트 role 매핑
    const messages: Message[] = response.messages.map((m, idx) => ({
      id: `msg_${Date.now()}_${idx}`,
      role: m.role as 'user' | 'assistant',
      content: m.content,
      timestamp: new Date()
    }));
    
    // 2) PreviewPanel 업데이트 정보 생성
    let activePreview: PreviewData | null = null;
    if (response.changed_field && response.changed_value) {
      activePreview = {
        field: response.changed_field,
        content: response.changed_value,
      };
    }
    
    // 3) 전체 상태 업데이트
    //    - 메시지
    //    - LangGraph 내부 state
    //    - 현재 단계
    //    - 완료 여부
    //    - 최근 변경 Preview
    set({
      sessionId: response.session_id,
      messages,
      surveyState: response.state,
      currentStep: response.current_step,
      isComplete: response.is_complete,
      activePreview,
    });
  },

  /**
   * Store 전체 초기화
   * 새로운 설문 시작 시 사용
   */
  reset: () => set(initialState),
}));