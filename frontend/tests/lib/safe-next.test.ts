import { resolveSafeNext } from '@/lib/safe-next';

test('returns the dashboard for non-string input', () => {
  expect(resolveSafeNext(undefined)).toBe('/');
  expect(resolveSafeNext(null)).toBe('/');
  expect(resolveSafeNext(123)).toBe('/');
  expect(resolveSafeNext({})).toBe('/');
  expect(resolveSafeNext(['/admin'])).toBe('/');
});

test('returns the dashboard for empty string input', () => {
  expect(resolveSafeNext('')).toBe('/');
});

test('returns the dashboard for values missing a leading slash', () => {
  expect(resolveSafeNext('admin')).toBe('/');
  expect(resolveSafeNext('admin/dashboard')).toBe('/');
});

test('returns the dashboard for protocol-relative (//) targets', () => {
  expect(resolveSafeNext('//evil.example')).toBe('/');
  expect(resolveSafeNext('//evil.example/path')).toBe('/');
});

test('returns the dashboard for values carrying a scheme', () => {
  expect(resolveSafeNext('javascript:alert(1)')).toBe('/');
  expect(resolveSafeNext('http://evil.example')).toBe('/');
  expect(resolveSafeNext('https://evil.example/path')).toBe('/');
  expect(resolveSafeNext('data:text/html,<script>alert(1)</script>')).toBe('/');
  expect(resolveSafeNext('mailto:test@example.com')).toBe('/');
});

test('returns the dashboard for backslash payloads', () => {
  expect(resolveSafeNext('/\\evil.example')).toBe('/');
  expect(resolveSafeNext('/\\\\evil.example')).toBe('/');
  expect(resolveSafeNext('/foo\\bar')).toBe('/');
});

test('returns the dashboard for control characters', () => {
  expect(resolveSafeNext('/foo\nbar')).toBe('/');
  expect(resolveSafeNext('/foo\tbar')).toBe('/');
  expect(resolveSafeNext('/foo\rbar')).toBe('/');
  expect(resolveSafeNext('/foo\u0000bar')).toBe('/');
  expect(resolveSafeNext('/foo\u007fbar')).toBe('/');
});

test('returns the dashboard for percent-encoded protocol-relative bypasses', () => {
  expect(resolveSafeNext('/%2F%2Fevil.example')).toBe('/');
  expect(resolveSafeNext('/%2f%2fevil.example')).toBe('/');
});

test('returns the dashboard for percent-encoded backslash bypasses', () => {
  expect(resolveSafeNext('/%5Cevil.example')).toBe('/');
  expect(resolveSafeNext('/foo%5Cbar')).toBe('/');
});

test('returns the dashboard for percent-encoded control character bypasses', () => {
  expect(resolveSafeNext('/foo%00bar')).toBe('/');
  expect(resolveSafeNext('/foo%0abar')).toBe('/');
  expect(resolveSafeNext('/foo%7fbar')).toBe('/');
});

test('returns the dashboard for malformed percent-encoding', () => {
  expect(resolveSafeNext('/foo%')).toBe('/');
  expect(resolveSafeNext('/foo%2')).toBe('/');
  expect(resolveSafeNext('/foo%zz')).toBe('/');
});

test('preserves a valid same-origin path', () => {
  expect(resolveSafeNext('/dashboard')).toBe('/dashboard');
  expect(resolveSafeNext('/documents/123')).toBe('/documents/123');
});

test('preserves a valid path with query string', () => {
  expect(resolveSafeNext('/documents?tab=preview')).toBe('/documents?tab=preview');
});

test('preserves a valid path with hash fragment', () => {
  expect(resolveSafeNext('/documents#section-2')).toBe('/documents#section-2');
});

test('preserves a valid path with query string and hash fragment combined', () => {
  expect(resolveSafeNext('/documents/123?tab=preview#section')).toBe('/documents/123?tab=preview#section');
});

test('preserves a root path', () => {
  expect(resolveSafeNext('/')).toBe('/');
});

test('preserves a benign percent-encoded value that decodes safely', () => {
  expect(resolveSafeNext('/search?q=%2Fpath')).toBe('/search?q=%2Fpath');
  expect(resolveSafeNext('/%EA%B0%80')).toBe('/%EA%B0%80');
});
