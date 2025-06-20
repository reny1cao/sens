'use client';

import { ChatInterfaceV5 } from '@/components/chat/ChatInterfaceV5';

export const dynamic = 'force-dynamic';

export default function ChatV5Page() {
  return (
    <div className="h-screen">
      <ChatInterfaceV5 />
    </div>
  );
}
