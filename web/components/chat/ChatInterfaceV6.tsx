"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Sparkles,
  Zap,
  Bot,
  User,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { ChatMessageV6 } from "./ChatMessageV6";
import { ExampleQueriesClient as ExampleQueries } from "../query/ExampleQueriesClient";
import { useAgentQueryV2 } from "@/hooks/useAgentQueryV2";
import { useQuery } from "@/hooks/useQuery";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  status?: "sending" | "processing" | "complete" | "error" | "failed";
  answer?: string;
  steps?: any[];
  data?: any;
  error?: string;
}

export function ChatInterfaceV6() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [useAgent, setUseAgent] = useState(true);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const activeMessageRef = useRef<string | null>(null);

  const agentQuery = useAgentQueryV2();
  const standardQuery = useQuery();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Handle agent streaming updates
  useEffect(() => {
    if (!agentQuery.queryId) return;

    const messageId = `agent-${agentQuery.queryId}`;

    // Transform steps to clean up display
    const transformedSteps = agentQuery.steps
      .filter((step, index) => {
        // Remove duplicate "Analyzing query..." except first
        if (step.type === "thought" && step.content === "Analyzing query...") {
          const firstAnalyzingIndex = agentQuery.steps.findIndex(
            s => s.type === "thought" && s.content === "Analyzing query..."
          );
          return index === firstAnalyzingIndex;
        }
        return true;
      })
      .map(step => step);

    // Determine current status
    let status: Message["status"] = "processing";
    let error: string | undefined;

    // Extract answer from result or from answer step
    let answer: string | undefined = agentQuery.result?.answer;
    if (!answer) {
      // Look for answer in steps
      const answerStep = transformedSteps.find(step => step.type === 'answer');
      if (answerStep) {
        answer = answerStep.content;
      }
    }

    if (agentQuery.error) {
      status = "error";
      error = agentQuery.error;
    } else if (agentQuery.isComplete) {
      console.log('[ChatV6] Query complete. Result:', agentQuery.result);
      console.log('[ChatV6] agentQuery.error:', agentQuery.error);

      // Only change status if we have a definitive result
      if (agentQuery.result) {
        if (agentQuery.result.success === false) {
          console.log('[ChatV6] Result success=false, marking as failed');
          status = "failed";
          error = agentQuery.result.error || "Query processing failed";
        } else if (agentQuery.result.answer || agentQuery.result.results || agentQuery.result.sql || agentQuery.result.success) {
          // If we have any of these, consider it successful
          console.log('[ChatV6] Has answer/results/sql/success, marking as complete');
          console.log('[ChatV6] Result details:', {
            hasAnswer: !!agentQuery.result.answer,
            hasResults: !!agentQuery.result.results,
            hasSql: !!agentQuery.result.sql,
            success: agentQuery.result.success
          });
          status = "complete";
          // Extract answer from result
          answer = agentQuery.result.answer || answer;
        } else {
          // Keep as processing if we're still waiting for result
          console.log('[ChatV6] Complete but no clear result yet, keeping as processing');
          status = "processing";
        }
      } else {
        // If complete but no result yet, check if we have an answer from steps
        if (answer) {
          console.log('[ChatV6] Complete with answer from steps, marking as complete');
          status = "complete";
        } else {
          console.log('[ChatV6] Complete but no result or answer yet, keeping as processing');
          status = "processing";
        }
      }
    }

    setMessages(prev => {
      const existingIndex = prev.findIndex(msg => msg.id === messageId);

      const updatedMessage: Message = {
        id: messageId,
        role: "assistant",
        content: "Processing your query...",
        timestamp: existingIndex >= 0 ? prev[existingIndex].timestamp : new Date(),
        status,
        answer,
        steps: transformedSteps,
        data: agentQuery.result,
        error,
      };

      if (existingIndex >= 0) {
        const updated = [...prev];
        updated[existingIndex] = updatedMessage;
        return updated;
      } else {
        activeMessageRef.current = messageId;
        return [...prev, updatedMessage];
      }
    });
  }, [agentQuery.queryId, agentQuery.steps, agentQuery.isComplete, agentQuery.isStreaming, agentQuery.result, agentQuery.error]);

  // Handle standard query results
  useEffect(() => {
    if (!standardQuery.data || useAgent) return;

    const messageId = `standard-${Date.now()}`;
    setMessages(prev => [...prev, {
      id: messageId,
      role: "assistant",
      content: "Query completed",
      timestamp: new Date(),
      status: "complete",
      answer: standardQuery.data.summary || `Found ${standardQuery.data.results?.row_count || 0} results`,
      data: standardQuery.data,
    }]);
  }, [standardQuery.data, useAgent]);

  // Handle standard query errors
  useEffect(() => {
    if (!standardQuery.error || useAgent) return;

    setMessages(prev => [...prev, {
      id: `error-${Date.now()}`,
      role: "assistant",
      content: "Query failed",
      timestamp: new Date(),
      status: "error",
      error: standardQuery.error instanceof Error ? standardQuery.error.message : "Query failed",
    }]);
  }, [standardQuery.error, useAgent]);

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

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  }, [handleSubmit]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, []);

  const handleExampleQuery = useCallback((query: string) => {
    setInput(query);
    textareaRef.current?.focus();
  }, []);

  const handleOptionClick = useCallback((option: string) => {
    // Add user message with the selected option
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: option,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);

    // Execute query with the selected option
    if (useAgent) {
      agentQuery.execute(option);
    } else {
      standardQuery.executeQuery(option);
    }
  }, [useAgent, agentQuery, standardQuery]);

  const isSubmitting = agentQuery.isStreaming || standardQuery.isLoading;

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-gray-100">
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          <h1 className="text-lg font-semibold text-gray-900">SENS</h1>

          <div className="flex items-center gap-3">
            <Label htmlFor="agent-mode" className="text-sm text-gray-600">
              {useAgent ? "Agent" : "Fast"}
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
              <Bot className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                Ask anything about your data
              </h2>
              <p className="text-gray-600 mb-8">
                Natural language to SQL, powered by AI
              </p>
              <ExampleQueries onExampleClick={handleExampleQuery} />
            </div>
          )}

          {messages.map((message, index) => (
            <ChatMessageV6
              key={message.id}
              message={message}
              index={index}
              onOptionClick={handleOptionClick}
            />
          ))}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="flex-shrink-0 border-t border-gray-100 px-6 py-4">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder="Ask me anything..."
                className="min-h-[56px] max-h-[200px] resize-none pr-12 py-4 border-gray-200 focus:border-gray-300"
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
