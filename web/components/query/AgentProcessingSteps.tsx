"use client";

import {
  CheckCircle,
  XCircle,
  Loader2,
  Brain,
  Search,
  Database,
  Lightbulb,
  ChevronDown,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AgentStep } from "@/hooks/useAgentQuery";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { useEffect, useRef } from "react";
import {
  animated,
  useSpring,
  useTrail,
  useTransition,
  config,
} from "@react-spring/web";

interface AgentProcessingStepsProps {
  steps: AgentStep[];
  isLoading: boolean;
  compact?: boolean;
}

export function AgentProcessingSteps({
  steps,
  isLoading,
  compact = false,
}: AgentProcessingStepsProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const lastScrollTimeRef = useRef<number>(0);

  // Auto-scroll to bottom when new steps arrive and the agent is loading
  useEffect(() => {
    if (!isLoading || steps.length === 0) return;

    const now = Date.now();
    // Throttle scroll attempts to avoid excessive calls
    if (now - lastScrollTimeRef.current < 50) return;
    lastScrollTimeRef.current = now;

    const scrollToBottom = () => {
      if (scrollAreaRef.current) {
        const viewport = scrollAreaRef.current.querySelector(
          "[data-radix-scroll-area-viewport]"
        ) as HTMLElement;
        if (viewport) {
          viewport.scrollTo({
            top: viewport.scrollHeight,
            behavior: "smooth",
          });
        }
      }
    };

    // Use requestAnimationFrame to ensure DOM has updated
    requestAnimationFrame(() => {
      setTimeout(scrollToBottom, 50);
    });
  }, [steps.length, isLoading]); // Only depend on steps.length, not the entire steps array

  // Container animation
  const containerSpring = useSpring({
    opacity: steps.length > 0 ? 1 : 0,
    transform: steps.length > 0 ? "translateY(0px)" : "translateY(20px)",
    config: config.gentle,
  });

  // Thinking animation
  const thinkingSpring = useSpring({
    opacity: steps.length === 0 && isLoading ? 1 : 0,
    transform: steps.length === 0 && isLoading ? "scale(1)" : "scale(0.9)",
    config: config.wobbly,
  });

  // Steps trail animation for staggered entrance
  const stepTrail = useTrail(steps.length, {
    opacity: 1,
    transform: "translateX(0px) translateY(0px)",
    from: { opacity: 0, transform: "translateX(-20px) translateY(10px)" },
    config: config.gentle,
  });

  // Loading indicator animation
  const loadingSpring = useSpring({
    opacity: isLoading ? 1 : 0,
    transform: isLoading ? "translateY(0px)" : "translateY(10px)",
    config: config.gentle,
  });

  const loadingDotSpring = useSpring({
    transform: isLoading ? "scale(1.1)" : "scale(1)",
    config: config.wobbly,
  });

  const loadingTextSpring = useSpring({
    opacity: isLoading ? 0.8 : 1,
    config: config.gentle,
  });

  // Completion animation
  const completionSpring = useSpring({
    opacity: !isLoading && steps.length > 0 ? 1 : 0,
    transform:
      !isLoading && steps.length > 0 ? "translateY(0px)" : "translateY(10px)",
    config: config.gentle,
    delay: 500,
  });

  const completionDotSpring = useSpring({
    transform: !isLoading && steps.length > 0 ? "scale(1)" : "scale(0)",
    config: config.wobbly,
    delay: 700,
  });

  const completionTextSpring = useSpring({
    opacity: !isLoading && steps.length > 0 ? 1 : 0,
    transform:
      !isLoading && steps.length > 0 ? "translateX(0px)" : "translateX(-10px)",
    config: config.gentle,
    delay: 800,
  });

  const getStepIcon = (step: AgentStep) => {
    if (step.status === "running") {
      return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
    }

    switch (step.type) {
      case "thought":
        return <Brain className="h-5 w-5 text-purple-500" />;
      case "action":
        if (step.metadata?.action_type === "explore_database") {
          return <Database className="h-5 w-5 text-blue-500" />;
        } else if (step.metadata?.action_type === "generate_sql") {
          return <Lightbulb className="h-5 w-5 text-yellow-500" />;
        }
        return <Search className="h-5 w-5 text-green-500" />;
      case "observation":
        return step.status === "error" ? (
          <XCircle className="h-5 w-5 text-red-500" />
        ) : (
          <CheckCircle className="h-5 w-5 text-green-500" />
        );
      case "answer":
        return <Lightbulb className="h-5 w-5 text-green-600" />;
      default:
        return <div className="h-5 w-5 rounded-full border-2 border-muted" />;
    }
  };

  const getStepTitle = (step: AgentStep) => {
    switch (step.type) {
      case "thought":
        return `Iteration ${step.iteration}: Thinking`;
      case "action":
        const actionType = step.metadata?.action_type || "unknown";
        const actionLabels: Record<string, string> = {
          explore_database: "Exploring Database",
          generate_sql: "Generating SQL",
          execute_sql: "Executing Query",
        };
        return `Iteration ${step.iteration}: ${
          actionLabels[actionType] || actionType
        }`;
      case "observation":
        return `Iteration ${step.iteration}: Result`;
      case "answer":
        return `Generating Answer`;
      default:
        return `Iteration ${step.iteration}`;
    }
  };

  const formatContent = (step: AgentStep) => {
    if (step.type === "action" && step.metadata?.parameters?.query) {
      return (
        <div className="space-y-2">
          <p className="text-sm">{step.content}</p>
          <pre className="text-xs bg-muted p-2 rounded overflow-x-auto">
            <code>{step.metadata.parameters.query}</code>
          </pre>
        </div>
      );
    }

    if (step.type === "observation" && step.metadata) {
      const details = [];

      if (step.metadata.row_count !== undefined) {
        details.push(`${step.metadata.row_count} rows`);
      }
      if (step.metadata.columns) {
        details.push(`${step.metadata.columns.length} columns`);
      }
      if (step.metadata.error) {
        details.push(step.metadata.error);
      }

      return (
        <div className="space-y-1">
          <p className="text-sm">{step.content}</p>
          {details.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {details.join(" • ")}
            </p>
          )}
        </div>
      );
    }

    return <p className="text-sm">{step.content}</p>;
  };

  const currentIteration =
    steps.length > 0 ? Math.max(...steps.map((s) => s.iteration)) : 0;

  if (compact) {
    return (
      <div className="space-y-4">
        {steps.length === 0 && isLoading && (
          <div className="flex items-center gap-3 text-sm text-gray-600">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="font-medium">Starting analysis...</span>
          </div>
        )}

        {steps.length > 0 && (
          <div className="space-y-3 max-h-[200px] overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300/30 scrollbar-track-transparent">
            {steps.slice(-3).map((step, index) => (
              <div
                key={step.id}
                className="flex gap-3 animate-in fade-in slide-in-from-left-2 duration-300"
              >
                <div className="flex-shrink-0 pt-0.5">{getStepIcon(step)}</div>
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-medium text-gray-800 mb-1">
                    {getStepTitle(step)}
                  </h4>
                  <div className="text-sm text-gray-600">
                    {formatContent(step)}
                  </div>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex gap-3 opacity-60">
                <div className="flex-shrink-0 pt-0.5">
                  <Loader2 className="h-4 w-4 text-gray-500 animate-spin" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="h-4 bg-gray-200 rounded animate-pulse w-32 mb-1" />
                  <div className="h-3 bg-gray-200 rounded animate-pulse w-48" />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Pure, focused thinking state with smooth spring animation */}
      <animated.div
        style={thinkingSpring}
        className="flex items-center gap-4 py-3"
      >
        {steps.length === 0 && isLoading && (
          <>
            <div className="relative">
              <div className="w-6 h-6 rounded-full bg-gray-900 flex items-center justify-center animate-spin-slow">
                <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
              </div>
              <div className="absolute inset-0 rounded-full border border-gray-300 animate-ping" />
            </div>
            <div className="text-sm font-medium text-gray-700 tracking-tight animate-pulse">
              Thinking...
            </div>
          </>
        )}
      </animated.div>

      {/* Modern reasoning flow with smooth React Spring animations */}
      <animated.div style={containerSpring}>
        {steps.length > 0 && (
          <div className="relative">
            <ScrollArea
              ref={scrollAreaRef}
              className="max-h-[300px] pr-2 scrollbar-thin scrollbar-thumb-gray-300/30 scrollbar-track-transparent"
            >
              <div className="space-y-1 pb-2">
                {stepTrail.map((springStyle, index) => {
                  const step = steps[index];
                  if (!step) return null;

                  return (
                    <animated.div
                      key={step.id}
                      style={springStyle}
                      className="px-3 py-2 hover:bg-gray-50/30 rounded-lg transition-all duration-200 cursor-pointer hover:scale-[1.01]"
                    >
                      <div className="flex items-start gap-3">
                        {/* Status dot with CSS animations */}
                        <div
                          className={cn(
                            "flex-shrink-0 mt-1 w-1.5 h-1.5 rounded-full transition-all duration-300",
                            step.status === "completed" && "bg-gray-400",
                            step.status === "error" && "bg-red-500",
                            step.status === "running" &&
                              "bg-blue-500 animate-pulse scale-125"
                          )}
                        />

                        <div className="flex-1 min-w-0 space-y-0.5">
                          {/* Step type with smooth fade */}
                          <animated.div
                            style={{
                              opacity: springStyle.opacity,
                              transform: "translateX(0px)",
                            }}
                            className="text-xs font-medium text-gray-500 uppercase tracking-wider"
                          >
                            {step.type === "thought" && "Reasoning"}
                            {step.type === "action" && "Action"}
                            {step.type === "observation" && "Result"}
                          </animated.div>

                          {/* Step content with smooth slide */}
                          <animated.div
                            style={{
                              ...springStyle,
                              transform:
                                springStyle.transform + " translateY(0px)",
                            }}
                            className="text-sm text-gray-800 leading-relaxed font-medium break-words"
                          >
                            {formatContent(step)}
                          </animated.div>
                        </div>
                      </div>
                    </animated.div>
                  );
                })}

                {/* Enhanced loading indicator with spring animation */}
                {isLoading && (
                  <animated.div style={loadingSpring} className="px-3 py-2">
                    <div className="flex items-start gap-3">
                      <animated.div
                        style={loadingDotSpring}
                        className="flex-shrink-0 mt-1 w-1.5 h-1.5 rounded-full bg-gray-400 animate-pulse"
                      />
                      <animated.div
                        style={loadingTextSpring}
                        className="flex-1 space-y-1 animate-pulse"
                      >
                        <div className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                          Processing...
                        </div>
                      </animated.div>
                    </div>
                  </animated.div>
                )}
              </div>
            </ScrollArea>
          </div>
        )}
      </animated.div>

      {/* Elegant completion state with smooth spring entrance */}
      <animated.div
        style={completionSpring}
        className="flex items-center gap-3 py-2"
      >
        {!isLoading && steps.length > 0 && (
          <>
            <animated.div
              style={completionDotSpring}
              className="w-1.5 h-1.5 rounded-full bg-gray-300"
            />
            <animated.div
              style={completionTextSpring}
              className="text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Complete • {steps.length} step{steps.length > 1 ? "s" : ""}
            </animated.div>
          </>
        )}
      </animated.div>
    </div>
  );
}
