'use client';

import { Sparkles } from 'lucide-react';

interface ExampleQueriesProps {
  onExampleClick: (example: string) => void;
}

const EXAMPLES = [
  'How many users do we have?',
  'Show me the top 10 customers by revenue',
  'What were our sales last month?',
  'List all active products with their prices',
  'Show me user growth over the last 6 months',
];

export function ExampleQueries({ onExampleClick }: ExampleQueriesProps) {
  return (
    <div className="mt-4">
      <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
        <Sparkles className="h-4 w-4" />
        <span>Try these examples:</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((example) => (
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
