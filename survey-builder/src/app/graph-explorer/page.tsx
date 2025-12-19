// src/app/graph-explorer/page.tsx

'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { Network } from 'vis-network';
import { DataSet } from 'vis-data';
import { getGraphData, getGraphHealth } from '@/lib/api';
import { GraphData } from '@/types/graph';
import { ArrowLeft, Loader2, Database, Server, AlertCircle, RefreshCw, CheckCircle2, XCircle } from 'lucide-react';
import Link from 'next/link';

// Neo4j 미연결 안내 컴포넌트
function Neo4jConnectionGuide({ 
  health, 
  onRetry 
}: { 
  health: any; 
  onRetry: () => void;
}) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-8">
      <div className="max-w-2xl w-full">
        {/* 헤더 */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-red-500/20 flex items-center justify-center">
            <Database className="w-10 h-10 text-red-400" />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Neo4j 연결 필요</h1>
          <p className="text-slate-400">
            Graph Explorer를 사용하려면 Neo4j 데이터베이스 연결이 필요합니다.
          </p>
        </div>

        {/* 상태 카드 */}
        <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6 mb-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Server className="w-5 h-5 text-orange-400" />
            연결 상태
          </h2>
          
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg">
              <span className="text-slate-300">Neo4j URI</span>
              <code className="text-sm text-orange-400 bg-slate-800 px-2 py-1 rounded">
                {health?.neo4j_uri || '설정안됨'}
              </code>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg">
              <span className="text-slate-300">Neo4j User</span>
              <code className="text-sm text-orange-400 bg-slate-800 px-2 py-1 rounded">
                {health?.neo4j_user || '설정안됨'}
              </code>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg">
              <span className="text-slate-300">GraphRAG 초기화</span>
              <span className={`flex items-center gap-1 ${health?.graphrag_initialized ? 'text-green-400' : 'text-red-400'}`}>
                {health?.graphrag_initialized ? (
                  <><CheckCircle2 className="w-4 h-4" /> 완료</>
                ) : (
                  <><XCircle className="w-4 h-4" /> 미완료</>
                )}
              </span>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg">
              <span className="text-slate-300">연결 상태</span>
              <span className="flex items-center gap-1 text-red-400">
                <XCircle className="w-4 h-4" /> {health?.status || 'not_connected'}
              </span>
            </div>
            {health?.error && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                <p className="text-sm text-red-300">{health.error}</p>
              </div>
            )}
          </div>
        </div>

        {/* 설정 가이드 */}
        <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6 mb-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-yellow-400" />
            설정 방법
          </h2>
          
          <div className="space-y-4">
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-orange-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-orange-400 font-bold">1</span>
              </div>
              <div>
                <h3 className="text-white font-medium mb-1">Neo4j 설치 및 실행</h3>
                <p className="text-sm text-slate-400 mb-2">Docker를 사용하여 Neo4j 실행:</p>
                <code className="block text-xs bg-slate-900 p-3 rounded-lg text-green-400 overflow-x-auto">
                  docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest
                </code>
              </div>
            </div>

            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-orange-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-orange-400 font-bold">2</span>
              </div>
              <div>
                <h3 className="text-white font-medium mb-1">환경 변수 설정</h3>
                <p className="text-sm text-slate-400 mb-2">backend/.env 파일에 추가:</p>
                <code className="block text-xs bg-slate-900 p-3 rounded-lg text-green-400">
                  NEO4J_URI=bolt://localhost:7687<br/>
                  NEO4J_USER=neo4j<br/>
                  NEO4J_PASSWORD=password
                </code>
              </div>
            </div>

            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-orange-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-orange-400 font-bold">3</span>
              </div>
              <div>
                <h3 className="text-white font-medium mb-1">서버 재시작</h3>
                <p className="text-sm text-slate-400">백엔드 서버를 재시작하세요.</p>
              </div>
            </div>
          </div>
        </div>

        {/* 버튼 */}
        <div className="flex gap-4">
          <button
            onClick={onRetry}
            className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-orange-500 hover:bg-orange-600 text-white font-medium rounded-xl transition-all"
          >
            <RefreshCw className="w-5 h-5" />
            다시 연결 시도
          </button>
          <Link href="/" className="flex-1">
            <button className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-xl transition-all">
              <ArrowLeft className="w-5 h-5" />
              설문 작성으로 이동
            </button>
          </Link>
        </div>

        <p className="text-center text-sm text-slate-500 mt-6">
          💡 Neo4j가 없어도 설문 작성 기능은 정상적으로 사용할 수 있습니다.
        </p>
      </div>
    </div>
  );
}

