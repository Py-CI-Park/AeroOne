'use client';

import React from 'react';

import { useEffect, useState } from 'react';
import { fetchAdminNewsletterDetail } from '@/lib/api';
import { NewsletterForm } from '@/components/admin/newsletter-form';
import type { NewsletterDetail } from '@/lib/types';

export function AdminNewsletterEditClient({ newsletterId }: { newsletterId: number }) {
  const [item, setItem] = useState<NewsletterDetail | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    void fetchAdminNewsletterDetail(newsletterId)
      .then(setItem)
      .catch((err: Error) => setError(err.message));
  }, [newsletterId]);

  if (error) {
    return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>;
  }

  if (!item) {
    return <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">데이터를 불러오는 중입니다.</div>;
  }

  return <NewsletterForm mode="edit" initialData={item} />;
}
