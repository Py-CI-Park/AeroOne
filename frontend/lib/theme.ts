export type NewsletterTheme = 'light' | 'dark';

export const NEWSLETTER_THEME_COOKIE = 'aeroone_theme';

export function resolveNewsletterTheme(value = process.env.NEWSLETTERS_THEME): NewsletterTheme {
  return value === 'dark' ? 'dark' : 'light';
}

export function resolveNewsletterThemeFromSearchParam(
  themeParam: string | undefined,
  envValue = process.env.NEWSLETTERS_THEME,
  cookieValue?: string,
): NewsletterTheme {
  if (themeParam === 'dark' || themeParam === 'light') {
    return themeParam;
  }

  if (cookieValue === 'dark' || cookieValue === 'light') {
    return cookieValue;
  }

  return resolveNewsletterTheme(envValue);
}
