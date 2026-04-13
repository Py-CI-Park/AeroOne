import { resolveNewsletterTheme, resolveNewsletterThemeFromSearchParam } from '@/lib/theme';

test('resolves environment theme with light fallback', () => {
  expect(resolveNewsletterTheme('dark')).toBe('dark');
  expect(resolveNewsletterTheme('light')).toBe('light');
  expect(resolveNewsletterTheme('unexpected')).toBe('light');
  expect(resolveNewsletterTheme(undefined)).toBe('light');
});

test('uses query theme before environment theme', () => {
  expect(resolveNewsletterThemeFromSearchParam('dark', 'light')).toBe('dark');
  expect(resolveNewsletterThemeFromSearchParam('light', 'dark')).toBe('light');
  expect(resolveNewsletterThemeFromSearchParam(undefined, 'dark')).toBe('dark');
  expect(resolveNewsletterThemeFromSearchParam('invalid', 'dark')).toBe('dark');
  expect(resolveNewsletterThemeFromSearchParam('invalid', undefined)).toBe('light');
});
