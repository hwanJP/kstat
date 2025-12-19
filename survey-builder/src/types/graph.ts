// src/types/graph.ts

export interface GraphNode {
  id: string;
  label: string;
  type: 'SurveyCategory' | 'Area' | 'Item' | 'Question' | 'Layout' | 'Document' | string;
  name?: string;
  color?: string;
  size?: number;
  full_text?: string;
  questionNumber?: number;
  properties?: Record<string, unknown>;
}

export interface GraphLink {
  source: string;
  target: string;
  label?: string;
  type: string;
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