# test_neo4j.py
# Neo4j 그래프 데이터 조회 테스트

import os
import json
from neo4j import GraphDatabase
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# Neo4j 연결 정보
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://a4643f6b.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "8D1egQnwNTqSdNKOF3TMCfr0wrbkS9Gs1Il4mdMICBw")

print("=" * 80)
print("Neo4j 그래프 데이터 테스트")
print("=" * 80)

# Neo4j 드라이버 초기화
try:
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD)
    )
    print("✅ Neo4j 연결 성공")
except Exception as e:
    print(f"❌ Neo4j 연결 실패: {e}")
    exit(1)

# ============================================
# 테스트 1: 연결 테스트
# ============================================
def test_connection():
    print("\n" + "=" * 80)
    print("테스트 1: 연결 확인")
    print("=" * 80)
    
    with driver.session() as session:
        result = session.run("RETURN 'Hello Neo4j!' as message, datetime() as time")
        record = result.single()
        print(f"✅ 메시지: {record['message']}")
        print(f"✅ 서버 시간: {record['time']}")


# ============================================
# 테스트 2: 노드 통계
# ============================================
def test_node_stats():
    print("\n" + "=" * 80)
    print("테스트 2: 노드 타입별 개수")
    print("=" * 80)
    
    with driver.session() as session:
        result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] as node_type, count(n) as count
            ORDER BY count DESC
        """)
        
        print(f"\n{'노드 타입':<30} {'개수':>10}")
        print("-" * 42)
        
        total = 0
        for record in result:
            node_type = record["node_type"] or "Unknown"
            count = record["count"]
            total += count
            print(f"{node_type:<30} {count:>10,}")
        
        print("-" * 42)
        print(f"{'전체':<30} {total:>10,}")


# ============================================
# 테스트 3: 관계 통계
# ============================================
def test_relationship_stats():
    print("\n" + "=" * 80)
    print("테스트 3: 관계 타입별 개수")
    print("=" * 80)
    
    with driver.session() as session:
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as relationship_type, count(r) as count
            ORDER BY count DESC
        """)
        
        print(f"\n{'관계 타입':<30} {'개수':>10}")
        print("-" * 42)
        
        total = 0
        for record in result:
            rel_type = record["relationship_type"]
            count = record["count"]
            total += count
            print(f"{rel_type:<30} {count:>10,}")
        
        print("-" * 42)
        print(f"{'전체':<30} {total:>10,}")


# ============================================
# 테스트 4: SurveyCategory 목록
# ============================================
def test_survey_categories():
    print("\n" + "=" * 80)
    print("테스트 4: 설문 카테고리 목록")
    print("=" * 80)
    
    with driver.session() as session:
        result = session.run("""
            MATCH (s:SurveyCategory)
            RETURN s.name as name, s.survey_year as year
            ORDER BY s.name
        """)
        
        print(f"\n{'카테고리명':<40} {'연도':>10}")
        print("-" * 52)
        
        for record in result:
            name = record["name"] or "Unknown"
            year = record["year"] or "N/A"
            print(f"{name:<40} {year:>10}")


# ============================================
# 테스트 5: 특정 영역의 항목들
# ============================================
def test_area_items(area_name="교육"):
    print("\n" + "=" * 80)
    print(f"테스트 5: '{area_name}' 영역의 항목들")
    print("=" * 80)
    
    with driver.session() as session:
        result = session.run("""
            MATCH (a:Area {name: $area_name})-[:HAS_ITEM]->(i:Item)
            RETURN i.name as item_name
            ORDER BY i.name
            LIMIT 20
        """, area_name=area_name)
        
        items = [record["item_name"] for record in result]
        
        if items:
            print(f"\n'{area_name}' 영역의 항목 ({len(items)}개):")
            for idx, item in enumerate(items, 1):
                print(f"  {idx}. {item}")
        else:
            print(f"\n'{area_name}' 영역을 찾을 수 없습니다.")


# ============================================
# 테스트 6: 그래프 구조 샘플
# ============================================
def test_graph_structure(limit=10):
    print("\n" + "=" * 80)
    print(f"테스트 6: 그래프 구조 샘플 (최대 {limit}개)")
    print("=" * 80)
    
    with driver.session() as session:
        result = session.run("""
            MATCH (s:SurveyCategory)-[:HAS_AREA]->(a:Area)-[:HAS_ITEM]->(i:Item)
            RETURN s.name as category, a.name as area, i.name as item
            LIMIT $limit
        """, limit=limit)
        
        print(f"\n{'카테고리':<25} {'영역':<25} {'항목':<40}")
        print("-" * 92)
        
        for record in result:
            category = record["category"] or "Unknown"
            area = record["area"] or "Unknown"
            item = record["item"] or "Unknown"
            
            # 긴 텍스트는 자르기
            category = (category[:22] + "...") if len(category) > 25 else category
            area = (area[:22] + "...") if len(area) > 25 else area
            item = (item[:37] + "...") if len(item) > 40 else item
            
            print(f"{category:<25} {area:<25} {item:<40}")


