import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Bot, User, Loader2, Sprout, X, Minimize2 } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { useTranslation } from 'react-i18next';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
  timestamp?: string;
}

interface SourceInfo {
  source: string;
  page?: number;
  chunk_id: string;
  score: number;
}

interface RAGResponse {
  answer: string;
  sources: SourceInfo[];
  retrieved_chunks: string[];
  latency_ms: number;
  node_latencies?: {
    embed_ms: number;
    retrieve_ms: number;
    generate_ms: number;
  };
  // Supervisor V2 fields
  session_id?: string;
  turn_count?: number;
  executed_agents?: string[];
}

const ChatbotPopup: React.FC = () => {
  const { toast } = useToast();
  const { t } = useTranslation();
  const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
  
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'Hi! I\'m here to help with your agricultural questions. Ask me anything about farming, crops, or fertilizers!',
      timestamp: new Date().toISOString()
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTo({ top: containerRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [messages]);

  // Fallback responses when RAG system has no indexed content
  const generateFallbackResponse = (query: string): string => {
    const lowerQuery = query.toLowerCase();
    
    if (lowerQuery.includes('wheat')) {
      return `Wheat is best grown during the Rabi season (October-March) in India. Key points:\n\n• **Sowing**: October-December\n• **Temperature**: 15-25°C optimal\n• **Rainfall**: 300-400mm required\n• **Soil**: Well-drained loamy soil, pH 6.0-7.5\n• **Harvest**: March-April\n\nWheat requires cool, dry weather during grain filling.`;
    }
    
    if (lowerQuery.includes('rice')) {
      return `Rice is primarily grown during Kharif season (June-November). Details:\n\n• **Sowing**: June-July\n• **Temperature**: 20-35°C\n• **Rainfall**: 1000-2000mm\n• **Soil**: Clayey, waterlogged conditions\n• **Harvest**: October-November\n\nRice requires high humidity and standing water.`;
    }
    
    if (lowerQuery.includes('fertilizer')) {
      return `General fertilizer recommendations:\n\n• **NPK ratio**: Varies by crop and soil test\n• **Timing**: Split application for better efficiency\n• **Organic**: Compost, FYM improve soil health\n• **Micronutrients**: Zinc, iron often deficient\n\nAlways conduct soil testing before fertilizer application.`;
    }
    
    if (lowerQuery.includes('pest') || lowerQuery.includes('disease')) {
      return `Integrated Pest Management (IPM) approach:\n\n• **Prevention**: Crop rotation, resistant varieties\n• **Monitoring**: Regular field inspection\n• **Biological**: Beneficial insects, biopesticides\n• **Chemical**: Last resort, follow label instructions\n\nEarly detection and prevention are key.`;
    }
    
    return `I'd be happy to help with your agricultural question! Here are some general principles:\n\n• **Soil health**: Regular testing and organic matter addition\n• **Water management**: Efficient irrigation and drainage\n• **Crop selection**: Choose varieties suited to your climate\n• **Timing**: Follow local agricultural calendars\n• **Integrated approach**: Combine traditional and modern practices\n\nFor specific guidance, please consult your local agricultural extension officer or provide more details about your farming context.`;
  };

  // Convert markdown formatting to JSX
  const renderMessageContent = (content: string) => {
    let processedContent = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    processedContent = processedContent.replace(/^\s*\*\s+/gm, '• ');
    
    const parts = processedContent.split(/(<strong>.*?<\/strong>)/g);
    
    return parts.map((part, index) => {
      if (part.startsWith('<strong>') && part.endsWith('</strong>')) {
        const boldText = part.replace(/<\/?strong>/g, '');
        return <strong key={index} className="font-semibold text-gray-900">{boldText}</strong>;
      }
      return part;
    });
  };

  async function sendMessage(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: input.trim(),
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE}/api/v1/rag/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          query: userMessage.content,
          top_k: 5,
          filters: null,
          session_id: sessionId  // Send session_id for multi-turn conversations
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data: RAGResponse = await response.json();

      // Store session_id for future requests
      if (data.session_id) {
        setSessionId(data.session_id);
      }

      let responseContent = data.answer;
      let responseSources = data.sources.map(s => s.source);

      // Only use fallback if answer is truly empty (not just no retrieved_chunks)
      // Specialist agents (crop, weather, fertilizer) don't use retrieved_chunks!
      if (!data.answer || data.answer.trim() === '') {
        responseContent = generateFallbackResponse(userMessage.content);
        responseSources = ["General Agricultural Knowledge"];
      }

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: responseContent,
        sources: responseSources,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, assistantMessage]);

    } catch (err: any) {
      console.error('Chat error:', err);
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `I apologize, but I encountered an error. Please try again. Error: ${err.message}`,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  }

  if (!isOpen) {
    return (
      <div className="fixed bottom-6 right-6 z-50">
        <div className="relative">
          {/* Subtle glow effect */}
          <div className="absolute inset-0 rounded-full bg-gradient-to-r from-emerald-400 to-teal-500 opacity-20 blur-lg animate-pulse"></div>
          
          <Button
            onClick={() => setIsOpen(true)}
            className="relative w-16 h-16 rounded-full bg-gradient-to-br from-emerald-500 via-green-500 to-teal-600 hover:from-emerald-600 hover:via-green-600 hover:to-teal-700 shadow-xl hover:shadow-2xl transition-all duration-500 transform hover:scale-105 border-2 border-white/20"
          >
            <div className="relative flex items-center justify-center">
              <Sprout className="w-7 h-7 text-white drop-shadow-lg" />
            </div>
          </Button>
          
          {/* Floating tooltip */}
          <div className="absolute bottom-full right-0 mb-2 px-3 py-1 bg-slate-800 text-white text-xs rounded-lg opacity-0 hover:opacity-100 transition-opacity duration-300 whitespace-nowrap">
            {t('chatbot.tooltip')}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <Card className={`w-80 transition-all duration-300 shadow-2xl ${isMinimized ? 'h-14' : 'h-96'}`}>
        <CardHeader className="p-3 bg-gradient-to-r from-emerald-500 via-green-500 to-teal-600 text-white rounded-t-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-white/90 backdrop-blur rounded-full flex items-center justify-center shadow-lg">
                <Sprout className="w-4 h-4 text-emerald-600" />
              </div>
              <div>
                <CardTitle className="text-sm font-medium">{t('chatbot.assistant_name')}</CardTitle>
                <p className="text-xs text-emerald-100">{t('chatbot.assistant_description')}</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsMinimized(!isMinimized)}
                className="w-6 h-6 p-0 text-white hover:bg-white/20 rounded-full transition-all duration-200"
              >
                <Minimize2 className="w-3 h-3" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsOpen(false)}
                className="w-6 h-6 p-0 text-white hover:bg-white/20 rounded-full transition-all duration-200"
              >
                <X className="w-3 h-3" />
              </Button>
            </div>
          </div>
        </CardHeader>
        
        {!isMinimized && (
          <>
            <CardContent className="p-0 h-64 overflow-y-auto" ref={containerRef}>
              <div className="p-3 space-y-3">
                {messages.map((message, idx) => (
                  <div key={idx} className={`flex gap-2 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {message.role === 'assistant' && (
                      <div className="w-6 h-6 bg-gradient-to-br from-emerald-100 to-green-100 rounded-full flex items-center justify-center flex-shrink-0 mt-1 shadow-sm">
                        <Sprout className="w-3 h-3 text-emerald-600" />
                      </div>
                    )}
                    <div className={`max-w-[75%] ${message.role === 'user' ? 'order-first' : ''}`}>
                      <div className={`px-3 py-2 rounded-lg text-xs ${
                        message.role === 'user' 
                          ? 'bg-gradient-to-r from-emerald-500 to-green-500 text-white ml-auto shadow-md' 
                          : 'bg-slate-50 text-slate-800 border border-slate-200'
                      }`}>
                        <div className="leading-relaxed whitespace-pre-wrap">
                          {renderMessageContent(message.content)}
                        </div>
                      </div>
                      {message.timestamp && (
                        <p className="text-xs text-gray-500 mt-1 px-1">
                          {new Date(message.timestamp).toLocaleTimeString()}
                        </p>
                      )}
                    </div>
                    {message.role === 'user' && (
                      <div className="w-6 h-6 bg-gradient-to-br from-blue-100 to-indigo-100 rounded-full flex items-center justify-center flex-shrink-0 mt-1 shadow-sm">
                        <User className="w-3 h-3 text-blue-600" />
                      </div>
                    )}
                  </div>
                ))}
                {loading && (
                  <div className="flex gap-2 justify-start">
                    <div className="w-6 h-6 bg-gradient-to-br from-emerald-100 to-green-100 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm">
                      <Sprout className="w-3 h-3 text-emerald-600" />
                    </div>
                    <div className="bg-gradient-to-r from-slate-50 to-gray-50 text-slate-700 px-3 py-2 rounded-lg border border-slate-200">
                      <div className="flex items-center gap-2">
                        <Loader2 className="w-3 h-3 animate-spin text-emerald-500" />
                        <span className="text-xs">{t('chatbot.thinking')}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
            
            <div className="p-3 border-t bg-gradient-to-r from-slate-50 to-gray-50">
              <form onSubmit={sendMessage} className="flex items-center gap-2">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={t('chatbot.placeholder')}
                  disabled={loading}
                  className="flex-1 text-xs h-8 border-slate-200 focus:border-emerald-300 focus:ring-emerald-200"
                />
                <Button 
                  type="submit" 
                  disabled={loading || !input.trim()} 
                  size="sm" 
                  className="h-8 px-3 bg-gradient-to-r from-emerald-500 to-green-500 hover:from-emerald-600 hover:to-green-600 shadow-md"
                >
                  {loading ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    t('chatbot.send')
                  )}
                </Button>
              </form>
            </div>
          </>
        )}
      </Card>
    </div>
  );
};

export default ChatbotPopup;
