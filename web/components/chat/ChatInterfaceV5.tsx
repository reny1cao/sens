"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Sparkles,
  Zap,
  Bot,
  Loader2,
  MessageCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { ChatMessageV5 } from "./ChatMessageV5";
import { ExampleQueriesClient as ExampleQueries } from "../query/ExampleQueriesClient";
import { useAgentQueryV4 } from "@/hooks/useAgentQueryV4";
import { useQuery } from "@/hooks/useQuery";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  status?: "streaming" | "complete" | "error";
  answer?: string;
  steps?: any[];
  data?: any;
  error?: string;
}

export function ChatInterfaceV5() {
  // Core state
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [useAgent, setUseAgent] = useState(true);

  // Refs
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const activeMessageRef = useRef<string | null>(null);

  // Hooks
  const agentQuery = useAgentQueryV4();
  const standardQuery = useQuery();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Handle agent updates - single message that updates
  useEffect(() => {
    if (!agentQuery.queryId) return;

    const messageId = `agent-${agentQuery.queryId}`;

    // Filter out duplicate reasoning steps that are followed by actions with the same content
    const filteredSteps = agentQuery.steps.filter((step, index) => {
      // Keep all non-thought steps
      if (step.type !== "thought") return true;

      // Check if the next step is an action with similar content
      const nextStep = agentQuery.steps[index + 1];
      if (nextStep && nextStep.type === "action") {
        // Extract the reasoning part from the action content (after the colon)
        const actionReasoning = nextStep.content.split(": ")[1]?.trim();
        const thoughtContent = step.content.trim();

        // Skip this thought if it matches the action reasoning
        if (actionReasoning && thoughtContent === actionReasoning) {
          return false;
        }
      }

      // Keep generic "Analyzing query..." only if it's the first step
      if (step.content === "Analyzing query..." && index > 0) {
        return false;
      }

      return true;
    });

    // Determine current status
    let status: Message["status"] = "streaming";
    let answer: string | undefined;
    let error: string | undefined;

    if (agentQuery.status === "error" && agentQuery.error) {
      status = "error";
      error = agentQuery.error;
    } else if (agentQuery.status === "complete") {
      status = "complete";
      answer = agentQuery.result?.answer ||
               agentQuery.result?.summary ||
               (agentQuery.result?.results ? `Found ${agentQuery.result.results.row_count} result${agentQuery.result.results.row_count !== 1 ? 's' : ''}` : "Query completed");
    }

    setMessages(prev => {
      // Find existing message for this query
      const existingIndex = prev.findIndex(msg => msg.id === messageId);

      const updatedMessage: Message = {
        id: messageId,
        role: "assistant",
        content: "Processing your query...",
        timestamp: existingIndex >= 0 ? prev[existingIndex].timestamp : new Date(),
        status,
        answer,
        steps: filteredSteps,
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
  }, [
    agentQuery.queryId,
    agentQuery.status,
    agentQuery.steps,
    agentQuery.result,
    agentQuery.error,
  ]);

  // Clear active message when complete
  useEffect(() => {
    if (agentQuery.status === "complete" || agentQuery.status === "error") {
      activeMessageRef.current = null;
    }
  }, [agentQuery.status]);

  // Handle standard query results
  useEffect(() => {
    if (!standardQuery.data || useAgent) return;

    const messageId = `standard-${Date.now()}`;
    const answer = standardQuery.data.summary ||
                  (standardQuery.data.results ? `Found ${standardQuery.data.results.row_count} results` : "Query completed");

    setMessages(prev => [...prev, {
      id: messageId,
      role: "assistant",
      content: "Query completed",
      timestamp: new Date(),
      status: "complete" as const,
      answer,
      data: standardQuery.data,
    }]);
  }, [standardQuery.data, useAgent]);

  // Handle standard query errors
  useEffect(() => {
    if (!standardQuery.error || useAgent) return;

    setMessages(prev => [...prev, {
      id: `standard-error-${Date.now()}`,
      role: "assistant",
      content: "Query failed",
      timestamp: new Date(),
      status: "error" as const,
      error: standardQuery.error instanceof Error ? standardQuery.error.message : "Query failed",
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

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header - Minimal */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-gray-100">
        <div className="flex items-center justify-between max-w-3xl mx-auto">
          <div className="flex items-center gap-3">
            <MessageCircle className="w-5 h-5 text-gray-700" />
            <h1 className="text-lg font-medium text-gray-900">SENS</h1>
          </div>

          <div className="flex items-center gap-2">
            <Label htmlFor="agent-mode" className="text-xs text-gray-500">
              {useAgent ? "Smart" : "Fast"}
            </Label>
            <Switch
              id="agent-mode"
              checked={useAgent}
              onCheckedChange={setUseAgent}
              className="data-[state=checked]:bg-gray-900 scale-75"
            />
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-8">
          {messages.length === 0 ? (
            <div className="text-center py-16">
              <Bot className="w-10 h-10 text-gray-300 mx-auto mb-4" />
              <h2 className="text-lg font-medium text-gray-900 mb-2">
                Ask anything about your data
              </h2>
              <p className="text-sm text-gray-500 mb-8">
                Natural language to SQL, powered by AI
              </p>
              <div className="max-w-md mx-auto">
                <ExampleQueries onExampleClick={handleExampleQuery} compact />
              </div>
            </div>
          ) : (
            <div className="space-y-8">
              {messages.map((message, index) => (
                <ChatMessageV5
                  key={message.id}
                  message={message}
                  index={index}
                />
              ))}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input - Clean and minimal */}
      <div className="flex-shrink-0 border-t border-gray-100 bg-gray-50/50">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto px-6 py-4">
          <div className="flex gap-3">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={useAgent ? "Ask me anything..." : "Enter your query..."}
              className={cn(
                "flex-1 min-h-[44px] max-h-[120px] resize-none",
                "border-gray-200 focus:border-gray-300",
                "placeholder:text-gray-400",
                "text-sm"
              )}
              disabled={isSubmitting}
            />
            <Button
              type="submit"
              size="default"
              disabled={!input.trim() || isSubmitting}
              className={cn(
                "px-4 h-[44px]",
                "bg-gray-900 hover:bg-gray-800",
                "disabled:bg-gray-100"
              )}
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
