# backend/app/services/workflow.py

"""
LangGraph 기반 설문 작성 워크플로우
- 10개 노드로 구성된 설문 작성 프로세스
"""

import os
import re
import json
from typing import TypedDict, Annotated, Optional, List, Dict, Any
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from .graphrag import (
    init_graphrag,
    is_initialized as is_graphrag_initialized,
    find_similar_areas_and_items,
    find_similar_survey_categories_and_areas,
    get_graphrag_context_from_section_items,
    extract_area_names_from_hierarchical_structure,
    extract_item_keywords_from_section_items,
    find_similar_items_and_questions,
)

load_dotenv()

# OpenAI API 키
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# LLM 초기화
llm = None
if OPENAI_API_KEY:
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.7,
        api_key=OPENAI_API_KEY
    )

# 레이아웃 코드 정보 (상세 설명 및 예시 포함)
LAYOUT_CODE_INFO = {
    "OQ": {
        "code": "OQ",
        "name": "오픈형",
        "description": "응답자가 자유롭게 의견을 서술하는 방식입니다. 정성적(Qualitative) 데이터 수집에 필수적이며, 깊이 있는 통찰력이나 예상치 못한 아이디어를 얻을 수 있습니다.",
        "example": "서비스 이용 중 가장 불만족스러웠던 점은 무엇입니까?' (텍스트 입력칸)"
    },
    "SC": {
        "code": "SC",
        "name": "Single Choice (선다형)",
        "description": "여러 선택지 중 오직 하나만 선택하도록 합니다. 응답이 상호 배타적일 때 사용하며, 가장 일반적인 폐쇄형 질문 유형입니다.",
        "example": "( ) 매우 그렇다 ( ) 그렇다 ( ) 보통이다 ( ) 그렇지 않다"
    },
    "MA": {
        "code": "MA",
        "name": "Multiple Answer (복수 응답형)",
        "description": "여러 선택지 중 하나 이상, 즉 다수를 선택할 수 있도록 합니다. 응답자의 다양한 선호나 경험을 파악할 때 유용합니다.",
        "example": "가장 자주 사용하는 SNS 채널을 모두 선택하세요.' [ ] 인스타그램 [ ] 페이스북 [ ] X"
    },
    "DC": {
        "code": "DC",
        "name": "Dichotomous (이분형)",
        "description": "응답 선택지가 두 가지로만 제한됩니다. 명확한 찬반이나 확인(예/아니오)을 측정할 때 사용합니다.",
        "example": "귀하는 만 19세 이상이십니까?' ( ) 예 ( ) 아니오"
    },
    "RS": {
        "code": "RS",
        "name": "Rating Scale (척도형)",
        "description": "특정 항목에 대한 정도나 수준을 측정하는 방식입니다. 리커트 척도(동의 정도), 만족도 척도, 중요도 척도 등이 포함됩니다.",
        "example": "강의 만족도를 1점(매우 불만족)부터 5점(매우 만족)까지 평가해 주세요."
    },
    "RK": {
        "code": "RK",
        "name": "Ranking (순위형)",
        "description": "제시된 항목들을 응답자의 선호도나 중요도에 따라 순서대로 나열하게 합니다. 응답 항목 간의 상대적인 우선순위를 파악할 수 있습니다.",
        "example": "다음 4가지 옵션을 선호하는 순서대로 1위부터 4위까지 나열하세요."
    },
    "MG": {
        "code": "MG",
        "name": "Matrix / Grid (매트릭스/표 형식)",
        "description": "여러 개의 항목(행)에 대해 동일한 응답 척도(열)를 반복 적용하여 표 형태로 구성합니다. 지면을 절약하고 응답의 일관성을 높일 수 있습니다.",
        "example": "각 제품에 대해 '만족도'와 '재구매 의향'을 평가하세요. (척도: 매우 낮음 ~ 매우 높음)"
    },
}

# 노드 순서
NODE_ORDER = [
    "set_survey_objective",
    "select_database",
    "set_survey_areas",
    "review_area_structure",
    "set_detailed_items",
    "review_detailed_items_structure",
    "set_layout_composition",
    "generate_and_review_survey",
    "finalize_and_refine_survey",
    "create_draft"
]

# 필드명 매핑
FIELD_NAMES = {
    "intent": "설문 목표",
    "hierarchical_structure": "단계별 영역",
    "section_items": "세부 항목",
    "layout_setting": "레이아웃 설정",
    "survey_draft": "설문지 초안",
    "final_survey": "최종 설문지",
    "area_review_message": "영역 검토 메시지",
    "detailed_items_review_message": "세부 항목 검토 메시지",
    "survey_review_message": "설문 검토 메시지",
    "graph_item_questions": "그래프 기반 추천 문항"
}

# 중요 필드 목록
IMPORTANT_FIELDS = [
    "intent", "hierarchical_structure", "section_items", "layout_setting",
    "survey_draft", "final_survey", "area_review_message",
    "detailed_items_review_message", "survey_review_message",
    "graph_item_questions"
]


# ============================================================================
# 상태 정의
# ============================================================================

class SurveyState(TypedDict, total=False):
    """설문 작성 상태"""
    messages: Annotated[list, add_messages]
    executed_nodes: list
    current_node: str
    
    # Step 1: 설문 목표
    intent: str
    survey_objective_question_step: int
    survey_objective_completed: bool
    
    # Step 2: DB 선택
    database_choice: str
    database_selection_completed: bool
    survey_type: str
    
    # Step 3: 영역 설정
    hierarchical_structure: str
    area_setting_method: str
    area_suggestion_constraints: str
    area: str  # 직접 설정한 영역 내용
    survey_areas_completed: bool
    
    # Step 3-2: 영역 검토
    area_structure_review_completed: bool
    area_review_message: str
    area_review_apply: bool
    original_hierarchical_structure: str
    area_additional_modification_requested: bool
    
    # Step 4: 세부 항목
    section_items: str
    items_setting_method: str
    detailed_items_completed: bool
    
    # Step 4-2: 세부 항목 검토
    detailed_items_review_completed: bool
    detailed_items_review_message: str
    detailed_items_review_apply: bool
    original_section_items: str
    
    # Step 5: 레이아웃
    layout_setting: str
    item_layouts: str
    layout_composition_completed: bool
    
    # Step 6: 설문 생성
    survey_draft: str
    survey_generation_completed: bool
    
    # Step 6-2: 최종 검토
    final_survey: str
    survey_finalization_completed: bool
    survey_review_message: str
    original_survey_draft: str
    survey_review_apply: bool
    
    # Step 6-3: 초안 생성
    draft_creation_completed: bool
    
    # GraphRAG
    graph_item_questions: str
    item_suggestion_constraints: str


# ============================================================================
# 유틸리티 함수
# ============================================================================

def extract_json_from_content(content: str) -> Optional[str]:
    """LLM 응답에서 JSON 추출"""
    if not content:
        return None
    
    content = content.strip()
    
    # 코드 블록 확인
    json_code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
    if json_code_block:
        json_str = json_code_block.group(1)
        json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        return json_str.strip()
    
    # 중괄호로 시작하는 JSON 찾기
    brace_count = 0
    start_idx = content.find('{')
    if start_idx == -1:
        return None
    
    for i in range(start_idx, len(content)):
        if content[i] == '{':
            brace_count += 1
        elif content[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                json_str = content[start_idx:i+1]
                json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
                json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
                return json_str.strip()
    
    return None


# ============================================================================
# 노드 함수
# ============================================================================

def set_survey_objective(state: SurveyState) -> SurveyState:
    """설문 목표 설정 노드 - 3가지 질문을 차례로 하고 LLM으로 검증"""
    executed_nodes = state.get("executed_nodes", [])
    messages = state.get("messages", [])
    survey_objective_completed = state.get("survey_objective_completed", False)
    question_step = state.get("survey_objective_question_step", 0)
    
    if survey_objective_completed:
        return {}
    
    # 첫 실행
    if "set_survey_objective" not in executed_nodes:
        message_content = """안녕하세요, 설문지 제작 전문가 AI 도우미입니다. 성공적인 설문 설계를 위해 핵심 정보를 먼저 정의해 주세요.

Q1: 설문의 목표와 용도는 무엇인가요?"""
        executed_nodes = list(executed_nodes) + ["set_survey_objective"]
        return {
            "current_node": "set_survey_objective",
            "executed_nodes": executed_nodes,
            "messages": [AIMessage(content=message_content)],
            "survey_objective_completed": False,
            "survey_objective_question_step": 1,
            "intent": ""
        }
    
    # 사용자 입력 확인
    if not messages or not isinstance(messages[-1], HumanMessage):
        return {}
    
    user_input = messages[-1].content
    existing_intent = state.get("intent", "")
    
    questions = {
        1: {
            "question": "설문의 목표와 용도는 무엇인가요?",
            "description": "이 설문의 목표 확인",
            "next_question": "Q2: 설문 대상은 누구입니까?",
            "label": "목표/용도"
        },
        2: {
            "question": "설문 대상은 누구입니까?",
            "description": "누가 이 설문에 응답할 예정인지",
            "next_question": "Q3: 설문 항목은 몇 개 정도로 예상합니까?",
            "label": "대상"
        },
        3: {
            "question": "설문 항목은 몇 개 정도로 예상합니까?",
            "description": "대략적인 문항 수",
            "next_question": None,
            "label": "항목 개수"
        }
    }
    
    current_q = questions.get(question_step)
    if not current_q:
        return {}
    
    # LLM으로 사용자 입력 검증
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 설문지 제작 전문가입니다. 사용자의 입력이 특정 질문에 대해 충분한 정보를 제공하는지 확인해주세요."),
            ("human", """질문: {question}
질문 설명: {description}

사용자 입력: {user_input}

위 질문에 대해 사용자가 충분한 정보를 제공했는지 확인하고, JSON 형식으로 응답해주세요:
{{"is_sufficient": true 또는 false, "reason": "이유", "extracted_info": "추출된 정보"}}

예시:
- 충분한 경우: {{"is_sufficient": true, "reason": "설문 목표와 용도가 명확히 설명되어 있습니다.", "extracted_info": "고객 만족도 조사를 통해 서비스 개선 방향을 결정하기 위한 설문"}}
- 부족한 경우: {{"is_sufficient": false, "reason": "설문 목표는 언급되었지만, 이 설문 결과로 어떤 의사 결정을 내릴 예정인지가 명확하지 않습니다.", "extracted_info": ""}}""")
        ])
        
        chain = prompt | llm
        response = chain.invoke({
            "question": current_q["question"],
            "description": current_q["description"],
            "user_input": user_input
        })
        
        content = response.content.strip()
        json_str = extract_json_from_content(content)
        
        is_sufficient = True  # 기본값: 충분
        reason = ""
        extracted_info = user_input
        
        if json_str:
            try:
                result = json.loads(json_str)
                is_sufficient = result.get("is_sufficient", True)
                reason = result.get("reason", "")
                extracted_info = result.get("extracted_info", user_input)
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 텍스트로 판단
                if "false" in content.lower() or "부족" in content:
                    is_sufficient = False
                    reason = "입력 내용을 더 구체적으로 작성해주세요."
        
        if is_sufficient:
            # 답변 충분 → 다음 진행
            new_intent = f"{existing_intent}\n{current_q['label']}: {extracted_info}".strip()
            
            if current_q["next_question"]:
                return {
                    "messages": [AIMessage(content=current_q["next_question"])],
                    "survey_objective_question_step": question_step + 1,
                    "intent": new_intent
                }
            else:
                # 모든 질문 완료
                summary = f"""설문 개요가 설정되었습니다.

{new_intent}

다음 단계로 진행합니다."""
                return {
                    "messages": [AIMessage(content=summary)],
                    "survey_objective_completed": True,
                    "intent": new_intent
                }
        else:
            # 답변 부족 → 재질문
            feedback_message = f"입력하신 내용을 확인했습니다. {reason}\n\n다시 한 번 답변해주세요:\n{current_q['question']}"
            return {
                "messages": [AIMessage(content=feedback_message)],
                "survey_objective_completed": False
            }
            
    except Exception as e:
        # 오류 발생 시 기본 동작 (다음 진행)
        print(f"[set_survey_objective] LLM 검증 오류: {e}")
        new_intent = f"{existing_intent}\n{current_q['label']}: {user_input}".strip()
        
        if current_q["next_question"]:
            return {
                "messages": [AIMessage(content=current_q["next_question"])],
                "survey_objective_question_step": question_step + 1,
                "intent": new_intent
            }
        else:
            summary = f"""설문 개요가 설정되었습니다.

{new_intent}

다음 단계로 진행합니다."""
            return {
                "messages": [AIMessage(content=summary)],
                "survey_objective_completed": True,
                "intent": new_intent
            }


