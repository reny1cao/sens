"use client";

import { QueryProvider } from "@/components/providers/QueryProvider";
import { DataSourceProvider } from "@/contexts/DataSourceContext";
import { ChatInterfaceV6 } from "@/components/chat/ChatInterfaceV6";
import { DataSourceSelector } from "@/components/datasource/DataSourceSelector";
import { Header } from "@/components/ui/header";

export default function ChatPage() {
  return (
    <DataSourceProvider>
      <QueryProvider>
        <div className="min-h-screen bg-gray-50 flex flex-col">
          <Header currentPage="chat" />

          <div className="flex-1 flex flex-col">
            <div className="flex-1 flex">
              <div className="flex-1 flex flex-col">
                <ChatInterfaceV6 />
              </div>
              <div className="w-80 border-l border-gray-200 bg-white p-4">
                <DataSourceSelector />
              </div>
            </div>
          </div>
        </div>
      </QueryProvider>
    </DataSourceProvider>
  );
}
