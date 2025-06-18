"use client";

import {
  User,
  Bot,
  Loader2,
  AlertCircle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Code,
  Database,
  Zap,
} from "lucide-react";
import * as Avatar from "@radix-ui/react-avatar";
import * as Collapsible from "@radix-ui/react-collapsible";
import * as Separator from "@radix-ui/react-separator";
import { cn } from "@/lib/utils";
import { QueryResults } from "../results/QueryResults";
import { AgentProcessingSteps } from "../query/AgentProcessingSteps";
import { SQLDisplay } from "../results/SQLDisplay";
import { format } from "date-fns";
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { MessageType } from "./ChatInterface";

interface MessageProps {
  message: {
    id: string;
    type: MessageType | "user" | "assistant";
    content: any;
    timestamp: Date;
    status?: "sending" | "processing" | "complete" | "error";
    metadata?: {
      parentId?: string;
      isCollapsible?: boolean;
      defaultCollapsed?: boolean;
      isAgent?: boolean;
      steps?: any[];
      data?: any;
      error?: string;
      sql?: string;
    };
    // Legacy support
    data?: any;
    error?: string;
    sql?: string;
    isAgent?: boolean;
    steps?: any[];
  };
  isProcessing?: boolean;
  index?: number;
}

const messageVariants = {
  hidden: {
    opacity: 0,
    y: 50,
    scale: 0.95,
  },
  visible: (index: number) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      type: "spring",
      damping: 25,
      stiffness: 300,
      delay: index * 0.1,
    },
  }),
  exit: {
    opacity: 0,
    y: -20,
    scale: 0.95,
    transition: { duration: 0.2 },
  },
};

