// src/lib/constants.ts

import { StepInfo } from '@/types/survey';

// 6단계 UI 스텝 정의
export const STEPS: StepInfo[] = [
  {
    id: 1,
    name: '설문 개요 설정',
    description: '설문 목적, 대상, 기간 설정',
    status: 'pending',
    backendNodes: ['set_survey_objective'],
  },
  {
    id: 2,
    name: 'DB 사용 여부',
    description: 'RAG 참조 데이터 선택',
    status: 'pending',
    backendNodes: ['select_database'],
  },
  {
    id: 3,
    name: '설문 영역 설정',
    description: '주요 측정 영역 정의 및 검토',
    status: 'pending',
    backendNodes: ['set_survey_areas', 'review_area_structure'],
  },
  {
    id: 4,
    name: '세부 항목 설정',
    description: '문항별 상세 설정 및 검토',
    status: 'pending',
    backendNodes: ['set_detailed_items', 'review_detailed_items_structure'],
  },
  {
    id: 5,
    name: '레이아웃 생성',
    description: '설문지 구조 배치',
    status: 'pending',
    backendNodes: ['set_layout_composition'],
  },
  {
    id: 6,
    name: '설문지 생성',
    description: '최종 산출물 생성',
    status: 'pending',
    backendNodes: ['generate_and_review_survey', 'finalize_and_refine_survey', 'create_draft'],
  },
];

// 필드명 → 표시명 매핑
export const FIELD_NAMES: Record<string, string> = {
  intent: '설문 목표',
  hierarchical_structure: '단계별 영역',
  section_items: '세부 항목',
  layout_setting: '레이아웃 설정',
  survey_draft: '설문지 초안',
  final_survey: '최종 설문지',
  area_review_message: '영역 검토 메시지',
  detailed_items_review_message: '세부 항목 검토 메시지',
  survey_review_message: '설문 검토 메시지',
  graph_item_questions: '그래프 기반 추천 문항',
};

// 중요 필드 (우측 패널에 표시할 필드들) - 우선순위 순서
export const IMPORTANT_FIELDS = [
  'final_survey',
  'survey_draft',
  'layout_setting',
  'section_items',
  'hierarchical_structure',
  'intent',
  'survey_review_message',
  'detailed_items_review_message',
  'area_review_message',
];

// 레이아웃 코드 정보
export const LAYOUT_CODE_INFO: Record<string, { code: string; name: string; description: string; example: string }> = {
  OQ: {
    code: 'OQ',
    name: '오픈형',
    description: '응답자가 자유롭게 의견을 서술하는 방식입니다.',
    example: "서비스 이용 중 가장 불만족스러웠던 점은 무엇입니까?' (텍스트 입력칸)",
  },
  SC: {
    code: 'SC',
    name: 'Single Choice (선다형)',
    description: '여러 선택지 중 오직 하나만 선택하도록 합니다.',
    example: '( ) 매우 그렇다 ( ) 그렇다 ( ) 보통이다 ( ) 그렇지 않다',
  },
  MA: {
    code: 'MA',
    name: 'Multiple Answer (복수 응답형)',
    description: '여러 선택지 중 하나 이상, 즉 다수를 선택할 수 있도록 합니다.',
    example: "가장 자주 사용하는 SNS 채널을 모두 선택하세요.' [ ] 인스타그램 [ ] 페이스북 [ ] X",
  },
  DC: {
    code: 'DC',
    name: 'Dichotomous (이분형)',
    description: '응답 선택지가 두 가지로만 제한됩니다.',
    example: "귀하는 만 19세 이상이십니까?' ( ) 예 ( ) 아니오",
  },
  RS: {
    code: 'RS',
    name: 'Rating Scale (척도형)',
    description: '특정 항목에 대한 정도나 수준을 측정하는 방식입니다.',
    example: '강의 만족도를 1점(매우 불만족)부터 5점(매우 만족)까지 평가해 주세요.',
  },
  RK: {
    code: 'RK',
    name: 'Ranking (순위형)',
    description: '제시된 항목들을 응답자의 선호도나 중요도에 따라 순서대로 나열하게 합니다.',
    example: '다음 4가지 옵션을 선호하는 순서대로 1위부터 4위까지 나열하세요.',
  },
  MG: {
    code: 'MG',
    name: 'Matrix / Grid (매트릭스/표 형식)',
    description: '여러 개의 항목(행)에 대해 동일한 응답 척도(열)를 반복 적용하여 표 형태로 구성합니다.',
    example: "각 제품에 대해 '만족도'와 '재구매 의향'을 평가하세요. (척도: 매우 낮음 ~ 매우 높음)",
  },
};

// API 엔드포인트 (백엔드 연결 시 수정)
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';