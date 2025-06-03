'use client';

import { useState } from 'react';
import { Send, Loader2, Info } from 'lucide-react';
import { useQuery } from '@/hooks/useQuery';
import { useDataSource } from '@/contexts/DataSourceContext';
import { ProcessingSteps } from './ProcessingSteps';
import { QueryResults } from '../results/QueryResults';
import { ExampleQueries } from './ExampleQueries';
import { DataSourceInfo } from '../datasource/DataSourceInfo';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';

export function QueryInterface() {
  const [question, setQuestion] = useState('');
  const { executeQuery, isLoading, data, error, steps } = useQuery();
  const { activeSource } = useDataSource();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;

    executeQuery({ question });
  };

  const handleExampleClick = (example: string) => {
    setQuestion(example);
    executeQuery({ question: example });
  };

  return (
    <div className="space-y-6">
      {/* Active Data Source Info */}
      {activeSource && (
        <Alert>
          <Info className="h-4 w-4" />
          <AlertDescription>
            {activeSource.id === 'default' ? (
              <>Querying <strong>{activeSource.name}</strong> - Upload files to query your own data</>
            ) : (
              <>Querying <strong>{activeSource.name}</strong> with {activeSource.tables.length} tables and {activeSource.totalRows.toLocaleString()} total rows</>
            )}
          </AlertDescription>
        </Alert>
      )}

      {/* Query Input */}
      <Card>
        <CardContent className="p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex gap-4">
              <Input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask a question about your data..."
                disabled={isLoading}
                autoFocus
                className="flex-1"
              />
              <Button
                type="submit"
                disabled={isLoading || !question.trim()}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Processing
                  </>
                ) : (
                  <>
                    <Send className="mr-2 h-4 w-4" />
                    Run Query
                  </>
                )}
              </Button>
            </div>
          </form>

          {/* Example Queries - Always show */}
          <ExampleQueries onExampleClick={handleExampleClick} />
        </CardContent>
      </Card>

      {/* Processing Steps */}
      {(isLoading || data || error) && (
        <ProcessingSteps steps={steps} isLoading={isLoading} />
      )}

      {/* Error Display */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4">
            <h3 className="text-red-800 font-medium mb-1">Error</h3>
            <p className="text-red-700">
              {error instanceof Error ? error.message : 'An unexpected error occurred'}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {data && !error && (
        <QueryResults response={data} />
      )}

      {/* Data Source Schema (optional - shown when there's an active source) */}
      {activeSource && !data && (
        <DataSourceInfo />
      )}
    </div>
  );
}
