'use client';

import { useEffect, useState } from 'react';
import { Sparkles, RefreshCw } from 'lucide-react';
import { useDataSource } from '@/contexts/DataSourceContext';
import { Button } from '@/components/ui/button';

interface ExampleQueriesProps {
  onExampleClick: (example: string) => void;
}

const DEFAULT_EXAMPLES = [
  'How many users do we have?',
  'Show me the top 10 customers by revenue',
  'What were our sales last month?',
  'List all active products with their prices',
  'Show me user growth over the last 6 months',
];

export function ExampleQueriesClient({ onExampleClick }: ExampleQueriesProps) {
  const { sessionId, activeSource } = useDataSource();
  const [suggestions, setSuggestions] = useState<string[]>(DEFAULT_EXAMPLES);
  const [isLoading, setIsLoading] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Ensure client-side only rendering
  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;

    console.log('[ExampleQueriesClient] Fetching suggestions...');
    fetchSuggestions();
  }, [mounted, activeSource?.id, sessionId]);

  const fetchSuggestions = async (forceRefresh = false) => {
    setIsLoading(true);
    try {
      const headers: Record<string, string> = {};
      if (sessionId && activeSource?.id !== 'default') {
        headers['X-Session-Id'] = sessionId;
      }

      const endpoint = '/api/datasource/suggestions';
      const response = await fetch(endpoint, {
        method: forceRefresh ? 'POST' : 'GET',
        headers,
      });

      if (response.ok) {
        const data = await response.json();
        console.log('[ExampleQueriesClient] Received data:', data);

        if (data.suggestions && data.suggestions.length > 0) {
          const newSuggestions = data.suggestions.slice(0, 5);
          console.log('[ExampleQueriesClient] Updating suggestions to:', newSuggestions);
          setSuggestions(newSuggestions);
        }
      }
    } catch (error) {
      console.error('[ExampleQueriesClient] Error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Don't render until mounted to avoid hydration issues
  if (!mounted) {
    return (
      <div className="mt-4">
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <Sparkles className="h-4 w-4" />
          <span>Loading suggestions...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <Sparkles className="h-4 w-4" />
          <span>{activeSource ? 'Suggested queries for your data:' : 'Try these examples:'}</span>
          {isLoading && <span className="text-xs text-gray-500">(Loading...)</span>}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => fetchSuggestions(true)}
          disabled={isLoading}
          className="h-7 px-2 text-xs"
          title="Refresh suggestions"
        >
          <RefreshCw className={`h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
        </Button>
      </div>
      <div className="flex flex-wrap gap-2">
        {suggestions.map((example, index) => (
          <button
            key={`${example}-${index}`}
            onClick={() => onExampleClick(example)}
            className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200 transition-colors"
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}
