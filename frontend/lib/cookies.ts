export const CSRF_COOKIE_NAME = process.env.NEXT_PUBLIC_CSRF_COOKIE_NAME ?? 'csrf_token';

export function getCookie(name: string) {
  if (typeof document === 'undefined') return '';
  const pair = document.cookie
    .split('; ')
    .find((item) => item.startsWith(`${name}=`));
  return pair ? decodeURIComponent(pair.split('=')[1] ?? '') : '';
}

export function getCsrfCookie() {
  return getCookie(CSRF_COOKIE_NAME);
}
