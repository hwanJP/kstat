// src/types/survey.ts

// 메시지 타입
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

// 6단계 UI 스텝 정의
export interface StepInfo {
  id: number;
  name: string;
  description: string;
  status: 'completed' | 'current' | 'pending';
  backendNodes: string[]; // 해당 단계에 포함된 백엔드 노드들
}

// 설문 영역 (섹션)
export interface SurveySection {
  name: string;
  status: 'confirmed' | 'reviewing' | 'draft';
  items: string[];
}

// 레이아웃 설정 항목
export interface LayoutSettingItem {
  item: string;
  layout_code: string;
  layout_description: string;
  layout_name?: string;
  layout_full_description?: string;
  layout_example?: string;
}

// 미리보기 패널에 표시할 데이터
export interface PreviewData {
  field: string;
  displayName: string;
  value: string;
}

// 백엔드 SurveyState 미러링
export interface SurveyState {
  // 메시지
  messages: Message[];
  executed_nodes: string[];
  current_node?: string;

  // Step 1: 설문 개요
  intent?: string;
  survey_objective_question_step?: number;
  survey_objective_completed?: boolean;

  // Step 2: DB 선택
  database_choice?: '기존_설문_DB' | '별도_설문지';
  survey_type?: string;
  database_selection_completed?: boolean;

  // Step 3: 영역 설정 + 검토
  hierarchical_structure?: string;
  area_setting_method?: '참고_제안' | '직접_설정';
  survey_areas_completed?: boolean;
  area_review_message?: string;
  area_structure_review_completed?: boolean;

  // Step 4: 세부 항목 + 검토
  section_items?: string;
  items_setting_method?: '참고_제안' | '직접_작성';
  detailed_items_completed?: boolean;
  detailed_items_review_message?: string;
  detailed_items_review_completed?: boolean;

  // Step 5: 레이아웃
  layout_setting?: string; // JSON 문자열
  layout_composition_completed?: boolean;

  // Step 6: 설문지 생성
  survey_draft?: string;
  graph_item_questions?: string;
  survey_generation_completed?: boolean;
  final_survey?: string;
  survey_review_message?: string;
  survey_finalization_completed?: boolean;
  draft_creation_completed?: boolean;
}

// API 응답 타입
export interface ChatResponse {
  messages: string[];
  state: Partial<SurveyState>;
  current_step: number;
  changed_fields: Record<string, string>;
  latest_field?: string;
  is_complete: boolean;
}