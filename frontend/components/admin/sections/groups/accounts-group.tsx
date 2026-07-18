'use client';

import { AdminUsersSection } from '../admin-users-section';
import { AdminRbacSection } from '../admin-rbac-section';
import { AdminSessionsSection } from '../admin-sessions-section';

export function AccountsGroup() {
  return (
    <div className="space-y-6">
      <AdminUsersSection />
      <AdminRbacSection />
      <AdminSessionsSection />
    </div>
  );
}
