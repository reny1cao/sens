'use client';

import { useEffect, useState } from 'react';
import { Sparkles } from 'lucide-react';
import { useDataSource } from '@/contexts/DataSourceContext';

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
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (activeSource && sessionId) {
      fetchSuggestions();
    } else {
      setSuggestions(DEFAULT_EXAMPLES);
    }
  }, [activeSource, sessionId, refreshKey]);

  const fetchSuggestions = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/datasource/suggestions', {
        headers: {
          'X-Session-Id': sessionId,
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.suggestions && data.suggestions.length > 0) {
          // Take first 5 suggestions
          setSuggestions(data.suggestions.slice(0, 5));
        }
      }
    } catch (error) {
      console.error('Failed to fetch suggestions:', error);
      // Keep default suggestions on error
    } finally {
      setIsLoading(false);
    }
  };
  return (
    <div className="mt-4">
      <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
        <Sparkles className="h-4 w-4" />
        <span>{activeSource ? 'Suggested queries for your data:' : 'Try these examples:'}</span>
        {isLoading && <span className="text-xs text-gray-500">(Loading...)</span>}
      </div>
      <div className="flex flex-wrap gap-2">
        {suggestions.map((example) => (
          <button
            key={example}
            onClick={() => {
              onExampleClick(example);
              // Don't refresh immediately - let user see what was clicked
              setTimeout(() => {
                if (activeSource) {
                  setRefreshKey(prev => prev + 1);
                }
              }, 2000);
            }}
            className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200 transition-colors"
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}
