import { cookies } from 'next/headers';

import { NEWSLETTER_THEME_COOKIE, resolveNewsletterThemeFromSearchParam } from '@/lib/theme';

export async function getAppTheme(themeParam?: string) {
  const cookieStore = await cookies();
  const cookieTheme = cookieStore.getAll().find((cookie) => cookie.name === NEWSLETTER_THEME_COOKIE)?.value;

  return resolveNewsletterThemeFromSearchParam(themeParam, process.env.NEWSLETTERS_THEME, cookieTheme);
}
