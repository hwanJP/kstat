# backend/app/services/graphrag.py

"""
Neo4j GraphRAG 연동 모듈
- 벡터 검색으로 유사한 설문/영역/항목/문항 검색
"""

import os
import re
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# 환경 변수
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://a4643f6b.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "8D1egQnwNTqSdNKOF3TMCfr0wrbkS9Gs1Il4mdMICBw")

# 인덱스 이름
NEO4J_INDEX_NAME = "question_text_index"
AREA_INDEX_NAME = "area_name_index"
SURVEY_CATEGORY_INDEX_NAME = "surveycategory_name_index"

# 전역 변수
neo4j_driver = None
graph_embedder = None
_initialized = False


def init_graphrag() -> bool:
    """GraphRAG 초기화"""
    global neo4j_driver, graph_embedder, _initialized
    
    if _initialized:
        return True
    
    if not OPENAI_API_KEY:
        print("[GraphRAG] 경고: OPENAI_API_KEY가 설정되지 않았습니다.")
        return False
    
    try:
        from neo4j import GraphDatabase
        from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
        
        neo4j_driver = GraphDatabase.driver(
            NEO4J_URI, 
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        
        graph_embedder = OpenAIEmbeddings(
            model="text-embedding-3-large",
            api_key=OPENAI_API_KEY,
        )
        
        # 연결 테스트
        with neo4j_driver.session() as session:
            session.run("RETURN 1")
        
        _initialized = True
        print("[GraphRAG] 초기화 완료")
        return True
        
    except Exception as e:
        print(f"[GraphRAG] 초기화 오류: {e}")
        return False


def close_graphrag():
    """GraphRAG 연결 종료"""
    global neo4j_driver, _initialized
    if neo4j_driver:
        neo4j_driver.close()
        neo4j_driver = None
    _initialized = False


def is_initialized() -> bool:
    """초기화 여부 확인"""
    return _initialized


# ============================================================================
# 파싱 유틸리티
# ============================================================================

def parse_section_items_to_keywords(section_items: str) -> List[str]:
    """section_items 문자열에서 항목 키워드 추출"""
    if not section_items:
        return []

    lines = [l.strip() for l in section_items.splitlines() if l.strip()]
    candidates = []
    
    for line in lines:
        if ":" in line:
            _, tail = line.split(":", 1)
        else:
            tail = line

        parts = [p.strip() for p in re.split(r"[，,·]", tail) if p.strip()]
        candidates.extend(parts)

    # 중복 제거 & 짧은 토큰 제거
    uniq = []
    for c in candidates:
        if len(c) < 2:
            continue
        if c not in uniq:
            uniq.append(c)

    return uniq


def extract_item_keywords_from_section_items(section_items: str) -> List[str]:
    """section_items에서 세부 항목 키워드 추출"""
    if not section_items:
        return []

    lines = [ln.strip() for ln in section_items.splitlines() if ln.strip()]
    result: List[str] = []

    for ln in lines:
        if ":" in ln:
            _, right = ln.split(":", 1)
        else:
            right = ln

        parts = [p.strip() for p in re.split(r"[,\u002c\uFF0C]", right) if p.strip()]
        result.extend(parts)

    return list(dict.fromkeys(result))


def extract_area_names_from_hierarchical_structure(hierarchical_structure: str) -> List[str]:
    """hierarchical_structure에서 영역 이름 추출"""
    if not hierarchical_structure:
        return []
    
    lines = [ln.strip() for ln in hierarchical_structure.splitlines() if ln.strip()]
    result: List[str] = []
    
    for ln in lines:
        cleaned = re.sub(r'^\d+\.\s*', '', ln)
        if ":" in cleaned:
            cleaned = cleaned.split(":", 1)[0]
        cleaned = re.sub(r'\s*\([^)]*\)', '', cleaned)
        cleaned = cleaned.strip()
        
        if cleaned:
            result.append(cleaned)
    
    return list(dict.fromkeys(result))


# ============================================================================
# 벡터 검색 함수
# ============================================================================

def search_similar_questions_for_keyword(
    keyword: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """키워드로 유사한 Question 검색"""
    if not keyword or not _initialized:
        return []

    try:
        embedding = graph_embedder.embed_query(keyword)

        with neo4j_driver.session() as session:
            result = session.run(
                """
                CALL db.index.vector.queryNodes($index_name, $topK, $embedding)
                YIELD node, score
                OPTIONAL MATCH (i:Item)-[:HAS_QUESTION]->(node)
                OPTIONAL MATCH (a:Area)-[:HAS_ITEM]->(i)
                RETURN
                    node.doc_id AS doc_id,
                    node.id AS question_local_id,
                    node.text AS question_text,
                    score,
                    head(collect(DISTINCT a.name)) AS area_name,
                    head(collect(DISTINCT i.name)) AS item_name
                ORDER BY score DESC
                """,
                index_name=NEO4J_INDEX_NAME,
                topK=top_k,
                embedding=embedding,
            )
            return result.data()
    except Exception as e:
        print(f"[GraphRAG] 검색 오류: {e}")
        return []


def find_similar_areas_and_items(
    area_names: List[str],
    top_k_areas: int = 3,
    top_k_items_per_area: int = 10
) -> Dict[str, List[Dict[str, Any]]]:
    """영역 이름으로 유사한 Area와 연결된 Item 검색"""
    if not area_names or not _initialized:
        return {}
    
    result: Dict[str, List[Dict[str, Any]]] = {}
    
    for area_name in area_names:
        if not area_name:
            continue
        
        try:
            embedding = graph_embedder.embed_query(area_name)
            
            with neo4j_driver.session() as session:
                cypher = """
                CALL db.index.vector.queryNodes($index_name, $top_k_areas, $embedding)
                YIELD node AS area_node, score AS area_score
                MATCH (area_node)-[:HAS_ITEM]->(i:Item)
                RETURN 
                    area_node.name AS area_name,
                    i.name AS item_name,
                    area_score,
                    i.element_id AS item_id
                ORDER BY area_score DESC
                LIMIT $top_k_items
                """
                
                records = session.run(
                    cypher,
                    index_name=AREA_INDEX_NAME,
                    top_k_areas=top_k_areas,
                    embedding=embedding,
                    top_k_items=top_k_items_per_area * top_k_areas,
                )
                
                items: List[Dict[str, Any]] = []
                seen_items = set()
                
                for r in records:
                    item_name = r.get("item_name")
                    if not item_name or item_name in seen_items:
                        continue
                    
                    seen_items.add(item_name)
                    items.append({
                        "area_name": r.get("area_name") or area_name,
                        "item_name": item_name,
                        "score": float(r.get("area_score", 0.0)),
                        "item_id": r.get("item_id"),
                    })
                
                items = items[:top_k_items_per_area]
                result[area_name] = items
                
        except Exception as e:
            print(f"[GraphRAG] 영역 '{area_name}' 검색 오류: {e}")
            result[area_name] = []
    
    return result


def find_similar_survey_categories_and_areas(
    survey_type: str,
    top_k_categories: int = 3,
    top_k_areas_per_category: int = 10
) -> List[Dict[str, Any]]:
    """설문유형으로 유사한 SurveyCategory와 Area 검색"""
    if not survey_type or not _initialized:
        return []
    
    result: List[Dict[str, Any]] = []
    
    try:
        embedding = graph_embedder.embed_query(survey_type)
        
        with neo4j_driver.session() as session:
            cypher = """
            CALL db.index.vector.queryNodes($index_name, $top_k_categories, $embedding)
            YIELD node AS category_node, score AS category_score
            MATCH (category_node)-[:HAS_AREA]->(a:Area)
            RETURN 
                category_node.name AS category_name,
                a.name AS area_name,
                category_score,
                a.element_id AS area_id
            ORDER BY category_score DESC
            LIMIT $top_k_areas
            """
            
            records = session.run(
                cypher,
                index_name=SURVEY_CATEGORY_INDEX_NAME,
                top_k_categories=top_k_categories,
                embedding=embedding,
                top_k_areas=top_k_areas_per_category * top_k_categories,
            )
            
            seen_areas = set()
            
            for r in records:
                area_name = r.get("area_name")
                if not area_name or area_name in seen_areas:
                    continue
                
                seen_areas.add(area_name)
                result.append({
                    "area_name": area_name,
                    "category_name": r.get("category_name") or survey_type,
                    "score": float(r.get("category_score", 0.0)),
                    "area_id": r.get("area_id"),
                })
            
            result = result[:top_k_areas_per_category * top_k_categories]
            
    except Exception as e:
        print(f"[GraphRAG] SurveyCategory 검색 오류: {e}")
        result = []
    
    return result


def get_graphrag_context_from_section_items(
    section_items: str,
    top_k_per_item: int = 3
) -> str:
    """section_items에서 GraphRAG 컨텍스트 생성"""
    keywords = parse_section_items_to_keywords(section_items)
    if not keywords:
        return ""

    lines: List[str] = []
    for kw in keywords:
        similar = search_similar_questions_for_keyword(kw, top_k=top_k_per_item)
        if not similar:
            continue

        lines.append(f"● 항목 키워드: {kw}")
        for q in similar:
            qtext = (q.get("question_text") or "").replace("\n", " ")
            area = q.get("area_name") or "미지정 영역"
            item = q.get("item_name") or "미지정 항목"
            score = q.get("score")
            lines.append(
                f"  - [참고 문항] 영역: {area}, 항목: {item}, "
                f"유사도 점수: {score:.3f}\n    문항: {qtext}"
            )
        lines.append("")

    return "\n".join(lines).strip()


def find_similar_items_and_questions(
    item_keywords: List[str],
    top_k_items: int = 5,
    top_k_questions: int = 5
) -> Dict[str, List[Dict[str, Any]]]:
    """
    항목 키워드로 유사한 Item과 Question 검색 (레이아웃 정보 포함)
    
    Args:
        item_keywords: 검색할 항목 키워드 리스트
        top_k_items: 각 키워드당 검색할 유사 Item 개수
        top_k_questions: 각 Item당 가져올 Question 개수
    
    Returns:
        {
            "키워드1": [
                {
                    "item_name": "항목명",
                    "question_text": "문항 내용",
                    "layout_code": "SC",
                    "layout_name": "단일선택형",
                    "area_name": "영역명",
                    "score": 0.92
                },
                ...
            ],
            ...
        }
    """
    if not item_keywords or not _initialized:
        return {}
    
    result: Dict[str, List[Dict[str, Any]]] = {}
    
    for keyword in item_keywords:
        if not keyword:
            continue
        
        try:
            embedding = graph_embedder.embed_query(keyword)
            
            with neo4j_driver.session() as session:
                # Question 벡터 인덱스로 유사 Question 검색 후 연결된 Item/Area 정보 조회
                cypher = """
                CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
                YIELD node, score
                OPTIONAL MATCH (i:Item)-[:HAS_QUESTION]->(node)
                OPTIONAL MATCH (a:Area)-[:HAS_ITEM]->(i)
                RETURN
                    node.doc_id AS doc_id,
                    node.id AS question_local_id,
                    node.text AS question_text,
                    node.layout_code AS layout_code,
                    node.layout_name AS layout_name,
                    score,
                    head(collect(DISTINCT a.name)) AS area_name,
                    head(collect(DISTINCT i.name)) AS item_name
                ORDER BY score DESC
                LIMIT $limit
                """
                
                records = session.run(
                    cypher,
                    index_name=NEO4J_INDEX_NAME,
                    top_k=top_k_items,
                    embedding=embedding,
                    limit=top_k_questions * top_k_items,
                )
                
                questions: List[Dict[str, Any]] = []
                seen_questions = set()
                
                for r in records:
                    question_text = r.get("question_text")
                    if not question_text or question_text in seen_questions:
                        continue
                    
                    seen_questions.add(question_text)
                    questions.append({
                        "item_name": r.get("item_name") or keyword,
                        "question_text": question_text,
                        "layout_code": r.get("layout_code") or "",
                        "layout_name": r.get("layout_name") or "",
                        "area_name": r.get("area_name") or "",
                        "score": float(r.get("score", 0.0)),
                        "doc_id": r.get("doc_id"),
                        "question_local_id": r.get("question_local_id"),
                    })
                
                result[keyword] = questions[:top_k_questions]
                
        except Exception as e:
            print(f"[GraphRAG] 키워드 '{keyword}' 검색 오류: {e}")
            result[keyword] = []
    
    return result