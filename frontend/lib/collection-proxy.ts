const COLLECTION_BACKEND_PREFIX = '/api/v1/collections';

export const ALLOWED_COLLECTIONS = ['document', 'civil', 'nsa'] as const;

export function isAllowedCollection(name: string): boolean {
  return (ALLOWED_COLLECTIONS as readonly string[]).includes(name);
}

export function buildCollectionUpstreamPath(segments: string[], search = ''): string {
  const cleanSegments = segments.filter(Boolean).map((segment) => encodeURIComponent(segment));
  const suffix = cleanSegments.length ? `/${cleanSegments.join('/')}` : '';
  return `${COLLECTION_BACKEND_PREFIX}${suffix}${search}`;
}
