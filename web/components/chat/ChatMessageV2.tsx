"use client";

import { useState, useEffect, useRef } from "react";
import {
  Bot,
  User,
  Code,
  Database,
  AlertCircle,
  ChevronDown,
  Loader2,
  CheckCircle,
  Brain,
  Search,
  Lightbulb,
} from "lucide-react";
import * as Avatar from "@radix-ui/react-avatar";
import * as Collapsible from "@radix-ui/react-collapsible";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { format } from "date-fns";
import { QueryResults } from "@/components/results/QueryResults";
import { SQLDisplay } from "@/components/results/SQLDisplay";

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

interface MessageProps {
  message: Message;
  index: number;
}

export function ChatMessageV2({ message, index }: MessageProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const isUser = message.role === "user";
  const isThinking = message.metadata?.type === "thinking";
  const isStreaming = message.metadata?.isStreaming;
  const hasSteps = isThinking && message.metadata?.steps && message.metadata.steps.length > 0;

  // Auto-expand while streaming
  useEffect(() => {
    if (isStreaming) {
      setIsExpanded(true);
    }
  }, [isStreaming]);

  // Auto-scroll steps while streaming
  useEffect(() => {
    if (isStreaming && isExpanded && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [isStreaming, isExpanded, message.metadata?.steps]);

  // Render user message
  if (isUser) {
    return (
      <div
        className="flex gap-4 animate-in fade-in slide-in-from-bottom duration-500"
        style={{ animationDelay: `${index * 50}ms` }}
      >
        <div className="flex-1" />
        <div className="max-w-3xl">
          <div className="px-5 py-4 rounded-2xl bg-gray-900 text-white shadow-sm">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">
              {message.content}
            </p>
          </div>
          <div className="mt-1 text-xs text-gray-400 text-right">
            {format(message.timestamp, "HH:mm")}
          </div>
        </div>
        <Avatar.Root className="flex-shrink-0 w-8 h-8">
          <Avatar.Fallback className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center">
            <User className="w-4 h-4 text-white" />
          </Avatar.Fallback>
        </Avatar.Root>
      </div>
    );
  }

  // Render assistant message
  return (
    <div
      className="flex gap-4 animate-in fade-in slide-in-from-bottom duration-500"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <Avatar.Root className="flex-shrink-0 w-8 h-8">
        <Avatar.Fallback className="w-8 h-8 rounded-full bg-gray-900 flex items-center justify-center">
          <Bot className="w-4 h-4 text-white" />
        </Avatar.Fallback>
      </Avatar.Root>

      <div className="flex-1 max-w-3xl space-y-3">
        {/* Thinking steps */}
        {isThinking && hasSteps && (
          <Collapsible.Root open={isExpanded} onOpenChange={setIsExpanded}>
            <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              <Collapsible.Trigger asChild>
                <Button
                  variant="ghost"
                  className="w-full px-5 py-3 flex items-center justify-between hover:bg-gray-50"
                  disabled={isStreaming}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-5 h-5 rounded-full bg-gray-100 flex items-center justify-center">
                      {isStreaming ? (
                        <Loader2 className="w-3 h-3 text-gray-600 animate-spin" />
                      ) : (
                        <Brain className="w-3 h-3 text-gray-600" />
                      )}
                    </div>
                    <span className="text-sm font-medium text-gray-900">
                      {isStreaming ? "Analyzing..." : "Analysis Steps"}
                    </span>
                    <span className="text-xs text-gray-500">
                      {message.metadata.steps.length} steps
                    </span>
                  </div>
                  {!isStreaming && (
                    <ChevronDown
                      className={cn(
                        "w-4 h-4 text-gray-400 transition-transform",
                        isExpanded && "rotate-180"
                      )}
                    />
                  )}
                </Button>
              </Collapsible.Trigger>

              <Collapsible.Content>
                <div
                  ref={scrollRef}
                  className="px-5 pb-4 max-h-64 overflow-y-auto border-t border-gray-100"
                >
                  <div className="space-y-2 pt-3">
                    {message.metadata.steps.map((step) => (
                      <div key={step.id} className="flex gap-3 text-sm">
                        <div className="flex-shrink-0 mt-0.5">
                          {getStepIcon(step)}
                        </div>
                        <div className="flex-1">
                          <span className="text-gray-600 leading-relaxed">
                            {step.content}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </Collapsible.Content>
            </div>
          </Collapsible.Root>
        )}

        {/* Regular content */}
        {!isThinking && message.content && (
          <div className="px-5 py-4 rounded-2xl bg-white border border-gray-200 shadow-sm">
            <p className="text-sm leading-relaxed text-gray-900 whitespace-pre-wrap">
              {message.content}
            </p>
          </div>
        )}

        {/* SQL display */}
        {message.metadata?.sql && (
          <div className="bg-gray-900 rounded-2xl overflow-hidden shadow-sm">
            <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 flex items-center gap-2">
              <Code className="w-4 h-4 text-gray-400" />
              <span className="text-sm font-medium text-gray-300">SQL Query</span>
            </div>
            <div className="p-4">
              <SQLDisplay sql={message.metadata.sql} />
            </div>
          </div>
        )}

        {/* Data display */}
        {message.metadata?.data && (
          <div className="bg-gray-50 rounded-2xl overflow-hidden border border-gray-200 shadow-sm">
            <div className="px-4 py-3 bg-gray-100 border-b border-gray-200 flex items-center gap-2">
              <Database className="w-4 h-4 text-gray-600" />
              <span className="text-sm font-medium text-gray-800">Query Results</span>
            </div>
            <div className="p-4">
              <QueryResults response={message.metadata.data} />
            </div>
          </div>
        )}

        {/* Error display */}
        {message.metadata?.type === "error" && (
          <div className="px-5 py-4 rounded-2xl bg-red-50 border border-red-200">
            <div className="flex gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
              <div>
                <p className="text-sm text-red-800 font-medium">Error</p>
                <p className="text-sm text-red-700 mt-1">
                  {message.metadata.error || message.content}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Timestamp */}
        <div className="text-xs text-gray-400">
          {format(message.timestamp, "HH:mm")}
        </div>
      </div>
    </div>
  );
}

function getStepIcon(step: AgentStep) {
  switch (step.type) {
    case "thought":
      return <Brain className="w-4 h-4 text-purple-500" />;
    case "action":
      return <Search className="w-4 h-4 text-blue-500" />;
    case "observation":
      return <CheckCircle className="w-4 h-4 text-green-500" />;
    case "answer":
      return <Lightbulb className="w-4 h-4 text-amber-500" />;
    default:
      return <div className="w-4 h-4 rounded-full bg-gray-300" />;
  }
}
