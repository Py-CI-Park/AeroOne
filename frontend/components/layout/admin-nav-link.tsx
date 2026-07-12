'use client';

// Deprecated: AccountMenu 로 대체되었다. AppShell 은 AccountMenu 를 직접 렌더링하며
// 이 파일은 이전 계약(AdminNavLink)과의 호환을 위한 얇은 재노출(re-export)만 담당한다.
// 실제 통합 지점은 AppShell -> AccountMenu 하나뿐이다.
export { AccountMenu as AdminNavLink } from '@/components/layout/account-menu';
