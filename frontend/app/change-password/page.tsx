import { ForceChangePasswordForm } from '@/components/auth/force-change-password-form';
import { AppShell } from '@/components/layout/app-shell';
import { getAppTheme } from '@/lib/server-theme';

type SearchParams = {
  theme?: string;
};

export default async function ChangePasswordPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);

  return (
    <AppShell title="비밀번호 변경" theme={theme} themePath="/change-password" contentClassName="max-w-5xl" hideTitle>
      <ForceChangePasswordForm />
    </AppShell>
  );
}
