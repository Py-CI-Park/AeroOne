import { AeroWorkShell } from '@/components/aero-work/aero-work-shell';
import { AppShell } from '@/components/layout/app-shell';
import { getAppTheme } from '@/lib/server-theme';

type SearchParams = {
  theme?: string;
};

export default async function AeroWorkPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);

  return (
    <AppShell title="Aero Work" theme={theme} showThemeSelector themePath="/aero-work" active="none" contentClassName="max-w-6xl">
      <AeroWorkShell />
    </AppShell>
  );
}