def select_database(state: SurveyState) -> SurveyState:
    """
    DB 사용 여부 선택 노드 (2단계 프로세스)
    - 1단계: 기존 설문 DB vs 별도 설문지 선택
    - 2단계: 기존 DB 선택 시 → 설문지 유형 선택 (사회지표조사/기타)
    """
    executed_nodes = state.get("executed_nodes", [])
    messages = state.get("messages", [])
    database_selection_completed = state.get("database_selection_completed", False)
    database_choice = state.get("database_choice", "")
    survey_type = state.get("survey_type", "")
    
    if database_selection_completed:
        return {}
    
    # 첫 실행: DB 선택 안내
    if "select_database" not in executed_nodes:
        message_content = """설문지 작성 방법을 선택해 주세요.

1. 기존 설문 DB 활용: 통계청 사회조사 DB를 참고하여 설문 영역과 항목을 제안받습니다.
2. 별도 설문지 작성: 처음부터 직접 설문을 구성합니다.

어떤 방법을 선택하시겠습니까? (1 또는 2)"""
        executed_nodes = list(executed_nodes) + ["select_database"]
        return {
            "current_node": "select_database",
            "executed_nodes": executed_nodes,
            "messages": [AIMessage(content=message_content)],
            "database_selection_completed": False
        }
    
    if not messages or not isinstance(messages[-1], HumanMessage):
        return {}
    
    user_input = messages[-1].content.strip()
    
    # 1단계: DB 선택이 아직 안 된 경우
    if not database_choice:
        # LLM으로 사용자 의도 분석
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "사용자의 입력을 분석하여 설문지 작성 방법을 판단하세요."),
                ("human", """사용자 입력: {user_input}

다음 중 하나를 판단하세요:
- "기존", "DB", "활용", "참고", "1" → 기존 설문 DB 활용
- "별도", "직접", "새로", "처음", "2" → 별도 설문지 작성

JSON 형식: {{"choice": "기존_설문_DB" 또는 "별도_설문지", "reason": "판단 이유"}}""")
            ])
            
            chain = prompt | llm
            response = chain.invoke({"user_input": user_input})
            json_str = extract_json_from_content(response.content)
            
            choice = ""
            if json_str:
                result = json.loads(json_str)
                choice = result.get("choice", "")
            
            # 키워드 폴백
            if not choice:
                if any(k in user_input for k in ["1", "기존", "DB", "활용", "참고"]):
                    choice = "기존_설문_DB"
                elif any(k in user_input for k in ["2", "별도", "직접", "새로", "처음"]):
                    choice = "별도_설문지"
        except Exception as e:
            print(f"[select_database] LLM 분석 오류: {e}")
            # 키워드 폴백
            if any(k in user_input for k in ["1", "기존", "DB"]):
                choice = "기존_설문_DB"
            elif any(k in user_input for k in ["2", "별도", "직접"]):
                choice = "별도_설문지"
            else:
                choice = ""
        
        if choice == "기존_설문_DB":
            # 2단계로 진행: 설문 유형 선택
            message_content = """기존 설문 DB를 활용합니다.

어떤 유형의 설문지를 참고하시겠습니까?

1. 사회지표조사: 통계청 사회조사(가구, 교육, 건강, 복지 등)
2. 기타: 기타 조사 유형

참고할 설문 유형을 선택해주세요. (1 또는 2, 또는 직접 입력)"""
            return {
                "messages": [AIMessage(content=message_content)],
                "database_choice": "기존_설문_DB",
                "database_selection_completed": False
            }
        elif choice == "별도_설문지":
            # 바로 완료
            return {
                "messages": [AIMessage(content="별도 설문지 작성으로 진행합니다. 다음 단계에서 영역을 직접 구성합니다.")],
                "database_choice": "별도_설문지",
                "survey_type": "",
                "database_selection_completed": True
            }
        else:
            return {
                "messages": [AIMessage(content="1(기존 설문 DB 활용) 또는 2(별도 설문지 작성)를 선택해 주세요.")]
            }
    
    # 2단계: 기존 DB 선택했고, 설문 유형 선택 필요
    if database_choice == "기존_설문_DB" and not survey_type:
        # LLM으로 설문 유형 분석
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "사용자의 입력을 분석하여 설문 유형을 판단하세요."),
                ("human", """사용자 입력: {user_input}

다음 중 하나를 판단하세요:
- "사회", "지표", "통계청", "1" → 사회지표조사
- "기타", "다른", "2" 또는 직접 입력한 유형명 → 해당 유형명

JSON 형식: {{"survey_type": "사회지표조사" 또는 사용자가 입력한 유형명}}""")
            ])
            
            chain = prompt | llm
            response = chain.invoke({"user_input": user_input})
            json_str = extract_json_from_content(response.content)
            
            selected_type = ""
            if json_str:
                result = json.loads(json_str)
                selected_type = result.get("survey_type", "")
            
            # 키워드 폴백
            if not selected_type:
                if any(k in user_input for k in ["1", "사회", "지표", "통계청"]):
                    selected_type = "사회지표조사"
                elif any(k in user_input for k in ["2", "기타"]):
                    selected_type = "기타"
                else:
                    selected_type = user_input.strip() if len(user_input.strip()) > 1 else "사회지표조사"
        except Exception as e:
            print(f"[select_database] 설문유형 분석 오류: {e}")
            if any(k in user_input for k in ["1", "사회", "지표"]):
                selected_type = "사회지표조사"
            else:
                selected_type = "기타"
        
        return {
            "messages": [AIMessage(content=f"'{selected_type}' 유형의 설문 DB를 참고하여 진행합니다.")],
            "survey_type": selected_type,
            "database_selection_completed": True
        }
    
    return {}


def set_survey_areas(state: SurveyState) -> SurveyState:
    """
    단계별 영역 설정 노드 (원본 패턴 반영)
    - 참고_제안: GraphRAG + LLM으로 영역 제안, 수정 피드백 루프
    - 직접_설정: 사용자가 직접 영역 입력
    """
    executed_nodes = state.get("executed_nodes", [])
    messages = state.get("messages", [])
    survey_areas_completed = state.get("survey_areas_completed", False)
    area_setting_method = state.get("area_setting_method", "")
    hierarchical_structure = state.get("hierarchical_structure", "")
    area_suggestion_constraints = state.get("area_suggestion_constraints", "")
    intent = state.get("intent", "")
    survey_type = state.get("survey_type", "")
    
    if survey_areas_completed:
        return {}
    
    # 첫 실행: 안내 메시지
    if "set_survey_areas" not in executed_nodes:
        executed_nodes = list(executed_nodes) + ["set_survey_areas"]
        
        goal_summary = intent.split("\n")[0][:50] + "..." if intent and len(intent.split("\n")[0]) > 50 else (intent.split("\n")[0] if intent else "설문 목표")
        
        message_content = f"""목표({goal_summary})를 달성하기 위해, 먼저 설문 구성을 위한 주요 영역을 설정합니다.

Q1. 기존 설문지를 참고해 영역에 대한 제안을 받으시겠습니까? 아니면 직접 영역을 설정하시겠습니까?

[영역 제안]을 선택하면 AI가 내부 DB를 참고하여 영역 구성과 순서를 제안합니다.
[직접 설정]을 선택하면 사용자가 핵심 영역들을 입력하시면 됩니다.
(예시: 1. 가구특성, 2. 가정, 3. 교육, 4. 교통, 5. 경제)"""
        
        return {
            "current_node": "set_survey_areas",
            "executed_nodes": executed_nodes,
            "messages": [AIMessage(content=message_content)],
            "survey_areas_completed": False,
            "area_setting_method": ""
        }
    
    # 사용자 입력 확인
    if not messages or not isinstance(messages[-1], HumanMessage):
        return {}
    
    user_input = messages[-1].content.strip()
    
    # 1단계: 영역 설정 방식 판단 (참고_제안 / 직접_설정)
    if not area_setting_method:
        # 너무 짧거나 의미없는 입력 체크
        valid_keywords = ["제안", "참고", "직접", "설정", "추천", "1.", "2.", "3.", "가구", "교육", "건강", "경제", "복지"]
        is_valid_input = len(user_input) >= 2 and (
            any(k in user_input for k in valid_keywords) or 
            any(c.isdigit() for c in user_input) or
            "," in user_input
        )
        
        if not is_valid_input and len(user_input) < 10:
            return {
                "messages": [AIMessage(content="""입력을 이해하지 못했습니다.

영역 설정 방법을 선택해주세요:
- AI가 영역을 제안받으려면 '제안' 또는 '추천'을 입력하세요.
- 직접 영역을 설정하려면 '직접'을 입력하거나 영역 목록을 입력하세요.
  예: 1. 가구특성, 2. 경제활동, 3. 건강""")],
                "survey_areas_completed": False
            }
        
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "당신은 설문지 설계 전문가입니다. 사용자의 입력을 분석하여 설문 영역 설정 방식을 판단해주세요."),
                ("human", """사용자 입력: {user_input}

사용자의 입력을 분석하여 다음 중 하나를 판단해주세요:
1. "참고해 제안", "제안", "참고", "기존 설문 참고" 등: 기존 설문을 참고하여 제안
2. "직접 작성", "직접", "내가 작성", "직접 설정" 등: 사용자가 직접 작성
3. "1. 가구특성, 2. 가정, ..."처럼 영역 이름 리스트를 바로 입력한 경우도 "직접_설정"으로 간주

JSON 형식으로 응답: {{"method": "참고_제안" 또는 "직접_설정"}}""")
            ])
            
            chain = prompt | llm
            response = chain.invoke({"user_input": user_input})
            content = response.content.strip()
            json_str = extract_json_from_content(content)
            
            if json_str:
                result = json.loads(json_str)
                area_setting_method = result.get("method", "직접_설정")
            else:
                # 키워드 폴백
                if any(k in user_input.lower() for k in ["참고", "제안", "기존"]):
                    area_setting_method = "참고_제안"
                else:
                    area_setting_method = "직접_설정"
        except Exception as e:
            print(f"[set_survey_areas] 방식 판단 오류: {e}")
            area_setting_method = "직접_설정" if any(c.isdigit() for c in user_input) else "참고_제안"
        
        # 참고_제안인 경우: 사용자 입력을 제약조건으로 저장
        if area_setting_method == "참고_제안":
            area_suggestion_constraints = user_input
        
        # 직접_설정이고 영역 리스트가 이미 있으면 바로 저장
        if area_setting_method == "직접_설정":
            # LLM으로 영역 리스트 추출 시도
            try:
                extract_prompt = ChatPromptTemplate.from_messages([
                    ("system", "사용자 입력에서 설문 영역 리스트가 있는지 확인하세요."),
                    ("human", """사용자 입력: {user_input}

영역 리스트가 있으면 추출하세요. JSON 형식으로:
{{"has_area_list": true/false, "hierarchical_structure": "1. 영역1\\n2. 영역2..."}}""")
                ])
                extract_chain = extract_prompt | llm
                extract_response = extract_chain.invoke({"user_input": user_input})
                extract_json = extract_json_from_content(extract_response.content)
                
                if extract_json:
                    extract_result = json.loads(extract_json)
                    if extract_result.get("has_area_list") and extract_result.get("hierarchical_structure"):
                        extracted = extract_result["hierarchical_structure"].strip()
                        return {
                            "area_setting_method": "직접_설정",
                            "area": extracted,
                            "hierarchical_structure": extracted,
                            "survey_areas_completed": True,
                            "messages": [AIMessage(content=f"입력하신 영역으로 설정했습니다:\n\n{extracted}\n\n다음 단계로 진행합니다.")]
                        }
            except Exception:
                pass
            
            # 영역 리스트가 없으면 입력 요청
            return {
                "area_setting_method": "직접_설정",
                "messages": [AIMessage(content="직접 영역 설정을 선택하셨습니다. 설문 구성을 위한 주요 영역들을 입력해주세요.\n(예시: 1. 가구특성, 2. 가정, 3. 교육, 4. 교통, 5. 경제)")]
            }
    
    # 2단계: 참고_제안 모드
    if area_setting_method == "참고_제안":
        # 아직 제안이 없는 경우: GraphRAG + LLM으로 최초 제안 생성
        if not hierarchical_structure:
            try:
                # GraphRAG로 유사 영역 검색
                graph_areas = []
                search_query = survey_type or intent
                if search_query and is_graphrag_initialized():
                    graph_areas = find_similar_survey_categories_and_areas(
                        survey_type=search_query,
                        top_k_categories=3,
                        top_k_areas_per_category=10
                    )
                
                graph_areas_text = ""
                if graph_areas:
                    unique_areas = list(dict.fromkeys([a.get("area_name", "") for a in graph_areas if a.get("area_name")]))
                    if unique_areas:
                        graph_areas_text = f"내부 DB에서 찾은 유사 영역 예시:\n{', '.join(unique_areas[:15])}"
                
                user_constraints = area_suggestion_constraints or "(사용자가 추가 요청 없음)"
                
                # LLM으로 영역 제안 생성
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "설문지 설계 전문가로서 영역을 제안해주세요."),
                    ("human", """설문 목표:
{intent}

{graph_areas_text}

사용자 추가 요청: {user_constraints}

위 정보를 바탕으로 설문 영역(섹션) 3~7개를 제안하세요.
- 사용자 추가 요청이 있으면 우선 반영
- 영역은 명확하고 구분되어야 함

JSON 형식: {{"hierarchical_structure": "1. 영역1\\n2. 영역2\\n3. 영역3...", "reason": "제안 이유"}}""")
                ])
                
                chain = prompt | llm
                response = chain.invoke({
                    "intent": intent,
                    "graph_areas_text": graph_areas_text,
                    "user_constraints": user_constraints
                })
                
                json_str = extract_json_from_content(response.content)
                if json_str:
                    result = json.loads(json_str)
                    proposed_structure = result.get("hierarchical_structure", "")
                    reason = result.get("reason", "")
                    
                    if proposed_structure:
                        msg = f"""다음과 같은 영역 구성을 제안합니다:

{proposed_structure}

{reason}

이 제안이 괜찮으면 '다음으로 진행', '좋아요' 등으로 답변해주세요.
수정이 필요하면 '7개로 줄여줘', '가구특성과 주거를 합쳐줘'처럼 구체적으로 입력해주세요."""
                        return {
                            "area_setting_method": "참고_제안",
                            "hierarchical_structure": proposed_structure,
                            "area_suggestion_constraints": area_suggestion_constraints,
                            "messages": [AIMessage(content=msg)],
                            "survey_areas_completed": False
                        }
            except Exception as e:
                print(f"[set_survey_areas] 영역 제안 오류: {e}")
            
            # 실패 시 직접 설정으로 전환
            return {
                "area_setting_method": "직접_설정",
                "messages": [AIMessage(content="영역 제안 생성에 문제가 발생했습니다. 직접 영역을 설정해주세요.\n(예시: 1. 가구특성, 2. 가정, 3. 교육)")]
            }
        
        # 이미 제안이 있고, 사용자 피드백을 받은 경우
        try:
            # 사용자 피드백 분석 (진행 vs 수정)
            feedback_prompt = ChatPromptTemplate.from_messages([
                ("system", "사용자의 피드백을 분석하세요."),
                ("human", """제안된 영역:
{hierarchical_structure}

사용자 입력: {user_feedback}

분석: {{"proceed": true/false, "needs_revision": true/false, "revision_request": "수정 요청 내용"}}""")
            ])
            
            feedback_chain = feedback_prompt | llm
            feedback_response = feedback_chain.invoke({
                "hierarchical_structure": hierarchical_structure,
                "user_feedback": user_input
            })
            feedback_json = extract_json_from_content(feedback_response.content)
            
            proceed = False
            needs_revision = False
            revision_request = ""
            
            # 1. 먼저 명확한 키워드 체크 (LLM 결과보다 우선)
            low = user_input.lower()
            proceed_keywords = ["다음", "괜찮", "좋아", "그대로", "진행", "확인", "넘어가", "다음으로", "좋습니다", "네"]
            revision_keywords = ["수정", "다시", "변경", "합치", "나누", "줄여", "늘려", "추가", "삭제", "바꿔"]
            
            has_proceed_keyword = any(k in low for k in proceed_keywords)
            has_revision_keyword = any(k in low for k in revision_keywords)
            
            # 명확한 진행 키워드가 있고 수정 키워드가 없으면 바로 진행
            if has_proceed_keyword and not has_revision_keyword:
                proceed = True
            # 명확한 수정 키워드가 있으면 수정 처리
            elif has_revision_keyword:
                needs_revision = True
                revision_request = user_input
            # 키워드가 불명확하면 LLM 결과 사용
            elif feedback_json:
                fb_result = json.loads(feedback_json)
                proceed = fb_result.get("proceed", False)
                needs_revision = fb_result.get("needs_revision", False)
                revision_request = fb_result.get("revision_request", user_input)
            
            # 그대로 진행
            if proceed and not needs_revision:
                return {"survey_areas_completed": True}
            
            # 수정 요청
            if needs_revision and revision_request:
                # GraphRAG 재조회 + LLM 수정
                graph_areas = []
                search_query = survey_type or intent
                if search_query and is_graphrag_initialized():
                    graph_areas = find_similar_survey_categories_and_areas(search_query, 3, 10)
                
                graph_text = ""
                if graph_areas:
                    unique = list(dict.fromkeys([a.get("area_name", "") for a in graph_areas if a.get("area_name")]))
                    graph_text = f"참고 영역: {', '.join(unique[:10])}" if unique else ""
                
                revision_prompt = ChatPromptTemplate.from_messages([
                    ("system", "기존 제안과 수정 요청을 반영하여 영역을 재설계하세요."),
                    ("human", """설문 목표: {intent}

{graph_text}

기존 영역: {current_structure}

수정 요청: {revision_request}

수정 반영한 영역을 JSON으로: {{"hierarchical_structure": "1. 영역1\\n2. 영역2...", "reason": "수정 이유"}}""")
                ])
                
                revision_chain = revision_prompt | llm
                revision_response = revision_chain.invoke({
                    "intent": intent,
                    "graph_text": graph_text,
                    "current_structure": hierarchical_structure,
                    "revision_request": revision_request
                })
                
                revision_json = extract_json_from_content(revision_response.content)
                if revision_json:
                    rev_result = json.loads(revision_json)
                    new_structure = rev_result.get("hierarchical_structure", "")
                    reason = rev_result.get("reason", "")
                    
                    if new_structure:
                        msg = f"""수정 요청을 반영하여 영역 구성을 다시 제안합니다:

{new_structure}

{reason}

이 구성이 괜찮으면 '다음으로 진행' 등으로 답변해주세요.
추가 수정이 있으면 계속 말씀해주세요."""
                        return {
                            "hierarchical_structure": new_structure,
                            "messages": [AIMessage(content=msg)],
                            "survey_areas_completed": False
                        }
        except Exception as e:
            print(f"[set_survey_areas] 피드백 처리 오류: {e}")
        
        # 어느 쪽도 명확하지 않으면 진행
        return {"survey_areas_completed": True}
    
    # 3단계: 직접_설정 모드
    return {
        "area": user_input,
        "hierarchical_structure": user_input,
        "survey_areas_completed": True,
        "messages": [AIMessage(content=f"다음과 같이 영역이 설정되었습니다:\n\n{user_input}\n\n다음 단계로 진행합니다.")]
    }


