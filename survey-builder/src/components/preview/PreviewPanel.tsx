// src/components/preview/PreviewPanel.tsx

'use client';

import { useSurveyStore } from '@/stores/survey-store';
import { CheckCircle2, Clock, Download, FileText, ChevronDown, ChevronUp, Edit3, Save, Plus, Trash2 } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import { exportSurvey, updateField } from '@/lib/api';

// 질문 타입 정의
interface Question {
  id: string;
  number: string;
  text: string;
  options: string[];
  type: string;
  isOpen: boolean;
}

// 질문 그룹 (10개씩)
interface QuestionGroup {
  startNum: number;
  endNum: number;
  questions: Question[];
  isExpanded: boolean;
}

export default function PreviewPanel() {
  const [showRawContent, setShowRawContent] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [editingQuestionId, setEditingQuestionId] = useState<string | null>(null);
  const [editingOptionIdx, setEditingOptionIdx] = useState<{qId: string, idx: number} | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [questionGroups, setQuestionGroups] = useState<QuestionGroup[]>([]);
  const [hasLocalChanges, setHasLocalChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  
  // 간단한 마크다운 처리 (볼드, 이탤릭)
  const renderMarkdown = (text: string) => {
    if (!text) return null;
    
    // **bold** → <strong>
    // *italic* → <em>
    // ## 헤더 → 볼드 처리
    const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|##\s*.+)/g);
    
    return parts.map((part, idx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={idx} className="text-orange-300 font-bold">{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('*') && part.endsWith('*') && !part.startsWith('**')) {
        return <em key={idx} className="text-slate-200">{part.slice(1, -1)}</em>;
      }
      if (part.startsWith('## ')) {
        return <strong key={idx} className="text-orange-300 font-bold">{part.slice(3)}</strong>;
      }
      return part;
    });
  };
  
  const { 
    sessionId,
    surveyState,
    updateSurveyState,
  } = useSurveyStore();

  // surveyState에서 데이터 추출
  const hierarchicalStructure = surveyState?.hierarchical_structure as string;
  const sectionItems = surveyState?.section_items as string;
  const surveyDraft = surveyState?.survey_draft;
  const finalSurvey = surveyState?.final_survey;
  const intent = surveyState?.intent as string;
  const surveyType = surveyState?.survey_type as string;
  const databaseChoice = surveyState?.database_choice as string;

  // survey_draft가 더 최신이므로 우선 사용
  // 문자열이 아닌 경우 처리 (배열, 객체 등)
  const getSurveyContent = (): string => {
    const draft = surveyDraft || finalSurvey;
    
    if (!draft) return '';
    
    // 이미 문자열인 경우
    if (typeof draft === 'string') return draft;
    
    // 배열인 경우 줄바꿈으로 연결
    if (Array.isArray(draft)) {
      return draft.join('\n');
    }
    
    // 객체인 경우 JSON 문자열로 변환 시도
    if (typeof draft === 'object') {
      try {
        return JSON.stringify(draft, null, 2);
      } catch {
        return String(draft);
      }
    }
    
    return String(draft);
  };
  
  const surveyContent = getSurveyContent();
  
  // 디버깅용 로그 (개발 모드에서만)
  useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      console.log('[PreviewPanel] surveyState:', surveyState);
      console.log('[PreviewPanel] survey_draft type:', typeof surveyDraft);
      console.log('[PreviewPanel] surveyContent length:', surveyContent.length);
    }
  }, [surveyState, surveyDraft, surveyContent]);
  
  const selectedAreaName = typeof hierarchicalStructure === 'string' ? hierarchicalStructure : '';
  const selectedItemName = typeof sectionItems === 'string' ? sectionItems : '';
  
  const getStep1Value = () => {
    if (surveyType) return surveyType;
    if (databaseChoice === '별도_설문지') return '직접 설문 작성';
    if (intent) {
      const lines = intent.split('\n');
      const goalLine = lines.find(l => l.includes('목표/용도:'));
      if (goalLine) {
        const value = goalLine.replace('목표/용도:', '').trim();
        return value.length > 50 ? value.substring(0, 50) + '...' : value;
      }
      return lines[0]?.substring(0, 50) || '';
    }
    return '';
  };

  // 설문지 파싱
  const parseSurveyDraft = useCallback((draft: string): Question[] => {
    if (!draft || typeof draft !== 'string') return [];
    if (draft.trim().length === 0) return [];

    const parsedQuestions: Question[] = [];
    
    // 배열 형태 문자열 처리
    let processedDraft = draft;
    if (draft.includes("', '") || draft.includes('", "')) {
      processedDraft = draft
        .replace(/^\[|\]$/g, '')
        .replace(/^['"]|['"]$/g, '')
        .replace(/['"]\s*,\s*['"]/g, '\n')
        .replace(/\\n/g, '\n');
    }
    
    const lines = processedDraft.split('\n');
    let currentQuestion: Question | null = null;
    let questionId = 0;

    // 타입 코드 패턴
    const TYPE_CODE_PATTERN = /\((SC|MA|OQ|RS|DC|RK|MG)(?:\(\d+\))?\)/i;
    
    // ★ 핵심: "문항" 또는 "Q"로 시작하는 질문 패턴만 질문으로 인식
    const QUESTION_KEYWORD_PATTERNS = [
      /^\*?\*?문항\s*(\d+(?:-\d+)?)[.:]?\*?\*?\s*(.+)/i,  // "문항 1. ..."
      /^Q(\d+(?:-\d+)?)[.:]?\s*(.+)/i,                     // "Q1. ..."
    ];

    // 선택지 패턴
    const optionPatterns = [
      /^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫]\s*(.+)/,
      /^[ⓞ]\s*(.+)/,
      /^\(\d+\)\s*(.+)/,
      /^[-•]\s+(.+)/,
      /^[○●]\s*(.+)/,
    ];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      
      // 1. "문항 X." 또는 "QX." 패턴 체크 → 무조건 질문
      let questionMatch = null;
      for (const pattern of QUESTION_KEYWORD_PATTERNS) {
        const match = line.match(pattern);
        if (match) {
          questionMatch = match;
          break;
        }
      }
      
      if (questionMatch) {
        // 새 질문 시작
        if (currentQuestion) {
          parsedQuestions.push(currentQuestion);
        }
        
        const typeMatch = line.match(TYPE_CODE_PATTERN);
        const type = typeMatch ? typeMatch[1].toUpperCase() : 'SC';
        
        let questionText = questionMatch[2]
          .replace(/\*\*/g, '')
          .replace(/\[.*?\]/g, '')
          .replace(/\((?:SC|MA|OQ|RS|DC|RK|MG)(?:\(\d+\))?\)/gi, '')
          .trim();
        
        currentQuestion = {
          id: `q_${questionId++}`,
          number: questionMatch[1],
          text: questionText,
          options: [],
          type: type,
          isOpen: type === 'OQ' || line.includes('주관식')
        };
        continue;
      }
      
      // 2. 현재 질문이 있으면 선택지로 처리
      if (currentQuestion) {
        let optionText = '';
        
        // 원문자/불릿 패턴 체크
        for (const pattern of optionPatterns) {
          const match = line.match(pattern);
          if (match) {
            optionText = match[1];
            break;
          }
        }
        
        // 숫자점 패턴 체크 (문항/Q 없으면 선택지로 인식)
        if (!optionText) {
          const numMatch = line.match(/^(\d{1,2})[.)]\s+(.+)/);
          if (numMatch) {
            optionText = numMatch[2];
          }
        }
        
        // 숫자 없이 "-"로 시작하거나 단순 텍스트인 경우
        if (!optionText) {
          const dashMatch = line.match(/^-\s*[①②③④⑤⑥⑦⑧⑨⑩]?\s*(.+)/);
          if (dashMatch) {
            optionText = dashMatch[1];
          }
        }
        
        if (optionText) {
          // 타입코드, 번호, 특수문자 제거
          optionText = optionText
            .split('→')[0]
            .replace(/\((?:SC|MA|OQ|RS|DC|RK|MG)(?:\(\d+\))?\)/gi, '')
            .replace(/^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫○●]\s*/, '')
            .trim();
          
          if (optionText.length > 0) {
            currentQuestion.options.push(optionText);
          }
        }
      }
    }

    if (currentQuestion) {
      parsedQuestions.push(currentQuestion);
    }
    
    if (process.env.NODE_ENV === 'development') {
      console.log('[PreviewPanel] 파싱 결과:', parsedQuestions.length, '개 문항');
    }

    return parsedQuestions;
  }, []);

  // 질문을 10개씩 그룹핑
  const groupQuestions = useCallback((qs: Question[]): QuestionGroup[] => {
    const groups: QuestionGroup[] = [];
    const groupSize = 10;
    
    for (let i = 0; i < qs.length; i += groupSize) {
      const groupQuestions = qs.slice(i, i + groupSize);
      const startNum = i + 1;
      const endNum = Math.min(i + groupSize, qs.length);
      
      groups.push({
        startNum,
        endNum,
        questions: groupQuestions,
        isExpanded: i === 0
      });
    }
    
    return groups;
  }, []);

  // 설문 내용이 변경될 때 파싱
  useEffect(() => {
    const parsed = parseSurveyDraft(surveyContent);
    setQuestions(parsed);
    setQuestionGroups(groupQuestions(parsed));
    setHasLocalChanges(false);
  }, [surveyContent, parseSurveyDraft, groupQuestions]);

  const toggleGroup = (groupIdx: number) => {
    setQuestionGroups(prev => prev.map((g, idx) => 
      idx === groupIdx ? { ...g, isExpanded: !g.isExpanded } : g
    ));
  };

  const updateQuestionText = (questionId: string, newText: string) => {
    setQuestions(prev => prev.map(q => 
      q.id === questionId ? { ...q, text: newText } : q
    ));
    setQuestionGroups(prev => prev.map(g => ({
      ...g,
      questions: g.questions.map(q => 
        q.id === questionId ? { ...q, text: newText } : q
      )
    })));
    setHasLocalChanges(true);
  };

  const updateOption = (questionId: string, optionIdx: number, newText: string) => {
    const updateFn = (q: Question) => {
      if (q.id === questionId) {
        const newOptions = [...q.options];
        newOptions[optionIdx] = newText;
        return { ...q, options: newOptions };
      }
      return q;
    };
    setQuestions(prev => prev.map(updateFn));
    setQuestionGroups(prev => prev.map(g => ({
      ...g,
      questions: g.questions.map(updateFn)
    })));
    setHasLocalChanges(true);
  };

  const addOption = (questionId: string) => {
    const updateFn = (q: Question) => {
      if (q.id === questionId) {
        return { ...q, options: [...q.options, '새 선택지'] };
      }
      return q;
    };
    setQuestions(prev => prev.map(updateFn));
    setQuestionGroups(prev => prev.map(g => ({
      ...g,
      questions: g.questions.map(updateFn)
    })));
    setHasLocalChanges(true);
  };

  const removeOption = (questionId: string, optionIdx: number) => {
    const updateFn = (q: Question) => {
      if (q.id === questionId) {
        const newOptions = q.options.filter((_, idx) => idx !== optionIdx);
        return { ...q, options: newOptions };
      }
      return q;
    };
    setQuestions(prev => prev.map(updateFn));
    setQuestionGroups(prev => prev.map(g => ({
      ...g,
      questions: g.questions.map(updateFn)
    })));
    setHasLocalChanges(true);
  };

  const questionsToText = useCallback((qs: Question[]): string => {
    let text = '';
    const circledNumbers = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩', '⑪', '⑫'];
    const numberPattern = /^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫○●]\s*/;
    
    qs.forEach((q, idx) => {
      text += `${idx + 1}. ${q.text} (${q.type})\n`;
      if (!q.isOpen && q.options.length > 0) {
        q.options.forEach((opt, optIdx) => {
          const cleanOpt = opt.replace(numberPattern, '').trim();
          const num = optIdx < 12 ? circledNumbers[optIdx] : `(${optIdx + 1})`;
          text += `   ${num} ${cleanOpt}\n`;
        });
      } else if (q.isOpen) {
        text += `   [주관식 응답]\n`;
      }
      text += '\n';
    });
    return text;
  }, []);

  const saveChanges = async () => {
    if (!sessionId || !hasLocalChanges) return;
    
    setIsSaving(true);
    try {
      const newSurveyText = questionsToText(questions);
      
      await updateField(sessionId, 'survey_draft', newSurveyText);
      await updateField(sessionId, 'final_survey', newSurveyText);
      
      updateSurveyState({
        survey_draft: newSurveyText,
        final_survey: newSurveyText
      });
      
      setHasLocalChanges(false);
    } catch (error) {
      console.error('Save error:', error);
      alert('저장 중 오류가 발생했습니다.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleExport = async (format: 'docx' | 'hwpx') => {
    if (!sessionId) {
      alert('세션 정보가 없습니다.');
      return;
    }
    
    if (hasLocalChanges) {
      await saveChanges();
    }
    
    setIsExporting(true);
    try {
      await exportSurvey(sessionId, format);
    } catch (error) {
      console.error('Export error:', error);
      alert('파일 다운로드 중 오류가 발생했습니다.');
    } finally {
      setIsExporting(false);
    }
  };

  const step1Value = getStep1Value();
  
  // 완료 조건: 값이 있으면 완료로 표시
  const selectionHistory = [
    { step: 1, title: '설문 개요', value: step1Value, completed: !!step1Value },
    { step: 2, title: '영역 선택', value: selectedAreaName, completed: !!selectedAreaName },
    { step: 3, title: '항목 선택', value: selectedItemName, completed: !!selectedItemName },
    { step: 4, title: '설문 생성', value: questions.length > 0 ? `${questions.length}개 문항 생성됨` : '', completed: questions.length > 0 }
  ];

  return (
    <div className="h-full flex flex-col bg-slate-900/30">
      {/* 헤더 */}
      <div className="p-4 border-b border-white/10 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <FileText className="w-6 h-6 text-orange-400" />
              설문 미리보기
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              클릭하여 직접 수정 • 자동 동기화
            </p>
          </div>
          
          {hasLocalChanges && (
            <button
              onClick={saveChanges}
              disabled={isSaving}
              className="flex items-center gap-2 px-4 py-2 bg-green-500 hover:bg-green-600 text-white font-medium rounded-lg transition-all disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {isSaving ? '저장 중...' : '저장'}
            </button>
          )}
        </div>
      </div>

      {/* 스크롤 영역 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 preview-scrollbar">
        
        {/* 진행 상황 - 세로 배치 */}
        <div className="space-y-3">
          {selectionHistory.map((item) => (
            <div
              key={item.step}
              className={`p-4 rounded-lg border transition-all ${
                item.completed 
                  ? 'bg-green-900/20 border-green-500/50' 
                  : 'bg-slate-800/30 border-slate-700/50'
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                {item.completed ? (
                  <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />
                ) : (
                  <Clock className="w-5 h-5 text-slate-500 flex-shrink-0" />
                )}
                <span className={`text-base font-semibold ${item.completed ? 'text-green-300' : 'text-slate-400'}`}>
                  {item.step}. {item.title}
                </span>
              </div>
              {item.value && (
                <p className={`text-sm ml-7 whitespace-pre-wrap break-words leading-relaxed ${item.completed ? 'text-white/90' : 'text-slate-500'}`}>
                  {renderMarkdown(item.value)}
                </p>
              )}
              {!item.value && !item.completed && (
                <p className="text-sm ml-7 text-slate-500 italic">대기 중...</p>
              )}
            </div>
          ))}
        </div>

        {/* 설문지 편집 영역 */}
        {questions.length > 0 && (
          <>
            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t-2 border-orange-500/50"></div>
              </div>
              <div className="relative flex justify-center">
                <span className="px-4 bg-slate-900/30 text-base font-semibold text-orange-400">
                  ✏️ 설문 편집 ({questions.length}문항)
                </span>
              </div>
            </div>

            {/* 다운로드 버튼 */}
            <div className="flex gap-3">
              <button 
                onClick={() => handleExport('docx')}
                disabled={isExporting}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-lg transition-all disabled:opacity-50"
              >
                <Download className="w-5 h-5" />
                DOCX 다운로드
              </button>
              <button 
                onClick={() => handleExport('hwpx')}
                disabled={isExporting}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-orange-500 hover:bg-orange-600 text-white font-medium rounded-lg transition-all disabled:opacity-50"
              >
                <Download className="w-5 h-5" />
                HWPX 다운로드
              </button>
            </div>

            {/* 질문 그룹 (10개씩) */}
            <div className="space-y-3">
              {questionGroups.map((group, groupIdx) => (
                <div key={groupIdx} className="border border-slate-700/50 rounded-lg overflow-hidden">
                  {/* 그룹 헤더 */}
                  <button
                    onClick={() => toggleGroup(groupIdx)}
                    className={`w-full flex items-center justify-between p-4 transition-all ${
                      group.isExpanded 
                        ? 'bg-orange-500/20 border-b border-orange-500/30' 
                        : 'bg-slate-800/50 hover:bg-slate-800/70'
                    }`}
                  >
                    <span className={`text-base font-semibold ${group.isExpanded ? 'text-orange-300' : 'text-slate-300'}`}>
                      문항 {group.startNum} ~ {group.endNum}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-slate-400">{group.questions.length}개</span>
                      {group.isExpanded ? (
                        <ChevronUp className="w-5 h-5 text-orange-400" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-slate-400" />
                      )}
                    </div>
                  </button>

                  {/* 그룹 내 질문들 */}
                  {group.isExpanded && (
                    <div className="p-4 space-y-4 bg-slate-900/20">
                      {group.questions.map((question) => (
                        <div
                          key={question.id}
                          className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4 hover:border-orange-500/30 transition-all"
                        >
                          {/* 질문 헤더 */}
                          <div className="flex items-start gap-3 mb-3">
                            <div className="flex-shrink-0 w-9 h-9 rounded-full bg-orange-500/20 flex items-center justify-center">
                              <span className="text-sm font-bold text-orange-400">
                                {question.number}
                              </span>
                            </div>
                            
                            {/* 질문 텍스트 편집 */}
                            <div className="flex-1 min-w-0">
                              {editingQuestionId === question.id ? (
                                <div className="flex items-start gap-2">
                                  <textarea
                                    className="flex-1 bg-slate-700 border border-orange-500 rounded p-3 text-base text-white resize-none focus:outline-none focus:ring-2 focus:ring-orange-500"
                                    value={question.text}
                                    onChange={(e) => updateQuestionText(question.id, e.target.value)}
                                    rows={2}
                                    autoFocus
                                  />
                                  <button
                                    onClick={() => setEditingQuestionId(null)}
                                    className="p-2 text-green-400 hover:text-green-300"
                                  >
                                    <Save className="w-5 h-5" />
                                  </button>
                                </div>
                              ) : (
                                <div 
                                  className="text-base font-medium text-white leading-relaxed cursor-pointer hover:text-orange-300 transition-colors group"
                                  onClick={() => setEditingQuestionId(question.id)}
                                >
                                  {renderMarkdown(question.text)}
                                  <Edit3 className="w-4 h-4 inline ml-2 opacity-0 group-hover:opacity-100" />
                                </div>
                              )}
                              <span className="text-sm text-slate-500 mt-1 block">타입: {question.type}</span>
                            </div>
                          </div>

                          {/* 선택지 */}
                          {!question.isOpen && question.options.length > 0 && (
                            <div className="ml-12 space-y-2">
                              {question.options.map((option, optIdx) => (
                                <div key={optIdx} className="flex items-center gap-2 group">
                                  <div className="w-4 h-4 rounded-full border-2 border-slate-500 flex-shrink-0"></div>
                                  
                                  {editingOptionIdx?.qId === question.id && editingOptionIdx?.idx === optIdx ? (
                                    <div className="flex-1 flex items-center gap-2">
                                      <input
                                        type="text"
                                        className="flex-1 bg-slate-700 border border-orange-500 rounded px-3 py-2 text-base text-white focus:outline-none"
                                        value={option}
                                        onChange={(e) => updateOption(question.id, optIdx, e.target.value)}
                                        autoFocus
                                      />
                                      <button onClick={() => setEditingOptionIdx(null)} className="p-2 text-green-400">
                                        <Save className="w-4 h-4" />
                                      </button>
                                    </div>
                                  ) : (
                                    <div className="flex-1 flex items-center justify-between p-2 bg-slate-900/30 rounded border border-slate-700/30 hover:border-slate-600/50">
                                      <span 
                                        className="text-base text-slate-300 cursor-pointer hover:text-orange-300 flex-1"
                                        onClick={() => setEditingOptionIdx({ qId: question.id, idx: optIdx })}
                                      >
                                        {renderMarkdown(option)}
                                      </span>
                                      <button
                                        onClick={() => removeOption(question.id, optIdx)}
                                        className="p-1 text-red-400 opacity-0 group-hover:opacity-100"
                                      >
                                        <Trash2 className="w-4 h-4" />
                                      </button>
                                    </div>
                                  )}
                                </div>
                              ))}
                              
                              <button
                                onClick={() => addOption(question.id)}
                                className="flex items-center gap-2 text-sm text-slate-500 hover:text-orange-400 ml-6 mt-2"
                              >
                                <Plus className="w-4 h-4" /> 선택지 추가
                              </button>
                            </div>
                          )}

                          {question.isOpen && (
                            <div className="ml-12">
                              <div className="p-3 bg-slate-900/30 border border-slate-700/30 rounded text-base text-slate-500 italic">
                                주관식 응답란
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* 원문 보기 */}
            <button
              onClick={() => setShowRawContent(!showRawContent)}
              className="w-full flex items-center justify-between p-4 bg-slate-800/50 rounded-lg border border-slate-700/50 hover:border-orange-500/30"
            >
              <span className="text-base text-slate-300">원문 보기</span>
              {showRawContent ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
            </button>

            {showRawContent && (
              <div className="bg-slate-800/30 rounded-lg p-4 border border-slate-700/50 max-h-80 overflow-y-auto">
                <pre className="text-sm text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">{surveyContent}</pre>
              </div>
            )}
          </>
        )}

        {/* 생성 전 */}
        {questions.length === 0 && !surveyContent && (
          <div className="mt-8 text-center p-8 bg-slate-800/30 rounded-lg border border-slate-700/50 border-dashed">
            <FileText className="w-16 h-16 text-slate-500 mx-auto mb-4" />
            <p className="text-base text-slate-400">설문을 생성하면 여기에 표시됩니다</p>
            <p className="text-sm text-slate-500 mt-2">모든 단계를 완료해주세요</p>
          </div>
        )}
      </div>

      {/* 변경사항 알림 */}
      {hasLocalChanges && (
        <div className="p-3 bg-yellow-500/20 border-t border-yellow-500/50 flex items-center justify-between">
          <span className="text-sm text-yellow-300">⚠️ 저장되지 않은 변경사항이 있습니다</span>
          <button
            onClick={saveChanges}
            disabled={isSaving}
            className="text-sm px-3 py-1 bg-yellow-500 text-black font-medium rounded"
          >
            저장
          </button>
        </div>
      )}

      <style jsx global>{`
        .preview-scrollbar::-webkit-scrollbar { width: 8px; }
        .preview-scrollbar::-webkit-scrollbar-track { background: rgba(30, 41, 59, 0.5); border-radius: 4px; }
        .preview-scrollbar::-webkit-scrollbar-thumb { background: linear-gradient(180deg, #f97316 0%, #ea580c 100%); border-radius: 4px; }
        .preview-scrollbar { scrollbar-width: thin; scrollbar-color: #f97316 rgba(30, 41, 59, 0.5); }
      `}</style>
    </div>
  );
}