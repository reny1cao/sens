'use client';

import { useEffect, useState } from 'react';
import { Sparkles, RefreshCw, MessageCircle, Zap } from 'lucide-react';
import { useDataSource } from '@/contexts/DataSourceContext';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ExampleQueriesProps {
  onExampleClick: (example: string) => void;
  compact?: boolean;
}

const DEFAULT_EXAMPLES = [
  'How many users do we have?',
  'Show me the top 10 customers by revenue',
  'What were our sales last month?',
  'List all active products with their prices',
  'Show me user growth over the last 6 months',
];

export function ExampleQueriesClient({ onExampleClick, compact = false }: ExampleQueriesProps) {
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

  if (compact) {
    return (
      <div className="flex flex-wrap gap-3">
        {suggestions.slice(0, 3).map((example, index) => (
          <button
            key={`${example}-${index}`}
            onClick={() => onExampleClick(example)}
            className="px-4 py-2 text-sm bg-gray-50/60 text-gray-700 rounded-xl border border-gray-200/50 hover:border-gray-300/70 hover:bg-gray-100/60 backdrop-blur-sm transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] animate-in fade-in slide-in-from-bottom font-medium"
            style={{ animationDelay: `${index * 100}ms` }}
          >
            {example}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom duration-500">
      <div className="flex items-center justify-between">
        <div className="animate-in fade-in slide-in-from-left duration-500 delay-200">
          <h3 className="font-semibold text-gray-900 mb-1">
            {activeSource ? 'Personalized suggestions' : 'Example queries'}
          </h3>
          <p className="text-sm text-gray-500 font-medium">
            Click any example to get started
          </p>
        </div>

        <div className="animate-in fade-in slide-in-from-right duration-500 delay-300">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => fetchSuggestions(true)}
            disabled={isLoading}
            className="text-gray-500 hover:text-gray-700 hover:bg-gray-100/60 rounded-xl"
          >
            <div className={cn(
              "transition-transform duration-1000",
              isLoading && "animate-spin"
            )}>
              <RefreshCw className="h-4 w-4" />
            </div>
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {suggestions.map((example, index) => (
          <button
            key={`${example}-${index}`}
            onClick={() => onExampleClick(example)}
            className="group relative p-5 bg-white/50 backdrop-blur-sm border border-gray-200/40 rounded-2xl shadow-sm hover:shadow-md transition-all duration-300 text-left hover:scale-[1.01] hover:-translate-y-0.5 active:scale-[0.99] animate-in fade-in slide-in-from-bottom"
            style={{ animationDelay: `${index * 100}ms` }}
          >
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 mt-0.5">
                <div className="w-7 h-7 bg-gray-100 rounded-lg flex items-center justify-center group-hover:bg-gray-200 transition-colors">
                  <MessageCircle className="h-3.5 w-3.5 text-gray-600" />
                </div>
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-base text-gray-800 leading-relaxed group-hover:text-gray-900 transition-colors font-medium">
                  {example}
                </p>
              </div>

              <div className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-all duration-200 -translate-x-1 group-hover:translate-x-0">
                <div className="w-5 h-5 bg-gray-100 rounded-full flex items-center justify-center">
                  <Zap className="h-3 w-3 text-gray-600" />
                </div>
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center gap-2 py-4 animate-in fade-in slide-in-from-bottom duration-500">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
              style={{ animationDelay: `${i * 200}ms` }}
            />
          ))}
          <span className="text-sm text-gray-500 ml-2 font-medium">
            Finding suggestions...
          </span>
        </div>
      )}
    </div>
  );
}
