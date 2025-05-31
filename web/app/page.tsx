'use client';

import { QueryProvider } from '@/components/providers/QueryProvider';
import { DataSourceProvider } from '@/contexts/DataSourceContext';
import { QueryInterface } from '@/components/query/QueryInterface';
import { DataSourceSelector } from '@/components/datasource/DataSourceSelector';
import { Database } from 'lucide-react';

export default function Home() {
  return (
    <DataSourceProvider>
      <QueryProvider>
        <div className="min-h-screen bg-gray-50">
          {/* Header */}
          <header className="bg-white shadow-sm border-b border-gray-200">
            <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex items-center justify-between h-16">
                <div className="flex items-center gap-3">
                  <Database className="h-6 w-6 text-blue-600" />
                  <h1 className="text-xl font-semibold text-gray-900">SENS</h1>
                  <span className="text-sm text-gray-500">Natural Language SQL</span>
                </div>
                <div className="flex items-center gap-4">
                  <DataSourceSelector />
                </div>
              </div>
            </div>
          </header>

        {/* Main Content */}
        <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Ask questions about your data in plain English
            </h2>
            <p className="text-gray-600">
              I'll convert your questions into SQL queries and show you the results.
            </p>
          </div>

          <QueryInterface />
        </main>

        {/* Footer */}
        <footer className="mt-auto py-8">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <p className="text-center text-sm text-gray-500">
              SENS - Semantic Natural SQL | Built with Next.js
            </p>
          </div>
        </footer>
      </div>
      </QueryProvider>
    </DataSourceProvider>
  );
}
