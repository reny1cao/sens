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
  useEffect(() => {
    // Always fetch suggestions, even for default database
    fetchSuggestions();
  }, [activeSource, sessionId]);

  const fetchSuggestions = async () => {
    setIsLoading(true);
    try {
      // Only send session ID if we have one and it's not the default source
      const headers: Record<string, string> = {};
      if (sessionId && activeSource?.id !== 'default') {
        headers['X-Session-Id'] = sessionId;
      }
      
      const response = await fetch('/api/datasource/suggestions', {
        headers,
      });

      if (response.ok) {
        const data = await response.json();
        if (data.suggestions && data.suggestions.length > 0) {
          // Take first 5 suggestions
          setSuggestions(data.suggestions.slice(0, 5));
        }
      } else {
        // Use default suggestions if API fails
        setSuggestions(DEFAULT_EXAMPLES);
      }
    } catch (error) {
      console.error('Failed to fetch suggestions:', error);
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
          onClick={fetchSuggestions}
          disabled={isLoading}
          className="h-7 px-2 text-xs"
          title="Get new suggestions"
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
