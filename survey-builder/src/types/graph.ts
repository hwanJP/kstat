// src/types/graph.ts

export interface GraphNode {
  id: string;
  label: string;
  type: 'SurveyCategory' | 'Area' | 'Item' | 'Question' | 'Layout' | 'Document';
  color: string;
  size: number;
  full_text?: string;  // Question의 전체 텍스트
}

export interface GraphLink {
  source: string;
  target: string;
  label: string;
  type: 'hierarchy' | 'direct' | 'normal' | 'followup';
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  stats: {
    total_nodes: number;
    total_links: number;
  };
}

export interface GraphStats {
  nodes: Array<{
    type: string;
    count: number;
  }>;
  relationships: Array<{
    type: string;
    count: number;
  }>;
}