export function ChatMessage({
  message,
  isProcessing,
  index = 0,
}: MessageProps) {
  const isUser = message.type === "user";

  // Use metadata for collapsible behavior, with fallback to always open
  const isCollapsible = message.metadata?.isCollapsible ?? false;
  const defaultCollapsed = message.metadata?.defaultCollapsed ?? false;
  const [isStepsOpen, setIsStepsOpen] = useState(!defaultCollapsed);

  // Support both new metadata structure and legacy fields
  const isAgent = message.metadata?.isAgent || message.isAgent;
  const steps = message.metadata?.steps || message.steps;
  const data = message.metadata?.data || message.data;
  const error = message.metadata?.error || message.error;
  const sql = message.metadata?.sql || message.sql;

  const hasSteps = !isUser && isAgent && steps && steps.length > 0;
  const isAgentWorking = isProcessing && message.status === "processing";

  // Handle different message types
  const isAgentThinking = message.type === MessageType.AGENT_THINKING;
  const isNaturalLanguage = message.type === MessageType.NATURAL_LANGUAGE;
  const isSqlQuery = message.type === MessageType.SQL_QUERY;
  const isDataTable = message.type === MessageType.DATA_TABLE;

  // Debug logging
  console.log("[ChatMessage] Rendering:", {
    id: message.id,
    type: message.type,
    isNaturalLanguage,
    isSqlQuery,
    isDataTable,
    isAgentThinking,
    content: message.content?.substring?.(0, 50),
  });

  // Debug logging for agent results
  if (data && isAgent) {
    console.log("[ChatMessage] Agent result data:", {
      messageType: message.type,
      hasData: !!data,
      dataKeys: Object.keys(data || {}),
      sql: sql,
      dataStructure: data,
    });
  }

  // Auto-collapse steps when processing is complete (only for collapsible messages)
  useEffect(() => {
    if (
      isAgentThinking &&
      hasSteps &&
      !isAgentWorking &&
      message.status === "complete" &&
      isCollapsible
    ) {
      const timer = setTimeout(() => {
        setIsStepsOpen(false);
      }, 5000); // Give user more time to read
      return () => clearTimeout(timer);
    }
  }, [
    isAgentThinking,
    hasSteps,
    isAgentWorking,
    message.status,
    isCollapsible,
  ]);

  // Keep steps expanded while agent is working
  useEffect(() => {
    if (isAgentWorking) {
      setIsStepsOpen(true);
    }
  }, [isAgentWorking]);

  // Special rendering for different message types
  if (isNaturalLanguage) {
    return (
      <div
        className="flex gap-5 animate-in fade-in slide-in-from-bottom duration-500 justify-start"
        style={{ animationDelay: `${index * 100}ms` }}
      >
        <div className="flex-shrink-0">
          <Avatar.Root className="relative h-9 w-9 aspect-square">
            <Avatar.Fallback className="h-9 w-9 rounded-full bg-gray-900 flex items-center justify-center shadow-sm">
              <Bot className="h-4 w-4 text-white" />
            </Avatar.Fallback>
          </Avatar.Root>
        </div>
        <div className="flex flex-col gap-2 max-w-4xl">
          <div className="relative px-6 py-5 rounded-2xl shadow-md backdrop-blur-sm bg-white border border-gray-200/60">
            <p className="text-base leading-relaxed whitespace-pre-wrap font-medium text-gray-900">
              {message.content}
            </p>
          </div>
          <div className="text-xs text-gray-400 px-1 font-medium">
            {format(message.timestamp, "HH:mm")}
          </div>
        </div>
      </div>
    );
  }

  if (isSqlQuery) {
    return (
      <div
        className="flex gap-5 animate-in fade-in slide-in-from-bottom duration-500 justify-start"
        style={{ animationDelay: `${index * 100}ms` }}
      >
        <div className="flex-shrink-0 w-9" />
        <div className="flex flex-col gap-2 max-w-4xl w-full">
          <div className="bg-gray-900/95 backdrop-blur-sm rounded-2xl border border-gray-700/50 shadow-sm overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 bg-gray-800/50 border-b border-gray-700/50">
              <Code className="h-4 w-4 text-gray-400" />
              <span className="text-sm font-medium text-gray-300">
                SQL Query
              </span>
            </div>
            <div className="p-5">
              <SQLDisplay sql={message.content} />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (isDataTable) {
    return (
      <div
        className="flex gap-5 animate-in fade-in slide-in-from-bottom duration-500 justify-start"
        style={{ animationDelay: `${index * 100}ms` }}
      >
        <div className="flex-shrink-0 w-9" />
        <div className="flex flex-col gap-2 max-w-4xl w-full">
          <div className="bg-gray-50/60 backdrop-blur-sm border border-gray-200/50 rounded-2xl overflow-hidden shadow-sm">
            <div className="flex items-center gap-2 px-5 py-4 bg-gray-100/50 border-b border-gray-200/50">
              <Database className="h-4 w-4 text-gray-600" />
              <span className="font-medium text-gray-800">Results</span>
            </div>
            <div className="p-5">
              <QueryResults response={message.content} />
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Default rendering for user, assistant, and agent thinking messages
  return (
    <div
      className={cn(
        "flex gap-5 animate-in fade-in slide-in-from-bottom duration-500",
        isUser ? "justify-end" : "justify-start"
      )}
      style={{ animationDelay: `${index * 100}ms` }}
    >
      {/* Assistant Avatar */}
      {!isUser && (
        <div className="flex-shrink-0">
          <Avatar.Root className="relative h-9 w-9 aspect-square">
            <Avatar.Fallback
              className={cn(
                "h-9 w-9 rounded-full flex items-center justify-center transition-all duration-500 shadow-sm",
                isAgentWorking ? "bg-gray-900 scale-105" : "bg-gray-100"
              )}
            >
              <div
                className={cn(
                  "transition-transform duration-300",
                  isAgentWorking && "animate-spin"
                )}
              >
                {isAgentWorking ? (
                  <Loader2 className="h-4 w-4 text-white" />
                ) : (
                  <Bot className="h-4 w-4 text-gray-600" />
                )}
              </div>
            </Avatar.Fallback>
          </Avatar.Root>
        </div>
      )}

      {/* Message Content */}
      <div
        className={cn("flex flex-col gap-5 max-w-4xl", isUser && "items-end")}
      >
        {/* Message Bubble - Show for all messages with content */}
        {message.content && (
          <div
            className={cn(
              "relative px-5 py-4 rounded-2xl shadow-sm backdrop-blur-sm transition-all duration-200",
              isUser
                ? "bg-gray-900 text-white"
                : "bg-white/60 border border-gray-200/40 text-gray-900"
            )}
          >
            <p className="text-base leading-relaxed whitespace-pre-wrap font-medium">
              {message.content}
            </p>

            {/* Status indicator */}
            {!isUser && message.status && (
              <div className="flex items-center gap-2 mt-4 pt-4 border-t border-gray-200/50 animate-in fade-in slide-in-from-bottom duration-300">
                {message.status === "processing" && (
                  <>
                    <Loader2 className="h-3 w-3 text-gray-500 animate-spin" />
                    <span className="text-sm font-medium text-gray-600">
                      Processing...
                    </span>
                  </>
                )}
                {message.status === "complete" && (
                  <>
                    <CheckCircle className="h-3 w-3 text-green-600" />
                    <span className="text-sm font-medium text-green-700">
                      Complete
                    </span>
                  </>
                )}
                {message.status === "error" && (
                  <>
                    <AlertCircle className="h-3 w-3 text-red-500" />
                    <span className="text-sm font-medium text-red-600">
                      Error occurred
                    </span>
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {/* Agent Analysis - Pure, focused design */}
        {(isAgent || isAgentThinking) && (
          <div className="w-full">
            <Collapsible.Root open={isStepsOpen} onOpenChange={setIsStepsOpen}>
              <div className="bg-white/60 backdrop-blur-xl rounded-3xl border border-gray-200/30 shadow-sm shadow-gray-900/5 overflow-hidden transition-all duration-500">
                <Collapsible.Trigger asChild>
                  <Button
                    variant="ghost"
                    className="w-full justify-between px-6 py-5 h-auto rounded-none hover:bg-white/40 text-left transition-all duration-300"
                    disabled={isAgentWorking || !isCollapsible}
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center">
                        <Database className="h-3 w-3 text-gray-600" />
                      </div>
                      <div>
                        <span className="text-sm font-semibold text-gray-900 tracking-tight">
                          {isAgentWorking
                            ? "Analysis in Progress"
                            : "Reasoning Steps"}
                        </span>
                        {steps && steps.length > 0 && (
                          <div className="text-xs text-gray-500 font-medium mt-0.5">
                            {steps.length} step{steps.length > 1 ? "s" : ""}
                          </div>
                        )}
                      </div>
                    </div>
                    {isCollapsible && !isAgentWorking && (
                      <div
                        className={cn(
                          "transition-transform duration-300 ease-out",
                          isStepsOpen && "rotate-180"
                        )}
                      >
                        <ChevronDown className="h-4 w-4 text-gray-400" />
                      </div>
                    )}
                  </Button>
                </Collapsible.Trigger>

                <Collapsible.Content className="overflow-hidden data-[state=open]:animate-slideDown data-[state=closed]:animate-slideUp">
                  <div className="px-6 pb-6 max-h-[300px] overflow-y-auto scrollbar-thin scrollbar-thumb-gray-200/50 scrollbar-track-transparent">
                    <AgentProcessingSteps
                      steps={steps || []}
                      isLoading={isAgentWorking}
                      compact={false}
                    />
                  </div>
                </Collapsible.Content>
              </div>
            </Collapsible.Root>
          </div>
        )}

        {/* SQL Display - Only for legacy messages */}
        {!isUser && !isSqlQuery && sql && (
          <div className="w-full animate-in fade-in slide-in-from-bottom duration-500">
            <div className="bg-gray-900/95 backdrop-blur-sm rounded-2xl border border-gray-700/50 shadow-sm overflow-hidden">
              <div className="flex items-center gap-2 px-5 py-3 bg-gray-800/50 border-b border-gray-700/50">
                <Code className="h-4 w-4 text-gray-400" />
                <span className="text-sm font-medium text-gray-300">
                  SQL Query
                </span>
              </div>
              <div className="p-5">
                <SQLDisplay sql={sql} />
              </div>
            </div>
          </div>
        )}

        {/* Error Display */}
        {!isUser && error && (
          <div className="w-full animate-in fade-in slide-in-from-bottom duration-500">
            <div className="bg-red-50/60 backdrop-blur-sm border border-red-200/50 rounded-2xl p-6 shadow-sm">
              <div className="flex gap-4">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-red-100 rounded-full flex items-center justify-center">
                    <AlertCircle className="h-4 w-4 text-red-600" />
                  </div>
                </div>
                <div>
                  <h4 className="text-base font-semibold text-red-800 mb-1">
                    Error
                  </h4>
                  <p className="text-sm text-red-700 leading-relaxed font-medium">
                    {error}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Results Display - Only for legacy messages */}
        {!isUser && !isDataTable && data && message.status === "complete" && (
          <div className="w-full animate-in fade-in slide-in-from-bottom duration-500 delay-200">
            <div className="bg-gray-50/60 backdrop-blur-sm border border-gray-200/50 rounded-2xl overflow-hidden shadow-sm">
              <div className="flex items-center gap-2 px-5 py-4 bg-gray-100/50 border-b border-gray-200/50">
                <Database className="h-4 w-4 text-gray-600" />
                <span className="font-medium text-gray-800">Results</span>
              </div>
              <div className="p-5">
                <QueryResults response={data} />
              </div>
            </div>
          </div>
        )}

        {/* Timestamp */}
        <div
          className={cn(
            "text-xs text-gray-400 px-1 animate-in fade-in duration-500 delay-500 font-medium",
            isUser ? "text-right" : "text-left"
          )}
        >
          {format(message.timestamp, "HH:mm")}
        </div>
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="flex-shrink-0">
          <Avatar.Root className="h-9 w-9 aspect-square">
            <Avatar.Fallback className="h-9 w-9 rounded-full bg-gray-700 flex items-center justify-center shadow-sm">
              <User className="h-4 w-4 text-white" />
            </Avatar.Fallback>
          </Avatar.Root>
        </div>
      )}
    </div>
  );
}
