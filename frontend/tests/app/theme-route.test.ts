import { GET } from '@/app/theme/route';
import { NEWSLETTER_THEME_COOKIE } from '@/lib/theme';

test('sets theme cookie and redirects to a safe relative next path', async () => {
  // 0.0.0.0 바인딩에서도 안전하도록 Location 은 origin 없는 상대 경로여야 한다.
  const request = new Request('http://0.0.0.0:29501/theme?theme=dark&next=/newsletters?slug=abc');

  const response = await GET(request);

  expect(response.status).toBe(307);
  expect(response.headers.get('location')).toBe('/newsletters?slug=abc');
  expect(response.headers.get('set-cookie')).toContain(`${NEWSLETTER_THEME_COOKIE}=dark`);
  expect(response.headers.get('set-cookie')).toContain('Path=/');
});

test('falls back to newsletters for invalid theme and unsafe redirect', async () => {
  const request = new Request('http://0.0.0.0:29501/theme?theme=invalid&next=https://example.com');

  const response = await GET(request);

  expect(response.status).toBe(307);
  expect(response.headers.get('location')).toBe('/newsletters');
  expect(response.headers.get('set-cookie')).toContain(`${NEWSLETTER_THEME_COOKIE}=light`);
});
