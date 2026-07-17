'use client';

import { AdminSystemSection } from '../admin-system-section';
import { AdminBackupsSection } from '../admin-backups-section';

export function SystemGroup() {
  return (
    <div className="space-y-6">
      <AdminSystemSection />
      <AdminBackupsSection />
    </div>
  );
}