def review_area_structure(state: SurveyState) -> SurveyState:
    """영역 구조 검토 노드"""
    executed_nodes = state.get("executed_nodes", [])
    messages = state.get("messages", [])
    area_structure_review_completed = state.get("area_structure_review_completed", False)
    hierarchical_structure = state.get("hierarchical_structure", "")
    
    if area_structure_review_completed:
        return {}
    
    if "review_area_structure" not in executed_nodes:
        executed_nodes = list(executed_nodes) + ["review_area_structure"]
        
        # LLM으로 검토
        review_message = ""
        if llm:
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "설문 전문가로서 영역 구조를 검토해주세요. 간결하게 피드백하세요."),
                    ("human", f"영역 구조:\n{hierarchical_structure}\n\n이 구조에 대해 검토 의견을 주세요.")
                ])
                response = llm.invoke(prompt.format_messages())
                review_message = response.content
            except Exception as e:
                review_message = "영역 구조가 적절해 보입니다."
        else:
            review_message = "영역 구조가 설정되었습니다."
        
        message_content = f"""[영역 구조 검토]

{review_message}

이대로 진행하시겠습니까? (확인/수정)"""
        
        return {
            "current_node": "review_area_structure",
            "executed_nodes": executed_nodes,
            "messages": [AIMessage(content=message_content)],
            "area_review_message": review_message,
            "original_hierarchical_structure": hierarchical_structure
        }
    
    if not messages or not isinstance(messages[-1], HumanMessage):
        return {}
    
    user_input = messages[-1].content.strip().lower()
    
    # 확인 키워드
    confirm_keywords = ["확인", "네", "예", "진행", "좋아", "ok", "yes", "다음", "완료"]
    # 수정 키워드
    modify_keywords = ["수정", "변경", "바꿔", "고쳐", "추가", "삭제", "제거"]
    
    if any(keyword in user_input for keyword in confirm_keywords):
        return {
            "messages": [AIMessage(content="영역 구조가 확정되었습니다. 다음 단계로 진행합니다.")],
            "area_structure_review_completed": True,
            "area_review_apply": False
        }
    elif any(keyword in user_input for keyword in modify_keywords):
        return {
            "messages": [AIMessage(content="수정할 영역 구조를 입력해 주세요.\n(예시: 1. 가구특성, 2. 경제활동, 3. 건강)")],
            "area_review_apply": True
        }
    elif len(user_input) > 10 and any(c.isdigit() for c in user_input):
        # 숫자가 포함된 10자 이상의 입력은 수정 내용으로 간주
        return {
            "messages": [AIMessage(content=f"영역이 수정되었습니다.\n\n{messages[-1].content}")],
            "hierarchical_structure": messages[-1].content,
            "area_structure_review_completed": True
        }
    else:
        # 엉뚱한 입력
        return {
            "messages": [AIMessage(content="입력을 이해하지 못했습니다.\n\n- 현재 영역 구조로 진행하려면 '확인' 또는 '예'를 입력하세요.\n- 영역을 수정하려면 '수정'을 입력하거나 새로운 영역 구조를 직접 입력해주세요.")],
            "area_review_apply": False
        }


