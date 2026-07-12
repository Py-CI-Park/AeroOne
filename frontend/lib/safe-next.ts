const DEFAULT_NEXT = '/';

function hasControlChar(value: string): boolean {
  for (let i = 0; i < value.length; i += 1) {
    const code = value.charCodeAt(i);
    if (code < 0x20 || code === 0x7f) {
      return true;
    }
  }
  return false;
}

function isUnsafeShape(value: string): boolean {
  if (!value.startsWith('/')) {
    return true;
  }
  if (value.startsWith('//')) {
    return true;
  }
  if (value.includes('\\')) {
    return true;
  }
  if (hasControlChar(value)) {
    return true;
  }
  return false;
}

/**
 * Resolves an arbitrary "next" redirect target into a safe, same-origin path.
 * Rejects anything that is not a bare same-origin path (no scheme, no
 * protocol-relative `//`, no backslashes, no control characters, and no
 * percent-encoded bypass of those rules) and falls back to the dashboard.
 */
export function resolveSafeNext(raw: unknown): string {
  if (typeof raw !== 'string' || raw.length === 0) {
    return DEFAULT_NEXT;
  }

  if (isUnsafeShape(raw)) {
    return DEFAULT_NEXT;
  }

  let decoded: string;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    return DEFAULT_NEXT;
  }

  if (isUnsafeShape(decoded)) {
    return DEFAULT_NEXT;
  }

  return raw;
}
