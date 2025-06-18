import { ProcessingStep, QueryResponse } from './index';
import { AgentStep } from '@/hooks/useAgentQuery';

export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  metadata?: ChatMessageMetadata;
}

export interface ChatMessageMetadata {
  queryId?: string;
  mode?: 'fast' | 'agent';
  processingSteps?: ProcessingStep[];
  agentSteps?: AgentStep[];
  response?: QueryResponse;
  error?: Error | string;
  isLoading?: boolean;
  // For follow-up context
  parentMessageId?: string;
  relatedMessageIds?: string[];
}

export interface ChatConversation {
  id: string;
  messages: ChatMessage[];
  createdAt: Date;
  updatedAt: Date;
  title?: string;
  context?: ChatContext;
}

export interface ChatContext {
  dataSourceId?: string;
  sessionId?: string;
  previousQueries?: string[];
  userPreferences?: {
    defaultMode?: 'fast' | 'agent';
    showSQL?: boolean;
    autoExecute?: boolean;
  };
}

export interface ChatInputState {
  query: string;
  mode: 'fast' | 'agent';
  isSubmitting: boolean;
}

export interface ChatActions {
  retry: (messageId: string) => void;
  copySQL: (sql: string) => void;
  exportResults: (messageId: string) => void;
  deleteMessage: (messageId: string) => void;
  editMessage: (messageId: string, newContent: string) => void;
}

export type ChatEventType =
  | 'message_sent'
  | 'message_received'
  | 'processing_started'
  | 'processing_step'
  | 'processing_completed'
  | 'error_occurred'
  | 'retry_requested';

export interface ChatEvent {
  type: ChatEventType;
  messageId: string;
  timestamp: Date;
  data?: any;
}
