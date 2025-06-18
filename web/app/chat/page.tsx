'use client';

import { QueryProvider } from '@/components/providers/QueryProvider';
import { DataSourceProvider } from '@/contexts/DataSourceContext';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { DataSourceSelector } from '@/components/datasource/DataSourceSelector';
import { Database, MessageSquare } from 'lucide-react';

export default function ChatPage() {
  return (
    <DataSourceProvider>
      <QueryProvider>
        <div className="min-h-screen bg-gray-50 flex flex-col">
          {/* Header */}
          <header className="bg-white shadow-sm border-b border-gray-200 flex-shrink-0">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
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
                      className="text-sm font-medium text-gray-700 hover:text-blue-600 transition-colors"
                    >
                      Classic
                    </a>
                    <a
                      href="/chat"
                      className="text-sm font-medium text-blue-600 flex items-center gap-1"
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
          <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6">
            <ChatInterface />
          </main>
        </div>
      </QueryProvider>
    </DataSourceProvider>
  );
}