def set_detailed_items(state: SurveyState) -> SurveyState:
    """
    세부 항목 설정 노드 (원본 패턴 반영)
    - 참고_제안: GraphRAG + LLM으로 항목 제안, 수정 피드백 루프
    - 직접_작성: 사용자가 직접 항목 입력
    """
    executed_nodes = state.get("executed_nodes", [])
    messages = state.get("messages", [])
    detailed_items_completed = state.get("detailed_items_completed", False)
    items_setting_method = state.get("items_setting_method", "")
    section_items = state.get("section_items", "")
    item_suggestion_constraints = state.get("item_suggestion_constraints", "")
    hierarchical_structure = state.get("hierarchical_structure", "")
    intent = state.get("intent", "")
    survey_type = state.get("survey_type", "")
    database_choice = state.get("database_choice", "")
    
    if detailed_items_completed:
        return {}
    
    # 첫 실행: 방식 선택 안내
    if "set_detailed_items" not in executed_nodes:
        executed_nodes = list(executed_nodes) + ["set_detailed_items"]
        
        message_content = f"""영역 구조가 설정되었습니다. 이제 각 영역별 세부 항목을 설정합니다.

Q. 세부 항목을 어떻게 설정하시겠습니까?

[항목 제안]을 선택하면 AI가 내부 DB를 참고하여 영역별 세부 항목을 제안합니다.
[직접 작성]을 선택하면 사용자가 각 영역에 포함될 항목들을 입력하시면 됩니다.

(예시 형식: "1. 가구특성: 가구원 수, 가구주 성별, 월 소득\\n2. 서비스 품질: 응대 만족도, 처리 속도")"""
        
        return {
            "current_node": "set_detailed_items",
            "executed_nodes": executed_nodes,
            "messages": [AIMessage(content=message_content)],
            "detailed_items_completed": False,
            "items_setting_method": ""
        }
    
    # 사용자 입력 확인
    if not messages or not isinstance(messages[-1], HumanMessage):
        return {}
    
    user_input = messages[-1].content.strip()
    
    # 1단계: 설정 방식 판단 (참고_제안 / 직접_작성)
    if not items_setting_method:
        # 너무 짧거나 의미없는 입력 체크
        valid_keywords = ["제안", "참고", "직접", "작성", "추천", "항목", ":", ","]
        is_valid_input = len(user_input) >= 2 and (
            any(k in user_input for k in valid_keywords) or 
            any(c.isdigit() for c in user_input)
        )
        
        if not is_valid_input and len(user_input) < 10:
            return {
                "messages": [AIMessage(content="""입력을 이해하지 못했습니다.

세부 항목 설정 방법을 선택해주세요:
- AI가 항목을 제안받으려면 '제안' 또는 '추천'을 입력하세요.
- 직접 항목을 설정하려면 '직접'을 입력하거나 항목 목록을 입력하세요.
  예: 1. 가구특성: 성별, 연령, 직업
      2. 경제활동: 취업여부, 월소득""")],
                "detailed_items_completed": False
            }
        
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "사용자의 입력을 분석하여 세부 항목 설정 방식을 판단하세요."),
                ("human", """사용자 입력: {user_input}

사용자의 입력을 분석하세요:
1. "제안", "참고", "추천", "AI가" 등 → 참고_제안
2. "직접", "내가", "작성" 등 → 직접_작성
3. "1. 영역: 항목1, 항목2" 형식으로 항목을 직접 입력한 경우 → 직접_작성

JSON 형식: {{"method": "참고_제안" 또는 "직접_작성"}}""")
            ])
            
            chain = prompt | llm
            response = chain.invoke({"user_input": user_input})
            json_str = extract_json_from_content(response.content)
            
            if json_str:
                result = json.loads(json_str)
                items_setting_method = result.get("method", "직접_작성")
            else:
                # 키워드 폴백
                if any(k in user_input.lower() for k in ["제안", "참고", "추천"]):
                    items_setting_method = "참고_제안"
                else:
                    items_setting_method = "직접_작성"
        except Exception as e:
            print(f"[set_detailed_items] 방식 판단 오류: {e}")
            items_setting_method = "직접_작성" if ":" in user_input else "참고_제안"
        
        # 참고_제안인 경우: 사용자 입력을 제약조건으로 저장
        if items_setting_method == "참고_제안":
            item_suggestion_constraints = user_input
        
        # 직접_작성이고 항목 리스트가 이미 있으면 바로 저장
        if items_setting_method == "직접_작성" and ":" in user_input:
            return {
                "items_setting_method": "직접_작성",
                "section_items": user_input,
                "detailed_items_completed": True,
                "messages": [AIMessage(content=f"입력하신 세부 항목으로 설정했습니다:\n\n{user_input}\n\n다음 단계로 진행합니다.")]
            }
        
        # 직접_작성 선택했지만 항목 없으면 입력 요청
        if items_setting_method == "직접_작성":
            return {
                "items_setting_method": "직접_작성",
                "messages": [AIMessage(content="직접 항목 작성을 선택하셨습니다. 각 영역별 세부 항목을 입력해주세요.\n\n(예시 형식:\n1. 가구특성: 가구원 수, 가구주 성별, 월 소득\n2. 서비스 품질: 응대 만족도, 처리 속도, 접근성)")]
            }
    
    # 2단계: 참고_제안 모드
    if items_setting_method == "참고_제안":
        # 아직 제안이 없는 경우: GraphRAG + LLM으로 최초 제안 생성
        if not section_items:
            try:
                # GraphRAG로 유사 항목 검색
                graph_items = {}
                area_names = extract_area_names_from_hierarchical_structure(hierarchical_structure)
                
                if area_names and is_graphrag_initialized():
                    graph_items = find_similar_areas_and_items(
                        area_names=area_names,
                        top_k_areas=3,
                        top_k_items_per_area=10
                    )
                
                # GraphRAG 결과를 텍스트로 변환
                graph_items_text = ""
                if graph_items:
                    lines = []
                    for area_name, items in graph_items.items():
                        if items:
                            item_names = [item.get("item_name", "") for item in items if item.get("item_name")]
                            if item_names:
                                lines.append(f"- {area_name}: {', '.join(item_names[:8])}")
                    if lines:
                        graph_items_text = "내부 DB에서 찾은 유사 항목 예시:\n" + "\n".join(lines)
                
                user_constraints = item_suggestion_constraints or "(사용자가 추가 요청 없음)"
                
                # LLM으로 항목 제안 생성
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "설문지 설계 전문가로서 영역별 세부 항목을 제안해주세요."),
                    ("human", """설문 목표:
{intent}

영역 구조:
{hierarchical_structure}

{graph_items_text}

사용자 추가 요청: {user_constraints}

위 정보를 바탕으로 각 영역별 세부 항목을 제안하세요.
- 각 영역당 3~7개 항목
- 사용자 추가 요청이 있으면 우선 반영
- 설문 목표 달성에 필요한 항목 포함

JSON 형식: {{"section_items": "1. 영역명: 항목1, 항목2, 항목3\\n2. 영역명: 항목1, 항목2...", "reason": "제안 이유"}}""")
                ])
                
                chain = prompt | llm
                response = chain.invoke({
                    "intent": intent,
                    "hierarchical_structure": hierarchical_structure,
                    "graph_items_text": graph_items_text if graph_items_text else "(참고 항목 없음)",
                    "user_constraints": user_constraints
                })
                
                json_str = extract_json_from_content(response.content)
                if json_str:
                    result = json.loads(json_str)
                    proposed_items = result.get("section_items", "")
                    reason = result.get("reason", "")
                    
                    if proposed_items:
                        msg = f"""다음과 같은 세부 항목 구성을 제안합니다:

{proposed_items}

{reason}

이 제안이 괜찮으면 '다음으로 진행', '좋아요' 등으로 답변해주세요.
수정이 필요하면 '항목을 더 추가해줘', '가구특성에 주거형태 추가해줘'처럼 구체적으로 입력해주세요."""
                        return {
                            "items_setting_method": "참고_제안",
                            "section_items": proposed_items,
                            "item_suggestion_constraints": item_suggestion_constraints,
                            "messages": [AIMessage(content=msg)],
                            "detailed_items_completed": False
                        }
            except Exception as e:
                print(f"[set_detailed_items] 항목 제안 오류: {e}")
            
            # 실패 시 직접 작성으로 전환
            return {
                "items_setting_method": "직접_작성",
                "messages": [AIMessage(content="항목 제안 생성에 문제가 발생했습니다. 직접 항목을 설정해주세요.\n\n(예시 형식:\n1. 가구특성: 가구원 수, 가구주 성별\n2. 서비스: 만족도, 이용 빈도)")]
            }
        
        # 이미 제안이 있고, 사용자 피드백을 받은 경우
        try:
            # 사용자 피드백 분석 (진행 vs 수정)
            low = user_input.lower()
            proceed_keywords = ["다음", "괜찮", "좋아", "그대로", "진행", "확인", "넘어가", "좋습니다", "네"]
            revision_keywords = ["수정", "다시", "변경", "추가", "삭제", "바꿔", "더", "빼", "넣어"]
            
            has_proceed_keyword = any(k in low for k in proceed_keywords)
            has_revision_keyword = any(k in low for k in revision_keywords)
            
            # 명확한 진행 키워드가 있고 수정 키워드가 없으면 완료
            if has_proceed_keyword and not has_revision_keyword:
                return {
                    "detailed_items_completed": True,
                    "messages": [AIMessage(content="세부 항목이 확정되었습니다. 다음 단계로 진행합니다.")]
                }
            
            # 수정 요청 처리
            if has_revision_keyword or len(user_input) > 5:
                # GraphRAG 재조회
                graph_items = {}
                area_names = extract_area_names_from_hierarchical_structure(hierarchical_structure)
                if area_names and is_graphrag_initialized():
                    graph_items = find_similar_areas_and_items(area_names, 3, 10)
                
                graph_text = ""
                if graph_items:
                    lines = []
                    for area_name, items in graph_items.items():
                        if items:
                            item_names = [item.get("item_name", "") for item in items[:5]]
                            if item_names:
                                lines.append(f"- {area_name}: {', '.join(item_names)}")
                    graph_text = "참고 항목: " + "; ".join([l.replace("- ", "") for l in lines]) if lines else ""
                
                # LLM으로 수정 반영
                revision_prompt = ChatPromptTemplate.from_messages([
                    ("system", "기존 제안과 수정 요청을 반영하여 세부 항목을 재설계하세요."),
                    ("human", """설문 목표: {intent}

영역 구조: {hierarchical_structure}

{graph_text}

기존 항목: {current_items}

수정 요청: {revision_request}

수정 반영한 항목을 JSON으로: {{"section_items": "1. 영역명: 항목1, 항목2...\\n2. 영역명: 항목1...", "reason": "수정 이유"}}""")
                ])
                
                revision_chain = revision_prompt | llm
                revision_response = revision_chain.invoke({
                    "intent": intent,
                    "hierarchical_structure": hierarchical_structure,
                    "graph_text": graph_text,
                    "current_items": section_items,
                    "revision_request": user_input
                })
                
                revision_json = extract_json_from_content(revision_response.content)
                if revision_json:
                    rev_result = json.loads(revision_json)
                    new_items = rev_result.get("section_items", "")
                    reason = rev_result.get("reason", "")
                    
                    if new_items:
                        msg = f"""수정 요청을 반영하여 세부 항목을 다시 제안합니다:

{new_items}

{reason}

이 구성이 괜찮으면 '다음으로 진행' 등으로 답변해주세요.
추가 수정이 있으면 계속 말씀해주세요."""
                        return {
                            "section_items": new_items,
                            "messages": [AIMessage(content=msg)],
                            "detailed_items_completed": False
                        }
        except Exception as e:
            print(f"[set_detailed_items] 피드백 처리 오류: {e}")
        
        # 어느 쪽도 명확하지 않으면 진행
        return {
            "detailed_items_completed": True,
            "messages": [AIMessage(content="세부 항목이 확정되었습니다. 다음 단계로 진행합니다.")]
        }
    
    # 3단계: 직접_작성 모드
    if items_setting_method == "직접_작성":
        if len(user_input) < 10:
            return {
                "messages": [AIMessage(content="세부 항목을 더 구체적으로 입력해 주세요.\n\n(예시:\n1. 가구특성: 가구원 수, 월 소득\n2. 서비스: 만족도, 이용빈도)")]
            }
        
        return {
            "section_items": user_input,
            "detailed_items_completed": True,
            "messages": [AIMessage(content=f"세부 항목이 설정되었습니다:\n\n{user_input}\n\n다음 단계로 진행합니다.")]
        }
    
    return {}


def review_detailed_items_structure(state: SurveyState) -> SurveyState:
    """세부 항목 검토 노드"""
    executed_nodes = state.get("executed_nodes", [])
    messages = state.get("messages", [])
    detailed_items_review_completed = state.get("detailed_items_review_completed", False)
    section_items = state.get("section_items", "")
    
    if detailed_items_review_completed:
        return {}
    
    if "review_detailed_items_structure" not in executed_nodes:
        executed_nodes = list(executed_nodes) + ["review_detailed_items_structure"]
        
        review_message = "세부 항목이 적절하게 구성되었습니다."
        if llm:
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "설문 전문가로서 세부 항목 구성을 검토해주세요."),
                    ("human", f"세부 항목:\n{section_items}\n\n검토 의견을 주세요.")
                ])
                response = llm.invoke(prompt.format_messages())
                review_message = response.content
            except:
                pass
        
        message_content = f"""[세부 항목 검토]

{review_message}

이대로 진행하시겠습니까? (확인/수정)"""
        
        return {
            "current_node": "review_detailed_items_structure",
            "executed_nodes": executed_nodes,
            "messages": [AIMessage(content=message_content)],
            "detailed_items_review_message": review_message,
            "original_section_items": section_items
        }
    
    if not messages or not isinstance(messages[-1], HumanMessage):
        return {}
    
    user_input = messages[-1].content.strip().lower()
    
    # 확인 키워드
    confirm_keywords = ["확인", "네", "예", "진행", "좋아", "ok", "yes", "다음", "완료"]
    # 수정 키워드
    modify_keywords = ["수정", "변경", "바꿔", "고쳐", "추가", "삭제", "제거"]
    
    if any(keyword in user_input for keyword in confirm_keywords):
        return {
            "messages": [AIMessage(content="세부 항목이 확정되었습니다.")],
            "detailed_items_review_completed": True
        }
    elif any(keyword in user_input for keyword in modify_keywords):
        return {
            "messages": [AIMessage(content="수정할 세부 항목을 입력해 주세요.\n(예시: 1. 가구특성: 성별, 연령, 직업\n2. 경제활동: 취업여부, 월소득)")],
        }
    elif len(user_input) > 15 and (":" in user_input or "," in user_input):
        # 콜론이나 쉼표가 포함된 15자 이상의 입력은 수정 내용으로 간주
        return {
            "messages": [AIMessage(content=f"항목이 수정되었습니다.\n\n{messages[-1].content}")],
            "section_items": messages[-1].content,
            "detailed_items_review_completed": True
        }
    else:
        # 엉뚱한 입력
        return {
            "messages": [AIMessage(content="입력을 이해하지 못했습니다.\n\n- 현재 세부 항목으로 진행하려면 '확인' 또는 '예'를 입력하세요.\n- 항목을 수정하려면 '수정'을 입력하거나 새로운 항목을 직접 입력해주세요.")]
        }


