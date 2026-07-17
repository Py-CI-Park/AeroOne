'use client';

import { AdminModulesSection } from '../admin-modules-section';
import { AdminTaxonomySection } from '../admin-taxonomy-section';
import { AdminSearchSection } from '../admin-search-section';

export function ContentGroup() {
  return (
    <div className="space-y-6">
      <AdminModulesSection />
      <AdminTaxonomySection />
      <AdminSearchSection />
    </div>
  );
}
