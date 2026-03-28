'use client';

import { useEffect, useState } from 'react';

import { AppShell } from '@/components/layout/app-shell';
import { NewsletterList } from '@/components/newsletter/newsletter-list';
import { fetchNewsletters } from '@/lib/api';
import type { NewsletterItem } from '@/lib/types';

export default function NewslettersPage() {
  const [items, setItems] = useState<NewsletterItem[]>([]);

  useEffect(() => {
    void fetchNewsletters().then(setItems).catch(() => setItems([]));
  }, []);

  return (
    <AppShell title="뉴스레터 목록">
      <NewsletterList items={items} />
    </AppShell>
  );
}
