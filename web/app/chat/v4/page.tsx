'use client';

import { ChatInterfaceV4 } from '@/components/chat/ChatInterfaceV4';

export const dynamic = 'force-dynamic';

export default function ChatV4Page() {
  return (
    <div className="h-screen">
      <ChatInterfaceV4 />
    </div>
  );
}
