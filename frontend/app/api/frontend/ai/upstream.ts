import { getServerApiBase } from '@/lib/api';

const LOCAL_BACKEND_BASE = 'http://127.0.0.1:18437';

function normalizeBaseUrl(baseUrl: string) {
  return baseUrl.replace(/\/$/, '');
}

export function getAiBackendUrls(path: string) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const candidates = [LOCAL_BACKEND_BASE, getServerApiBase()]
    .map(normalizeBaseUrl)
    .filter((baseUrl, index, values) => values.indexOf(baseUrl) === index);

  return candidates.map((baseUrl) => `${baseUrl}${normalizedPath}`);
}
