'use client';

import { ChatInterfaceV7 } from '@/components/chat/ChatInterfaceV7';

export const dynamic = 'force-dynamic';

export default function ChatV7Page() {
  return (
    <div className="h-screen">
      <ChatInterfaceV7 />
    </div>
  );
}
