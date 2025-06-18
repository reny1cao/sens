"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Code, Database, Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { useAgentStream } from "@/hooks/useAgentStream";
import { QueryResults } from "@/components/results/QueryResults";
import { SQLDisplay } from "@/components/results/SQLDisplay";

interface Message {
  id: string;
  type: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export function StreamingChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    thinking,
    sql,
    data,
    answer,
    isStreaming,
    error,
    startStream,
    reset: resetStream,
  } = useAgentStream();

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking, answer]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isSubmitting || isStreaming) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      type: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsSubmitting(true);

    try {
      await startStream(input.trim());
    } catch (err) {
      console.error("Failed to start stream:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // When streaming completes, add the assistant response to messages
  useEffect(() => {
    if (!isStreaming && answer && messages.length > 0) {
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        type: "assistant",
        content: answer,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      resetStream(); // Clean up stream state
    }
  }, [isStreaming, answer, messages.length, resetStream]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  return (
    <div className="flex flex-col h-full max-w-6xl mx-auto">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "flex gap-4 animate-in fade-in slide-in-from-bottom duration-500",
              message.type === "user" ? "justify-end" : "justify-start"
            )}
          >
            {message.type === "assistant" && (
              <div className="flex-shrink-0">
                <div className="w-8 h-8 rounded-full bg-gray-900 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-white" />
                </div>
              </div>
            )}

            <div
              className={cn(
                "max-w-3xl px-4 py-3 rounded-2xl",
                message.type === "user"
                  ? "bg-gray-900 text-white"
                  : "bg-white border border-gray-200 text-gray-900"
              )}
            >
              <p className="whitespace-pre-wrap leading-relaxed">
                {message.content}
              </p>
            </div>

            {message.type === "user" && (
              <div className="flex-shrink-0">
                <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">
                  <User className="w-4 h-4 text-white" />
                </div>
              </div>
            )}
          </div>
        ))}

        {/* Active Stream Display */}
        {isStreaming && (
          <div className="flex gap-4 justify-start">
            <div className="flex-shrink-0">
              <div className="w-8 h-8 rounded-full bg-gray-900 flex items-center justify-center">
                <Bot className="w-4 h-4 text-white animate-pulse" />
              </div>
            </div>

            <div className="flex-1 space-y-4">
              {/* Thinking Stream */}
              {thinking && (
                <div className="bg-blue-50 border border-blue-200 rounded-2xl overflow-hidden">
                  <div className="px-4 py-2 bg-blue-100 border-b border-blue-200 flex items-center gap-2">
                    <Lightbulb className="w-4 h-4 text-blue-600" />
                    <span className="text-sm font-medium text-blue-800">Agent Thinking</span>
                  </div>
                  <div className="p-4 max-h-60 overflow-y-auto">
                    <pre className="whitespace-pre-wrap text-sm text-blue-800 font-mono">
                      {thinking}
                    </pre>
                  </div>
                </div>
              )}

              {/* SQL Display */}
              {sql && (
                <div className="bg-gray-900 rounded-2xl overflow-hidden">
                  <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 flex items-center gap-2">
                    <Code className="w-4 h-4 text-gray-400" />
                    <span className="text-sm font-medium text-gray-300">Generated SQL</span>
                  </div>
                  <div className="p-4">
                    <SQLDisplay sql={sql} />
                  </div>
                </div>
              )}

              {/* Data Results */}
              {data && (
                <div className="bg-gray-50 border border-gray-200 rounded-2xl overflow-hidden">
                  <div className="px-4 py-2 bg-gray-100 border-b border-gray-200 flex items-center gap-2">
                    <Database className="w-4 h-4 text-gray-600" />
                    <span className="text-sm font-medium text-gray-800">Query Results</span>
                  </div>
                  <div className="p-4">
                    <QueryResults response={data} />
                  </div>
                </div>
              )}

              {/* Final Answer */}
              {answer && (
                <div className="bg-green-50 border border-green-200 rounded-2xl p-4">
                  <p className="text-green-800 leading-relaxed">{answer}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="flex gap-4 justify-start">
            <div className="flex-shrink-0">
              <div className="w-8 h-8 rounded-full bg-red-500 flex items-center justify-center">
                <Bot className="w-4 h-4 text-white" />
              </div>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-2xl p-4">
              <p className="text-red-800">Error: {error}</p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <div className="border-t border-gray-200 p-6">
        <form onSubmit={handleSubmit} className="flex gap-4">
          <div className="flex-1 relative">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything about your data..."
              className="min-h-[60px] max-h-[200px] resize-none pr-12"
              disabled={isSubmitting || isStreaming}
            />
          </div>
          <Button
            type="submit"
            size="lg"
            disabled={!input.trim() || isSubmitting || isStreaming}
            className="px-6"
          >
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </div>
    </div>
  );
}
