"use client";

import React, { useState, useEffect } from "react";
import {
  Bot,
  User,
  AlertCircle,
  ChevronRight,
  Loader2,
  Sparkles,
  Zap,
  CheckCircle2,
  XCircle,
  MessageSquare,
  Code2,
  Table2,
  HelpCircle,
} from "lucide-react";
import * as Avatar from "@radix-ui/react-avatar";
import * as Collapsible from "@radix-ui/react-collapsible";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/ui/markdown";
import { cn } from "@/lib/utils";
import { format } from "date-fns";

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
  status?: "sending" | "processing" | "complete" | "error" | "failed";
  answer?: string;
  steps?: AgentStep[];
  data?: any;
  error?: string;
}

interface ChatMessageV6Props {
  message: Message;
  index: number;
  onOptionClick?: (option: string) => void;
}

export function ChatMessageV6({ message, index, onOptionClick }: ChatMessageV6Props) {
  // Keep analysis open until answer appears or failed
  const [isAnalysisExpanded, setIsAnalysisExpanded] = useState(
    !message.answer && message.status !== "failed"
  );
  const [isSQLExpanded, setIsSQLExpanded] = useState(false);

  // Auto-close analysis when answer appears or status is final
  useEffect(() => {
    if (message.answer || message.status === "failed" || message.status === "error") {
      setIsAnalysisExpanded(false);
    }
  }, [message.answer, message.status]);

  const isStreaming = message.status === "processing";
  const hasSteps = message.steps && message.steps.length > 0;
  const hasData = message.data?.results?.data?.length > 0;
  const hasSql = message.data?.sql;

  // Check if query failed (no results but completed)
  const isQueryFailed = message.status === "complete" && !hasData && !message.error;

  // Check for conversational responses
  const isClarification = message.data?.clarification_needed;
  const isDirectAnswer = message.data?.direct_answer;
  const hasSuggestions = message.data?.suggestions;

  if (message.role === "user") {
    return (
      <div className="flex gap-3 group">
        <Avatar.Root className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center">
          <User className="w-4 h-4 text-gray-600" />
        </Avatar.Root>
        <div className="flex-1 min-w-0">
          <Markdown className="text-sm text-gray-900">
            {message.content}
          </Markdown>
          <div className="text-xs text-gray-400 mt-1">
            {format(message.timestamp, "HH:mm")}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 group">
      <Avatar.Root className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-gray-900 to-gray-700 flex items-center justify-center">
        <Bot className="w-4 h-4 text-white" />
      </Avatar.Root>

      <div className="flex-1 min-w-0 space-y-3">
        {/* Analysis Steps - Show first and keep open until answer */}
        {hasSteps && (
          <Collapsible.Root open={isAnalysisExpanded} onOpenChange={setIsAnalysisExpanded}>
            <Collapsible.Trigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 -ml-2"
              >
                {isStreaming && !message.answer ? (
                  <>
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3 h-3 mr-1" />
                    <span>Analysis process</span>
                  </>
                )}
                <span className="text-gray-400 ml-1">({message.steps.length} steps)</span>
                <ChevronRight
                  className={cn(
                    "w-3 h-3 ml-1 transition-transform duration-200",
                    isAnalysisExpanded && "rotate-90"
                  )}
                />
              </Button>
            </Collapsible.Trigger>

            <Collapsible.Content className="mt-2">
              <div className="bg-gray-50/50 rounded-lg p-4 space-y-3">
                {message.steps.map((step) => (
                  <div key={step.id} className="flex gap-3">
                    {getStepIcon(step)}
                    <div className="flex-1 min-w-0">
                      {step.type === "action" ? (
                        <div className="text-xs font-medium text-gray-900 leading-relaxed">
                          {step.content}
                        </div>
                      ) : (
                        <Markdown className="text-xs text-gray-600">
                          {step.content}
                        </Markdown>
                      )}
                      {step.type === "action" && step.metadata?.parameters?.query && (
                        <div className="mt-1.5 bg-gray-900 text-gray-100 rounded p-2 font-mono text-[10px] overflow-x-auto">
                          <SQLHighlight sql={step.metadata.parameters.query} />
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </Collapsible.Content>
          </Collapsible.Root>
        )}

        {/* Clarification Request */}
        {isClarification && message.data && (
          <div className="space-y-3">
            <div className="flex items-start gap-3 text-sm text-blue-700 bg-blue-50 rounded-lg p-4">
              <HelpCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
              <div className="space-y-2">
                <Markdown>{message.data.message}</Markdown>
                {message.data.options && message.data.options.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {message.data.options.map((option: string, idx: number) => (
                      <div
                        key={idx}
                        className="px-3 py-2 bg-white/50 rounded text-sm text-blue-600 cursor-pointer hover:bg-white transition-colors"
                        onClick={() => {
                          if (onOptionClick) {
                            onOptionClick(option);
                          }
                        }}
                      >
                        {option}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Direct Answer (No SQL needed) */}
        {isDirectAnswer && message.data && (
          <Markdown className="text-sm text-gray-900">
            {message.data.answer}
          </Markdown>
        )}

        {/* Suggestions */}
        {hasSuggestions && message.data && (
          <div className="space-y-3">
            {message.data.context && (
              <Markdown className="text-sm text-gray-700">
                {message.data.context}
              </Markdown>
            )}
            <div className="space-y-2">
              {message.data.suggestions.map((suggestion: string, idx: number) => (
                <div
                  key={idx}
                  className="px-4 py-3 bg-gray-50 rounded-lg text-sm text-gray-700 border border-gray-200 cursor-pointer hover:bg-gray-100 transition-colors"
                  onClick={() => {
                    if (onOptionClick) {
                      onOptionClick(suggestion);
                    }
                  }}
                >
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-gray-500" />
                    <span>{suggestion}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Primary Answer Section - Success Case (SQL executed) */}
        {message.answer && !isQueryFailed && !isClarification && !isDirectAnswer && (
          <div className="space-y-2">
            <Markdown className="text-sm text-gray-900">
              {message.answer}
            </Markdown>

            {/* Inline SQL Toggle */}
            {hasSql && (
              <Collapsible.Root open={isSQLExpanded} onOpenChange={setIsSQLExpanded}>
                <Collapsible.Trigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 -ml-2"
                  >
                    <Code2 className="w-3 h-3 mr-1" />
                    <span>View SQL</span>
                    <ChevronRight
                      className={cn(
                        "w-3 h-3 ml-1 transition-transform duration-200",
                        isSQLExpanded && "rotate-90"
                      )}
                    />
                  </Button>
                </Collapsible.Trigger>

                <Collapsible.Content className="mt-2">
                  <div className="bg-gray-900 text-gray-100 rounded-lg p-3 font-mono text-xs overflow-x-auto">
                    <SQLHighlight sql={message.data.sql} />
                  </div>
                </Collapsible.Content>
              </Collapsible.Root>
            )}
          </div>
        )}

        {/* Failed Query State - No Results Found */}
        {isQueryFailed && !isClarification && !isDirectAnswer && !hasSuggestions && (
          <div className="space-y-3">
            <div className="flex items-start gap-3 text-sm text-amber-700 bg-amber-50 rounded-lg p-4">
              <HelpCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
              <div className="space-y-1">
                <div className="font-medium">No results found</div>
                <div className="text-amber-600">
                  I couldn't find any data matching your query. This could mean:
                </div>
                <ul className="list-disc list-inside text-amber-600 space-y-0.5 ml-2">
                  <li>The data doesn't exist in the database</li>
                  <li>The search criteria might be too specific</li>
                  <li>There might be a mismatch in naming or values</li>
                </ul>
              </div>
            </div>

            {/* Still show SQL if generated */}
            {hasSql && (
              <Collapsible.Root open={isSQLExpanded} onOpenChange={setIsSQLExpanded}>
                <Collapsible.Trigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 -ml-2"
                  >
                    <Code2 className="w-3 h-3 mr-1" />
                    <span>View generated SQL</span>
                    <ChevronRight
                      className={cn(
                        "w-3 h-3 ml-1 transition-transform duration-200",
                        isSQLExpanded && "rotate-90"
                      )}
                    />
                  </Button>
                </Collapsible.Trigger>

                <Collapsible.Content className="mt-2">
                  <div className="bg-gray-900 text-gray-100 rounded-lg p-3 font-mono text-xs overflow-x-auto">
                    <SQLHighlight sql={message.data.sql} />
                  </div>
                </Collapsible.Content>
              </Collapsible.Root>
            )}
          </div>
        )}

        {/* Data Table - Refined Design */}
        {hasData && (
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Table2 className="w-4 h-4 text-gray-500" />
                <span className="text-sm font-medium text-gray-700">
                  {message.data.results.row_count} result{message.data.results.row_count !== 1 ? 's' : ''}
                </span>
              </div>
              <span className="text-xs text-gray-500">
                {message.data.results.columns.length} columns
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-100">
                    {message.data.results.columns.map((col: string) => (
                      <th
                        key={col}
                        className="px-4 py-2 text-left text-xs font-medium text-gray-600 uppercase tracking-wider"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {message.data.results.data.slice(0, 10).map((row: any, idx: number) => (
                    <tr key={idx} className="border-b border-gray-50 hover:bg-gray-50">
                      {Object.values(row).map((value: any, colIdx: number) => (
                        <td key={colIdx} className="px-4 py-2 text-sm text-gray-700">
                          {formatCellValue(value)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {message.data.results.row_count > 10 && (
              <div className="px-4 py-2 bg-gray-50 text-xs text-gray-500 text-center">
                Showing first 10 of {message.data.results.row_count} rows
              </div>
            )}
          </div>
        )}

        {/* Error State - Technical Errors */}
        {message.error && (
          <div className="flex items-start gap-2 text-sm text-red-600 bg-red-50 rounded-lg p-3">
            <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{message.error}</span>
          </div>
        )}

        {/* Unable to Process State */}
        {message.status === "failed" && !message.error && !isQueryFailed && (
          <div className="flex items-start gap-3 text-sm text-gray-600 bg-gray-100 rounded-lg p-4">
            <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
            <div className="space-y-1">
              <div className="font-medium">Unable to process your query</div>
              <div className="text-gray-500">
                I wasn't able to understand how to answer your question. Try rephrasing it or breaking it down into simpler parts.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function getStepIcon(step: AgentStep) {
  const iconClass = "w-2.5 h-2.5";
  switch (step.type) {
    case "thought":
      return (
        <div className="w-4 h-4 rounded-full bg-gradient-to-br from-purple-50 to-purple-100 flex items-center justify-center flex-shrink-0">
          <Sparkles className={cn(iconClass, "text-purple-600")} />
        </div>
      );
    case "action":
      return (
        <div className="w-4 h-4 rounded-full bg-gradient-to-br from-blue-50 to-blue-100 flex items-center justify-center flex-shrink-0">
          <Zap className={cn(iconClass, "text-blue-600")} />
        </div>
      );
    case "observation":
      // Check if it's a failed observation
      const isFailed = step.content.includes("Failed") || step.content.includes("error");
      return (
        <div className={cn(
          "w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0",
          isFailed
            ? "bg-gradient-to-br from-red-50 to-red-100"
            : "bg-gradient-to-br from-green-50 to-green-100"
        )}>
          {isFailed ? (
            <XCircle className={cn(iconClass, "text-red-600")} />
          ) : (
            <CheckCircle2 className={cn(iconClass, "text-green-600")} />
          )}
        </div>
      );
    default:
      return <div className="w-4 h-4 rounded-full bg-gray-100 flex-shrink-0" />;
  }
}

function formatCellValue(value: any): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    // Format large numbers with commas
    if (Math.abs(value) >= 1000) {
      return value.toLocaleString();
    }
    // Format decimals to 2 places
    if (!Number.isInteger(value)) {
      return value.toFixed(2);
    }
  }
  if (value instanceof Date) {
    return format(value, "MMM d, yyyy");
  }
  return String(value);
}

// SQL Syntax Highlighting Component
function SQLHighlight({ sql }: { sql: string }) {
  // SQL keywords - comprehensive list
  const keywords = new Set([
    'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
    'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET', 'UNION', 'ALL',
    'AS', 'ON', 'AND', 'OR', 'NOT', 'IN', 'EXISTS', 'BETWEEN', 'LIKE', 'ILIKE',
    'IS', 'NULL', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'DISTINCT',
    'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'WITH', 'OVER', 'PARTITION',
    'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TABLE',
    'DESC', 'ASC', 'CAST', 'COALESCE', 'EXTRACT', 'DATE_TRUNC',
    'PERCENTILE_CONT', 'WITHIN', 'VALUES', 'INTO'
  ]);

  // Tokenize SQL for proper highlighting
  const tokenize = (text: string) => {
    const tokens: Array<{ type: 'keyword' | 'string' | 'number' | 'text', value: string }> = [];
    let current = '';
    let inString = false;
    let stringChar = '';

    for (let i = 0; i < text.length; i++) {
      const char = text[i];

      // Handle strings
      if ((char === "'" || char === '"') && !inString) {
        // Flush current token
        if (current) {
          tokens.push(...parseNonString(current));
          current = '';
        }
        inString = true;
        stringChar = char;
        current = char;
      } else if (char === stringChar && inString) {
        current += char;
        tokens.push({ type: 'string', value: current });
        current = '';
        inString = false;
        stringChar = '';
      } else if (inString) {
        current += char;
      } else {
        current += char;
      }
    }

    // Flush remaining
    if (current) {
      if (inString) {
        tokens.push({ type: 'string', value: current });
      } else {
        tokens.push(...parseNonString(current));
      }
    }

    return tokens;
  };

  // Parse non-string content for keywords and numbers
  const parseNonString = (text: string) => {
    const tokens: Array<{ type: 'keyword' | 'number' | 'text', value: string }> = [];
    const words = text.split(/\b/);

    for (const word of words) {
      if (!word) continue;

      if (keywords.has(word.toUpperCase())) {
        tokens.push({ type: 'keyword', value: word });
      } else if (/^\d+(\.\d+)?$/.test(word)) {
        tokens.push({ type: 'number', value: word });
      } else {
        tokens.push({ type: 'text', value: word });
      }
    }

    return tokens;
  };

  // Render tokens with appropriate styling
  const renderToken = (token: { type: string, value: string }, index: number) => {
    switch (token.type) {
      case 'keyword':
        return <span key={index} className="text-blue-400 font-semibold">{token.value.toUpperCase()}</span>;
      case 'string':
        return <span key={index} className="text-green-400">{token.value}</span>;
      case 'number':
        return <span key={index} className="text-purple-400">{token.value}</span>;
      default:
        return <span key={index}>{token.value}</span>;
    }
  };

  const lines = sql.split('\n');

  return (
    <>
      {lines.map((line, lineIndex) => (
        <div key={lineIndex}>
          {tokenize(line).map((token, tokenIndex) =>
            renderToken(token, `${lineIndex}-${tokenIndex}`)
          )}
        </div>
      ))}
    </>
  );
}
