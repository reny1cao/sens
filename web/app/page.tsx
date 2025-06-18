'use client';

import { QueryProvider } from '@/components/providers/QueryProvider';
import { DataSourceProvider } from '@/contexts/DataSourceContext';
import { QueryInterfaceWithAgent } from '@/components/query/QueryInterfaceWithAgent';
import { DataSourceSelector } from '@/components/datasource/DataSourceSelector';
import { Database, MessageSquare } from 'lucide-react';

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
                <div className="flex items-center gap-6">
                  <nav className="flex items-center gap-4">
                    <a
                      href="/"
                      className="text-sm font-medium text-blue-600"
                    >
                      Classic
                    </a>
                    <a
                      href="/chat"
                      className="text-sm font-medium text-gray-700 hover:text-blue-600 transition-colors flex items-center gap-1"
                    >
                      <MessageSquare className="h-4 w-4" />
                      Chat
                    </a>
                    <a
                      href="/schema"
                      className="text-sm font-medium text-gray-700 hover:text-blue-600 transition-colors"
                    >
                      Schema
                    </a>
                  </nav>
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

          <QueryInterfaceWithAgent />
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
