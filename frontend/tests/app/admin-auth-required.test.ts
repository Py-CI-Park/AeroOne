import React from 'react';

import AdminImportsPage from '@/app/admin/imports/page';
import AdminNewsletterEditPage from '@/app/admin/newsletters/[id]/edit/page';
import AdminNewsletterCreatePage from '@/app/admin/newsletters/new/page';
import AdminNewslettersPage from '@/app/admin/newsletters/page';
import { requireAdminSession } from '@/lib/server-auth';

const { requireAdminSessionMock } = vi.hoisted(() => ({
  requireAdminSessionMock: vi.fn(),
}));

vi.mock('@/lib/server-auth', () => ({
  requireAdminSession: requireAdminSessionMock,
}));

vi.mock('@/lib/server-theme', () => ({
  getAppTheme: vi.fn(() => Promise.resolve('light')),
}));

vi.mock('@/components/layout/app-shell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => React.createElement('div', null, children),
}));

vi.mock('@/components/admin/admin-newsletter-list', () => ({
  AdminNewsletterList: () => React.createElement('div', { 'data-testid': 'admin-newsletter-list' }),
}));

vi.mock('@/components/admin/import-panel', () => ({
  ImportPanel: () => React.createElement('div', { 'data-testid': 'import-panel' }),
}));

vi.mock('@/components/admin/newsletter-form', () => ({
  NewsletterForm: () => React.createElement('div', { 'data-testid': 'newsletter-form' }),
}));

vi.mock('@/components/admin/newsletter-edit-client', () => ({
  AdminNewsletterEditClient: () => React.createElement('div', { 'data-testid': 'newsletter-edit-client' }),
}));

beforeEach(() => {
  requireAdminSessionMock.mockResolvedValue({ id: 1, username: 'admin', role: 'admin' });
});

afterEach(() => {
  requireAdminSessionMock.mockReset();
});

test('admin page modules require an admin session before rendering', async () => {
  await AdminNewslettersPage({ searchParams: Promise.resolve({}) });
  await AdminImportsPage({ searchParams: Promise.resolve({}) });
  await AdminNewsletterCreatePage({ searchParams: Promise.resolve({}) });
  await AdminNewsletterEditPage({
    params: Promise.resolve({ id: '1' }),
    searchParams: Promise.resolve({}),
  });

  expect(requireAdminSession).toHaveBeenCalledTimes(4);
});
