import { LoginForm } from '@/components/auth/login-form';
import { AppShell } from '@/components/layout/app-shell';
import { getAppTheme } from '@/lib/server-theme';

type SearchParams = {
  theme?: string;
  next?: string;
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const theme = await getAppTheme(params.theme);

  return (
    <AppShell title="로그인" theme={theme} themePath="/login" contentClassName="max-w-5xl" hideTitle>
      <LoginForm next={params.next} />
    </AppShell>
  );
}
