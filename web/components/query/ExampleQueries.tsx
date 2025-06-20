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

export function ExampleQueries({ onExampleClick }: ExampleQueriesProps) {
  const { sessionId, activeSource } = useDataSource();
  const [suggestions, setSuggestions] = useState<string[]>(DEFAULT_EXAMPLES);
  const [isLoading, setIsLoading] = useState(false);

  // Debug render
  console.log('[ExampleQueries] Component rendered', {
    suggestions,
    isLoading,
    sessionId,
    activeSourceId: activeSource?.id,
  });

  useEffect(() => {
    // Fetch suggestions on mount and when context changes
    console.log('[ExampleQueries] useEffect triggered', { activeSource, sessionId });

    // Small delay to ensure component is fully mounted
    const timer = setTimeout(() => {
      fetchSuggestions();
    }, 100);

    return () => clearTimeout(timer);
  }, [activeSource?.id, sessionId]); // Depend on activeSource.id instead of the whole object

  // Debug effect to log when suggestions actually change
  useEffect(() => {
    console.log('[ExampleQueries] Suggestions state updated:', suggestions);
  }, [suggestions]);

  const fetchSuggestions = async (forceRefresh = false) => {
    console.log('[ExampleQueries] fetchSuggestions called', {
      forceRefresh,
      sessionId,
      activeSourceId: activeSource?.id,
      currentSuggestions: suggestions
    });

    setIsLoading(true);
    try {
      // Only send session ID if we have one and it's not the default source
      const headers: Record<string, string> = {};
      if (sessionId && activeSource?.id !== 'default') {
        headers['X-Session-Id'] = sessionId;
      }

      // Use same endpoint but different method for refresh
      const endpoint = '/api/datasource/suggestions';

      console.log('[ExampleQueries] Fetching from:', endpoint, 'headers:', headers);

      const response = await fetch(endpoint, {
        method: forceRefresh ? 'POST' : 'GET',
        headers,
      });

      console.log('[ExampleQueries] Response status:', response.status);

      if (response.ok) {
        const data = await response.json();
        console.log('[ExampleQueries] Fetched data:', data);

        if (data.suggestions && data.suggestions.length > 0) {
          // Take first 5 suggestions
          const newSuggestions = data.suggestions.slice(0, 5);
          console.log('[ExampleQueries] Setting new suggestions:', newSuggestions);
          setSuggestions(prevSuggestions => {
            console.log('[ExampleQueries] Previous suggestions:', prevSuggestions);
            console.log('[ExampleQueries] New suggestions to set:', newSuggestions);
            return newSuggestions;
          });
        } else {
          console.log('[ExampleQueries] No suggestions in response, keeping defaults');
          console.log('[ExampleQueries] Response data:', data);
        }
      } else {
        // Use default suggestions if API fails
        console.error('[ExampleQueries] API failed:', response.status, response.statusText);
        setSuggestions(DEFAULT_EXAMPLES);
      }
    } catch (error) {
      console.error('[ExampleQueries] Failed to fetch suggestions:', error);
      // Keep default suggestions on error
      setSuggestions(DEFAULT_EXAMPLES);
    } finally {
      setIsLoading(false);
    }
  };
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
        {suggestions.map((example) => (
          <button
            key={example}
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
