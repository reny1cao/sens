'use client';

import { ChatInterfaceV2 } from '@/components/chat/ChatInterfaceV2';

export const dynamic = 'force-dynamic';

export default function ChatV2Page() {
  return (
    <div className="h-screen">
      <ChatInterfaceV2 />
    </div>
  );
}
