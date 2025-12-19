# backend/app/services/session.py

"""
세션 관리 모듈
- 메모리 기반 세션 저장소
- 세션별 LangGraph 인스턴스 관리
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import copy

from .workflow import create_survey_graph, SurveyState


# 세션 저장소 (메모리)
sessions: Dict[str, Dict[str, Any]] = {}


def create_session() -> str:
    """새 세션 생성"""
    session_id = str(uuid.uuid4())
    
    # LangGraph 인스턴스 생성
    graph = create_survey_graph()
    
    # 초기 상태
    initial_state: SurveyState = {
        "messages": [],
        "executed_nodes": []
    }
    
    # 첫 실행 (환영 메시지)
    result = graph.invoke(initial_state)
    
    sessions[session_id] = {
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "state": result,
        "previous_state": {},
        "graph": graph,
        "message_count": len(result.get("messages", []))
    }
    
    return session_id


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """세션 조회"""
    return sessions.get(session_id)


def update_session_state(session_id: str, new_state: SurveyState) -> bool:
    """세션 상태 업데이트"""
    if session_id not in sessions:
        return False
    
    sessions[session_id]["previous_state"] = copy.deepcopy(sessions[session_id]["state"])
    sessions[session_id]["state"] = new_state
    sessions[session_id]["updated_at"] = datetime.now().isoformat()
    sessions[session_id]["message_count"] = len(new_state.get("messages", []))
    
    return True


def update_session_field(session_id: str, field: str, value: Any) -> bool:
    """세션 특정 필드 업데이트"""
    if session_id not in sessions:
        return False
    
    sessions[session_id]["state"][field] = value
    sessions[session_id]["updated_at"] = datetime.now().isoformat()
    
    return True


def delete_session(session_id: str) -> bool:
    """세션 삭제"""
    if session_id in sessions:
        del sessions[session_id]
        return True
    return False


def reset_session(session_id: str) -> Optional[Dict[str, Any]]:
    """세션 초기화 (새로 시작)"""
    if session_id in sessions:
        delete_session(session_id)
    
    # 같은 ID로 새 세션 생성
    graph = create_survey_graph()
    initial_state: SurveyState = {
        "messages": [],
        "executed_nodes": []
    }
    result = graph.invoke(initial_state)
    
    sessions[session_id] = {
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "state": result,
        "previous_state": {},
        "graph": graph,
        "message_count": len(result.get("messages", []))
    }
    
    return sessions[session_id]


def get_all_sessions() -> Dict[str, Dict[str, Any]]:
    """모든 세션 조회 (디버깅용)"""
    return {
        sid: {
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "current_node": data["state"].get("current_node"),
            "message_count": data["message_count"]
        }
        for sid, data in sessions.items()
    }