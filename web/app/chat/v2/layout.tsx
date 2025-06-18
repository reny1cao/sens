'use client';

import { DataSourceProvider } from '@/contexts/DataSourceContext';
import { QueryProvider } from '@/components/providers/QueryProvider';

export default function ChatV2Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <QueryProvider>
      <DataSourceProvider>
        {children}
      </DataSourceProvider>
    </QueryProvider>
  );
}
