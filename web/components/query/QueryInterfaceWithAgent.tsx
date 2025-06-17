'use client';

import { useState } from 'react';
import { Send, Sparkles, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { QueryResults } from '../results/QueryResults';
import { ProcessingSteps } from './ProcessingSteps';
import { AgentProcessingSteps } from './AgentProcessingSteps';
import { ExampleQueriesClient } from './ExampleQueriesClient';
import { useQuery } from '@/hooks/useQuery';
import { useAgentQuery } from '@/hooks/useAgentQuery';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';


export function QueryInterfaceWithAgent() {
  const [query, setQuery] = useState('');
  const [useAgent, setUseAgent] = useState(false);

  // Standard query hook
  const standardQuery = useQuery();

  // Agent query hook
  const agentQuery = useAgentQuery();

  // Select which hook to use based on mode
  const activeQuery = useAgent ? agentQuery : standardQuery;
  const isLoading = activeQuery.isLoading;
  const error = useAgent
    ? activeQuery.error
    : (activeQuery.error instanceof Error ? activeQuery.error.message : activeQuery.error);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      activeQuery.executeQuery(query.trim());
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleExampleClick = (exampleQuery: string) => {
    setQuery(exampleQuery);
    if (!isLoading) {
      activeQuery.executeQuery(exampleQuery);
    }
  };

  return (
    <div className="space-y-6">
      {/* Query Input */}
      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Natural Language Query</h2>

              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="flex items-center space-x-2">
                      <Switch
                        id="agent-mode"
                        checked={useAgent}
                        onCheckedChange={setUseAgent}
                        disabled={isLoading}
                      />
                      <Label
                        htmlFor="agent-mode"
                        className="cursor-pointer flex items-center gap-2"
                      >
                        {useAgent ? (
                          <>
                            <Sparkles className="h-4 w-4 text-purple-500" />
                            <span>Agent Mode</span>
                          </>
                        ) : (
                          <>
                            <Zap className="h-4 w-4 text-blue-500" />
                            <span>Fast Mode</span>
                          </>
                        )}
                      </Label>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="max-w-xs">
                      {useAgent
                        ? "Agent Mode: AI explores the database intelligently to answer complex queries"
                        : "Fast Mode: Direct SQL generation for quick results"
                      }
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>

            <div className="relative">
              <Textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question about your data in plain English..."
                className="min-h-[100px] pr-12 resize-none"
                disabled={isLoading}
              />
              <Button
                type="submit"
                size="icon"
                className="absolute bottom-2 right-2"
                disabled={!query.trim() || isLoading}
              >
                <Send className="h-4 w-4" />
                <span className="sr-only">Submit query</span>
              </Button>
            </div>

            {/* Example Queries */}
            <ExampleQueriesClient onExampleClick={handleExampleClick} />
          </form>
        </CardContent>
      </Card>

      {/* Processing Steps */}
      {(isLoading || (!useAgent && standardQuery.data) || (useAgent && agentQuery.steps.length > 0)) && (
        useAgent ? (
          <AgentProcessingSteps
            steps={agentQuery.steps}
            isLoading={isLoading}
          />
        ) : (
          <ProcessingSteps
            steps={standardQuery.steps}
            isLoading={isLoading}
          />
        )
      )}

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{typeof error === 'string' ? error : error.message}</AlertDescription>
        </Alert>
      )}

      {/* Results Display */}
      {(() => {
        console.log('[QueryInterface] Render state:', {
          error,
          isLoading,
          useAgent,
          hasStandardData: !!standardQuery.data,
          hasAgentResult: !!agentQuery.result,
          standardQueryData: standardQuery.data,
          agentQueryResult: agentQuery.result,
          standardQueryKeys: standardQuery.data ? Object.keys(standardQuery.data) : null,
          standardQueryResultsKeys: standardQuery.data?.results ? Object.keys(standardQuery.data.results) : null,
        });
        return null;
      })()}

      {!error && !isLoading && (
        useAgent ? (
          agentQuery.result && (
            <QueryResults
              response={agentQuery.result}
            />
          )
        ) : (
          standardQuery.data && (
            <QueryResults
              response={standardQuery.data}
            />
          )
        )
      )}

      {/* Agent Mode Info */}
      {useAgent && !isLoading && !error && agentQuery.steps.length === 0 && (
        <Alert>
          <Sparkles className="h-4 w-4" />
          <AlertDescription>
            <strong>Agent Mode Active:</strong> The AI agent will explore your database intelligently,
            discovering table structures and value mappings to answer complex queries.
            You'll see its thinking process in real-time!
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