def set_layout_composition(state: SurveyState) -> SurveyState:
    """
    세부 항목 레이아웃 구성 노드
    - GraphRAG 기반 레이아웃 추천 지원
    - 직접 입력 및 수정 지원
    """
    executed_nodes = state.get("executed_nodes", [])
    messages = state.get("messages", [])
    layout_composition_completed = state.get("layout_composition_completed", False)
    section_items = state.get("section_items", "")
    layout_setting = state.get("layout_setting", "")
    
    # 이미 완료되었으면 아무것도 하지 않음
    if layout_composition_completed:
        return {}
    
    # 첫 실행 시 안내 메시지 출력
    if "set_layout_composition" not in executed_nodes:
        print("\n[세부 항목 레이아웃 구성 노드]")
        executed_nodes = list(executed_nodes) + ["set_layout_composition"]
        
        # 간결한 레이아웃 약어 안내
        layout_info = "OQ(오픈형), SC(선다형), MA(복수응답), DC(이분형), RS(척도형), RK(순위형), MG(매트릭스)"
        
        message_content = f"""개별 항목별로 설문의 레이아웃을 설정합니다.

[사용 가능한 레이아웃]
{layout_info}
※ RS, RK, MG는 숫자 입력 필요 (예: RS(7), RK(5), MG(3))

[현재 설정된 영역별 세부 항목]
{section_items}

"제안" 또는 "추천"이라고 입력하시면 AI가 자동으로 레이아웃을 제안합니다.

직접 설정하시려면 "항목명 약어" 형식으로 입력해주세요.
예시:
성별 SC
만족도 RS(5)
기타 의견 OQ"""
        
        return {
            "current_node": "set_layout_composition",
            "executed_nodes": executed_nodes,
            "messages": [AIMessage(content=message_content)],
            "layout_composition_completed": False
        }
    
    # 사용자 입력이 있는지 확인
    if not messages or not isinstance(messages[-1], HumanMessage):
        return {}
    
    # 사용자 입력 추출
    user_input = messages[-1].content.strip()
    
    # =========================================================================
    # 이미 레이아웃이 결정된 상태라면 확인/수정 처리
    # =========================================================================
    if layout_setting:
        # 키워드 기반으로 빠르게 판단 (LLM 호출 제거)
        user_lower = user_input.lower()
        
        # 확인 키워드 체크
        confirm_keywords = ["예", "네", "확인", "좋아", "적용", "진행", "진행한다", "진행합니다", "다음", "다음으로", "완료", "ok", "yes", "ㅇㅋ", "ㅇㅇ"]
        if any(keyword in user_lower for keyword in confirm_keywords):
            print("\n[처리 결과] 레이아웃 설정 확인 완료")
            return {
                "layout_composition_completed": True,
                "messages": [AIMessage(content="레이아웃 설정이 완료되었습니다. 다음 단계로 진행합니다.")]
            }
        
        # 수정 키워드 체크
        modify_keywords = ["수정", "변경", "바꿔", "고쳐", "다시", "아니", "no"]
        is_modify_request = any(keyword in user_lower for keyword in modify_keywords) or len(user_input) > 10
        
        if is_modify_request:
            print("\n[처리 결과] 레이아웃 수정 요청")
            
            # 기존 레이아웃 정보 로드
            try:
                current_layouts = json.loads(layout_setting) if layout_setting else []
            except json.JSONDecodeError:
                current_layouts = []
            
            if llm:
                # LLM으로 수정 요청 처리
                prompt_modify = ChatPromptTemplate.from_messages([
                    ("system", "당신은 설문지 설계 전문가입니다. 사용자의 수정 요청을 반영하여 레이아웃을 재설정해주세요."),
                    ("human", """현재 레이아웃 설정:
{current_layouts}

사용자 수정 요청:
{modification_request}

현재 설정된 영역별 세부 항목:
{section_items}

사용자의 수정 요청을 반영하여 레이아웃을 재설정해주세요.

중요 지침:
1. 사용자가 "항목명 약어" 형식으로 입력한 경우 (예: "만족도 RS(7)", "기타 의견 OQ"):
   - 해당 약어를 정확히 사용하세요
   - RS, RK, MG는 숫자가 필요한 경우가 있으므로 괄호 안의 숫자도 함께 파싱하세요

2. 수정 요청에 명시된 항목만 수정하고, 나머지 항목은 현재 레이아웃을 유지하세요.

3. section_items에 나열된 모든 항목에 대해 레이아웃을 지정해야 합니다.

JSON 형식으로 응답해주세요:
{{
  "layout_settings": [
    {{
      "item": "항목명 또는 항목 설명",
      "layout_code": "약어",
      "layout_description": "레이아웃 설명"
    }},
    ...
  ]
}}""")
                ])
                
                chain_modify = prompt_modify | llm
                response_modify = chain_modify.invoke({
                    "current_layouts": json.dumps(current_layouts, ensure_ascii=False, indent=2),
                    "modification_request": user_input,
                    "section_items": section_items
                })
                
                content_modify = response_modify.content.strip()
                json_str_modify = extract_json_from_content(content_modify)
                
                if json_str_modify:
                    try:
                        result_modify = json.loads(json_str_modify)
                        layout_settings_list_modify = result_modify.get("layout_settings", [])
                        
                        # 각 항목에 약어별 상세 정보 추가
                        for layout_item in layout_settings_list_modify:
                            layout_code = layout_item.get("layout_code", "")
                            base_code = re.sub(r'\(.*?\)', '', layout_code).strip()
                            
                            if base_code in LAYOUT_CODE_INFO:
                                code_info = LAYOUT_CODE_INFO[base_code]
                                layout_item["layout_name"] = code_info["name"]
                                layout_item["layout_full_description"] = code_info["description"]
                        
                        layout_setting_json_modify = json.dumps(layout_settings_list_modify, ensure_ascii=False, indent=2)
                        
                        # 결과를 간결한 형식으로 변환
                        layout_result_text_modify = "[수정된 레이아웃 설정]\n\n"
                        for idx, layout_item in enumerate(layout_settings_list_modify, 1):
                            item_name = layout_item.get('item', '')
                            lc = layout_item.get('layout_code', '')
                            ln = layout_item.get('layout_name', '')
                            
                            if ln:
                                layout_result_text_modify += f"{idx}. {item_name}: {lc} ({ln})\n"
                            else:
                                layout_result_text_modify += f"{idx}. {item_name}: {lc}\n"
                        
                        layout_result_text_modify += "\n이대로 진행하시겠습니까? (예/아니오)"
                        
                        return {
                            "current_node": "set_layout_composition",
                            "executed_nodes": executed_nodes,
                            "messages": [AIMessage(content=layout_result_text_modify)],
                            "layout_setting": layout_setting_json_modify,
                            "layout_composition_completed": False
                        }
                    except json.JSONDecodeError:
                        pass
            
            # LLM 실패 시 기본 처리
            return {
                "current_node": "set_layout_composition",
                "executed_nodes": executed_nodes,
                "messages": [AIMessage(content="수정 요청을 처리할 수 없습니다. 다시 시도해주세요.")],
                "layout_composition_completed": False
            }
        
        # 수정 요청이 아닌 경우 (엉뚱한 입력)
        return {
            "messages": [AIMessage(content="레이아웃 설정을 확인해주세요.\n'예' 또는 '확인'으로 진행하거나, 수정할 내용을 입력해주세요.")],
            "layout_composition_completed": False
        }
    
    # =========================================================================
    # GraphRAG 제안 요청인지 직접 설정인지 판단
    # =========================================================================
    suggestion_keywords = ["제안", "추천", "llm 제안", "llm추천", "자동", "자동 제안", "자동추천"]
    is_suggestion_request = any(keyword in user_input.lower() for keyword in suggestion_keywords)
    
    # =========================================================================
    # GraphRAG 기반 레이아웃 제안
    # =========================================================================
    if is_suggestion_request:
        try:
            print("\n[GraphRAG 레이아웃 제안 생성 중...]")
            
            # section_items에서 항목 키워드 추출
            item_keywords = extract_item_keywords_from_section_items(section_items)
            
            if not item_keywords:
                return {
                    "current_node": "set_layout_composition",
                    "executed_nodes": executed_nodes,
                    "messages": [AIMessage(content="세부 항목을 찾을 수 없습니다. 다시 시도해주세요.")],
                    "layout_composition_completed": False
                }
            
            # GraphRAG로 유사 항목-문항-레이아웃 정보 수집
            graphrag_results = {}
            if is_graphrag_initialized():
                graphrag_results = find_similar_items_and_questions(
                    item_keywords=item_keywords,
                    top_k_items=5,
                    top_k_questions=5
                )
            
            # GraphRAG 결과를 LLM 프롬프트용 컨텍스트로 변환
            graphrag_context = ""
            for keyword, results in graphrag_results.items():
                if results:
                    graphrag_context += f"\n● 항목: {keyword}\n"
                    for idx, result in enumerate(results[:3], 1):
                        item_name = result.get("item_name", "")
                        question_text = result.get("question_text", "")
                        layout_code = result.get("layout_code", "")
                        layout_name = result.get("layout_name", "")
                        score = result.get("score", 0.0)
                        
                        graphrag_context += f"  {idx}. 유사 문항: {question_text}\n"
                        if layout_code:
                            graphrag_context += f"     사용된 레이아웃: {layout_code}"
                            if layout_name:
                                graphrag_context += f" ({layout_name})"
                            graphrag_context += f"\n"
                        graphrag_context += f"     유사도: {score:.3f}\n\n"
            
            if llm:
                # LLM에 GraphRAG 컨텍스트를 제공하여 레이아웃 제안 생성
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "당신은 설문지 설계 전문가입니다. GraphRAG를 통해 찾은 유사 설문의 레이아웃 정보를 참고하여 각 항목에 적합한 레이아웃을 제안해주세요."),
                    ("human", """현재 설정된 영역별 세부 항목:
{section_items}

GraphRAG를 통해 찾은 유사 설문의 레이아웃 정보:
{graphrag_context}

위 정보를 참고하여 각 항목에 적합한 레이아웃을 제안해주세요.

중요 지침:
1. GraphRAG에서 찾은 유사 문항의 레이아웃을 참고하되, 항목의 특성에 맞게 조정하세요.
2. RS, RK, MG는 숫자가 필요한 경우가 있으므로 적절한 숫자를 포함하세요 (예: RS(7), RK(5), MG(3))
3. section_items에 나열된 모든 항목에 대해 레이아웃을 제안해야 합니다.
4. 레이아웃 약어는 다음 중에서 선택하세요: SC, MA, DC, RS, RK, MG, OQ

JSON 형식으로 응답해주세요:
{{
  "layout_settings": [
    {{
      "item": "항목명 또는 항목 설명",
      "layout_code": "약어 (예: SC, RS(7), RK(5), MG(3), OQ 등)",
      "layout_description": "레이아웃 설명",
      "reasoning": "이 레이아웃을 선택한 이유 (GraphRAG 결과 참고)"
    }},
    ...
  ]
}}""")
                ])
                
                chain = prompt | llm
                response = chain.invoke({
                    "section_items": section_items,
                    "graphrag_context": graphrag_context if graphrag_context else "유사한 설문을 찾지 못했습니다. 항목의 특성에 맞게 레이아웃을 제안해주세요."
                })
                
                content = response.content.strip()
                json_str = extract_json_from_content(content)
                
                if json_str:
                    try:
                        result = json.loads(json_str)
                        layout_settings_list = result.get("layout_settings", [])
                        
                        # 각 항목에 약어별 상세 정보 추가
                        for layout_item in layout_settings_list:
                            layout_code = layout_item.get("layout_code", "")
                            base_code = re.sub(r'\(.*?\)', '', layout_code).strip()
                            
                            if base_code in LAYOUT_CODE_INFO:
                                code_info = LAYOUT_CODE_INFO[base_code]
                                layout_item["layout_name"] = code_info["name"]
                                layout_item["layout_full_description"] = code_info["description"]
                        
                        layout_setting_json = json.dumps(layout_settings_list, ensure_ascii=False, indent=2)
                        
                        # 결과를 간결한 형식으로 변환
                        layout_result_text = "[항목별 레이아웃 제안]\n\n"
                        for idx, layout_item in enumerate(layout_settings_list, 1):
                            item_name = layout_item.get('item', '')
                            lc = layout_item.get('layout_code', '')
                            ln = layout_item.get('layout_name', '')
                            
                            if ln:
                                layout_result_text += f"{idx}. {item_name}: {lc} ({ln})\n"
                            else:
                                layout_result_text += f"{idx}. {item_name}: {lc}\n"
                        
                        layout_result_text += "\n이대로 진행하시겠습니까? (예/아니오)"
                        
                        print("\n[GraphRAG 레이아웃 제안 완료] ✅")
                        
                        return {
                            "current_node": "set_layout_composition",
                            "executed_nodes": executed_nodes,
                            "messages": [AIMessage(content=layout_result_text)],
                            "layout_setting": layout_setting_json,
                            "layout_composition_completed": False
                        }
                    except json.JSONDecodeError:
                        pass
            
            # LLM 없거나 파싱 실패 시
            return {
                "current_node": "set_layout_composition",
                "executed_nodes": executed_nodes,
                "messages": [AIMessage(content="GraphRAG 레이아웃 제안 중 오류가 발생했습니다. 직접 레이아웃을 입력해주세요.")],
                "layout_composition_completed": False
            }
            
        except Exception as e:
            print(f"\n[오류] GraphRAG 레이아웃 제안 중 오류: {str(e)}")
            return {
                "current_node": "set_layout_composition",
                "executed_nodes": executed_nodes,
                "messages": [AIMessage(content=f"GraphRAG 레이아웃 제안 중 오류가 발생했습니다: {str(e)}\n\n직접 레이아웃을 입력해주세요.")],
                "layout_composition_completed": False
            }
    
    # =========================================================================
    # 직접 레이아웃 설정 (LLM으로 파싱)
    # =========================================================================
    try:
        print("\n[LLM 처리 중...] (항목별 레이아웃 파싱)")
        
        if llm:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "당신은 설문지 설계 전문가입니다. 사용자의 입력을 분석하여 각 항목에 지정된 레이아웃을 파악하고 JSON 형식으로 정리해주세요."),
                ("human", """현재 설정된 영역별 세부 항목:
{section_items}

사용자 입력:
{user_input}

사용자의 입력을 분석하여 각 항목에 지정된 레이아웃을 파악해주세요.

중요 지침:
1. 사용자가 "항목명 약어" 형식으로 입력한 경우 (예: "가구원 수 SC", "만족도 RS(7)", "기타 의견 OQ"):
   - 해당 약어를 정확히 사용하세요
   - RS, RK, MG는 숫자가 필요한 경우가 있으므로 괄호 안의 숫자도 함께 파싱하세요

2. 사용자가 여러 줄로 입력한 경우 (줄바꿈으로 구분):
   - 각 줄을 "항목명 약어" 형식으로 파싱하여 처리하세요

3. section_items에 나열된 모든 항목에 대해 레이아웃을 지정해야 합니다.
   - 사용자가 명시적으로 지정하지 않은 항목은 "미지정"으로 표시하세요.

JSON 형식으로 응답해주세요:
{{
  "layout_settings": [
    {{
      "item": "항목명 또는 항목 설명",
      "layout_code": "약어 (예: SC, RS(7), RK(5), MG(3), OQ 등)",
      "layout_description": "레이아웃 설명"
    }},
    ...
  ]
}}""")
            ])
            
            chain = prompt | llm
            response = chain.invoke({
                "section_items": section_items,
                "user_input": user_input
            })
            
            content = response.content.strip()
            json_str = extract_json_from_content(content)
            
            if json_str:
                try:
                    result = json.loads(json_str)
                    layout_settings_list = result.get("layout_settings", [])
                    
                    # 각 항목에 약어별 상세 정보 추가
                    for layout_item in layout_settings_list:
                        layout_code = layout_item.get("layout_code", "")
                        base_code = re.sub(r'\(.*?\)', '', layout_code).strip()
                        
                        if base_code in LAYOUT_CODE_INFO:
                            code_info = LAYOUT_CODE_INFO[base_code]
                            layout_item["layout_name"] = code_info["name"]
                            layout_item["layout_full_description"] = code_info["description"]
                    
                    layout_setting_json = json.dumps(layout_settings_list, ensure_ascii=False, indent=2)
                    
                    # 결과를 간결한 형식으로 변환
                    layout_result_text = "[항목별 레이아웃 설정]\n\n"
                    for idx, layout_item in enumerate(layout_settings_list, 1):
                        item_name = layout_item.get('item', '')
                        lc = layout_item.get('layout_code', '')
                        ln = layout_item.get('layout_name', '')
                        
                        if ln:
                            layout_result_text += f"{idx}. {item_name}: {lc} ({ln})\n"
                        else:
                            layout_result_text += f"{idx}. {item_name}: {lc}\n"
                    
                    layout_result_text += "\n이대로 진행하시겠습니까? (예/아니오)"
                    
                    print("\n[레이아웃 파싱 완료] ✅")
                    
                    return {
                        "current_node": "set_layout_composition",
                        "executed_nodes": executed_nodes,
                        "messages": [AIMessage(content=layout_result_text)],
                        "layout_setting": layout_setting_json,
                        "layout_composition_completed": False
                    }
                    
                except json.JSONDecodeError as e:
                    print(f"\n[오류] JSON 파싱 실패: {str(e)}")
        
        # LLM 없거나 파싱 실패 시 - 입력 형식 안내
        # 입력이 너무 짧거나 레이아웃 약어가 없으면 안내 메시지
        layout_codes = ["OQ", "SC", "MA", "DC", "RS", "RK", "MG"]
        has_layout_code = any(code in user_input.upper() for code in layout_codes)
        
        if not has_layout_code or len(user_input) < 5:
            return {
                "messages": [AIMessage(content="""입력 형식을 확인해주세요.

레이아웃 설정 방법:
1. "제안" 또는 "추천" 입력 → AI가 자동 제안
2. "항목명 약어" 형식으로 직접 입력

예시:
성별 SC
연령 SC
만족도 RS(5)

사용 가능한 약어: OQ, SC, MA, DC, RS, RK, MG""")],
                "layout_composition_completed": False
            }
        
        return {
            "messages": [AIMessage(content="레이아웃이 설정되었습니다.")],
            "layout_setting": user_input,
            "layout_composition_completed": True
        }
        
    except Exception as e:
        print(f"\n[오류] 레이아웃 설정 중 오류: {str(e)}")
        return {
            "messages": [AIMessage(content="레이아웃이 설정되었습니다.")],
            "layout_setting": user_input,
            "layout_composition_completed": True
        }


