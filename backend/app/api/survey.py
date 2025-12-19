# backend/app/api/survey.py

"""
설문 채팅/상태 API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import copy

from ..services.session import (
    create_session,
    get_session,
    update_session_state,
    update_session_field,
    reset_session,
)
from ..services.workflow import (
    process_user_input,
    get_new_ai_messages,
    get_changed_fields,
    get_latest_changed_field,
    is_survey_complete,
    NODE_ORDER,
    FIELD_NAMES,
    IMPORTANT_FIELDS,
)
from langchain_core.messages import AIMessage, HumanMessage

router = APIRouter(prefix="/api/survey", tags=["survey"])


# ============================================================================
# Request/Response 모델
# ============================================================================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class MessageResponse(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatResponse(BaseModel):
    session_id: str
    messages: List[MessageResponse]
    state: Dict[str, Any]
    current_step: int
    is_complete: bool
    changed_field: Optional[str] = None
    changed_value: Optional[str] = None


class StateResponse(BaseModel):
    session_id: str
    state: Dict[str, Any]
    current_step: int
    is_complete: bool


class PreviewResponse(BaseModel):
    session_id: str
    field_name: Optional[str] = None
    field_display_name: Optional[str] = None
    field_value: Optional[str] = None
    all_fields: Dict[str, Any]


class FieldUpdateRequest(BaseModel):
    value: str


# ============================================================================
# 헬퍼 함수
# ============================================================================

def calculate_current_step(executed_nodes: List[str]) -> int:
    """실행된 노드를 기반으로 현재 단계 계산"""
    step_mapping = {
        1: ["set_survey_objective"],
        2: ["select_database"],
        3: ["set_survey_areas", "review_area_structure"],
        4: ["set_detailed_items", "review_detailed_items_structure"],
        5: ["set_layout_composition"],
        6: ["generate_and_review_survey", "finalize_and_refine_survey", "create_draft"]
    }
    
    current_step = 1
    for step, nodes in step_mapping.items():
        if any(node in executed_nodes for node in nodes):
            current_step = step
    
    return current_step


def serialize_messages(messages: list) -> List[MessageResponse]:
    """LangChain 메시지를 직렬화"""
    result = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            result.append(MessageResponse(role="assistant", content=msg.content))
        elif isinstance(msg, HumanMessage):
            result.append(MessageResponse(role="user", content=msg.content))
    return result


def serialize_state(state: dict) -> Dict[str, Any]:
    """상태를 JSON 직렬화 가능하게 변환"""
    serialized = {}
    for key, value in state.items():
        if key == "messages":
            continue  # messages는 별도 처리
        elif isinstance(value, (str, int, float, bool, type(None))):
            serialized[key] = value
        elif isinstance(value, list):
            serialized[key] = value
        elif isinstance(value, dict):
            serialized[key] = value
        else:
            serialized[key] = str(value)
    return serialized


# ============================================================================
# 엔드포인트
# ============================================================================

@router.post("/init", response_model=ChatResponse)
async def init_survey():
    """새 설문 세션 초기화"""
    session_id = create_session()
    session = get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=500, detail="세션 생성 실패")
    
    state = session["state"]
    messages = serialize_messages(state.get("messages", []))
    executed_nodes = state.get("executed_nodes", [])
    current_step = calculate_current_step(executed_nodes)
    
    return ChatResponse(
        session_id=session_id,
        messages=messages,
        state=serialize_state(state),
        current_step=current_step,
        is_complete=is_survey_complete(state)
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """사용자 메시지 처리"""
    # 세션 확인 또는 생성
    if request.session_id:
        session = get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        session_id = request.session_id
    else:
        session_id = create_session()
        session = get_session(session_id)
    
    # 이전 상태 저장
    previous_state = copy.deepcopy(session["state"])
    prev_message_count = session["message_count"]
    
    # 사용자 입력 처리
    graph = session["graph"]
    current_state = session["state"]
    
    result = process_user_input(graph, current_state, request.message)
    
    # 세션 상태 업데이트
    update_session_state(session_id, result)
    
    # 새 AI 메시지 추출
    new_messages, new_count = get_new_ai_messages(result, prev_message_count)
    
    # 변경된 필드 확인
    changed_fields = get_changed_fields(previous_state, result)
    latest_field, latest_value = get_latest_changed_field(changed_fields, result)
    
    # 응답 생성
    messages = serialize_messages(result.get("messages", []))
    executed_nodes = result.get("executed_nodes", [])
    current_step = calculate_current_step(executed_nodes)
    
    return ChatResponse(
        session_id=session_id,
        messages=messages,
        state=serialize_state(result),
        current_step=current_step,
        is_complete=is_survey_complete(result),
        changed_field=latest_field,
        changed_value=str(latest_value) if latest_value else None
    )


@router.get("/state/{session_id}", response_model=StateResponse)
async def get_state(session_id: str):
    """세션 상태 조회"""
    session = get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    
    state = session["state"]
    executed_nodes = state.get("executed_nodes", [])
    current_step = calculate_current_step(executed_nodes)
    
    return StateResponse(
        session_id=session_id,
        state=serialize_state(state),
        current_step=current_step,
        is_complete=is_survey_complete(state)
    )


@router.put("/state/{session_id}/{field}")
async def update_field(session_id: str, field: str, request: FieldUpdateRequest):
    """특정 필드 업데이트 (사이드바 편집)"""
    session = get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    
    if field not in IMPORTANT_FIELDS and field not in FIELD_NAMES:
        raise HTTPException(status_code=400, detail="유효하지 않은 필드입니다")
    
    success = update_session_field(session_id, field, request.value)
    
    if not success:
        raise HTTPException(status_code=500, detail="필드 업데이트 실패")
    
    return {
        "success": True,
        "field": field,
        "field_display_name": FIELD_NAMES.get(field, field),
        "value": request.value
    }


@router.get("/preview/{session_id}", response_model=PreviewResponse)
async def get_preview(session_id: str):
    """미리보기 데이터 조회"""
    session = get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    
    state = session["state"]
    previous_state = session.get("previous_state", {})
    
    # 변경된 필드 확인
    changed_fields = get_changed_fields(previous_state, state)
    latest_field, latest_value = get_latest_changed_field(changed_fields, state)
    
    # 중요 필드들 수집
    all_fields = {}
    for field in IMPORTANT_FIELDS:
        value = state.get(field)
        if value:
            all_fields[FIELD_NAMES.get(field, field)] = value
    
    return PreviewResponse(
        session_id=session_id,
        field_name=latest_field,
        field_display_name=FIELD_NAMES.get(latest_field, latest_field) if latest_field else None,
        field_value=str(latest_value) if latest_value else None,
        all_fields=all_fields
    )


@router.post("/reset/{session_id}")
async def reset(session_id: str):
    """세션 초기화"""
    session = reset_session(session_id)
    
    if not session:
        raise HTTPException(status_code=500, detail="세션 초기화 실패")
    
    state = session["state"]
    messages = serialize_messages(state.get("messages", []))
    
    return {
        "success": True,
        "session_id": session_id,
        "messages": messages
    }