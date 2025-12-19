// src/lib/api.ts

import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 타입 정의
export interface MessageResponse {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  session_id: string;
  messages: MessageResponse[];
  state: Record<string, unknown>;
  current_step: number;
  is_complete: boolean;
  changed_field?: string;
  changed_value?: string;
}

export interface PreviewResponse {
  session_id: string;
  field_name?: string;
  field_display_name?: string;
  field_value?: string;
  all_fields: Record<string, string>;
}

// API 함수
export const initSurvey = async (): Promise<ChatResponse> => {
  const response = await api.post('/api/survey/init');
  return response.data;
};

export const sendMessage = async (
  message: string,
  sessionId?: string
): Promise<ChatResponse> => {
  const response = await api.post('/api/survey/chat', {
    message,
    session_id: sessionId,
  });
  return response.data;
};

export const getState = async (sessionId: string) => {
  const response = await api.get(`/api/survey/state/${sessionId}`);
  return response.data;
};

export const updateField = async (
  sessionId: string,
  field: string,
  value: string
) => {
  const response = await api.put(`/api/survey/state/${sessionId}/${field}`, {
    value,
  });
  return response.data;
};

export const getPreview = async (sessionId: string): Promise<PreviewResponse> => {
  const response = await api.get(`/api/survey/preview/${sessionId}`);
  return response.data;
};

export const resetSurvey = async (sessionId: string) => {
  const response = await api.post(`/api/survey/reset/${sessionId}`);
  return response.data;
};

/**
 * 설문지 내보내기 및 다운로드 (DOCX/HWPX)
 */
export const exportSurvey = async (
  sessionId: string,
  format: 'docx' | 'hwpx' = 'docx'
): Promise<void> => {
  try {
    const response = await api.post(
      `/api/survey/export/${sessionId}`,
      { format },
      { responseType: 'blob' }
    );
    
    const mimeTypes: Record<string, string> = {
      docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      hwpx: 'application/hwp+zip'
    };
    
    const blob = new Blob([response.data], { 
      type: mimeTypes[format] || mimeTypes.docx
    });
    
    const filename = `survey_${Date.now()}.${format}`;
    
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    
  } catch (error) {
    console.error('Export error:', error);
    throw error;
  }
};

export default api;

// GraphRAG API 타입 정의
export interface GraphNode {
  id: string;
  label: string;
  type: string;
  name: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
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

export interface GraphLink {
  source: string;
  target: string;
  label: string;
  type: string;
}

export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  node_counts: Record<string, number>;
  edge_counts: Record<string, number>;
}

export const getGraphData = async (
  limit: number = 100, 
  depth: number = 3
): Promise<GraphData> => {
  const response = await api.get('/api/graph/overview', {
    params: { limit, depth }
  });
  return response.data;
};

export const getGraphStats = async (): Promise<GraphStats> => {
  const response = await api.get('/api/graph/stats');
  return response.data;
};

// Graph Health Check
export interface GraphHealthStatus {
  neo4j_uri: string;
  neo4j_user: string;
  neo4j_password: string;
  graphrag_initialized: boolean;
  neo4j_driver_exists: boolean;
  status: string;
  error?: string;
}

export const getGraphHealth = async (): Promise<GraphHealthStatus> => {
  const response = await api.get('/api/graph/health');
  return response.data;
};