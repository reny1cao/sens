'use client';

import { ChatInterfaceV6 } from '@/components/chat/ChatInterfaceV6';

export const dynamic = 'force-dynamic';

export default function ChatV6Page() {
  return (
    <div className="h-screen">
      <ChatInterfaceV6 />
    </div>
  );
}
