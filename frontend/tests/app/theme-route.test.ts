import { GET } from '@/app/theme/route';
import { NEWSLETTER_THEME_COOKIE } from '@/lib/theme';

test('sets theme cookie and redirects to a safe local next path', async () => {
  const request = new Request('http://localhost/theme?theme=dark&next=/newsletters?slug=abc');

  const response = await GET(request);

  expect(response.status).toBe(307);
  expect(response.headers.get('location')).toBe('http://localhost/newsletters?slug=abc');
  expect(response.headers.get('set-cookie')).toContain(`${NEWSLETTER_THEME_COOKIE}=dark`);
  expect(response.headers.get('set-cookie')).toContain('Path=/');
});

test('falls back to newsletters for invalid theme and unsafe redirect', async () => {
  const request = new Request('http://localhost/theme?theme=invalid&next=https://example.com');

  const response = await GET(request);

  expect(response.status).toBe(307);
  expect(response.headers.get('location')).toBe('http://localhost/newsletters');
  expect(response.headers.get('set-cookie')).toContain(`${NEWSLETTER_THEME_COOKIE}=light`);
});
