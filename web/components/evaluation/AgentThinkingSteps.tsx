/**
 * Agent Thinking Steps Component
 *
 * Displays real-time agent reasoning steps during BIRD-CRITIC evaluation,
 * similar to the chat interface but optimized for evaluation tasks.
 *
 * Refined with Jony Ive-inspired design principles:
 * - Clean visual hierarchy for reasoning steps
 * - Elegant use of color and typography
 * - Thoughtful spacing and material design
 */

"use client";

import React, { useEffect, useRef } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AgentEvent, TaskResult } from "@/hooks/useBirdCriticEvaluation";

interface AgentThinkingStepsProps {
  events: AgentEvent[];
  currentTask: TaskResult | null;
  isRunning: boolean;
}

interface ProcessedStep {
  id: string;
  type: "thinking" | "action" | "observation" | "sql" | "answer";
  title: string;
  content: string;
  timestamp: Date;
  success?: boolean;
  metadata?: Record<string, any>;
}

export function AgentThinkingSteps({
  events,
  currentTask,
  isRunning,
}: AgentThinkingStepsProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Process raw events into structured steps
  const processedSteps: ProcessedStep[] = events.map((event, index) => {
    const timestamp = event.timestamp ? new Date(event.timestamp) : new Date();
    const stepId = `${event.type}-${index}`;

    switch (event.type) {
      case "reasoning":
      case "thought":
        return {
          id: stepId,
          type: "thinking",
          title: `Reasoning Step ${event.data?.iteration || index + 1}`,
          content:
            event.data?.content ||
            event.data?.reasoning ||
            "Agent is thinking...",
          timestamp,
          metadata: { iteration: event.data?.iteration },
        };

      case "action":
        return {
          id: stepId,
          type: "action",
          title: `Action: ${event.data?.action_type || "Unknown"}`,
          content:
            event.data?.reasoning ||
            event.data?.content ||
            "Executing action...",
          timestamp,
          metadata: {
            action_type: event.data?.action_type,
            parameters: event.data?.parameters,
          },
        };

      case "observation":
        return {
          id: stepId,
          type: "observation",
          title: event.data?.success ? "Success" : "Failed",
          content:
            event.data?.error || event.data?.content || "Action completed",
          timestamp,
          success: event.data?.success,
          metadata: event.data,
        };

      case "sql_generated":
        return {
          id: stepId,
          type: "sql",
          title: "SQL Generated",
          content: event.data?.sql || "SQL query generated",
          timestamp,
          success: true,
        };

      case "answer_generated":
        return {
          id: stepId,
          type: "answer",
          title: "Answer Provided",
          content:
            event.data?.answer || event.data?.content || "Answer generated",
          timestamp,
          success: true,
        };

      default:
        return {
          id: stepId,
          type: "thinking",
          title: `Event: ${event.type}`,
          content: JSON.stringify(event.data, null, 2),
          timestamp,
        };
    }
  });

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  const getStepConfig = (step: ProcessedStep) => {
    switch (step.type) {
      case "thinking":
        return {
          icon: "💭",
          color:
            "from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950",
          border: "border-blue-100 dark:border-blue-800",
          text: "text-blue-700 dark:text-blue-300",
          badge:
            "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
        };
      case "action":
        return {
          icon: "⚡",
          color:
            "from-purple-50 to-violet-50 dark:from-purple-950 dark:to-violet-950",
          border: "border-purple-100 dark:border-purple-800",
          text: "text-purple-700 dark:text-purple-300",
          badge:
            "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
        };
      case "observation":
        if (step.success === false) {
          return {
            icon: "⚠️",
            color: "from-red-50 to-rose-50 dark:from-red-950 dark:to-rose-950",
            border: "border-red-100 dark:border-red-800",
            text: "text-red-700 dark:text-red-300",
            badge: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
          };
        }
        return {
          icon: "✅",
          color:
            "from-emerald-50 to-teal-50 dark:from-emerald-950 dark:to-teal-950",
          border: "border-emerald-100 dark:border-emerald-800",
          text: "text-emerald-700 dark:text-emerald-300",
          badge:
            "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
        };
      case "sql":
        return {
          icon: "📝",
          color:
            "from-amber-50 to-yellow-50 dark:from-amber-950 dark:to-yellow-950",
          border: "border-amber-100 dark:border-amber-800",
          text: "text-amber-700 dark:text-amber-300",
          badge:
            "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
        };
      case "answer":
        return {
          icon: "🎯",
          color:
            "from-emerald-50 to-green-50 dark:from-emerald-950 dark:to-green-950",
          border: "border-emerald-100 dark:border-emerald-800",
          text: "text-emerald-700 dark:text-emerald-300",
          badge:
            "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
        };
      default:
        return {
          icon: "📋",
          color:
            "from-gray-50 to-slate-50 dark:from-gray-950 dark:to-slate-950",
          border: "border-gray-100 dark:border-gray-800",
          text: "text-gray-700 dark:text-gray-300",
          badge:
            "bg-gray-100 text-gray-700 dark:bg-gray-900 dark:text-gray-300",
        };
    }
  };

  if (!currentTask && events.length === 0) {
    return (
      <div className="text-center py-16 px-6">
        <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950 flex items-center justify-center border border-blue-100 dark:border-blue-800">
          <span className="text-2xl">🤖</span>
        </div>
        <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
          Ready for Agent Insights
        </h3>
        <p className="text-gray-600 dark:text-gray-400 max-w-md mx-auto leading-relaxed">
          Agent thinking steps will appear here during evaluation. Start an
          evaluation to see real-time reasoning and decision-making processes.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Current Task Status */}
      {currentTask && (
        <div className="p-4 rounded-xl bg-gradient-to-r from-blue-50 via-indigo-50 to-purple-50 dark:from-blue-950 dark:via-indigo-950 dark:to-purple-950 border border-blue-100 dark:border-blue-800">
          <div className="flex items-center gap-3">
            <div
              className={`w-3 h-3 rounded-full ${
                isRunning ? "bg-blue-500 animate-pulse" : "bg-gray-400"
              }`}
            />
            <div className="flex-1">
              <h4 className="font-medium text-blue-900 dark:text-blue-100">
                Task: {currentTask.task_id}
              </h4>
              <p className="text-sm text-blue-700 dark:text-blue-300">
                {isRunning
                  ? "Agent is actively reasoning..."
                  : "Task completed"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Thinking Steps Timeline */}
      <ScrollArea
        className="h-[600px] rounded-xl border border-gray-200 dark:border-gray-700 bg-white/50 dark:bg-gray-900/50 backdrop-blur-sm"
        ref={scrollRef}
      >
        <div className="p-6 space-y-4">
          {processedSteps.map((step, index) => {
            const config = getStepConfig(step);

            return (
              <div key={step.id} className="relative">
                {/* Timeline connector */}
                {index < processedSteps.length - 1 && (
                  <div className="absolute left-6 top-16 w-0.5 h-8 bg-gradient-to-b from-gray-200 to-transparent dark:from-gray-700" />
                )}

                <Card
                  className={`border-0 shadow-sm bg-gradient-to-br ${config.color} backdrop-blur-sm transition-all duration-200 ease-in-out hover:shadow-md`}
                >
                  <CardContent className="p-5">
                    <div className="flex items-start gap-4">
                      {/* Step Icon */}
                      <div className="w-12 h-12 rounded-xl bg-white/60 dark:bg-gray-800/60 flex items-center justify-center text-lg shadow-sm border border-white/20 dark:border-gray-700/20">
                        {config.icon}
                      </div>

                      {/* Step Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-3">
                          <h4 className={`font-medium ${config.text}`}>
                            {step.title}
                          </h4>
                          <Badge
                            variant="outline"
                            className={`text-xs ${config.badge} border-current/20`}
                          >
                            {step.timestamp.toLocaleTimeString()}
                          </Badge>
                          {step.metadata?.action_type && (
                            <Badge
                              variant="secondary"
                              className="text-xs bg-white/60 dark:bg-gray-800/60"
                            >
                              {step.metadata.action_type}
                            </Badge>
                          )}
                        </div>

                        {/* Step Content */}
                        <div className="space-y-3">
                          {step.type === "sql" ? (
                            <div className="bg-white/80 dark:bg-gray-800/80 p-4 rounded-lg border border-white/40 dark:border-gray-700/40">
                              <pre className="text-sm font-mono text-gray-800 dark:text-gray-200 overflow-x-auto">
                                <code>{step.content}</code>
                              </pre>
                            </div>
                          ) : (
                            <p
                              className={`text-sm leading-relaxed ${config.text} whitespace-pre-wrap break-words`}
                            >
                              {step.content}
                            </p>
                          )}

                          {/* Parameters Expansion */}
                          {step.metadata?.parameters && (
                            <details className="group">
                              <summary
                                className={`text-xs ${config.text} opacity-70 cursor-pointer hover:opacity-100 transition-opacity duration-200 ease-in-out select-none`}
                              >
                                <span className="group-open:hidden">
                                  → Show parameters
                                </span>
                                <span className="hidden group-open:inline">
                                  ↓ Hide parameters
                                </span>
                              </summary>
                              <div className="mt-2 bg-white/80 dark:bg-gray-800/80 p-3 rounded-lg border border-white/40 dark:border-gray-700/40">
                                <pre className="text-xs font-mono text-gray-700 dark:text-gray-300 overflow-x-auto">
                                  {JSON.stringify(
                                    step.metadata.parameters,
                                    null,
                                    2
                                  )}
                                </pre>
                              </div>
                            </details>
                          )}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            );
          })}

          {/* Active Processing Indicator */}
          {isRunning && (
            <div className="relative">
              <Card className="border-0 shadow-sm bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950 backdrop-blur-sm">
                <CardContent className="p-5">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-white/60 dark:bg-gray-800/60 flex items-center justify-center shadow-sm border border-white/20 dark:border-gray-700/20">
                      <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                    <div>
                      <h4 className="font-medium text-blue-700 dark:text-blue-300">
                        Processing...
                      </h4>
                      <p className="text-sm text-blue-600 dark:text-blue-400">
                        The agent is working on the current step
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Elegant Step Summary */}
      {processedSteps.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950 border border-blue-100 dark:border-blue-800">
            <div className="text-lg font-light text-blue-600 dark:text-blue-400">
              {processedSteps.length}
            </div>
            <div className="text-xs font-medium text-blue-700 dark:text-blue-300 uppercase tracking-wide">
              Total Steps
            </div>
          </div>
          <div className="p-3 rounded-lg bg-purple-50 dark:bg-purple-950 border border-purple-100 dark:border-purple-800">
            <div className="text-lg font-light text-purple-600 dark:text-purple-400">
              {processedSteps.filter((s) => s.type === "thinking").length}
            </div>
            <div className="text-xs font-medium text-purple-700 dark:text-purple-300 uppercase tracking-wide">
              Thinking
            </div>
          </div>
          <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950 border border-amber-100 dark:border-amber-800">
            <div className="text-lg font-light text-amber-600 dark:text-amber-400">
              {processedSteps.filter((s) => s.type === "action").length}
            </div>
            <div className="text-xs font-medium text-amber-700 dark:text-amber-300 uppercase tracking-wide">
              Actions
            </div>
          </div>
          <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950 border border-emerald-100 dark:border-emerald-800">
            <div className="text-lg font-light text-emerald-600 dark:text-emerald-400">
              {processedSteps.filter((s) => s.type === "sql").length}
            </div>
            <div className="text-xs font-medium text-emerald-700 dark:text-emerald-300 uppercase tracking-wide">
              SQL Generated
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
