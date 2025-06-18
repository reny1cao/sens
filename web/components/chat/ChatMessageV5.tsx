"use client";

import { useState, useEffect } from "react";
import {
  Bot,
  User,
  Database,
  AlertCircle,
  ChevronDown,
  Loader2,
  Brain,
  Search,
  CheckCircle,
  Lightbulb,
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
                      <Brain className="w-3.5 h-3.5 text-gray-500" />
                      <span className="text-sm text-gray-700">View analysis steps</span>
                      <span className="text-xs text-gray-400">({message.steps.length})</span>
                    </>
                  )}
                </div>
                {!isStreaming && (
                  <ChevronDown
                    className={cn(
                      "w-3.5 h-3.5 text-gray-400 transition-transform duration-200",
                      isExpanded && "rotate-180"
                    )}
                  />
                )}
              </Button>
            </Collapsible.Trigger>

            <Collapsible.Content className="mt-2">
              <div className="bg-gray-50 rounded-lg p-3 space-y-2">
                {message.steps.map((step) => (
                  <div key={step.id} className="text-xs">
                    <div className="flex items-start gap-2">
                      <div className="mt-0.5">{getStepIcon(step)}</div>
                      <div className="flex-1">
                        <span className="text-gray-600 leading-relaxed">
                          {formatStepContent(step)}
                        </span>
                        {/* Show SQL for action steps */}
                        {step.type === "action" && (step.metadata?.sql || step.metadata?.parameters?.query) && (
                          <div className="mt-1 bg-gray-900 text-gray-100 rounded p-2 font-mono text-xs overflow-x-auto">
                            <code>{step.metadata.sql || step.metadata.parameters.query}</code>
                          </div>
                        )}
                      </div>
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
  const iconClass = "w-3.5 h-3.5";
  switch (step.type) {
    case "thought":
      return <Brain className={cn(iconClass, "text-purple-500")} />;
    case "action":
      return <Search className={cn(iconClass, "text-blue-500")} />;
    case "observation":
      return <CheckCircle className={cn(iconClass, "text-green-500")} />;
    case "answer":
      return <Lightbulb className={cn(iconClass, "text-amber-500")} />;
    default:
      return <div className="w-3.5 h-3.5 rounded-full bg-gray-300" />;
  }
}

function formatStepContent(step: AgentStep): string {
  // The backend now sends user-friendly messages, so just return them
  // Truncate if too long for the collapsed view
  return step.content.length > 150
    ? step.content.substring(0, 150) + "..."
    : step.content;
}
