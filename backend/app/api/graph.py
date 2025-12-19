# backend/app/api/graph.py

"""
GraphRAG 시각화 API
- Neo4j 그래프 데이터 조회
- 그래프 통계 정보 제공
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from ..services import graphrag
from ..services.graphrag import (
    init_graphrag,
    is_initialized as is_graphrag_initialized,
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
)

router = APIRouter(prefix="/api/graph", tags=["graph"])


# ============================================================================
# 응답 모델
# ============================================================================

class GraphNode(BaseModel):
    """그래프 노드"""
    id: str
    label: str
    type: str  # SurveyCategory, Area, Item, Question
    name: str
    color: str = "#ffffff"
    size: int = 20
    full_text: Optional[str] = None
    properties: Dict[str, Any] = {}


class GraphLink(BaseModel):
    """그래프 링크 (엣지)"""
    source: str
    target: str
    label: str  # HAS_AREA, HAS_ITEM, HAS_QUESTION


class GraphStatsInfo(BaseModel):
    """그래프 통계"""
    total_nodes: int
    total_links: int


class GraphData(BaseModel):
    """그래프 데이터 - 프론트엔드 형식에 맞춤"""
    nodes: List[GraphNode]
    links: List[GraphLink]  # edges -> links
    stats: GraphStatsInfo


class GraphStats(BaseModel):
    """그래프 통계 (상세)"""
    total_nodes: int
    total_edges: int
    node_counts: Dict[str, int]
    edge_counts: Dict[str, int]


# 노드 타입별 색상 및 크기
NODE_STYLES = {
    "SurveyCategory": {"color": "#E67E22", "size": 40},
    "Area": {"color": "#3498DB", "size": 30},
    "Item": {"color": "#2ECC71", "size": 20},
    "Question": {"color": "#9B59B6", "size": 15},
}


# ============================================================================
# API 엔드포인트
# ============================================================================

@router.get("/health")
async def check_graph_health():
    """
    GraphRAG/Neo4j 연결 상태 확인
    """
    status = {
        "neo4j_uri": NEO4J_URI or "설정안됨",
        "neo4j_user": NEO4J_USER or "설정안됨",
        "neo4j_password": "***" if NEO4J_PASSWORD else "설정안됨",
        "graphrag_initialized": is_graphrag_initialized(),
        "neo4j_driver_exists": graphrag.neo4j_driver is not None,
        "status": "unknown"
    }
    
    if not is_graphrag_initialized():
        try:
            init_graphrag()
            status["graphrag_initialized"] = is_graphrag_initialized()
            status["neo4j_driver_exists"] = graphrag.neo4j_driver is not None
        except Exception as e:
            status["error"] = str(e)
            status["status"] = "error"
            return status
    
    if is_graphrag_initialized() and graphrag.neo4j_driver:
        try:
            with graphrag.neo4j_driver.session() as session:
                result = session.run("RETURN 1 as test")
                record = result.single()
                if record and record["test"] == 1:
                    status["status"] = "connected"
                else:
                    status["status"] = "query_failed"
        except Exception as e:
            status["status"] = "connection_error"
            status["error"] = str(e)
    else:
        status["status"] = "not_initialized"
    
    return status


@router.get("/overview", response_model=GraphData)
async def get_graph_overview(
    limit: int = Query(default=100, ge=1, le=500, description="최대 노드 수"),
    depth: int = Query(default=3, ge=1, le=4, description="탐색 깊이 (1-4)")
):
    """
    그래프 개요 데이터 조회
    
    - depth=1: SurveyCategory만
    - depth=2: SurveyCategory + Area
    - depth=3: SurveyCategory + Area + Item
    - depth=4: 전체 (SurveyCategory + Area + Item + Question)
    """
    # GraphRAG 초기화 시도
    if not is_graphrag_initialized():
        try:
            init_graphrag()
        except Exception as e:
            raise HTTPException(
                status_code=503, 
                detail=f"GraphRAG 초기화 실패: {str(e)}. Neo4j 서버가 실행 중인지 확인하세요."
            )
    
    if not is_graphrag_initialized():
        raise HTTPException(
            status_code=503, 
            detail="GraphRAG가 초기화되지 않았습니다. Neo4j 연결 설정을 확인하세요. (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)"
        )
    
    if not graphrag.neo4j_driver:
        raise HTTPException(
            status_code=503, 
            detail="Neo4j 드라이버가 없습니다. Neo4j 서버가 실행 중인지 확인하세요."
        )
    
    try:
        nodes = []
        links = []
        seen_nodes = set()
        
        with graphrag.neo4j_driver.session() as session:
            # depth에 따른 쿼리 생성
            if depth == 1:
                cypher = """
                MATCH (sc:SurveyCategory)
                RETURN sc
                LIMIT $limit
                """
            elif depth == 2:
                cypher = """
                MATCH (sc:SurveyCategory)-[r:HAS_AREA]->(a:Area)
                RETURN sc, r, a
                LIMIT $limit
                """
            elif depth == 3:
                cypher = """
                MATCH (sc:SurveyCategory)-[r1:HAS_AREA]->(a:Area)-[r2:HAS_ITEM]->(i:Item)
                RETURN sc, r1, a, r2, i
                LIMIT $limit
                """
            else:  # depth == 4
                cypher = """
                MATCH (sc:SurveyCategory)-[r1:HAS_AREA]->(a:Area)-[r2:HAS_ITEM]->(i:Item)-[r3:HAS_QUESTION]->(q:Question)
                RETURN sc, r1, a, r2, i, r3, q
                LIMIT $limit
                """
            
            result = session.run(cypher, limit=limit)
            
            for record in result:
                # SurveyCategory 노드
                if "sc" in record.keys():
                    sc = record["sc"]
                    node_id = str(sc.element_id)
                    if node_id not in seen_nodes:
                        seen_nodes.add(node_id)
                        style = NODE_STYLES.get("SurveyCategory", {})
                        nodes.append(GraphNode(
                            id=node_id,
                            label=sc.get("name", "Unknown"),
                            type="SurveyCategory",
                            name=sc.get("name", "Unknown"),
                            color=style.get("color", "#E67E22"),
                            size=style.get("size", 40),
                            properties=dict(sc)
                        ))
                
                # Area 노드
                if "a" in record.keys():
                    a = record["a"]
                    node_id = str(a.element_id)
                    if node_id not in seen_nodes:
                        seen_nodes.add(node_id)
                        style = NODE_STYLES.get("Area", {})
                        nodes.append(GraphNode(
                            id=node_id,
                            label=a.get("name", "Unknown"),
                            type="Area",
                            name=a.get("name", "Unknown"),
                            color=style.get("color", "#3498DB"),
                            size=style.get("size", 30),
                            properties=dict(a)
                        ))
                
                # Item 노드
                if "i" in record.keys():
                    i = record["i"]
                    node_id = str(i.element_id)
                    if node_id not in seen_nodes:
                        seen_nodes.add(node_id)
                        style = NODE_STYLES.get("Item", {})
                        nodes.append(GraphNode(
                            id=node_id,
                            label=i.get("name", "Unknown"),
                            type="Item",
                            name=i.get("name", "Unknown"),
                            color=style.get("color", "#2ECC71"),
                            size=style.get("size", 20),
                            properties=dict(i)
                        ))
                
                # Question 노드
                if "q" in record.keys():
                    q = record["q"]
                    node_id = str(q.element_id)
                    if node_id not in seen_nodes:
                        seen_nodes.add(node_id)
                        text = q.get("text", "Unknown")
                        style = NODE_STYLES.get("Question", {})
                        nodes.append(GraphNode(
                            id=node_id,
                            label=text[:30] + "..." if len(text) > 30 else text,
                            type="Question",
                            name=text,
                            color=style.get("color", "#9B59B6"),
                            size=style.get("size", 15),
                            full_text=text,
                            properties=dict(q)
                        ))
                
                # HAS_AREA 엣지
                if "r1" in record.keys():
                    r = record["r1"]
                    links.append(GraphLink(
                        source=str(r.start_node.element_id),
                        target=str(r.end_node.element_id),
                        label="HAS_AREA"
                    ))
                
                # HAS_ITEM 엣지
                if "r2" in record.keys():
                    r = record["r2"]
                    links.append(GraphLink(
                        source=str(r.start_node.element_id),
                        target=str(r.end_node.element_id),
                        label="HAS_ITEM"
                    ))
                
                # HAS_QUESTION 엣지
                if "r3" in record.keys():
                    r = record["r3"]
                    links.append(GraphLink(
                        source=str(r.start_node.element_id),
                        target=str(r.end_node.element_id),
                        label="HAS_QUESTION"
                    ))
        
        # 중복 링크 제거
        unique_links = []
        seen_links = set()
        for link in links:
            link_key = f"{link.source}-{link.target}-{link.label}"
            if link_key not in seen_links:
                seen_links.add(link_key)
                unique_links.append(link)
        
        # stats 생성
        stats = GraphStatsInfo(
            total_nodes=len(nodes),
            total_links=len(unique_links)
        )
        
        return GraphData(nodes=nodes, links=unique_links, stats=stats)
        
    except Exception as e:
        print(f"[Graph API] 오류: {e}")
        raise HTTPException(status_code=500, detail=f"그래프 데이터 조회 오류: {str(e)}")


@router.get("/stats", response_model=GraphStats)
async def get_graph_stats():
    """그래프 통계 정보 조회"""
    if not is_graphrag_initialized():
        try:
            init_graphrag()
        except Exception as e:
            raise HTTPException(
                status_code=503, 
                detail=f"GraphRAG 초기화 실패: {str(e)}"
            )
    
    if not is_graphrag_initialized() or not graphrag.neo4j_driver:
        raise HTTPException(
            status_code=503, 
            detail="Neo4j에 연결할 수 없습니다. 서버 설정을 확인하세요."
        )
    
    try:
        node_counts = {}
        edge_counts = {}
        
        with graphrag.neo4j_driver.session() as session:
            # 노드 타입별 개수
            for node_type in ["SurveyCategory", "Area", "Item", "Question"]:
                result = session.run(f"MATCH (n:{node_type}) RETURN count(n) as cnt")
                record = result.single()
                node_counts[node_type] = record["cnt"] if record else 0
            
            # 엣지 타입별 개수
            for edge_type in ["HAS_AREA", "HAS_ITEM", "HAS_QUESTION"]:
                result = session.run(f"MATCH ()-[r:{edge_type}]->() RETURN count(r) as cnt")
                record = result.single()
                edge_counts[edge_type] = record["cnt"] if record else 0
        
        total_nodes = sum(node_counts.values())
        total_edges = sum(edge_counts.values())
        
        return GraphStats(
            total_nodes=total_nodes,
            total_edges=total_edges,
            node_counts=node_counts,
            edge_counts=edge_counts
        )
        
    except Exception as e:
        print(f"[Graph API] 통계 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"그래프 통계 조회 오류: {str(e)}")


@router.get("/search")
async def search_graph(
    query: str = Query(..., description="검색어"),
    node_type: Optional[str] = Query(default=None, description="노드 타입 필터"),
    limit: int = Query(default=20, ge=1, le=100, description="최대 결과 수")
):
    """
    그래프 검색
    - query: 검색어
    - node_type: SurveyCategory, Area, Item, Question 중 하나
    """
    if not is_graphrag_initialized():
        try:
            init_graphrag()
        except Exception as e:
            raise HTTPException(
                status_code=503, 
                detail=f"GraphRAG 초기화 실패: {str(e)}"
            )
    
    if not is_graphrag_initialized() or not graphrag.neo4j_driver:
        raise HTTPException(
            status_code=503, 
            detail="Neo4j에 연결할 수 없습니다. 서버 설정을 확인하세요."
        )
    
    try:
        results = []
        
        with graphrag.neo4j_driver.session() as session:
            if node_type:
                # 특정 노드 타입에서만 검색
                cypher = f"""
                MATCH (n:{node_type})
                WHERE n.name CONTAINS $query OR n.text CONTAINS $query
                RETURN n
                LIMIT $limit
                """
            else:
                # 모든 노드 타입에서 검색
                cypher = """
                MATCH (n)
                WHERE n.name CONTAINS $query OR n.text CONTAINS $query
                RETURN n, labels(n) as labels
                LIMIT $limit
                """
            
            result = session.run(cypher, query=query, limit=limit)
            
            for record in result:
                node = record["n"]
                labels = record.get("labels", [node_type]) if "labels" in record.keys() else [node_type]
                
                results.append({
                    "id": str(node.element_id),
                    "type": labels[0] if labels else "Unknown",
                    "name": node.get("name") or node.get("text", "Unknown"),
                    "properties": dict(node)
                })
        
        return {"results": results, "count": len(results)}
        
    except Exception as e:
        print(f"[Graph API] 검색 오류: {e}")
        raise HTTPException(status_code=500, detail=f"그래프 검색 오류: {str(e)}")