'use client';

import { useState, useEffect } from 'react';
import { Code2, Copy, Check, ChevronDown, ChevronUp, Maximize2, Minimize2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { format } from 'sql-formatter';

interface SQLDisplayProps {
  sql: string;
  execution_time_ms?: number;
}

export function SQLDisplay({ sql, execution_time_ms }: SQLDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(true); // Start expanded
  const [isCopied, setIsCopied] = useState(false);
  const [isFormatted, setIsFormatted] = useState(true);
  const [formattedSql, setFormattedSql] = useState(sql);

  useEffect(() => {
    // Format SQL on mount and when SQL changes
    try {
      const formatted = format(sql, {
        language: 'postgresql',
        uppercase: true,
        linesBetweenQueries: 2,
      });
      setFormattedSql(formatted);
    } catch (error) {
      // If formatting fails, use original SQL
      console.warn('Failed to format SQL:', error);
      setFormattedSql(sql);
    }
  }, [sql]);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(isFormatted ? formattedSql : sql);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const displaySql = isFormatted ? formattedSql : sql;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Code2 className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">Generated SQL</CardTitle>
            {execution_time_ms !== undefined && (
              <Badge variant="secondary" className="font-mono">
                {execution_time_ms.toFixed(0)}ms
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsFormatted(!isFormatted)}
              title={isFormatted ? "Show compact SQL" : "Show formatted SQL"}
            >
              {isFormatted ? (
                <Minimize2 className="h-4 w-4" />
              ) : (
                <Maximize2 className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopy}
              title="Copy SQL to clipboard"
            >
              {isCopied ? (
                <Check className="h-4 w-4 text-green-500" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              title={isExpanded ? "Collapse SQL" : "Expand SQL"}
            >
              {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </CardHeader>

      {isExpanded && (
        <CardContent className="pt-0">
          <div className="rounded-lg overflow-hidden border border-border">
            <SyntaxHighlighter
              language="sql"
              style={atomDark}
              customStyle={{
                margin: 0,
                fontSize: '0.875rem',
                lineHeight: '1.5',
                padding: '1rem',
                maxHeight: '400px',
                overflow: 'auto',
              }}
              showLineNumbers={displaySql.split('\n').length > 1}
              lineNumberStyle={{
                minWidth: '3em',
                paddingRight: '1em',
                color: '#666',
                userSelect: 'none',
              }}
            >
              {displaySql}
            </SyntaxHighlighter>
          </div>
          {!isExpanded && (
            <div className="mt-2 text-sm text-muted-foreground">
              Click header to view SQL query
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
