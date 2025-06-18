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
} from "lucide-react";
import * as Avatar from "@radix-ui/react-avatar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { ChatMessageV2 } from "./ChatMessageV2";
import { ExampleQueriesClient as ExampleQueries } from "../query/ExampleQueriesClient";
import { useAgentQueryV2 } from "@/hooks/useAgentQueryV2";
import { useQuery } from "@/hooks/useQuery";

// Simple, clear message types
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
    steps?: AgentStep[];
    isStreaming?: boolean;
  };
}

interface AgentStep {
  id: string;
  type: "thought" | "action" | "observation" | "answer";
  content: string;
  iteration: number;
  timestamp: number;
}

export function ChatInterfaceV3() {
  // Core state
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [useAgent, setUseAgent] = useState(true);

  // Refs
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentStreamingMessageRef = useRef<string | null>(null);

  // Hooks
  const agentQuery = useAgentQueryV2();
  const standardQuery = useQuery();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Handle agent streaming updates - Update the streaming message as steps come in
  useEffect(() => {
    if (!agentQuery.queryId || !agentQuery.isStreaming) {
      return;
    }

    const streamingMessageId = `thinking-${agentQuery.queryId}`;

    setMessages(prev => {
      // Find existing streaming message
      const existingIndex = prev.findIndex(msg => msg.id === streamingMessageId);

      const streamingMessage: Message = {
        id: streamingMessageId,
        role: "assistant",
        content: "Analyzing your query...",
        timestamp: new Date(),
        metadata: {
          type: "thinking",
          steps: [...agentQuery.steps], // Create a new array to ensure React detects the change
          isStreaming: true,
        },
      };

      if (existingIndex >= 0) {
        // Update existing
        const updated = [...prev];
        updated[existingIndex] = streamingMessage;
        return updated;
      } else {
        // Add new
        currentStreamingMessageRef.current = streamingMessageId;
        return [...prev, streamingMessage];
      }
    });
  }, [agentQuery.queryId, agentQuery.steps, agentQuery.isStreaming]);

  // Handle agent completion - Only process once
  useEffect(() => {
    if (!agentQuery.queryId || !agentQuery.isComplete) {
      return;
    }

    console.log('[V3] Agent completion detected', {
      queryId: agentQuery.queryId,
      hasResult: !!agentQuery.result,
      result: agentQuery.result,
      hasError: !!agentQuery.error,
      error: agentQuery.error,
    });

    // Clear the streaming message reference
    const streamingMessageId = currentStreamingMessageRef.current;
    currentStreamingMessageRef.current = null;

    setMessages(prev => {
      // Remove the streaming message
      let filtered = prev;
      if (streamingMessageId) {
        filtered = prev.filter(msg => msg.id !== streamingMessageId);
      }

      // Check if we already have final messages for this query
      const hasCompletionMessages = filtered.some(msg =>
        msg.id.startsWith(`answer-${agentQuery.queryId}`) ||
        msg.id.startsWith(`sql-${agentQuery.queryId}`) ||
        msg.id.startsWith(`data-${agentQuery.queryId}`) ||
        msg.id.startsWith(`thinking-complete-${agentQuery.queryId}`)
      );

      if (hasCompletionMessages) {
        return filtered; // Don't add duplicates
      }

      const newMessages: Message[] = [];

      // Check if we have an error result (not a connection error)
      const hasErrorResult = agentQuery.result?.error && !agentQuery.result?.sql;
      console.log('[V3] Checking error result', {
        hasErrorResult,
        errorInResult: agentQuery.result?.error,
        hasSql: !!agentQuery.result?.sql,
      });

      // Add completed thinking message if we have steps
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
          },
        });
      }

      // Skip success messages if we have an error result
      if (!hasErrorResult) {
        // Add answer message
        const answerStep = agentQuery.steps.find(s => s.type === "answer");
        const answerContent = answerStep?.content ||
                             agentQuery.result?.answer ||
                             agentQuery.result?.summary ||
                             (agentQuery.result?.results ? `Found ${agentQuery.result.results.row_count || 0} results` : "Query completed");

        newMessages.push({
          id: `answer-${agentQuery.queryId}`,
          role: "assistant",
          content: answerContent,
          timestamp: new Date(),
          metadata: {
            type: "answer",
          },
        });

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
            },
          });
        }

        // Add data if available
        if (agentQuery.result?.results?.data?.length > 0) {
          console.log('[V3] Adding data message', {
            queryId: agentQuery.queryId,
            dataLength: agentQuery.result.results.data.length,
            columns: agentQuery.result.results.columns,
            firstRow: agentQuery.result.results.data[0],
          });
          newMessages.push({
            id: `data-${agentQuery.queryId}`,
            role: "assistant",
            content: "Query Results",
            timestamp: new Date(),
            metadata: {
              type: "data",
              data: agentQuery.result, // This is correct - QueryResults expects the full response
            },
          });
        }
      }

      return [...filtered, ...newMessages];
    });
  }, [agentQuery.queryId, agentQuery.isComplete, agentQuery.result]);

  // Handle agent errors
  useEffect(() => {
    if (!agentQuery.error || !agentQuery.queryId) return;

    // Don't show connection lost errors if we have results
    if (agentQuery.error === 'Connection to server lost' && agentQuery.result) {
      console.log('[V3] Ignoring connection lost error - we have results');
      return;
    }

    // Clear streaming message if any
    currentStreamingMessageRef.current = null;

    setMessages(prev => {
      // Remove any streaming message
      const filtered = prev.filter(msg =>
        !(msg.metadata?.isStreaming && msg.id.includes(agentQuery.queryId))
      );

      // Check if we already have an error for this query
      const hasError = filtered.some(msg =>
        msg.id === `error-${agentQuery.queryId}`
      );

      if (hasError) return filtered;

      return [...filtered, {
        id: `error-${agentQuery.queryId}`,
        role: "assistant",
        content: `Sorry, I encountered an error: ${agentQuery.error}`,
        timestamp: new Date(),
        metadata: {
          type: "error",
          error: agentQuery.error,
        },
      }];
    });
  }, [agentQuery.error, agentQuery.queryId, agentQuery.result]);

  // Handle standard query results
  useEffect(() => {
    if (!standardQuery.data || useAgent) return;

    const newMessages: Message[] = [];

    // Add answer
    if (standardQuery.data.summary) {
      newMessages.push({
        id: `answer-std-${Date.now()}`,
        role: "assistant",
        content: standardQuery.data.summary,
        timestamp: new Date(),
        metadata: { type: "answer" },
      });
    }

    // Add SQL
    if (standardQuery.data.sql) {
      newMessages.push({
        id: `sql-std-${Date.now()}`,
        role: "assistant",
        content: "Generated SQL Query",
        timestamp: new Date(),
        metadata: {
          type: "sql",
          sql: standardQuery.data.sql,
        },
      });
    }

    // Add data
    if (standardQuery.data.results?.data?.length > 0) {
      newMessages.push({
        id: `data-std-${Date.now()}`,
        role: "assistant",
        content: "Query Results",
        timestamp: new Date(),
        metadata: {
          type: "data",
          data: standardQuery.data,
        },
      });
    }

    if (newMessages.length > 0) {
      setMessages(prev => [...prev, ...newMessages]);
    }
  }, [standardQuery.data, useAgent]);

  // Handle standard query errors
  useEffect(() => {
    if (!standardQuery.error || useAgent) return;

    setMessages(prev => [...prev, {
      id: `error-std-${Date.now()}`,
      role: "assistant",
      content: `Error: ${standardQuery.error instanceof Error ? standardQuery.error.message : "Query failed"}`,
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

  const isSubmitting = agentQuery.isStreaming || standardQuery.isLoading;

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-gray-50 to-white">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-gray-200/50 bg-white/50 backdrop-blur-sm">
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          <div className="flex items-center gap-3">
            <MessageCircle className="w-5 h-5 text-gray-600" />
            <h1 className="text-lg font-semibold text-gray-900">SENS Chat V3</h1>
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
                Welcome to SENS Chat
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
