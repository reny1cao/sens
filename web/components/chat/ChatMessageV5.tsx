"use client";

import { useState, useEffect } from "react";
import {
  Bot,
  User,
  Database,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Loader2,
  Sparkles,
  Zap,
  CheckCircle2,
  MessageSquare,
  Code,
} from "lucide-react";
import * as Avatar from "@radix-ui/react-avatar";
import * as Collapsible from "@radix-ui/react-collapsible";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { format } from "date-fns";
import { QueryResults } from "@/components/results/QueryResults";

interface AgentStep {
  id: string;
  type: "thought" | "action" | "observation" | "answer";
  content: string;
  iteration: number;
  timestamp: number;
  metadata?: any;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  status?: "streaming" | "complete" | "error";
  answer?: string;
  steps?: AgentStep[];
  data?: any;
  error?: string;
}

interface ChatMessageV5Props {
  message: Message;
  index: number;
}

export function ChatMessageV5({ message, index }: ChatMessageV5Props) {
  const [isExpanded, setIsExpanded] = useState(false);

  const isUser = message.role === "user";
  const isStreaming = message.status === "streaming";
  const hasSteps = message.steps && message.steps.length > 0;
  const hasData = message.data?.results?.data?.length > 0;

  // Auto-expand while streaming
  useEffect(() => {
    if (isStreaming) {
      setIsExpanded(true);
    }
  }, [isStreaming]);

  if (isUser) {
    return (
      <div
        className="flex gap-4 animate-in fade-in slide-in-from-bottom duration-300"
        style={{ animationDelay: `${index * 50}ms` }}
      >
        <Avatar.Root className="flex-shrink-0 w-9 h-9">
          <Avatar.Fallback className="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center">
            <User className="w-4 h-4 text-gray-600" />
          </Avatar.Fallback>
        </Avatar.Root>

        <div className="flex-1 pt-0.5">
          <div className="text-sm font-medium text-gray-900 mb-1">You</div>
          <div className="text-sm leading-relaxed text-gray-700">
            {message.content}
          </div>
          <div className="mt-1 text-xs text-gray-400">
            {format(message.timestamp, "HH:mm")}
          </div>
        </div>
      </div>
    );
  }

  // Assistant message - consolidated view
  return (
    <div
      className="flex gap-4 animate-in fade-in slide-in-from-bottom duration-300"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <Avatar.Root className="flex-shrink-0 w-9 h-9">
        <Avatar.Fallback className="w-9 h-9 rounded-full bg-gray-900 flex items-center justify-center">
          <Bot className="w-4 h-4 text-white" />
        </Avatar.Fallback>
      </Avatar.Root>

      <div className="flex-1 pt-0.5 space-y-3">
        <div className="text-sm font-medium text-gray-900">Assistant</div>

        {/* Analysis steps (collapsible) */}
        {hasSteps && (
          <Collapsible.Root open={isExpanded} onOpenChange={setIsExpanded}>
            <Collapsible.Trigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-between px-3 py-2 h-auto hover:bg-gray-50 transition-colors"
                disabled={isStreaming}
              >
                <div className="flex items-center gap-2">
                  {isStreaming ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-500" />
                      <span className="text-sm text-gray-700">Analyzing...</span>
                    </>
                  ) : (
                    <>
                      <div className="w-4 h-4 rounded-full bg-gray-100 flex items-center justify-center">
                        <Sparkles className="w-2.5 h-2.5 text-gray-600" />
                      </div>
                      <span className="text-sm text-gray-700">View analysis steps</span>
                      <span className="text-xs text-gray-400">({message.steps.length})</span>
                    </>
                  )}
                </div>
                {!isStreaming && (
                  <ChevronRight
                    className={cn(
                      "w-3.5 h-3.5 text-gray-400 transition-transform duration-200",
                      isExpanded && "rotate-90"
                    )}
                  />
                )}
              </Button>
            </Collapsible.Trigger>

            <Collapsible.Content className="mt-2">
              <div className="bg-gray-50/50 rounded-lg p-4 space-y-4">
                <div className="text-[10px] text-gray-500 font-medium uppercase tracking-widest mb-3">
                  Analysis Steps
                </div>
                {message.steps.map((step) => (
                  <div key={step.id} className="flex gap-3">
                    {getStepIcon(step)}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-gray-700 leading-relaxed">
                        {step.content}
                      </div>
                      {/* Show SQL for action steps */}
                      {step.type === "action" && (step.metadata?.sql || step.metadata?.parameters?.query) && (
                        <div className="mt-2 bg-white border border-gray-200 rounded-lg p-3 font-mono text-[11px] text-gray-700 overflow-x-auto">
                          <code className="whitespace-pre">{step.metadata.sql || step.metadata.parameters.query}</code>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </Collapsible.Content>
          </Collapsible.Root>
        )}

        {/* Answer */}
        {message.answer && (
          <div className="text-sm leading-relaxed text-gray-700">
            {message.answer}
          </div>
        )}

        {/* Data results */}
        {hasData && (
          <div className="mt-3">
            <QueryResults response={message.data} />
          </div>
        )}

        {/* Error */}
        {message.error && (
          <div className="flex items-start gap-2 text-sm text-red-600 bg-red-50 rounded-lg p-3">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{message.error}</span>
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
  const iconClass = "w-3 h-3";
  switch (step.type) {
    case "thought":
      return (
        <div className="w-5 h-5 rounded-full bg-gradient-to-br from-purple-50 to-purple-100 flex items-center justify-center">
          <Sparkles className={cn(iconClass, "text-purple-600")} />
        </div>
      );
    case "action":
      return (
        <div className="w-5 h-5 rounded-full bg-gradient-to-br from-blue-50 to-blue-100 flex items-center justify-center">
          <Zap className={cn(iconClass, "text-blue-600")} />
        </div>
      );
    case "observation":
      return (
        <div className="w-5 h-5 rounded-full bg-gradient-to-br from-green-50 to-green-100 flex items-center justify-center">
          <CheckCircle2 className={cn(iconClass, "text-green-600")} />
        </div>
      );
    case "answer":
      return (
        <div className="w-5 h-5 rounded-full bg-gradient-to-br from-amber-50 to-amber-100 flex items-center justify-center">
          <MessageSquare className={cn(iconClass, "text-amber-600")} />
        </div>
      );
    default:
      return <div className="w-5 h-5 rounded-full bg-gray-100" />;
  }
}