export default function GraphExplorerPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const positionedNodesRef = useRef<any[]>([]);  // positionedNodes 저장용 ref
  const isFirstRenderRef = useRef(true);  // 첫 로드 여부 (fit 제어용)
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [neo4jError, setNeo4jError] = useState(false);  // 🆕 Neo4j 연결 오류
  const [healthStatus, setHealthStatus] = useState<any>(null);  // 🆕 Health 상태
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [collapsedNodes, setCollapsedNodes] = useState<Set<string>>(new Set());
  const [depth, setDepth] = useState<number>(3);
  
  // 커스텀 더블클릭 감지용
  const lastClickRef = useRef<{ nodeId: string | null; time: number }>({
    nodeId: null,
    time: 0
  });

  // 데이터 로드 함수
  const loadData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      setNeo4jError(false);
      
      // 🆕 먼저 health check
      try {
        const health = await getGraphHealth();
        setHealthStatus(health);
        
        if (health.status !== 'connected') {
          setNeo4jError(true);
          setIsLoading(false);
          return;
        }
      } catch (healthErr) {
        // health API 자체가 실패해도 graph 데이터 로드 시도
        console.warn('Health check failed, trying to load graph data anyway');
      }
      
      const data = await getGraphData(200, depth);
      setGraphData(data);
      setCollapsedNodes(new Set());
      isFirstRenderRef.current = true;  // 새 데이터 로드 시 fit() 실행하도록 리셋
    } catch (err: any) {
      console.error('그래프 데이터 로드 실패:', err);
      
      // 🆕 503 에러 체크
      if (err?.response?.status === 503) {
        setNeo4jError(true);
        // health 정보 가져오기 시도
        try {
          const health = await getGraphHealth();
          setHealthStatus(health);
        } catch {
          setHealthStatus(null);
        }
      } else {
        setError('그래프 데이터를 불러올 수 없습니다.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [depth]);

  // 데이터 로드
  useEffect(() => {
    loadData();
  }, [loadData]);

  // 노드 접기/펼치기
  const toggleNodeCollapse = useCallback((nodeId: string) => {
    console.log('🔄 Toggle node:', nodeId);

    setCollapsedNodes(prev => {
      const newCollapsed = new Set(prev);
      const isCollapsed = prev.has(nodeId);

      if (isCollapsed) {
        console.log('✅ Expanding');
        newCollapsed.delete(nodeId);
      } else {
        console.log('❌ Collapsing');
        newCollapsed.add(nodeId);
      }

      return newCollapsed;
    });
  }, []);

  // 그래프 렌더링
  useEffect(() => {
    if (!graphData || !containerRef.current) return;

    // findChildNodes 로컬 함수
    const findChildNodesLocal = (nodeId: string): string[] => {
      const children: string[] = [];
      const queue = [nodeId];
      const visited = new Set<string>();

      while (queue.length > 0) {
        const current = queue.shift()!;
        if (visited.has(current)) continue;
        visited.add(current);

        graphData.links
          .filter(link => link.source === current)
          .forEach(link => {
            if (!visited.has(link.target)) {
              children.push(link.target);
              queue.push(link.target);
            }
          });
      }

      return children;
    };

    // 노드 위치 계산
    const calculateNodePositions = () => {
      const positionedNodes: any[] = [];
      const addedNodeIds = new Set<string>();
      
      const categories = graphData.nodes.filter(n => n.type === 'SurveyCategory');
      const areas = graphData.nodes.filter(n => n.type === 'Area');
      const items = graphData.nodes.filter(n => n.type === 'Item');
      const questions = graphData.nodes.filter(n => n.type === 'Question');

      const centerX = 0;
      const centerY = 0;

      // 1. SurveyCategory - 중심
      categories.forEach(node => {
        if (!addedNodeIds.has(node.id)) {
          positionedNodes.push({
            ...node,
            x: centerX,
            y: centerY,
            fixed: true,
            physics: false
          });
          addedNodeIds.add(node.id);
        }
      });

      // 2. Area - 원형 배치 (중심에서 균등하게)
      const areaRadius = 450;  // 중심에서 Area까지 거리
      const areaAngleStep = (2 * Math.PI) / Math.max(areas.length, 1);

      areas.forEach((node, index) => {
        if (!addedNodeIds.has(node.id)) {
          const angle = areaAngleStep * index - Math.PI / 2;
          const x = centerX + areaRadius * Math.cos(angle);
          const y = centerY + areaRadius * Math.sin(angle);

          positionedNodes.push({
            ...node,
            x,
            y,
            fixed: true,
            physics: false,
            angle
          });
          addedNodeIds.add(node.id);
        }
      });

      // 3. Item - 각 Area에서 외곽 방향으로 펼침
      const baseItemRadius = 180;
      const areaItemMap = new Map<string, any[]>();
      
      graphData.links
        .filter(link => link.label === 'HAS_ITEM')
        .forEach(link => {
          if (!areaItemMap.has(link.source)) {
            areaItemMap.set(link.source, []);
          }
          const item = items.find(i => i.id === link.target);
          if (item && !addedNodeIds.has(item.id)) {
            areaItemMap.get(link.source)!.push(item);
          }
        });

      positionedNodes.filter(n => n.type === 'Area').forEach(area => {
        const areaItems = areaItemMap.get(area.id) || [];
        const itemCount = areaItems.length;
        
        if (itemCount === 0) return;
        
        // Area의 외곽 방향 (중심에서 Area로의 방향)
        const areaOutwardAngle = area.angle || Math.atan2(area.y, area.x);
        
        // 부채꼴 각도: Item 개수에 따라 조절 (1개면 0도, 많으면 최대 150도)
        const maxSpread = Math.PI * 0.8;  // 144도
        const spreadAngle = itemCount === 1 ? 0 : Math.min(maxSpread, (itemCount - 1) * 0.25);
        const startAngle = areaOutwardAngle - spreadAngle / 2;
        const angleStep = itemCount > 1 ? spreadAngle / (itemCount - 1) : 0;
        
        // Item 개수에 따라 반경 조절
        const itemRadius = baseItemRadius + Math.min(itemCount * 10, 50);

        areaItems.forEach((item, index) => {
          if (!addedNodeIds.has(item.id)) {
            const angle = itemCount === 1 
              ? areaOutwardAngle 
              : startAngle + angleStep * index;

            const x = area.x + itemRadius * Math.cos(angle);
            const y = area.y + itemRadius * Math.sin(angle);

            positionedNodes.push({
              ...item,
              x,
              y,
              fixed: true,
              physics: false,
              angle  // 이 angle은 Question 배치에 사용됨
            });
            addedNodeIds.add(item.id);
          }
        });
      });

      // 4. Question - Item 외곽 방향으로 균형있게 배치 (겹침 방지)
      if (depth >= 4) {
        const itemQuestionMap = new Map<string, any[]>();
        
        graphData.links
          .filter(link => link.label === 'HAS_QUESTION')
          .forEach(link => {
            if (!itemQuestionMap.has(link.source)) {
              itemQuestionMap.set(link.source, []);
            }
            const question = questions.find(q => q.id === link.target);
            if (question && !addedNodeIds.has(question.id)) {
              itemQuestionMap.get(link.source)!.push(question);
            }
          });

        // 전체 Question에 순차 번호 부여
        let globalQuestionIndex = 1;

        positionedNodes.filter(n => n.type === 'Item').forEach(item => {
          const itemQuestions = itemQuestionMap.get(item.id) || [];
          const questionCount = itemQuestions.length;
          
          if (questionCount === 0) return;

          // Item의 angle 사용 (Area에서 Item으로의 방향 = 외곽 방향)
          const outwardAngle = item.angle !== undefined ? item.angle : Math.atan2(item.y, item.x);
          
          // 반경: Question 개수에 따라 동적 조절 (많을수록 멀리)
          const baseRadius = 80;
          const radiusPerQuestion = 15;
          const questionRadius = baseRadius + Math.min(questionCount * radiusPerQuestion, 100);
          
          // 부채꼴 각도: Question 개수에 따라 조절 (많을수록 넓게)
          const minSpread = Math.PI / 3;  // 최소 60도
          const maxSpread = Math.PI;       // 최대 180도
          const spreadAngle = Math.min(maxSpread, minSpread + (questionCount - 1) * 0.15);
          
          // 시작 각도 (외곽 방향 중심으로 좌우 펼침)
          const startAngle = outwardAngle - spreadAngle / 2;
          const angleStep = questionCount > 1 ? spreadAngle / (questionCount - 1) : 0;

          itemQuestions.forEach((question, index) => {
            if (!addedNodeIds.has(question.id)) {
              // 각도 계산
              const angle = questionCount === 1 
                ? outwardAngle  // 1개면 정확히 외곽 방향
                : startAngle + angleStep * index;
              
              // 겹침 방지: 짝수/홀수 인덱스로 반경 살짝 다르게
              const radiusOffset = (index % 2 === 0) ? 0 : 20;
              const finalRadius = questionRadius + radiusOffset;

              const x = item.x + finalRadius * Math.cos(angle);
              const y = item.y + finalRadius * Math.sin(angle);

              positionedNodes.push({
                ...question,
                x,
                y,
                fixed: true,
                physics: false,
                questionNumber: globalQuestionIndex
              });
              addedNodeIds.add(question.id);
              globalQuestionIndex++;
            }
          });
        });
      }

      return positionedNodes;
    };

    const positionedNodes = calculateNodePositions();
    positionedNodesRef.current = positionedNodes;  // ref에 저장

    // 접힌 노드의 자식들 숨김 처리
    const hiddenNodeIds = new Set<string>();
    collapsedNodes.forEach(parentId => {
      const children = findChildNodesLocal(parentId);
      children.forEach(childId => hiddenNodeIds.add(childId));
    });

    // vis-network 데이터
    const nodes = new DataSet(
      positionedNodes.map(node => {
        const hasChildren = graphData.links.some(link => link.source === node.id);
        const isCollapsed = collapsedNodes.has(node.id);
        const isHidden = hiddenNodeIds.has(node.id);
        
        // 라벨 결정
        let displayLabel = node.label;
        if (node.type === 'Question') {
          // Question은 Q번호 형식으로 표시 (간결하게)
          displayLabel = `Q${node.questionNumber || ''}`;
        } else if (hasChildren && ['SurveyCategory', 'Area', 'Item'].includes(node.type)) {
          displayLabel = isCollapsed ? `${node.label} ➕` : `${node.label} ➖`;
        }

        // 노드 타입별 스타일
        const isQuestion = node.type === 'Question';
        
        return {
          id: node.id,
          label: displayLabel,
          x: node.x,
          y: node.y,
          fixed: { x: true, y: true },
          physics: false,
          hidden: isHidden,
          color: {
            background: isQuestion ? '#9B59B6' : node.color,
            border: isQuestion ? '#8E44AD' : '#ffffff',
            highlight: {
              background: isQuestion ? '#A569BD' : node.color,
              border: '#E67E22'
            }
          },
          font: {
            color: '#ffffff',
            size: isQuestion ? 9 : 14,  // Question 라벨 더 작게
            face: 'Arial',
            bold: !isQuestion && hasChildren
          },
          size: isQuestion ? 10 : node.size,  // Question 노드 더 작게
          title: hasChildren 
            ? `${node.type}: ${node.label}\n\n더블클릭으로 ${isCollapsed ? '펼치기' : '접기'}`
            : isQuestion
            ? `Q${node.questionNumber}: ${node.full_text || node.label}`  // 툴팁에 전체 질문 표시
            : `${node.type}: ${node.label}`,
          shape: 'dot',
          borderWidth: isQuestion ? 1 : (isCollapsed ? 4 : 2),  // Question 테두리 얇게
          shapeProperties: {
            borderDashes: isCollapsed ? [5, 5] : false
          }
        };
      })
    );

    const edges = new DataSet(
      graphData.links.map((link, index) => {
        const isHidden = hiddenNodeIds.has(link.source) || hiddenNodeIds.has(link.target);
        
        return {
          id: index,
          from: link.source,
          to: link.target,
          hidden: isHidden,
          color: {
            color: 'rgba(255, 255, 255, 0.3)',
            highlight: 'rgba(230, 126, 34, 0.8)'
          },
          width: 2,
          arrows: {
            to: {
              enabled: true,
              scaleFactor: 0.5
            }
          },
          smooth: {
            enabled: true,
            type: 'continuous',
            roundness: 0.5
          }
        };
      })
    );

    // vis-network 옵션
    const options = {
      nodes: {
        borderWidth: 2,
        borderWidthSelected: 4,
        shadow: {
          enabled: true,
          color: 'rgba(0,0,0,0.3)',
          size: 10,
          x: 0,
          y: 0
        }
      },
      edges: {
        shadow: {
          enabled: true,
          color: 'rgba(0,0,0,0.2)',
          size: 5,
          x: 0,
          y: 0
        }
      },
      physics: {
        enabled: false
      },
      interaction: {
        hover: true,
        tooltipDelay: 100,
        zoomView: true,
        dragView: true,
        dragNodes: false
      },
      layout: {
        improvedLayout: false
      }
    };

    // 네트워크 생성
    const network = new Network(containerRef.current, { nodes, edges }, options);
    networkRef.current = network;

    // 첫 로드 시에만 전체 그래프가 보이도록 자동 줌 조절
    if (isFirstRenderRef.current) {
      network.once('stabilized', () => {
        network.fit({
          animation: {
            duration: 500,
            easingFunction: 'easeInOutQuad'
          }
        });
      });
      isFirstRenderRef.current = false;  // 이후에는 fit() 실행 안함
    }

    // 커스텀 더블클릭 구현
    network.on('click', (params) => {
      const now = Date.now();
      const DOUBLE_CLICK_THRESHOLD = 300;

      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const lastClick = lastClickRef.current;

        if (
          lastClick.nodeId === nodeId && 
          now - lastClick.time < DOUBLE_CLICK_THRESHOLD
        ) {
          // 더블클릭
          const node = graphData.nodes.find(n => n.id === nodeId);
          
          if (node && ['SurveyCategory', 'Area', 'Item'].includes(node.type)) {
            toggleNodeCollapse(nodeId);
          }

          lastClickRef.current = { nodeId: null, time: 0 };
        } else {
          // 단일 클릭 - positionedNodesRef에서 찾아서 questionNumber 포함
          const node = positionedNodesRef.current.find(n => n.id === nodeId) 
            || graphData.nodes.find(n => n.id === nodeId);
          setSelectedNode(node);
          lastClickRef.current = { nodeId, time: now };
        }
      } else {
        setSelectedNode(null);
        lastClickRef.current = { nodeId: null, time: 0 };
      }
    });

    return () => {
      network.destroy();
    };
  }, [graphData, collapsedNodes, toggleNodeCollapse, depth]);

  // 🆕 Neo4j 연결 오류 화면
  if (neo4jError) {
    return (
      <Neo4jConnectionGuide 
        health={healthStatus} 
        onRetry={loadData}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-orange-500 mx-auto mb-4" />
          <p className="text-white text-lg">그래프 데이터 로딩 중...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="text-center">
          <p className="text-red-400 text-lg mb-4">{error}</p>
          <Link href="/">
            <button className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700">
              챗봇으로 돌아가기
            </button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* 헤더 */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-sm flex-shrink-0">
        <div className="flex items-center gap-4">
          <Link href="/">
            <button className="flex items-center gap-2 px-4 py-2 text-sm text-slate-300 border border-slate-600 rounded-lg hover:bg-slate-800/50 hover:border-orange-500 transition-all duration-200">
              <ArrowLeft className="w-4 h-4" />
              챗봇으로 돌아가기
            </button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-white">🕸️ GraphRAG 시각화</h1>
            <p className="text-xs text-slate-400">
              Neo4j 데이터베이스 구조 탐색
            </p>
          </div>
        </div>
        
        {graphData && (
          <div className="flex gap-4 text-sm items-center">
            {/* 깊이 토글 버튼 */}
            <div className="flex gap-1 bg-slate-800/50 rounded-lg p-1 border border-slate-700">
              <button
                onClick={() => setDepth(3)}
                className={`px-3 py-1 rounded transition-all ${
                  depth === 3
                    ? 'bg-orange-600 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                3단계
              </button>
              <button
                onClick={() => setDepth(4)}
                className={`px-3 py-1 rounded transition-all ${
                  depth === 4
                    ? 'bg-orange-600 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                4단계
              </button>
            </div>

            {collapsedNodes.size > 0 && (
              <button
                onClick={() => setCollapsedNodes(new Set())}
                className="px-3 py-1 bg-orange-600/80 text-white rounded-lg hover:bg-orange-600 transition-colors text-xs"
              >
                전체 펼치기
              </button>
            )}
            
            <div className="px-3 py-1 bg-slate-800/50 rounded-lg border border-slate-700">
              <span className="text-slate-400">노드:</span>
              <span className="ml-2 text-orange-400 font-semibold">
                {graphData.stats.total_nodes}
              </span>
            </div>
            <div className="px-3 py-1 bg-slate-800/50 rounded-lg border border-slate-700">
              <span className="text-slate-400">관계:</span>
              <span className="ml-2 text-orange-400 font-semibold">
                {graphData.stats.total_links}
              </span>
            </div>
          </div>
        )}
      </header>

      {/* 메인 콘텐츠 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 그래프 영역 */}
        <div className="flex-1 relative">
          <div
            ref={containerRef}
            className="w-full h-full"
            style={{ background: '#0F172A' }}
          />
          
          {/* 범례 */}
          <div className="absolute top-4 right-4 bg-slate-900/90 backdrop-blur-sm p-4 rounded-lg border border-slate-700/50 shadow-lg">
            <h3 className="text-sm font-semibold text-white mb-3">범례</h3>
            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full" style={{ background: '#E67E22' }}></div>
                <span className="text-slate-300">SurveyCategory</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full" style={{ background: '#3498DB' }}></div>
                <span className="text-slate-300">Area (영역)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded-full" style={{ background: '#2ECC71' }}></div>
                <span className="text-slate-300">Item (항목)</span>
              </div>
              {depth >= 4 && (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-full" style={{ background: '#9B59B6' }}></div>
                  <span className="text-slate-300">Question (질문)</span>
                </div>
              )}
            </div>
            
            <div className="mt-4 pt-3 border-t border-slate-700">
              <h4 className="text-xs font-semibold text-white mb-2">관계</h4>
              <div className="space-y-2 text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-0.5 bg-white/30"></div>
                  <span className="text-slate-300">계층 구조</span>
                </div>
              </div>
            </div>
          </div>

          {/* 도움말 */}
          <div className="absolute bottom-4 left-4 bg-slate-900/90 backdrop-blur-sm p-3 rounded-lg border border-slate-700/50 text-xs text-slate-400">
            <div>👆 <strong>클릭</strong>: 노드 정보 표시</div>
            <div>👆👆 <strong>더블클릭</strong>: 하위 노드 접기/펼치기</div>
            <div>🔍 <strong>휠</strong>: 확대/축소</div>
            <div>🖱️ <strong>드래그</strong>: 화면 이동</div>
          </div>
        </div>

        {/* 노드 정보 패널 */}
        {selectedNode && (
          <div className="w-80 border-l border-slate-700/50 bg-slate-900/50 p-6 overflow-y-auto">
            <h3 className="text-lg font-semibold text-white mb-4">노드 정보</h3>
            
            <div className="space-y-3">
              <div>
                <p className="text-xs text-slate-400">타입</p>
                <p className="text-sm text-white font-medium mt-1">
                  {selectedNode.type === 'Question' ? 'Question (질문)' : selectedNode.type}
                </p>
              </div>
              
              <div>
                <p className="text-xs text-slate-400">
                  {selectedNode.type === 'Question' ? '질문 번호' : '이름'}
                </p>
                <p className="text-sm text-white font-medium mt-1">
                  {selectedNode.type === 'Question' 
                    ? `Q${selectedNode.questionNumber || ''}`
                    : selectedNode.label}
                </p>
              </div>

              {selectedNode.type === 'Question' && (
                <div>
                  <p className="text-xs text-slate-400">질문 내용</p>
                  <p className="text-sm text-white mt-1 leading-relaxed bg-slate-800/50 p-3 rounded-lg">
                    {selectedNode.full_text || selectedNode.label || selectedNode.name}
                  </p>
                </div>
              )}
              
              <div>
                <p className="text-xs text-slate-400">노드 ID</p>
                <p className="text-xs text-slate-500 mt-1 break-all font-mono">
                  {selectedNode.id}
                </p>
              </div>
            </div>
            
            <button
              onClick={() => setSelectedNode(null)}
              className="w-full mt-6 px-4 py-2 bg-slate-800 text-white rounded-lg hover:bg-slate-700 transition-colors text-sm"
            >
              닫기
            </button>
          </div>
        )}
      </div>
    </div>
  );
}