# ============================================
# 테스트 7: 샘플 질문 조회
# ============================================
def test_sample_questions(limit=5):
    print("\n" + "=" * 80)
    print(f"테스트 7: 샘플 질문 ({limit}개)")
    print("=" * 80)
    
    with driver.session() as session:
        result = session.run("""
            MATCH (q:Question)
            RETURN q.text as question
            LIMIT $limit
        """, limit=limit)
        
        questions = [record["question"] for record in result]
        
        if questions:
            print()
            for idx, question in enumerate(questions, 1):
                print(f"{idx}. {question}")
                print()
        else:
            print("\n질문을 찾을 수 없습니다.")


# ============================================
# 테스트 8: JSON 데이터 출력 (시각화용)
# ============================================
def test_export_json(limit=20):
    print("\n" + "=" * 80)
    print(f"테스트 8: JSON 데이터 생성 (시각화용, 최대 {limit}개)")
    print("=" * 80)
    
    with driver.session() as session:
        result = session.run("""
            MATCH (s:SurveyCategory)-[r1:HAS_AREA]->(a:Area)-[r2:HAS_ITEM]->(i:Item)
            RETURN s, a, i
            LIMIT $limit
        """, limit=limit)
        
        nodes = {}
        links = []
        
        for record in result:
            # SurveyCategory 노드
            s = record["s"]
            s_id = s.element_id
            if s_id not in nodes:
                nodes[s_id] = {
                    "id": s_id,
                    "label": s.get("name", "Unknown"),
                    "type": "SurveyCategory",
                    "color": "#E67E22"
                }
            
            # Area 노드
            a = record["a"]
            a_id = a.element_id
            if a_id not in nodes:
                nodes[a_id] = {
                    "id": a_id,
                    "label": a.get("name", "Unknown"),
                    "type": "Area",
                    "color": "#3498DB"
                }
            
            # Item 노드
            i = record["i"]
            i_id = i.element_id
            if i_id not in nodes:
                nodes[i_id] = {
                    "id": i_id,
                    "label": i.get("name", "Unknown"),
                    "type": "Item",
                    "color": "#2ECC71"
                }
            
            # 관계
            links.append({"source": s_id, "target": a_id, "label": "HAS_AREA"})
            links.append({"source": a_id, "target": i_id, "label": "HAS_ITEM"})
        
        graph_data = {
            "nodes": list(nodes.values()),
            "links": links,
            "stats": {
                "total_nodes": len(nodes),
                "total_links": len(links)
            }
        }
        
        # JSON 파일로 저장
        with open("graph_data.json", "w", encoding="utf-8") as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        
        print("\n✅ JSON 파일 생성 완료: graph_data.json")
        print(f"   - 노드 수: {len(nodes)}")
        print(f"   - 링크 수: {len(links)}")
        print("\n샘플 데이터:")
        print(json.dumps(graph_data, ensure_ascii=False, indent=2)[:500] + "...")


# ============================================
# 테스트 9: 벡터 검색 테스트
# ============================================
def test_vector_search(keyword="가구원"):
    print("\n" + "=" * 80)
    print(f"테스트 9: 벡터 검색 - '{keyword}' 관련 질문")
    print("=" * 80)
    
    # OpenAI 임베딩 필요 - 간단한 텍스트 검색으로 대체
    with driver.session() as session:
        result = session.run("""
            MATCH (q:Question)
            WHERE q.text CONTAINS $keyword
            RETURN q.text as question
            LIMIT 5
        """, keyword=keyword)
        
        questions = [record["question"] for record in result]
        
        if questions:
            print(f"\n'{keyword}' 관련 질문 ({len(questions)}개):")
            for idx, question in enumerate(questions, 1):
                print(f"\n{idx}. {question}")
        else:
            print(f"\n'{keyword}' 관련 질문을 찾을 수 없습니다.")


# ============================================
# 테스트 10: 전체 경로 조회
# ============================================
def test_full_path():
    print("\n" + "=" * 80)
    print("테스트 10: 전체 경로 조회 (Category → Area → Item → Question)")
    print("=" * 80)
    
    with driver.session() as session:
        result = session.run("""
            MATCH path = (s:SurveyCategory)-[:HAS_AREA]->(a:Area)
                         -[:HAS_ITEM]->(i:Item)
                         -[:HAS_QUESTION]->(q:Question)
            RETURN s.name as category, 
                   a.name as area, 
                   i.name as item, 
                   q.text as question
            LIMIT 3
        """)
        
        for idx, record in enumerate(result, 1):
            print(f"\n경로 {idx}:")
            print(f"  카테고리: {record['category']}")
            print(f"  영역:     {record['area']}")
            print(f"  항목:     {record['item']}")
            print(f"  질문:     {record['question']}")


# ============================================
# 메인 실행
# ============================================
if __name__ == "__main__":
    try:
        # 모든 테스트 실행
        test_connection()
        test_node_stats()
        test_relationship_stats()
        test_survey_categories()
        test_area_items("교육")
        test_graph_structure(10)
        test_sample_questions(5)
        test_export_json(20)
        test_vector_search("가구원")
        test_full_path()
        
        print("\n" + "=" * 80)
        print("✅ 모든 테스트 완료!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 연결 종료
        driver.close()
        print("\n✅ Neo4j 연결 종료")