def generate_and_review_survey(state: SurveyState) -> SurveyState:
    """
    설문지 생성 및 검토 노드 (원본 패턴 반영)
    - GraphRAG로 유사 문항 조회
    - 분기 문항 설계 지침 포함
    - 수정 요청 처리 루프
    """
    executed_nodes = state.get("executed_nodes", [])
    messages = state.get("messages", [])
    survey_generation_completed = state.get("survey_generation_completed", False)
    survey_draft = state.get("survey_draft", "")
    intent = state.get("intent", "")
    hierarchical_structure = state.get("hierarchical_structure", "")
    section_items = state.get("section_items", "")
    layout_setting = state.get("layout_setting", "")
    
    if survey_generation_completed:
        return {}
    
    # 첫 실행: 설문지 생성
    if "generate_and_review_survey" not in executed_nodes:
        executed_nodes = list(executed_nodes) + ["generate_and_review_survey"]
        
        message_content = "이제 기존의 영역/설문구성/레이아웃을 참고해 설문지를 작성합니다."
        
        # 1. 세부항목에서 키워드 추출
        item_keywords = extract_item_keywords_from_section_items(section_items)
        
        # 2. GraphRAG: 유사 Item/Question 조회
        graph_item_questions = {}
        graph_item_questions_str = ""
        if item_keywords and is_graphrag_initialized():
            try:
                graph_item_questions = find_similar_items_and_questions(
                    item_keywords=item_keywords,
                    top_k_items=5,
                    top_k_questions=5
                )
                graph_item_questions_str = json.dumps(graph_item_questions, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[generate_and_review_survey] GraphRAG 오류: {e}")
        
        # 3. 프롬프트용 텍스트 변환
        graph_questions_text = ""
        if graph_item_questions:
            lines = []
            for kw, q_list in graph_item_questions.items():
                for q in q_list:
                    qtxt = q.get("question_text") or q.get("text") or ""
                    item_name = q.get("item_name") or kw
                    layout_code = q.get("layout_code") or ""
                    if qtxt:
                        line = f"{item_name}: {qtxt}"
                        if layout_code:
                            line += f" [{layout_code}]"
                        lines.append(line)
            graph_questions_text = "\n".join(lines)
        
        # 4. layout_setting 파싱
        layout_info = ""
        if layout_setting:
            try:
                layout_list = json.loads(layout_setting)
                layout_info = "항목별 레이아웃 설정:\n"
                for item in layout_list:
                    layout_info += f"- {item.get('item', '')}: {item.get('layout_code', '')}"
                    if item.get("layout_name"):
                        layout_info += f" ({item.get('layout_name')})"
                    layout_info += "\n"
            except:
                layout_info = f"레이아웃 설정: {layout_setting}\n"
        
        # 5. intent에서 문항 수 추출
        target_question_count = ""
        if intent:
            # "항목 개수: 20" 또는 "예상 문항 수: 20개" 패턴 찾기
            count_match = re.search(r'항목\s*개수[:\s]*(?:예상\s*문항\s*수[:\s]*)?\s*(\d+)', intent)
            if count_match:
                target_question_count = count_match.group(1)
        
        # 6. LLM으로 설문지 생성 (원본의 상세 프롬프트)
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "당신은 설문지 작성 전문가입니다. 주어진 정보와 내부 그래프 DB에서 가져온 기존 설문 문항들을 참고해 완전한 설문지를 작성해주세요."),
                ("human", """설문 목표:
{intent}

설문 영역 구조:
{hierarchical_structure}

영역별 세부 항목:
{section_items}

항목별 레이아웃 정보:
{layout_info}

내부 그래프 DB에서 가져온 유사 항목 및 기존 문항 예시:
{graph_questions_text}

★★★ 중요: 목표 문항 수 ★★★
{question_count_instruction}

설문지 작성 지침:
1. 각 영역별로 명확하게 구분하여 작성
2. 각 항목에 대해 지정된 레이아웃 형식(약어)에 맞게 질문과 응답 형식을 작성
3. 질문은 명확하고 이해하기 쉽게 작성
4. 선택지가 필요한 경우 적절한 선택지를 제공
5. 전체적으로 자연스럽고 일관성 있는 설문지가 되도록 작성
6. 위의 '기존 문항 예시'를 우선적으로 재사용하거나 적절히 변형하되, 조사 목적과 맞지 않는 경우에는 새로운 문항을 설계해도 됩니다.

7. 문항 번호 부여 및 분기 문항 설계 규칙:
   - 설문 전체에서 문항 번호는 1, 2, 3, 4... 와 같이 **영역과 상관없이 연속적으로** 부여합니다.
   - 영역(섹션) 번호(예: "1. 가구특성", "2. 경제활동")는 **제목에만 사용하고**, 문항 번호에는 포함하지 않습니다.
   - 질문 내용과 선택지, 레이아웃 정보를 보고, 특정 응답자에게만 추가 질문이 필요하다고 판단되면 **분기/조건부 문항을 스스로 설계**합니다.
   - 분기/조건부 문항은 **부모 문항 번호에 '-1', '-2'를 붙이는 방식**으로 번호를 부여합니다.
   - 분기 문항이 있는 경우, 부모 문항의 보기 옆에 **다음 문항 이동 규칙**을 명확하게 적어줍니다.
     예) "① 있다 → 문항 3-1로 이동 / ② 없다 → 문항 4로 이동"
   - 분기 후속 문항의 머리말에는 "(문항 3에서 '있다'라고 응답한 분만 응답)"과 같이 응답 조건을 표기합니다.

[분기 문항 예시]
문항 X. 지난 1년간 의료기관을 이용한 적이 있습니까? (예/아니오)
① 예 → 문항 X-1로 이동
② 아니오 → 문항 X+1로 이동

문항 X-1. (문항 X에서 '예' 응답자만) 주로 이용한 의료기관은 어디입니까? (SC)

8. 레이아웃 코드에 'MG'가 포함된 항목은 **마크다운 표(Markdown table)** 형식으로 작성
9. 레이아웃 코드에 'RS'가 포함된 경우 괄호 안의 숫자를 척도로 사용해서 숫자 위에 기준을 표시
   예시: 만족도(RS(10))
   전혀 만족하지 않는다          보통          매우만족한다
   ⓞ---①---②---③---④---⑤---⑥---⑦---⑧---⑨---⑩

★★★ 매우 중요: 문항과 선택지 형식 규칙 (반드시 준수) ★★★
10. 문항 형식: 반드시 "문항 X." 형식으로 시작하고, 끝에 레이아웃 코드를 괄호 안에 표시
    예시: 문항 1. 귀하의 성별은 무엇입니까? (SC)
    
11. 선택지 형식 (절대 규칙):
    - 반드시 원문자(①②③④⑤⑥⑦⑧⑨⑩)만 사용
    - 숫자점(1. 2. 3.) 절대 사용 금지
    - 대시(-) 절대 사용 금지
    - 불릿(•) 절대 사용 금지
    - 타입코드(SC, MA 등) 선택지에 절대 붙이지 않음
    
    [올바른 형식 - 반드시 이렇게 작성]:
    문항 1. 귀하의 성별은 무엇입니까? (SC)
    ① 남성
    ② 여성
    
    문항 2. 귀하의 나이는 몇 세입니까? (RS)
    ① 20대
    ② 30대
    ③ 40대
    ④ 50대
    ⑤ 60대 이상
    
    문항 3. 귀하의 직업은 무엇입니까? (RK)
    ① 전문직, 행정관리직
    ② 사무-기술직
    ③ 서비스 판매직
    ④ 농림·임업·어업·축산업
    ⑤ 기능, 기계조작, 단순노무
    
    [잘못된 형식 - 절대 사용 금지]:
    - 20대          ← 대시 사용 금지!
    1. 전문직       ← 숫자점 사용 금지!
    • 남성          ← 불릿 사용 금지!
    ① 남성 (SC)    ← 타입코드 붙이기 금지!

설문지 내용을 실제 설문지처럼 작성하되, 각 영역과 항목을 명확히 구분하여 작성해주세요.""")
            ])
            
            # 문항 수 지침 생성
            if target_question_count:
                question_count_instruction = f"사용자가 요청한 문항 수는 약 {target_question_count}개입니다. 이 숫자에 최대한 맞춰서 설문지를 작성해주세요. 분기 문항(X-1, X-2 등)을 포함해도 총 문항 수가 {target_question_count}개를 크게 초과하지 않도록 해주세요."
            else:
                question_count_instruction = "문항 수는 세부 항목 수에 맞춰 적절하게 작성해주세요."
            
            chain = prompt | llm
            response = chain.invoke({
                "intent": intent,
                "hierarchical_structure": hierarchical_structure,
                "section_items": section_items,
                "layout_info": layout_info,
                "graph_questions_text": graph_questions_text if graph_questions_text else "(참고 문항 없음)",
                "question_count_instruction": question_count_instruction
            })
            
            survey_draft = response.content.strip()
            
        except Exception as e:
            print(f"[generate_and_review_survey] 설문지 생성 오류: {e}")
            survey_draft = f"설문지 생성 중 오류가 발생했습니다: {e}"
        
        result_message = f"""{message_content}

[생성된 설문지]

{survey_draft}

설문 구성이 필요한 항목 번호와 변경이 필요한 내용을 말씀해 주시면 됩니다.
예시: "1번 항목의 질문을 더 명확하게 수정해주세요", "3번과 5번 항목의 선택지를 추가해주세요"
수정이 필요없으시면 '완료', '확인' 등으로 답변해주세요."""
        
        return {
            "current_node": "generate_and_review_survey",
            "executed_nodes": executed_nodes,
            "messages": [AIMessage(content=result_message)],
            "survey_draft": survey_draft,
            "graph_item_questions": graph_item_questions_str,
            "survey_generation_completed": False
        }
    
    # 설문지 생성 이후: 사용자 피드백 처리
    if not messages or not isinstance(messages[-1], HumanMessage):
        return {}
    
    user_input = messages[-1].content.strip()
    
    if survey_draft:
        try:
            # 사용자 입력 분석 (완료 vs 수정)
            prompt = ChatPromptTemplate.from_messages([
                ("system", "사용자의 입력이 설문 완료 확인인지, 수정 요청인지 판단하세요."),
                ("human", """설문지: {survey_draft}

사용자 입력: {user_input}

JSON으로 응답: {{"is_complete": true/false, "is_modify_request": true/false, "comment": "해석"}}""")
            ])
            
            chain = prompt | llm
            response = chain.invoke({
                "survey_draft": survey_draft[:1000],  # 길이 제한
                "user_input": user_input
            })
            
            json_str = extract_json_from_content(response.content)
            
            is_complete = False
            is_modify_request = False
            
            if json_str:
                result = json.loads(json_str)
                is_complete = result.get("is_complete", False)
                is_modify_request = result.get("is_modify_request", False)
            
            # 키워드 폴백
            low = user_input.lower()
            complete_keywords = ["완료", "확인", "다음", "진행", "좋아", "괜찮", "ok", "yes", "네", "예"]
            modify_keywords = ["수정", "변경", "바꿔", "고쳐", "추가", "삭제", "문항", "질문", "선택지", "보기"]
            
            if any(k in low for k in complete_keywords):
                is_complete = True
            elif any(k in low for k in modify_keywords) or (len(user_input) > 20 and any(c.isdigit() for c in user_input)):
                is_modify_request = True
            
            # 완료 처리
            if is_complete and not is_modify_request:
                return {
                    "messages": [AIMessage(content="설문지 구성이 완료되었습니다. 다음 단계(최종 검토)로 진행합니다.")],
                    "survey_generation_completed": True
                }
            
            # 엉뚱한 입력 처리
            if not is_complete and not is_modify_request:
                return {
                    "messages": [AIMessage(content="""입력을 이해하지 못했습니다.

- 현재 설문지로 진행하려면 '완료' 또는 '확인'을 입력하세요.
- 수정이 필요하면 구체적인 수정 내용을 입력해주세요.
  예: "3번 문항의 선택지를 5개로 늘려주세요"
  예: "만족도 문항을 추가해주세요" """)],
                    "survey_generation_completed": False
                }
            
            # 수정 요청 처리
            if is_modify_request:
                try:
                    modify_prompt = ChatPromptTemplate.from_messages([
                        ("system", "기존 설문지와 사용자의 수정 요청을 반영하여 수정된 설문지를 작성하세요."),
                        ("human", """기존 설문지:
{survey_draft}

사용자 수정 요청:
{user_input}

수정된 설문지 전체를 작성해주세요.""")
                    ])
                    
                    modify_chain = modify_prompt | llm
                    modify_response = modify_chain.invoke({
                        "survey_draft": survey_draft,
                        "user_input": user_input
                    })
                    
                    modified_draft = modify_response.content.strip()
                    
                    modify_message = f"""수정 요청을 반영하여 설문지를 수정했습니다.

[수정된 설문지]

{modified_draft}

추가 수정이 필요하시면 말씀해주세요.
수정이 완료되었으면 '완료', '확인' 등으로 답변해주세요."""
                    
                    return {
                        "messages": [AIMessage(content=modify_message)],
                        "survey_draft": modified_draft,
                        "final_survey": modified_draft,
                        "survey_generation_completed": False
                    }
                except Exception as e:
                    return {
                        "messages": [AIMessage(content=f"수정 중 오류가 발생했습니다: {e}\n다시 시도해주세요.")],
                        "survey_generation_completed": False
                    }
            
            # 불명확한 경우
            return {
                "messages": [AIMessage(content="설문지를 확인하시겠습니까? 수정이 필요하시면 구체적으로 말씀해주세요.\n완료하시려면 '완료', '확인' 등으로 답변해주세요.")],
                "survey_generation_completed": False
            }
            
        except Exception as e:
            print(f"[generate_and_review_survey] 피드백 처리 오류: {e}")
            # 키워드로 간단히 처리
            low = user_input.lower()
            if any(k in low for k in ["완료", "확인", "다음", "진행"]):
                return {
                    "messages": [AIMessage(content="설문지 생성이 완료되었습니다.")],
                    "survey_generation_completed": True
                }
            return {
                "messages": [AIMessage(content="수정 사항을 확인했습니다. 구체적인 수정 내용을 입력해주세요.")],
                "survey_generation_completed": False
            }
    
    return {}


