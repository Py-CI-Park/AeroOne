export function getCookie(name: string) {
  if (typeof document === 'undefined') return '';
  const pair = document.cookie
    .split('; ')
    .find((item) => item.startsWith(`${name}=`));
  return pair ? decodeURIComponent(pair.split('=')[1] ?? '') : '';
}
