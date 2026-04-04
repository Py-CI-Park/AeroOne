type LoggedFetchOptions = {
  label: string;
  baseUrl: string;
  path: string;
  init?: RequestInit;
  fetchImpl?: typeof fetch;
  log?: (message: string) => void;
  errorLog?: (message: string) => void;
};

const NEWSLETTER_BACKEND_PREFIX = '/api/v1/newsletters';
const NEWSLETTER_PROXY_PREFIX = '/api/frontend/newsletters';

export function buildNewsletterProxyPath(path: string) {
  if (!path.startsWith(`${NEWSLETTER_BACKEND_PREFIX}/`)) {
    throw new Error('Only newsletter read paths can be proxied');
  }

  return path.replace(NEWSLETTER_BACKEND_PREFIX, NEWSLETTER_PROXY_PREFIX);
}

export function buildNewsletterUpstreamPath(segments: string[], search = '') {
  const cleanSegments = segments.filter(Boolean).map((segment) => encodeURIComponent(segment));
  const suffix = cleanSegments.length ? `/${cleanSegments.join('/')}` : '';
  return `${NEWSLETTER_BACKEND_PREFIX}${suffix}${search}`;
}

export async function loggedServerFetchJson<T>({
  label,
  baseUrl,
  path,
  init,
  fetchImpl = fetch,
  log = console.info,
  errorLog = console.error,
}: LoggedFetchOptions): Promise<T> {
  const normalizedBaseUrl = baseUrl.replace(/\/$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;

  log(`[FRONTEND][FETCH] ${label} -> ${normalizedPath}`);
  try {
    const response = await fetchImpl(`${normalizedBaseUrl}${normalizedPath}`, {
      ...init,
      cache: 'no-store',
    });
    log(`[FRONTEND][FETCH] ${label} <- ${response.status} ${normalizedPath}`);

    if (!response.ok) {
      throw new Error(`Request failed: ${response.status} ${normalizedPath}`);
    }

    return (await response.json()) as T;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    errorLog(`[FRONTEND][FETCH] ${label} !! ${normalizedPath} ${message}`);
    throw error;
  }
}