def finalize_and_refine_survey(state: SurveyState) -> SurveyState:
    """
    설문 최종 검토 및 정교화 노드 (원본 패턴 반영)
    - 7가지 관점 품질 검토
    - 개선된 설문지 제안
    - 수정 피드백 루프
    """
    executed_nodes = state.get("executed_nodes", [])
    messages = state.get("messages", [])
    survey_finalization_completed = state.get("survey_finalization_completed", False)
    survey_draft = state.get("survey_draft", "")
    intent = state.get("intent", "")
    survey_review_apply = state.get("survey_review_apply")
    
    if survey_finalization_completed:
        return {}
    
    # 첫 실행: LLM 품질 검토 수행
    if "finalize_and_refine_survey" not in executed_nodes:
        executed_nodes = list(executed_nodes) + ["finalize_and_refine_survey"]
        
        # 원래 설문지 저장
        original_survey = survey_draft
        
        message_intro = "생성된 초안에 대해 타당성, 편향성, 이중 질문 등의 품질 검토를 수행하겠습니다."
        
        # LLM으로 7가지 관점 품질 검토
        review_result = ""
        refined_survey = survey_draft
        has_improvements = False
        
        if llm:
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "당신은 설문지 품질 검토 전문가입니다. 주어진 설문지에 대해 다양한 관점에서 품질을 검토하고, 개선점이 있다면 제안해주세요."),
                    ("human", """조사 목적:
{intent}

설문지 초안:
{survey_draft}

위 설문지에 대해 다음 7가지 관점에서 품질을 검토해주세요:

1. **타당성**: 질문이 조사 목적을 정확히 측정하는가?
2. **편향성**: 질문이나 선택지에 편향이 있는가? (예: 유도 질문, 사회적 바람직성 편향 등)
3. **이중 질문**: 하나의 질문에 두 가지 이상의 내용이 포함되어 있는가?
4. **명확성**: 질문이 명확하고 이해하기 쉬운가?
5. **응답 범주**: 선택지가 적절하고 포괄적인가?
6. **순서와 흐름**: 질문 순서가 논리적이고 자연스러운가?
7. **기타 개선 사항**: 기타 발견된 문제점이나 개선 제안

검토 결과를 JSON 형식으로 제공해주세요:
{{"review_result": "검토 결과 상세 설명", "refined_survey": "개선된 설문지 (개선이 있으면 수정본, 없으면 현재 그대로)", "has_improvements": true 또는 false}}

중요:
- 개선 제안이 있으면 "refined_survey"에 개선된 설문지를 작성
- 개선이 없으면 "refined_survey"에 현재 설문지 그대로 반환
- "review_result"에는 각 관점별 검토 결과를 포함""")
                ])
                
                chain = prompt | llm
                response = chain.invoke({
                    "intent": intent,
                    "survey_draft": survey_draft
                })
                
                content = response.content.strip()
                json_str = extract_json_from_content(content)
                
                if json_str:
                    result = json.loads(json_str)
                    review_result = result.get("review_result", "")
                    refined_survey = result.get("refined_survey", survey_draft)
                    has_improvements = result.get("has_improvements", False)
                else:
                    # JSON 파싱 실패 시 전체 응답을 검토 결과로 사용
                    review_result = content
                    refined_survey = survey_draft
                    has_improvements = False
                    
            except Exception as e:
                print(f"[finalize_and_refine_survey] 품질 검토 오류: {e}")
                review_result = "품질 검토를 완료했습니다. 현재 설문지를 그대로 유지합니다."
        
        # 검토 결과 메시지 생성
        if has_improvements:
            review_message = f"""{message_intro}

[품질 검토 결과]

{review_result}

[개선된 설문지]

{refined_survey}

검토 의견을 반영하여 설문지를 개선하시겠습니까? (예/아니오)"""
        else:
            review_message = f"""{message_intro}

[품질 검토 결과]

{review_result}

[검토된 설문지]

{refined_survey}

현재 설문지가 적절합니다. 다음 단계로 진행하시겠습니까? (예/아니오)"""
        
        return {
            "current_node": "finalize_and_refine_survey",
            "executed_nodes": executed_nodes,
            "messages": [AIMessage(content=review_message)],
            "survey_finalization_completed": False,
            "survey_review_message": review_result,
            "original_survey_draft": original_survey,
            "survey_draft": refined_survey,
            "final_survey": refined_survey
        }
    
    # 사용자 입력 확인
    if not messages or not isinstance(messages[-1], HumanMessage):
        return {}
    
    user_input = messages[-1].content.strip()
    
    # 검토 의견 반영 여부가 아직 결정되지 않은 경우
    if survey_review_apply is None:
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "사용자의 입력을 분석하여 검토 의견 반영 여부를 판단하세요."),
                ("human", """사용자 입력: {user_input}

"예", "네", "동의", "반영", "수정", "적용" → 반영
"아니오", "아니요", "거부", "스킵", "다음", "필요없어" → 미반영

JSON 형식: {{"apply": true 또는 false}}""")
            ])
            
            chain = prompt | llm
            response = chain.invoke({"user_input": user_input})
            
            json_str = extract_json_from_content(response.content)
            
            apply = False
            if json_str:
                result = json.loads(json_str)
                apply = result.get("apply", False)
            else:
                # 키워드 폴백
                low = user_input.lower()
                if any(k in low for k in ["예", "네", "동의", "반영", "수정", "적용"]):
                    apply = True
            
            if apply:
                # 검토 의견 반영 - refined_survey가 이미 survey_draft에 저장됨
                return {
                    "survey_review_apply": True,
                    "final_survey": state.get("survey_draft", ""),
                    "messages": [AIMessage(content="검토 의견을 반영하여 설문지를 개선했습니다.\n\n추가로 수정할 사항이 있으시면 알려주세요.\n수정이 필요없으시면 '완료', '확인' 등으로 답변해주세요.")],
                    "survey_finalization_completed": False
                }
            else:
                # 검토 의견 미반영 - 원래 설문지 복원
                original_survey = state.get("original_survey_draft", survey_draft)
                return {
                    "survey_review_apply": False,
                    "final_survey": original_survey,
                    "survey_draft": original_survey,
                    "messages": [AIMessage(content="검토 의견을 반영하지 않고 원래 설문지를 유지합니다.\n\n추가로 수정할 사항이 있으시면 알려주세요.\n수정이 필요없으시면 '완료', '확인' 등으로 답변해주세요.")],
                    "survey_finalization_completed": False
                }
                
        except Exception as e:
            print(f"[finalize_and_refine_survey] 반영 여부 판단 오류: {e}")
            return {
                "messages": [AIMessage(content="입력을 이해하지 못했습니다.\n\n- 검토 의견을 반영하려면 '예' 또는 '네'를 입력하세요.\n- 반영하지 않으려면 '아니오'를 입력하세요.")],
                "survey_finalization_completed": False
            }
    
    # 검토 의견 반영 여부가 결정된 후 추가 수정 요청 처리
    if survey_review_apply is not None:
        completion_keywords = ["완료", "확인", "다음", "진행", "수정할 내용 없", "수정 없", "변경 없", "ok", "yes", "네", "예", "좋아"]
        modify_keywords = ["수정", "변경", "바꿔", "고쳐", "추가", "삭제", "문항", "질문", "선택지"]
        low = user_input.lower()
        
        if any(k in low for k in completion_keywords) and not any(k in low for k in modify_keywords):
            # 최종 완료
            return {
                "survey_finalization_completed": True,
                "messages": [AIMessage(content="설문 최종 검토 및 정교화가 완료되었습니다. 다음 단계로 진행합니다.")]
            }
        elif len(user_input) < 5 and not any(k in low for k in modify_keywords):
            # 짧고 의미없는 입력
            return {
                "messages": [AIMessage(content="입력을 이해하지 못했습니다.\n\n- 설문지를 완료하려면 '완료' 또는 '확인'을 입력하세요.\n- 수정이 필요하면 구체적인 수정 내용을 입력해주세요.\n  예: '3번 문항 삭제해주세요', '만족도 항목 추가해주세요'")],
                "survey_finalization_completed": False
            }
        else:
            # 추가 수정 요청 처리
            try:
                modify_prompt = ChatPromptTemplate.from_messages([
                    ("system", "기존 설문지와 사용자의 수정 요청을 반영하여 수정된 설문지를 작성하세요."),
                    ("human", """기존 설문지:
{survey_draft}

사용자 수정 요청:
{user_input}

수정된 설문지 전체를 작성해주세요.""")
                ])
                
                modify_chain = modify_prompt | llm
                modify_response = modify_chain.invoke({
                    "survey_draft": state.get("survey_draft", ""),
                    "user_input": user_input
                })
                
                modified_draft = modify_response.content.strip()
                
                return {
                    "survey_draft": modified_draft,
                    "final_survey": modified_draft,
                    "messages": [AIMessage(content=f"수정 요청을 반영했습니다.\n\n[수정된 설문지]\n\n{modified_draft}\n\n추가 수정이 필요하시면 말씀해주세요.\n완료하시려면 '완료', '확인' 등으로 답변해주세요.")],
                    "survey_finalization_completed": False
                }
            except Exception as e:
                return {
                    "messages": [AIMessage(content=f"수정 중 오류가 발생했습니다: {e}\n다시 시도해주세요.")],
                    "survey_finalization_completed": False
                }
    
    return {}


