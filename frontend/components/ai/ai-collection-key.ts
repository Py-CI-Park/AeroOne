import type { AiCitation, CollectionSearchResult } from '@/lib/types';

export function citationKey(citation: AiCitation | CollectionSearchResult): string {
  return `${citation.collection}:${citation.path}`;
}
