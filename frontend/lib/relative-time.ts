export function formatRelativeTime(iso: string | null | undefined, now: Date | number = new Date()): string {
  if (!iso) return '';

  const targetTime = new Date(iso).getTime();
  const nowTime = now instanceof Date ? now.getTime() : now;
  if (!Number.isFinite(targetTime) || !Number.isFinite(nowTime)) return '';

  const diffMs = Math.max(0, nowTime - targetTime);
  const diffSeconds = Math.floor(diffMs / 1000);
  if (diffSeconds <= 10) return '방금';

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${Math.max(1, diffMinutes)}분 전`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}시간 전`;

  return `${Math.floor(diffHours / 24)}일 전`;
}