def create_draft(state: SurveyState) -> SurveyState:
    """초안 생성 완료 노드"""
    executed_nodes = state.get("executed_nodes", [])
    draft_creation_completed = state.get("draft_creation_completed", False)
    final_survey = state.get("final_survey", "")
    survey_draft = state.get("survey_draft", "")
    
    if draft_creation_completed:
        return {}
    
    if "create_draft" not in executed_nodes:
        executed_nodes = list(executed_nodes) + ["create_draft"]
        
        survey_content = final_survey or survey_draft
        
        if not survey_content:
            return {
                "current_node": "create_draft",
                "executed_nodes": executed_nodes,
                "messages": [AIMessage(content="오류: 생성할 설문지 내용이 없습니다.")],
                "draft_creation_completed": False
            }
        
        message_content = """설문지 작성이 완료되었습니다!

상단의 '내보내기' 버튼을 클릭하여 DOCX 또는 PDF로 다운로드할 수 있습니다."""
        
        return {
            "current_node": "create_draft",
            "executed_nodes": executed_nodes,
            "messages": [AIMessage(content=message_content)],
            "draft_creation_completed": True
        }
    
    return {}


# ============================================================================
# 라우팅 함수
# ============================================================================

def should_continue_to_database(state: SurveyState) -> str:
    if state.get("survey_objective_completed", False):
        return "select_database"
    return "wait"

def should_continue_after_database(state: SurveyState) -> str:
    if state.get("database_selection_completed", False):
        return "set_survey_areas"
    return "wait"

def should_continue_after_survey_areas(state: SurveyState) -> str:
    if state.get("survey_areas_completed", False):
        return "review_area_structure"
    return "wait"

def should_continue_after_area_review(state: SurveyState) -> str:
    if state.get("area_structure_review_completed", False):
        return "set_detailed_items"
    return "wait"

def should_continue_after_detailed_items(state: SurveyState) -> str:
    if state.get("detailed_items_completed", False):
        return "review_detailed_items_structure"
    return "wait"

def should_continue_after_detailed_items_review(state: SurveyState) -> str:
    if state.get("detailed_items_review_completed", False):
        return "set_layout_composition"
    return "wait"

def should_continue_after_layout_composition(state: SurveyState) -> str:
    if state.get("layout_composition_completed", False):
        return "generate_and_review_survey"
    return "wait"

def should_continue_after_survey_generation(state: SurveyState) -> str:
    if state.get("survey_generation_completed", False):
        return "finalize_and_refine_survey"
    return "wait"

def should_continue_after_finalization(state: SurveyState) -> str:
    if state.get("survey_finalization_completed", False):
        return "create_draft"
    return "wait"

def should_continue_after_draft_creation(state: SurveyState) -> str:
    if state.get("draft_creation_completed", False):
        return "continue"
    return "wait"


# ============================================================================
# 그래프 생성
# ============================================================================

def create_survey_graph():
    """설문 작성 그래프 생성"""
    workflow = StateGraph(SurveyState)
    
    # 노드 추가
    workflow.add_node("set_survey_objective", set_survey_objective)
    workflow.add_node("select_database", select_database)
    workflow.add_node("set_survey_areas", set_survey_areas)
    workflow.add_node("review_area_structure", review_area_structure)
    workflow.add_node("set_detailed_items", set_detailed_items)
    workflow.add_node("review_detailed_items_structure", review_detailed_items_structure)
    workflow.add_node("set_layout_composition", set_layout_composition)
    workflow.add_node("generate_and_review_survey", generate_and_review_survey)
    workflow.add_node("finalize_and_refine_survey", finalize_and_refine_survey)
    workflow.add_node("create_draft", create_draft)
    
    # 엣지 설정
    workflow.set_entry_point("set_survey_objective")
    
    workflow.add_conditional_edges("set_survey_objective", should_continue_to_database,
        {"select_database": "select_database", "wait": END})
    workflow.add_conditional_edges("select_database", should_continue_after_database,
        {"set_survey_areas": "set_survey_areas", "wait": END})
    workflow.add_conditional_edges("set_survey_areas", should_continue_after_survey_areas,
        {"review_area_structure": "review_area_structure", "wait": END})
    workflow.add_conditional_edges("review_area_structure", should_continue_after_area_review,
        {"set_detailed_items": "set_detailed_items", "wait": END})
    workflow.add_conditional_edges("set_detailed_items", should_continue_after_detailed_items,
        {"review_detailed_items_structure": "review_detailed_items_structure", "wait": END})
    workflow.add_conditional_edges("review_detailed_items_structure", should_continue_after_detailed_items_review,
        {"set_layout_composition": "set_layout_composition", "wait": END})
    workflow.add_conditional_edges("set_layout_composition", should_continue_after_layout_composition,
        {"generate_and_review_survey": "generate_and_review_survey", "wait": END})
    workflow.add_conditional_edges("generate_and_review_survey", should_continue_after_survey_generation,
        {"finalize_and_refine_survey": "finalize_and_refine_survey", "wait": END})
    workflow.add_conditional_edges("finalize_and_refine_survey", should_continue_after_finalization,
        {"create_draft": "create_draft", "wait": END})
    workflow.add_conditional_edges("create_draft", should_continue_after_draft_creation,
        {"wait": END, "continue": END})
    
    return workflow.compile()


# ============================================================================
# API 함수
# ============================================================================

def initialize_survey():
    """설문 초기화"""
    initial_state: SurveyState = {
        "messages": [],
        "executed_nodes": []
    }
    graph = create_survey_graph()
    result = graph.invoke(initial_state)
    return graph, result


def process_user_input(graph, state: SurveyState, user_input: str) -> SurveyState:
    """사용자 입력 처리"""
    current_state = state.copy()
    if "messages" not in current_state:
        current_state["messages"] = []
    
    current_state["messages"] = current_state["messages"] + [HumanMessage(content=user_input)]
    result = graph.invoke(current_state)
    
    # 다음 노드로 자동 진행
    current_node_after = result.get("current_node")
    if current_node_after and current_node_after in NODE_ORDER:
        current_idx = NODE_ORDER.index(current_node_after)
        if current_idx < len(NODE_ORDER) - 1:
            messages = result.get("messages", [])
            if messages and isinstance(messages[-1], HumanMessage):
                result = graph.invoke(result)
    
    return result


def get_new_ai_messages(state: SurveyState, prev_message_count: int):
    """새 AI 메시지 추출"""
    messages = state.get("messages", [])
    new_messages = []
    for i in range(prev_message_count, len(messages)):
        if isinstance(messages[i], AIMessage):
            new_messages.append(messages[i].content)
    return new_messages, len(messages)


def get_changed_fields(previous_state: SurveyState, current_state: SurveyState):
    """변경된 필드 반환"""
    changed_fields = {}
    for field in IMPORTANT_FIELDS:
        prev_value = previous_state.get(field)
        curr_value = current_state.get(field)
        if prev_value != curr_value:
            if curr_value is not None and curr_value != "":
                changed_fields[field] = curr_value
    return changed_fields


def get_latest_changed_field(changed_fields: dict, current_state: SurveyState):
    """가장 최근 변경된 필드"""
    if changed_fields:
        priority_order = ["final_survey", "survey_draft", "section_items", "hierarchical_structure",
                         "intent", "layout_setting", "survey_review_message",
                         "detailed_items_review_message", "area_review_message"]
        for field in priority_order:
            if field in changed_fields:
                return field, changed_fields[field]
        first_field = list(changed_fields.keys())[0]
        return first_field, changed_fields[first_field]
    else:
        important_fields = [
            ("final_survey", "최종 설문지"),
            ("survey_draft", "설문지 초안"),
            ("section_items", "세부 항목"),
            ("hierarchical_structure", "단계별 영역"),
            ("intent", "설문 목표"),
        ]
        for field_key, _ in important_fields:
            value = current_state.get(field_key)
            if value:
                return field_key, value
        return None, None


def is_survey_complete(state: SurveyState) -> bool:
    """완료 여부 확인"""
    return state.get("draft_creation_completed", False)