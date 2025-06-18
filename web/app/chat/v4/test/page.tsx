'use client';

import { useState } from 'react';
import { useAgentQueryV4 } from '@/hooks/useAgentQueryV4';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export default function V4TestPage() {
  const agentQuery = useAgentQueryV4();
  const [testQueries] = useState([
    'SELECT 1 as test',
    'Show me all tables',
    'How many records are in the stocks table?',
    'What is 2 + 2?',
  ]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">V4 Agent Query Test</h1>

      <div className="grid grid-cols-2 gap-8">
        {/* Test Queries */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Test Queries</h2>
          <div className="space-y-2">
            {testQueries.map((query, i) => (
              <Button
                key={i}
                onClick={() => agentQuery.execute(query)}
                disabled={agentQuery.isLoading}
                variant="outline"
                className="w-full justify-start"
              >
                {query}
              </Button>
            ))}
            <Button
              onClick={() => agentQuery.reset()}
              variant="destructive"
              className="w-full"
            >
              Reset
            </Button>
          </div>
        </div>

        {/* Status */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Status</h2>
          <Card className="p-4">
            <div className="space-y-2 font-mono text-sm">
              <div>Query ID: {agentQuery.queryId || 'None'}</div>
              <div>Status: <span className={`font-bold ${
                agentQuery.status === 'complete' ? 'text-green-600' :
                agentQuery.status === 'error' ? 'text-red-600' :
                agentQuery.status === 'idle' ? 'text-gray-600' :
                'text-blue-600'
              }`}>{agentQuery.status}</span></div>
              <div>Loading: {agentQuery.isLoading ? 'Yes' : 'No'}</div>
              <div>Steps: {agentQuery.steps.length}</div>
              <div>Error: {agentQuery.error || 'None'}</div>
            </div>
          </Card>
        </div>
      </div>

      {/* Steps */}
      {agentQuery.steps.length > 0 && (
        <div className="mt-8">
          <h2 className="text-xl font-semibold mb-4">Steps ({agentQuery.steps.length})</h2>
          <div className="space-y-2">
            {agentQuery.steps.map((step, i) => (
              <Card key={step.id} className="p-3">
                <div className="flex items-start gap-3">
                  <div className={`px-2 py-1 rounded text-xs font-medium ${
                    step.type === 'thought' ? 'bg-purple-100 text-purple-700' :
                    step.type === 'action' ? 'bg-blue-100 text-blue-700' :
                    step.type === 'observation' ? 'bg-green-100 text-green-700' :
                    'bg-amber-100 text-amber-700'
                  }`}>
                    {step.type}
                  </div>
                  <div className="flex-1">
                    <div className="text-sm text-gray-600">Iteration {step.iteration}</div>
                    <div className="text-sm">{step.content}</div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Result */}
      {agentQuery.result && (
        <div className="mt-8">
          <h2 className="text-xl font-semibold mb-4">Result</h2>
          <Card className="p-4">
            <pre className="text-xs overflow-auto">
              {JSON.stringify(agentQuery.result, null, 2)}
            </pre>
          </Card>
        </div>
      )}
    </div>
  );
}
