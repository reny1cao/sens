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
  deleteTable: (tableName: string) => Promise<void>;
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

  const refreshSession = useCallback(async () => {
    console.log('Refreshing session:', sessionId);
    try {
      const response = await fetch(`/api/datasource/session/${sessionId}`, {
        headers: {
          'X-Session-Id': sessionId,
        },
      });

      if (response.ok) {
        const data = await response.json();
        console.log('Session data loaded:', data);
        setActiveSource({
          id: data.source_id,
          name: data.name,
          type: data.type,
          tables: data.tables,
          totalRows: data.total_rows,
          createdAt: new Date(),
        });
      } else if (response.status === 404) {
        // Session not found - this is OK, user hasn't uploaded anything yet
        console.log('No active session found');
        setActiveSource(null);
      } else {
        console.log('Session load error:', response.status);
        // For other errors, clear the session and start fresh
        const newSessionId = generateSessionId();
        setSessionId(newSessionId);
        setActiveSource(null);
      }
    } catch (err) {
      // No existing session, that's ok
      console.log('Error loading session:', err);
    }
  }, [sessionId]);

  // Check for existing session on mount
  useEffect(() => {
    if (sessionId) {
      refreshSession();
    }
  }, [sessionId, refreshSession]);

  const uploadFiles = async (files: File[]) => {
    setIsLoading(true);
    setError(null);

    try {
      console.log('Uploading files:', files.map(f => ({ name: f.name, size: f.size })));
      console.log('Session ID:', sessionId);
      
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

      console.log('Upload response status:', response.status);

      if (!response.ok) {
        const errorData = await response.json();
        console.error('Upload error:', errorData);
        throw new Error(errorData.error || errorData.detail || 'Failed to upload files');
      }

      const data = await response.json();
      console.log('Upload success:', data);
      
      setActiveSource({
        id: data.source_id,
        name: data.name,
        type: data.type,
        tables: data.tables,
        totalRows: data.total_rows,
        createdAt: new Date(),
      });
    } catch (err) {
      console.error('Upload error:', err);
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

  const deleteTable = async (tableName: string) => {
    if (!activeSource) return;

    const confirmed = window.confirm(
      `Are you sure you want to delete the table "${tableName}"? This action cannot be undone.`
    );
    
    if (!confirmed) return;

    try {
      const response = await fetch(`/api/datasource/session/${sessionId}/table/${tableName}`, {
        method: 'DELETE',
        headers: {
          'X-Session-Id': sessionId,
        },
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to delete table');
      }

      const result = await response.json();
      
      // Refresh session to get updated table list
      await refreshSession();
      
      // Show success message
      if (result.remaining_tables && result.remaining_tables.length === 0) {
        // All tables deleted, session was cleaned up
        setActiveSource(null);
      }
    } catch (err) {
      console.error('Failed to delete table:', err);
      setError(err instanceof Error ? err.message : 'Failed to delete table');
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
        deleteTable,
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