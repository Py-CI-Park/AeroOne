import { AppShell } from '@/components/layout/app-shell';
import { ServiceCard } from '@/components/dashboard/service-card';
import { getAppTheme } from '@/lib/server-theme';

type SearchParams = {
  theme?: string;
};

const MODULES = [
  {
    id: 'newsletter',
    title: 'Newsletter',
    href: '/newsletters',
    badge: 'Active',
    active: true,
  },
  {
    id: 'announcement',
    title: 'Announcement',
    description: 'Company-wide announcements module.',
    href: '/newsletters',
    badge: 'Coming soon',
    active: false,
  },
  {
    id: 'schedule',
    title: 'Schedule',
    description: 'Shared calendar & event tracking.',
    href: '/newsletters',
    badge: 'Coming soon',
    active: false,
  },
  {
    id: 'document',
    title: 'Document',
    description: 'Long-form document archive.',
    href: '/newsletters',
    badge: 'Coming soon',
    active: false,
  },
] as const;

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);

  return (
    <AppShell title="Dashboard" theme={theme} themePath="/" active="dashboard" titleMeta="1 active · 3 coming soon">
      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {MODULES.map((module) => (
          <ServiceCard
            key={module.id}
            title={module.title}
            description={'description' in module ? module.description : undefined}
            href={module.href}
            badge={module.badge}
            active={module.active}
          />
        ))}
      </section>
    </AppShell>
  );
}
