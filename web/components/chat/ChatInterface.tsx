"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Sparkles,
  Zap,
  MessageCircle,
  Bot,
  Loader2,
  Minimize2,
  Maximize2,
} from "lucide-react";
import * as Avatar from "@radix-ui/react-avatar";
import * as Separator from "@radix-ui/react-separator";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { ChatMessage } from "./ChatMessage";
import { ExampleQueriesClient as ExampleQueries } from "../query/ExampleQueriesClient";
import { useQuery } from "@/hooks/useQuery";
import { useAgentQuery } from "@/hooks/useAgentQuery";

export enum MessageType {
  USER = "user",
  ASSISTANT = "assistant",
  AGENT_THINKING = "agent_thinking",
  NATURAL_LANGUAGE = "natural_language",
  SQL_QUERY = "sql_query",
  DATA_TABLE = "data_table",
  ERROR = "error",
}

interface Message {
  id: string;
  type: MessageType | "user" | "assistant"; // Support both for backward compatibility
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
}

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [useAgent, setUseAgent] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isCompact, setIsCompact] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Query hooks
  const standardQuery = useQuery();
  const agentQuery = useAgentQuery();

  // Enhanced auto-scroll
  const scrollToBottom = useCallback((immediate = false) => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({
        behavior: immediate ? "auto" : "smooth",
        block: "end",
      });
    }
  }, []);

  // Auto-scroll when messages change
  useEffect(() => {
    const timer = setTimeout(() => scrollToBottom(), 150);
    return () => clearTimeout(timer);
  }, [messages, scrollToBottom]);

  // Auto-scroll when agent steps update (real-time SSE)
  useEffect(() => {
    if (isProcessing && useAgent && agentQuery.steps.length > 0) {
      const timer = setTimeout(() => scrollToBottom(), 250);
      return () => clearTimeout(timer);
    }
  }, [agentQuery.steps, isProcessing, useAgent, scrollToBottom]);

  // Handle query submission
  const handleSubmit = (query: string) => {
    if (!query.trim() || isProcessing) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      type: "user",
      content: query,
      timestamp: new Date(),
      status: "complete" as const,
    };

    const messageId = `assistant-${Date.now()}`;
    const assistantMessage: Message = {
      id: messageId,
      type: useAgent ? MessageType.AGENT_THINKING : "assistant",
      content: useAgent ? "" : "Processing your query...",
      timestamp: new Date(),
      status: "processing" as const,
      metadata: {
        isAgent: useAgent,
        parentId: messageId,
      },
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput("");
    setIsProcessing(true);

    // Execute query
    if (useAgent) {
      agentQuery.executeQuery(query);
    } else {
      standardQuery.executeQuery(query);
    }
  };

  // Monitor agent steps in real-time
  useEffect(() => {
    if (!isProcessing || !useAgent) return;

    const lastMessage = messages[messages.length - 1];
    console.log("[ChatInterface] Monitoring steps:", {
      isProcessing,
      useAgent,
      lastMessage,
      steps: agentQuery.steps,
      stepsLength: agentQuery.steps?.length,
    });

    if (
      !lastMessage ||
      (lastMessage.type !== MessageType.AGENT_THINKING &&
        lastMessage.type !== "assistant") ||
      lastMessage.status !== "processing"
    )
      return;

    // Update message with current steps (real-time)
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === lastMessage.id
          ? {
              ...msg,
              metadata: {
                ...msg.metadata,
                steps: agentQuery.steps,
              },
            }
          : msg
      )
    );
  }, [agentQuery.steps, isProcessing, useAgent]);

  // Monitor query completion
  useEffect(() => {
    if (!isProcessing) return;

    // Use functional state update to get the latest messages without dependency
    setMessages((currentMessages) => {
      const lastMessage = currentMessages[currentMessages.length - 1];

      console.log("[ChatInterface] Completion check:", {
        isProcessing,
        useAgent,
        isLoading: agentQuery.isLoading,
        hasResult: !!agentQuery.result,
        hasError: !!agentQuery.error,
        lastMessage,
        lastMessageType: lastMessage?.type,
        lastMessageStatus: lastMessage?.status,
      });

      if (
        !lastMessage ||
        (lastMessage.type !== MessageType.AGENT_THINKING &&
          lastMessage.type !== "assistant") ||
        lastMessage.status !== "processing"
      ) {
        return currentMessages; // No changes needed
      }

      if (useAgent) {
        if (!agentQuery.isLoading) {
          if (agentQuery.error) {
            return currentMessages.map((msg) =>
              msg.id === lastMessage.id
                ? {
                    ...msg,
                    status: "error" as const,
                    error:
                      typeof agentQuery.error === "string"
                        ? agentQuery.error
                        : "Query failed",
                    content: `Sorry, I encountered an error: ${
                      typeof agentQuery.error === "string"
                        ? agentQuery.error
                        : "Failed to process your query"
                    }`,
                    steps: agentQuery.steps,
                  }
                : msg
            );
          } else if (agentQuery.result) {
            console.log(
              "[ChatInterface] Agent query result:",
              agentQuery.result
            );
            console.log(
              "[ChatInterface] Agent answer:",
              agentQuery.result?.answer
            );
            console.log(
              "[ChatInterface] Agent summary:",
              agentQuery.result?.summary
            );

            const parentId = lastMessage.id;
            const newMessages: Message[] = [];

            // First, update the existing thinking message
            const updatedMessages = currentMessages.map((msg) =>
              msg.id === lastMessage.id
                ? {
                    ...msg,
                    status: "complete" as const,
                    metadata: {
                      ...msg.metadata,
                      steps: agentQuery.steps,
                      isCollapsible: true,
                      defaultCollapsed: false,
                    },
                  }
                : msg
            );

            // Extract answer from agent steps or result
            const answerStep = agentQuery.steps.find(step => step.type === 'answer');
            const answerContent = answerStep?.content ||
                                agentQuery.result?.answer ||
                                agentQuery.result?.summary;

            // Add natural language answer as separate message
            if (answerContent) {
              newMessages.push({
                id: `${parentId}-answer`,
                type: MessageType.NATURAL_LANGUAGE,
                content: answerContent,
                timestamp: new Date(),
                status: "complete" as const,
                metadata: {
                  parentId,
                },
              });
            }

            // Add SQL query if exists
            if (agentQuery.result?.sql) {
              newMessages.push({
                id: `${parentId}-sql`,
                type: MessageType.SQL_QUERY,
                content: agentQuery.result.sql,
                timestamp: new Date(),
                status: "complete" as const,
                metadata: {
                  parentId,
                  isCollapsible: true,
                  defaultCollapsed: false,
                },
              });
            }

            // Add data table if exists and has data
            if (
              agentQuery.result?.results &&
              agentQuery.result.results.data &&
              agentQuery.result.results.data.length > 0
            ) {
              newMessages.push({
                id: `${parentId}-data`,
                type: MessageType.DATA_TABLE,
                content: agentQuery.result,
                timestamp: new Date(),
                status: "complete" as const,
                metadata: {
                  parentId,
                  data: agentQuery.result,
                },
              });
            }

            console.log("[ChatInterface] Adding new messages:", newMessages);
            console.log(
              "[ChatInterface] New message types:",
              newMessages.map((m) => ({
                id: m.id,
                type: m.type,
                content: m.content?.substring(0, 50),
              }))
            );
            const finalMessages = [...updatedMessages, ...newMessages];
            console.log(
              "[ChatInterface] Total messages after update:",
              finalMessages.length
            );
            console.log(
              "[ChatInterface] All message types:",
              finalMessages.map((m) => ({ id: m.id, type: m.type }))
            );

            // Set processing to false and reset agent query after state update
            setTimeout(() => {
              setIsProcessing(false);
              agentQuery.reset();
            }, 0);

            return finalMessages;
          }
        }
      } else {
        if (!standardQuery.isLoading) {
          if (standardQuery.error) {
            setTimeout(() => {
              setIsProcessing(false);
              standardQuery.reset();
            }, 0);

            return currentMessages.map((msg) =>
              msg.id === lastMessage.id
                ? {
                    ...msg,
                    status: "error" as const,
                    error:
                      standardQuery.error instanceof Error
                        ? standardQuery.error.message
                        : String(standardQuery.error),
                    content:
                      "Sorry, I encountered an error processing your query.",
                  }
                : msg
            );
          } else if (standardQuery.data) {
            setTimeout(() => {
              setIsProcessing(false);
              standardQuery.reset();
            }, 0);

            return currentMessages.map((msg) =>
              msg.id === lastMessage.id
                ? {
                    ...msg,
                    status: "complete" as const,
                    data: standardQuery.data,
                    sql: standardQuery.data?.sql,
                    content: "Here are the results of your query:",
                  }
                : msg
            );
          }
        }
      }

      return currentMessages; // No changes
    });
  }, [
    isProcessing,
    useAgent,
    agentQuery.isLoading,
    agentQuery.error,
    agentQuery.result,
    standardQuery.isLoading,
    standardQuery.error,
    standardQuery.data,
    agentQuery,
    standardQuery,
  ]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(input);
    }
  };

  const handleExampleClick = (exampleQuery: string) => {
    setInput(exampleQuery);
    inputRef.current?.focus();
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-w-6xl mx-auto relative px-6">
      {/* Minimal Header */}
      <div className="relative mb-8 animate-in fade-in slide-in-from-top duration-700">
        <div className="bg-white/60 backdrop-blur-2xl border border-gray-200/30 rounded-3xl shadow-lg shadow-gray-900/5 p-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-5">
              <Avatar.Root className="relative h-11 w-11">
                <Avatar.Fallback className="h-full w-full rounded-full bg-gray-900 flex items-center justify-center shadow-sm">
                  <Bot className="h-5 w-5 text-white" />
                </Avatar.Fallback>
              </Avatar.Root>

              <div>
                <h2 className="text-lg font-semibold text-gray-900 tracking-tight">
                  Assistant
                </h2>
                <p className="text-sm text-gray-500 font-medium">
                  Natural language to insights
                </p>
              </div>
            </div>

            <div className="flex items-center gap-6">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-3">
                  <Switch
                    id="agent-mode"
                    checked={useAgent}
                    onCheckedChange={setUseAgent}
                    disabled={isProcessing}
                    className="data-[state=checked]:bg-gray-900"
                  />
                  <Label
                    htmlFor="agent-mode"
                    className="cursor-pointer text-sm font-medium text-gray-700"
                  >
                    {useAgent ? "Advanced" : "Standard"}
                  </Label>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Messages Container */}
      <div className="flex-1 relative mb-8 overflow-hidden animate-in fade-in slide-in-from-bottom duration-700 delay-200">
        <div className="absolute inset-0 bg-white/40 backdrop-blur-2xl rounded-3xl border border-gray-200/40 shadow-lg shadow-gray-900/5">
          <div className="h-full overflow-hidden rounded-3xl">
            <div className="h-full overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300/30 scrollbar-track-transparent p-10">
              {messages.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center max-w-2xl animate-in fade-in slide-in-from-bottom duration-1000">
                    <div className="mb-12">
                      <div className="relative inline-block">
                        <div className="w-16 h-16 bg-gray-100 rounded-2xl flex items-center justify-center shadow-sm">
                          <Bot className="h-7 w-7 text-gray-400" />
                        </div>
                      </div>
                    </div>

                    <h3 className="text-2xl font-semibold mb-3 text-gray-900 tracking-tight">
                      How can I help you today?
                    </h3>

                    <p className="text-gray-500 text-base mb-12 leading-relaxed font-medium">
                      Ask me anything about your data and I'll provide clear,
                      accurate insights.
                    </p>

                    <ExampleQueries onExampleClick={handleExampleClick} />
                  </div>
                </div>
              ) : (
                <div className="space-y-8">
                  {messages.map((message, index) => (
                    <ChatMessage
                      key={message.id}
                      message={message}
                      isProcessing={
                        isProcessing && message.status === "processing"
                      }
                      index={index}
                    />
                  ))}

                  {/* Thinking Indicator - Only show for non-agent mode */}
                  {isProcessing && !useAgent && (
                    <div className="flex items-center gap-4 animate-in fade-in slide-in-from-bottom duration-500">
                      <Avatar.Root className="h-9 w-9 aspect-square">
                        <Avatar.Fallback className="h-9 w-9 rounded-full bg-gray-900 text-white flex items-center justify-center">
                          <Loader2 className="h-4 w-4 animate-spin" />
                        </Avatar.Fallback>
                      </Avatar.Root>

                      <div className="flex items-center gap-2 bg-white/60 backdrop-blur-sm rounded-2xl px-4 py-2 border border-gray-200/50">
                        {[0, 1, 2].map((i) => (
                          <div
                            key={i}
                            className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                            style={{ animationDelay: `${i * 200}ms` }}
                          />
                        ))}
                        <span className="text-sm text-gray-600 ml-2 font-medium">
                          Processing...
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )}
              <div ref={messagesEndRef} className="h-4" />
            </div>
          </div>
        </div>
      </div>

      {/* Input Area */}
      <div className="relative animate-in fade-in slide-in-from-bottom duration-700 delay-400">
        <div className="bg-white/60 backdrop-blur-2xl border border-gray-200/40 rounded-3xl shadow-lg shadow-gray-900/5 overflow-hidden transition-all duration-300">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit(input);
            }}
            className="p-8"
          >
            <div className="flex gap-4">
              <div className="flex-1 relative">
                <Textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    isProcessing ? "Processing..." : "Ask me anything..."
                  }
                  className={cn(
                    "min-h-[60px] border-0 bg-gray-50/50 rounded-2xl resize-none text-base",
                    "placeholder:text-gray-400 focus:ring-2 focus:ring-gray-900/10 focus:bg-white",
                    "transition-all duration-300 pr-16 font-medium",
                    isProcessing && "bg-gray-100/50 text-gray-500"
                  )}
                  disabled={isProcessing}
                />

                {!isProcessing && input.trim() && (
                  <div className="absolute right-4 top-4 text-xs text-gray-400 bg-white/80 px-2 py-1 rounded-lg backdrop-blur-sm animate-in fade-in duration-200 font-medium">
                    ⏎ Send
                  </div>
                )}
              </div>

              <Button
                type="submit"
                size="lg"
                disabled={!input.trim() || isProcessing}
                className={cn(
                  "h-[60px] px-6 bg-gray-900 hover:bg-gray-800 disabled:bg-gray-200",
                  "shadow-sm disabled:shadow-none transition-all duration-300 rounded-2xl",
                  "text-white disabled:text-gray-400",
                  input.trim() && !isProcessing && "hover:scale-[1.02]",
                  isProcessing && "scale-[0.98]"
                )}
              >
                <div
                  className={cn(
                    "transition-transform duration-300",
                    isProcessing && "animate-spin"
                  )}
                >
                  {isProcessing ? (
                    <Loader2 className="h-4 w-4" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </div>
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
