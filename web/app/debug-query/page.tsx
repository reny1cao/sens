'use client';

import { useState } from 'react';
import { DataSourceProvider } from '@/contexts/DataSourceContext';
import { useQuery } from '@/hooks/useQuery';
import { useAgentQuery } from '@/hooks/useAgentQuery';
import { QueryResults } from '@/components/results/QueryResults';
import { ProcessingSteps } from '@/components/query/ProcessingSteps';
import { AgentProcessingSteps } from '@/components/query/AgentProcessingSteps';

function DebugQueryTest() {
  const [query, setQuery] = useState('Show me the top 5 stock prices for AAPL');
  const [useAgent, setUseAgent] = useState(false);

  const standardQuery = useQuery();
  const agentQuery = useAgentQuery();

  const activeQuery = useAgent ? agentQuery : standardQuery;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      if (useAgent) {
        agentQuery.executeQuery(query.trim());
      } else {
        standardQuery.executeQuery(query.trim());
      }
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Debug Query Execution</h1>

      <form onSubmit={handleSubmit} className="mb-6">
        <div className="mb-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={useAgent}
              onChange={(e) => setUseAgent(e.target.checked)}
            />
            Use Agent Mode
          </label>
        </div>

        <div className="mb-4">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter your query..."
            className="w-full p-3 border rounded"
            disabled={activeQuery.isLoading}
          />
        </div>

        <button
          type="submit"
          className="px-6 py-3 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-400"
          disabled={!query.trim() || activeQuery.isLoading}
        >
          {activeQuery.isLoading ? 'Processing...' : 'Execute Query'}
        </button>
      </form>

      {activeQuery.error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded">
          <h3 className="font-medium text-red-800 mb-2">Error:</h3>
          <p className="text-red-700">{typeof activeQuery.error === 'string' ? activeQuery.error : activeQuery.error.message}</p>
        </div>
      )}

      {/* Processing Steps */}
      {(activeQuery.isLoading || (!useAgent && standardQuery.data) || (useAgent && agentQuery.steps.length > 0)) && (
        <div className="mb-6">
          {useAgent ? (
            <AgentProcessingSteps
              steps={agentQuery.steps}
              isLoading={agentQuery.isLoading}
            />
          ) : (
            <ProcessingSteps
              steps={standardQuery.steps}
              isLoading={standardQuery.isLoading}
            />
          )}
        </div>
      )}

      {/* Results */}
      {!activeQuery.error && !activeQuery.isLoading && (
        <div>
          {useAgent ? (
            agentQuery.result && (
              <div>
                <h2 className="text-lg font-semibold mb-4">Agent Query Results:</h2>
                <QueryResults response={agentQuery.result} />
              </div>
            )
          ) : (
            standardQuery.data && (
              <div>
                <h2 className="text-lg font-semibold mb-4">Standard Query Results:</h2>
                <QueryResults response={standardQuery.data} />
              </div>
            )
          )}
        </div>
      )}

      <div className="mt-8 p-4 bg-gray-50 rounded">
        <h3 className="font-medium mb-2">Debug Info:</h3>
        <pre className="text-xs overflow-auto">
          {JSON.stringify({
            mode: useAgent ? 'agent' : 'standard',
            isLoading: activeQuery.isLoading,
            hasData: useAgent ? !!agentQuery.result : !!standardQuery.data,
            hasError: !!activeQuery.error,
            stepsCount: useAgent ? agentQuery.steps.length : standardQuery.steps.length,
          }, null, 2)}
        </pre>
      </div>
    </div>
  );
}

export default function DebugQueryPage() {
  return (
    <DataSourceProvider>
      <DebugQueryTest />
    </DataSourceProvider>
  );
}
