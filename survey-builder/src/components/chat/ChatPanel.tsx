// src/components/chat/ChatPanel.tsx

'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send, Bot, User, Loader2, Sparkles } from 'lucide-react';
import { useSurveyStore } from '@/stores/survey-store';
import { initSurvey, sendMessage, getPreview } from '@/lib/api';

// 간단한 마크다운 처리 함수 (볼드, 이탤릭, 헤더)
function renderMarkdown(text: string): React.ReactNode {
  if (!text) return null;
  
  // **bold**, *italic*, ## 헤더 처리
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
}

// 타이핑 효과 커스텀 훅 (첫 글자 누락 버그 수정)
function useTypingEffect(
  text: string, 
  speed: number = 30,
  enabled: boolean = true,
  onUpdate?: () => void
) {
  const [displayedText, setDisplayedText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const indexRef = useRef(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // 타이핑 비활성화 또는 텍스트 없음
    if (!enabled || !text) {
      setDisplayedText(text || '');
      setIsTyping(false);
      return;
    }

    // 초기화
    setIsTyping(true);
    setDisplayedText('');
    indexRef.current = 0;

    // 타이핑 함수
    const typeNextChar = () => {
      if (indexRef.current < text.length) {
        const nextChar = text.charAt(indexRef.current);
        setDisplayedText(prev => prev + nextChar);
        indexRef.current += 1;
        
        if (onUpdate) {
          onUpdate();
        }
        
        timerRef.current = setTimeout(typeNextChar, speed);
      } else {
        setIsTyping(false);
      }
    };

    // 첫 글자 즉시 시작
    timerRef.current = setTimeout(typeNextChar, 0);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [text, speed, enabled]);

  return { displayedText, isTyping };
}

// 타이핑 메시지 컴포넌트
function TypingMessage({ 
  content, 
  isLatest,
  onTextUpdate 
}: { 
  content: string; 
  isLatest: boolean;
  onTextUpdate?: () => void;
}) {
  const { displayedText, isTyping } = useTypingEffect(
    content, 
    25,  // 25ms per character
    isLatest,
    onTextUpdate
  );
  
  const textToRender = isLatest ? displayedText : content;
  
  return (
    <p className="text-sm leading-relaxed whitespace-pre-wrap">
      {renderMarkdown(textToRender)}
      {isTyping && <span className="inline-block w-1 h-4 ml-1 bg-orange-400 animate-pulse" />}
    </p>
  );
}

export default function ChatPanel() {
  const [input, setInput] = useState('');
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const initialized = useRef(false);
  const [latestMessageIndex, setLatestMessageIndex] = useState<number | null>(null);
  
  const {
    sessionId,
    messages,
    isProcessing,
    setIsProcessing,
    updateFromResponse,
    setAllFields,
  } = useSurveyStore();

  // 타이핑 중 스크롤 (즉시)
  const scrollToBottom = useCallback(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    
    const init = async () => {
      try {
        setIsProcessing(true);
        const response = await initSurvey();
        updateFromResponse(response);
        setLatestMessageIndex(0);
      } catch (error) {
        console.error('초기화 오류:', error);
      } finally {
        setIsProcessing(false);
      }
    };
    
    init();
  }, []);

  // 응답 완료 후 입력창에 포커스
  useEffect(() => {
    if (!isProcessing && textareaRef.current) {
      const timer = setTimeout(() => {
        textareaRef.current?.focus();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isProcessing, messages]);

  // 새 메시지 추가 시 스크롤
  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSend = async () => {
    if (!input.trim() || isProcessing) return;
    
    const userMessage = input.trim();
    setInput('');
    
    useSurveyStore.getState().addMessage('user', userMessage);
    
    try {
      setIsProcessing(true);
      const response = await sendMessage(userMessage, sessionId || undefined);
      updateFromResponse(response);
      
      // 새 AI 메시지에 타이핑 효과 적용
      const newMessages = useSurveyStore.getState().messages;
      const lastAssistantIndex = newMessages.map((m, i) => ({ m, i }))
        .filter(x => x.m.role === 'assistant')
        .pop()?.i;
      if (lastAssistantIndex !== undefined) {
        setLatestMessageIndex(lastAssistantIndex);
      }
      
      if (response.session_id) {
        const preview = await getPreview(response.session_id);
        setAllFields(preview.all_fields);
      }
    } catch (error) {
      console.error('메시지 전송 오류:', error);
      useSurveyStore.getState().addMessage(
        'assistant',
        '오류가 발생했습니다. 다시 시도해주세요.'
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 빠른 응답 클릭 시 입력창에 포커스
  const handleQuickResponse = (text: string) => {
    setInput(text);
    setTimeout(() => {
      textareaRef.current?.focus();
    }, 0);
  };

  const quickResponses = ['확인', '수정 필요', '다음 단계', '이전으로'];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 헤더 */}
      <div className="p-4 border-b border-white/10 flex-shrink-0 bg-slate-800/30">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-orange-400" />
          <h2 className="font-semibold text-lg text-white">대화</h2>
        </div>
      </div>

      {/* 메시지 영역 - 커스텀 스크롤바 */}
      <div 
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-6 chat-scrollbar"
      >
        <div className="space-y-6 max-w-4xl mx-auto">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex gap-3 ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {message.role === 'assistant' && (
                <div className="w-10 h-10 rounded-full gradient-primary flex items-center justify-center flex-shrink-0 shadow-lg">
                  <Bot className="w-6 h-6 text-white" />
                </div>
              )}
              
              <div
                className={`max-w-[75%] rounded-2xl p-4 shadow-lg transition-all duration-200 ${
                  message.role === 'user'
                    ? 'gradient-primary text-white'
                    : 'glass text-slate-100 border border-white/10'
                }`}
              >
                {/* AI 메시지에 타이핑 효과 적용 */}
                {message.role === 'assistant' ? (
                  <TypingMessage 
                    content={message.content} 
                    isLatest={index === latestMessageIndex}
                    onTextUpdate={scrollToBottom}
                  />
                ) : (
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">
                    {message.content}
                  </p>
                )}
              </div>
              
              {message.role === 'user' && (
                <div className="w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center flex-shrink-0 shadow-lg">
                  <User className="w-6 h-6 text-slate-300" />
                </div>
              )}
            </div>
          ))}
          
          {/* 로딩 */}
          {isProcessing && (
            <div className="flex gap-3 justify-start">
              <div className="w-10 h-10 rounded-full gradient-primary flex items-center justify-center shadow-lg">
                <Bot className="w-6 h-6 text-white" />
              </div>
              <div className="glass rounded-2xl p-4 border border-white/10">
                <div className="flex gap-1.5">
                  <div className="w-2 h-2 bg-orange-400 rounded-full typing-animation" style={{ animationDelay: '0s' }}></div>
                  <div className="w-2 h-2 bg-orange-400 rounded-full typing-animation" style={{ animationDelay: '0.2s' }}></div>
                  <div className="w-2 h-2 bg-orange-400 rounded-full typing-animation" style={{ animationDelay: '0.4s' }}></div>
                </div>
              </div>
            </div>
          )}
          
          <div ref={scrollAnchorRef} />
        </div>
      </div>

      {/* 빠른 응답 */}
      <div className="px-6 py-3 border-t border-white/10 flex gap-2 flex-wrap flex-shrink-0 bg-slate-800/30">
        {quickResponses.map((text) => (
          <button
            key={text}
            onClick={() => handleQuickResponse(text)}
            disabled={isProcessing}
            className="px-4 py-2 text-sm border border-orange-500/50 bg-orange-500/10 text-orange-400 rounded-lg hover:bg-orange-500/20 hover:border-orange-500 transition-all duration-200 disabled:opacity-50"
          >
            {text}
          </button>
        ))}
      </div>

      {/* 입력 영역 */}
      <div className="p-6 border-t border-white/10 flex-shrink-0 bg-slate-900/50">
        <div className="flex gap-3 max-w-4xl mx-auto">
          <div className="flex-1 relative">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="메시지를 입력하세요... (Shift+Enter: 줄바꿈)"
              className="min-h-[56px] resize-none glass border-white/20 text-white placeholder:text-slate-500 focus:border-orange-500/50 focus:ring-2 focus:ring-orange-500/20 rounded-xl pr-4"
              disabled={isProcessing}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={!input.trim() || isProcessing}
            className="self-end px-6 py-3 gradient-primary text-white rounded-xl hover:opacity-90 transition-all duration-200 shadow-lg hover:shadow-orange-500/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isProcessing ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                <Send className="w-5 h-5" />
                <span className="font-medium">전송</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* 커스텀 스크롤바 스타일 */}
      <style jsx global>{`
        .chat-scrollbar::-webkit-scrollbar {
          width: 8px;
        }
        
        .chat-scrollbar::-webkit-scrollbar-track {
          background: rgba(30, 41, 59, 0.5);
          border-radius: 4px;
        }
        
        .chat-scrollbar::-webkit-scrollbar-thumb {
          background: linear-gradient(180deg, #f97316 0%, #ea580c 100%);
          border-radius: 4px;
          border: 2px solid rgba(30, 41, 59, 0.5);
        }
        
        .chat-scrollbar::-webkit-scrollbar-thumb:hover {
          background: linear-gradient(180deg, #fb923c 0%, #f97316 100%);
        }
        
        /* Firefox */
        .chat-scrollbar {
          scrollbar-width: thin;
          scrollbar-color: #f97316 rgba(30, 41, 59, 0.5);
        }
      `}</style>
    </div>
  );
}