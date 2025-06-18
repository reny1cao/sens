"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Sparkles,
  Zap,
  Bot,
  User,
  Loader2,
  MessageCircle,
  AlertTriangle,
  CheckCircle,
  XCircle,
} from "lucide-react";
import * as Avatar from "@radix-ui/react-avatar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ChatMessageV2 } from "./ChatMessageV2";
import { ExampleQueriesClient as ExampleQueries } from "../query/ExampleQueriesClient";
import { useAgentQueryV4 } from "@/hooks/useAgentQueryV4";
import { useQuery } from "@/hooks/useQuery";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  metadata?: {
    type?: "thinking" | "answer" | "sql" | "data" | "error";
    sql?: string;
    data?: any;
    error?: string;
    steps?: any[];
    isStreaming?: boolean;
    queryId?: string;
  };
}

export function ChatInterfaceV4() {
  // Core state
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [useAgent, setUseAgent] = useState(true);

  // Refs
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Hooks
  const agentQuery = useAgentQueryV4();
  const standardQuery = useQuery();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Handle agent streaming - show thinking steps in real-time
  useEffect(() => {
    if (!agentQuery.queryId || agentQuery.status !== 'streaming') {
      return;
    }

    setMessages(prev => {
      const streamingId = `thinking-${agentQuery.queryId}`;
      const existingIndex = prev.findIndex(msg => msg.id === streamingId);

      const streamingMessage: Message = {
        id: streamingId,
        role: "assistant",
        content: "Analyzing your query...",
        timestamp: new Date(),
        metadata: {
          type: "thinking",
          steps: agentQuery.steps,
          isStreaming: true,
          queryId: agentQuery.queryId,
        },
      };

      if (existingIndex >= 0) {
        const updated = [...prev];
        updated[existingIndex] = streamingMessage;
        return updated;
      } else {
        return [...prev, streamingMessage];
      }
    });
  }, [agentQuery.queryId, agentQuery.steps, agentQuery.status]);

  // Handle agent completion
  useEffect(() => {
    if (!agentQuery.queryId || agentQuery.status !== 'complete') {
      return;
    }

    console.log('[V4 UI] Processing completion for query:', agentQuery.queryId);
    console.log('[V4 UI] Result:', agentQuery.result);

    setMessages(prev => {
      // Remove streaming message
      const filtered = prev.filter(msg =>
        !(msg.id === `thinking-${agentQuery.queryId}` && msg.metadata?.isStreaming)
      );

      // Check if we already processed this completion
      const hasCompletion = filtered.some(msg =>
        msg.metadata?.queryId === agentQuery.queryId && !msg.metadata?.isStreaming
      );

      if (hasCompletion) {
        console.log('[V4 UI] Already processed completion');
        return filtered;
      }

      const newMessages: Message[] = [];

      // Add thinking steps summary if available
      if (agentQuery.steps.length > 0) {
        newMessages.push({
          id: `thinking-complete-${agentQuery.queryId}`,
          role: "assistant",
          content: "Analysis complete",
          timestamp: new Date(),
          metadata: {
            type: "thinking",
            steps: agentQuery.steps,
            isStreaming: false,
            queryId: agentQuery.queryId,
          },
        });
      }

      // Add answer if available
      const answer = agentQuery.result?.answer ||
                    agentQuery.result?.summary ||
                    (agentQuery.result?.results ? `Found ${agentQuery.result.results.row_count} result${agentQuery.result.results.row_count !== 1 ? 's' : ''}` : null);

      if (answer) {
        newMessages.push({
          id: `answer-${agentQuery.queryId}`,
          role: "assistant",
          content: answer,
          timestamp: new Date(),
          metadata: {
            type: "answer",
            queryId: agentQuery.queryId,
          },
        });
      }

      // Add SQL if available
      if (agentQuery.result?.sql) {
        newMessages.push({
          id: `sql-${agentQuery.queryId}`,
          role: "assistant",
          content: "Generated SQL Query",
          timestamp: new Date(),
          metadata: {
            type: "sql",
            sql: agentQuery.result.sql,
            queryId: agentQuery.queryId,
          },
        });
      }

      // Add data if available
      if (agentQuery.result?.results?.data && agentQuery.result.results.data.length > 0) {
        newMessages.push({
          id: `data-${agentQuery.queryId}`,
          role: "assistant",
          content: "Query Results",
          timestamp: new Date(),
          metadata: {
            type: "data",
            data: agentQuery.result,
            queryId: agentQuery.queryId,
          },
        });
      }

      console.log('[V4 UI] Adding', newMessages.length, 'new messages');
      return [...filtered, ...newMessages];
    });
  }, [agentQuery.queryId, agentQuery.status, agentQuery.result, agentQuery.steps]);

  // Handle agent errors
  useEffect(() => {
    if (!agentQuery.queryId || agentQuery.status !== 'error' || !agentQuery.error) {
      return;
    }

    console.log('[V4 UI] Processing error:', agentQuery.error);

    setMessages(prev => {
      // Remove streaming message
      const filtered = prev.filter(msg =>
        !(msg.id === `thinking-${agentQuery.queryId}` && msg.metadata?.isStreaming)
      );

      // Check if we already have an error for this query
      const hasError = filtered.some(msg =>
        msg.id === `error-${agentQuery.queryId}`
      );

      if (hasError) {
        return filtered;
      }

      // Add completed thinking if we have steps
      const newMessages: Message[] = [];

      if (agentQuery.steps.length > 0) {
        newMessages.push({
          id: `thinking-error-${agentQuery.queryId}`,
          role: "assistant",
          content: "Analysis incomplete",
          timestamp: new Date(),
          metadata: {
            type: "thinking",
            steps: agentQuery.steps,
            isStreaming: false,
            queryId: agentQuery.queryId,
          },
        });
      }

      // Add error message
      newMessages.push({
        id: `error-${agentQuery.queryId}`,
        role: "assistant",
        content: agentQuery.error,
        timestamp: new Date(),
        metadata: {
          type: "error",
          error: agentQuery.error,
          queryId: agentQuery.queryId,
        },
      });

      return [...filtered, ...newMessages];
    });
  }, [agentQuery.queryId, agentQuery.status, agentQuery.error, agentQuery.steps]);

  // Handle standard query results
  useEffect(() => {
    if (!standardQuery.data || useAgent) return;

    const messages: Message[] = [];

    if (standardQuery.data.summary) {
      messages.push({
        id: `answer-std-${Date.now()}`,
        role: "assistant",
        content: standardQuery.data.summary,
        timestamp: new Date(),
        metadata: { type: "answer" },
      });
    }

    if (standardQuery.data.sql) {
      messages.push({
        id: `sql-std-${Date.now()}`,
        role: "assistant",
        content: "Generated SQL Query",
        timestamp: new Date(),
        metadata: { type: "sql", sql: standardQuery.data.sql },
      });
    }

    if (standardQuery.data.results?.data?.length > 0) {
      messages.push({
        id: `data-std-${Date.now()}`,
        role: "assistant",
        content: "Query Results",
        timestamp: new Date(),
        metadata: { type: "data", data: standardQuery.data },
      });
    }

    if (messages.length > 0) {
      setMessages(prev => [...prev, ...messages]);
    }
  }, [standardQuery.data, useAgent]);

  // Handle standard query errors
  useEffect(() => {
    if (!standardQuery.error || useAgent) return;

    setMessages(prev => [...prev, {
      id: `error-std-${Date.now()}`,
      role: "assistant",
      content: standardQuery.error instanceof Error ? standardQuery.error.message : "Query failed",
      timestamp: new Date(),
      metadata: {
        type: "error",
        error: standardQuery.error instanceof Error ? standardQuery.error.message : "Query failed",
      },
    }]);
  }, [standardQuery.error, useAgent]);

  // Submit handler
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();

    const query = input.trim();
    if (!query) return;

    // Add user message
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: query,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput("");

    // Reset textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    // Execute query
    if (useAgent) {
      agentQuery.execute(query);
    } else {
      standardQuery.executeQuery(query);
    }
  }, [input, useAgent, agentQuery, standardQuery]);

  // Handle key press
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  }, [handleSubmit]);

  // Auto-resize textarea
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, []);

  // Handle example query
  const handleExampleQuery = useCallback((query: string) => {
    setInput(query);
    textareaRef.current?.focus();
  }, []);

  const isSubmitting = agentQuery.isLoading || standardQuery.isLoading;

  // Get status badge
  const getStatusBadge = () => {
    if (!useAgent || agentQuery.status === 'idle') return null;

    const statusConfig = {
      connecting: { label: 'Connecting', icon: Loader2, className: 'bg-blue-500' },
      streaming: { label: 'Analyzing', icon: Loader2, className: 'bg-purple-500' },
      fetching: { label: 'Fetching Results', icon: Loader2, className: 'bg-indigo-500' },
      complete: { label: 'Complete', icon: CheckCircle, className: 'bg-green-500' },
      error: { label: 'Error', icon: XCircle, className: 'bg-red-500' },
    };

    const config = statusConfig[agentQuery.status];
    if (!config) return null;

    const Icon = config.icon;

    return (
      <Badge className={cn('gap-1', config.className, 'text-white border-0')}>
        <Icon className={cn('w-3 h-3', agentQuery.status !== 'complete' && agentQuery.status !== 'error' && 'animate-spin')} />
        {config.label}
      </Badge>
    );
  };

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-gray-50 to-white">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-gray-200/50 bg-white/50 backdrop-blur-sm">
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          <div className="flex items-center gap-3">
            <MessageCircle className="w-5 h-5 text-gray-600" />
            <h1 className="text-lg font-semibold text-gray-900">SENS Chat V4</h1>
            {getStatusBadge()}
          </div>

          <div className="flex items-center gap-3">
            <Label htmlFor="agent-mode" className="text-sm text-gray-600">
              {useAgent ? "Agent Mode" : "Fast Mode"}
            </Label>
            <Switch
              id="agent-mode"
              checked={useAgent}
              onCheckedChange={setUseAgent}
              className="data-[state=checked]:bg-gray-900"
            />
            <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
              {useAgent ? (
                <Sparkles className="w-4 h-4 text-gray-600" />
              ) : (
                <Zap className="w-4 h-4 text-gray-600" />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-8">
        <div className="max-w-4xl mx-auto space-y-6">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <Bot className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                Welcome to SENS Chat V4
              </h2>
              <p className="text-gray-600 mb-8">
                Ask questions about your data in natural language
              </p>
              <ExampleQueries onExampleClick={handleExampleQuery} />
            </div>
          )}

          {messages.map((message, index) => (
            <ChatMessageV2
              key={message.id}
              message={message}
              index={index}
            />
          ))}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="flex-shrink-0 border-t border-gray-200/50 bg-white/50 backdrop-blur-sm px-6 py-4">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder="Ask me anything about your data..."
                className="min-h-[56px] max-h-[200px] resize-none pr-12 py-4"
                disabled={isSubmitting}
              />
              {input.length > 0 && (
                <div className="absolute bottom-2 right-2 text-xs text-gray-400">
                  {input.length}
                </div>
              )}
            </div>
            <Button
              type="submit"
              size="lg"
              disabled={!input.trim() || isSubmitting}
              className="px-6 bg-gray-900 hover:bg-gray-800"
            >
              {isSubmitting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
