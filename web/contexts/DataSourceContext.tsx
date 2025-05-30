'use client';

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { DataSource, DataSourceType, TableInfo } from '@/types';

interface DataSourceContextType {
  activeSource: DataSource | null;
  sessionId: string;
  isLoading: boolean;
  error: string | null;
  uploadFiles: (files: File[]) => Promise<void>;
  setActiveSource: (source: DataSource) => void;
  clearDataSource: () => Promise<void>;
  previewTable: (tableName: string) => Promise<any>;
  refreshSession: () => Promise<void>;
}

const DataSourceContext = createContext<DataSourceContextType | undefined>(undefined);

// Generate a session ID
const generateSessionId = () => {
  return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

export function DataSourceProvider({ children }: { children: React.ReactNode }) {
  const [activeSource, setActiveSource] = useState<DataSource | null>(null);
  const [sessionId, setSessionId] = useState<string>(() => {
    // Try to get from localStorage or generate new
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('sens-session-id');
      return stored || generateSessionId();
    }
    return generateSessionId();
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Save session ID to localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('sens-session-id', sessionId);
    }
  }, [sessionId]);

  // Check for existing session on mount
  useEffect(() => {
    refreshSession();
  }, []);

  const refreshSession = async () => {
    try {
      const response = await fetch(`/api/datasource/session/${sessionId}`, {
        headers: {
          'X-Session-Id': sessionId,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setActiveSource({
          id: data.source_id,
          name: data.name,
          type: data.type,
          tables: data.tables,
          totalRows: data.total_rows,
          createdAt: new Date(),
        });
      }
    } catch (err) {
      // No existing session, that's ok
      console.log('No existing session found');
    }
  };

  const uploadFiles = async (files: File[]) => {
    setIsLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      files.forEach(file => {
        formData.append('files', file);
      });

      const response = await fetch('/api/datasource/upload', {
        method: 'POST',
        headers: {
          'X-Session-Id': sessionId,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to upload files');
      }

      const data = await response.json();
      
      setActiveSource({
        id: data.source_id,
        name: data.name,
        type: data.type,
        tables: data.tables,
        totalRows: data.total_rows,
        createdAt: new Date(),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload files');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const clearDataSource = async () => {
    if (!activeSource) return;

    // Confirm before clearing
    const confirmed = window.confirm(
      `Are you sure you want to clear "${activeSource.name}"? This will remove all uploaded data.`
    );
    
    if (!confirmed) return;

    try {
      await fetch(`/api/datasource/session/${sessionId}`, {
        method: 'DELETE',
        headers: {
          'X-Session-Id': sessionId,
        },
      });

      // Generate new session
      const newSessionId = generateSessionId();
      setSessionId(newSessionId);
      setActiveSource(null);
      setError(null);
    } catch (err) {
      console.error('Failed to clear data source:', err);
    }
  };

  const previewTable = async (tableName: string) => {
    try {
      const response = await fetch(`/api/datasource/preview/${tableName}`, {
        headers: {
          'X-Session-Id': sessionId,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to preview table');
      }

      return await response.json();
    } catch (err) {
      console.error('Failed to preview table:', err);
      throw err;
    }
  };

  return (
    <DataSourceContext.Provider
      value={{
        activeSource,
        sessionId,
        isLoading,
        error,
        uploadFiles,
        setActiveSource,
        clearDataSource,
        previewTable,
        refreshSession,
      }}
    >
      {children}
    </DataSourceContext.Provider>
  );
}

export function useDataSource() {
  const context = useContext(DataSourceContext);
  if (context === undefined) {
    throw new Error('useDataSource must be used within a DataSourceProvider');
  }
  return context;
}