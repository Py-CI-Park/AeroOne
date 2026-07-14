'use client';

import React from 'react';

import type { OfficeJobDetail } from '@/lib/types';

export type OfficeWorkspaceSelectionMode = 'reopen' | 'duplicate';

export interface OfficeWorkspaceSelection {
  sequence: number;
  mode: OfficeWorkspaceSelectionMode;
  job: OfficeJobDetail;
}

const OfficeWorkspaceContext = React.createContext<OfficeWorkspaceSelection | null>(null);

export function OfficeWorkspaceProvider({
  children,
  selection,
}: {
  children: React.ReactNode;
  selection: OfficeWorkspaceSelection | null;
}) {
  return <OfficeWorkspaceContext.Provider value={selection}>{children}</OfficeWorkspaceContext.Provider>;
}

/**
 * 현재 허브에서 선택한 작업 이력이다. 폼은 sequence 변경을 기준으로 reopen/duplicate
 * 요청을 한 번씩 적용하고, 원본 입력이 없는 경우에는 재첨부를 요구해야 한다.
 */
export function useOfficeWorkspaceSelection() {
  return React.useContext(OfficeWorkspaceContext);
}
