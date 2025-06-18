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
  MessageSquare,
  Code2,
  Table2,
} from "lucide-react";
import * as Avatar from "@radix-ui/react-avatar";
import * as Collapsible from "@radix-ui/react-collapsible";
import { Button } from "@/components/ui/button";
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
  status?: "sending" | "processing" | "complete" | "error";
  answer?: string;
  steps?: AgentStep[];
  data?: any;
  error?: string;
}

interface ChatMessageV7Props {
  message: Message;
  index: number;
}

export function ChatMessageV7({ message, index }: ChatMessageV7Props) {
  // Keep analysis open while streaming, closed when complete
  const [isAnalysisExpanded, setIsAnalysisExpanded] = useState(message.status === "processing");
  const [isSQLExpanded, setIsSQLExpanded] = useState(false);

  // Update analysis expansion state when status changes
  useEffect(() => {
    if (message.status === "complete") {
      setIsAnalysisExpanded(false);
    }
  }, [message.status]);

  const isStreaming = message.status === "processing";
  const hasSteps = message.steps && message.steps.length > 0;
  const hasData = message.data?.results?.data?.length > 0;
  const hasSql = message.data?.sql;

  if (message.role === "user") {
    return (
      <div className="flex gap-3 group">
        <Avatar.Root className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center">
          <User className="w-4 h-4 text-gray-600" />
        </Avatar.Root>
        <div className="flex-1 min-w-0">
          <div className="text-sm text-gray-900 leading-relaxed">
            {message.content}
          </div>
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
        {/* Analysis Steps - Show first and keep open while processing */}
        {hasSteps && (
          <Collapsible.Root open={isAnalysisExpanded} onOpenChange={setIsAnalysisExpanded}>
            <Collapsible.Trigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 -ml-2"
              >
                {isStreaming ? (
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
                      <div className={cn(
                        "text-xs leading-relaxed",
                        step.type === "action" ? "font-medium text-gray-900" : "text-gray-600"
                      )}>
                        {step.content}
                      </div>
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

        {/* Primary Answer Section */}
        {message.answer && (
          <div className="space-y-2">
            <div className="text-sm leading-relaxed text-gray-900">
              {message.answer}
            </div>

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

        {/* Error State */}
        {message.error && (
          <div className="flex items-start gap-2 text-sm text-red-600 bg-red-50 rounded-lg p-3">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{message.error}</span>
          </div>
        )}

        {/* Processing State */}
        {isStreaming && !message.answer && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span>Processing your query...</span>
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
      return (
        <div className="w-4 h-4 rounded-full bg-gradient-to-br from-green-50 to-green-100 flex items-center justify-center flex-shrink-0">
          <CheckCircle2 className={cn(iconClass, "text-green-600")} />
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
