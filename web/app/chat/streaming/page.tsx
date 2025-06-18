import { StreamingChatInterface } from '@/components/chat/StreamingChatInterface';

export default function StreamingChatPage() {
  return (
    <div className="h-screen bg-gray-50">
      <div className="h-full flex flex-col">
        <header className="bg-white border-b border-gray-200 px-6 py-4">
          <h1 className="text-xl font-semibold text-gray-900">
            SENS Chat - Streaming (2025 Architecture)
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Clean SSE-based real-time agent responses
          </p>
        </header>
        <div className="flex-1 overflow-hidden">
          <StreamingChatInterface />
        </div>
      </div>
    </div>
  );
}
