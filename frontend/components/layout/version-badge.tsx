'use client';

import React, { useEffect, useState } from 'react';

import { Icon } from '@/components/ui/icons';
import { Btn } from '@/components/ui/primitives';
import { APP_CONTACT, APP_VERSION, CHANGELOG } from '@/lib/changelog';

// 헤더의 버전 라벨. 누르면 릴리스 업데이트 내역과 문의 정보를 모달로 띄운다.
// AppShell 이 서버 컴포넌트라, 상호작용이 필요한 이 부분만 클라이언트 섬으로 분리한다.
export function VersionBadge() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        title="업데이트 날짜와 내역 보기"
        className="ml-1.5 rounded font-mono text-xs text-ink-3 transition-colors hover:text-accent hover:underline focus-visible:shadow-focus focus-visible:outline-none"
      >
        v{APP_VERSION}
      </button>

      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="업데이트 내역"
            data-testid="version-dialog"
            onClick={(event) => event.stopPropagation()}
            className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-lg border border-line bg-surface-raised p-6 text-ink-1 shadow-lg"
          >
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-xl font-semibold tracking-tight">업데이트 내역</h2>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="닫기"
                className="inline-flex h-7 w-7 items-center justify-center rounded text-ink-2 transition-colors hover:bg-surface-sunken hover:text-ink-1"
              >
                <Icon.x size={14} />
              </button>
            </div>

            <ul className="flex flex-col gap-5">
              {CHANGELOG.map((entry) => (
                <li key={entry.version}>
                  <div className="mb-1.5 flex items-baseline gap-2">
                    <span className="font-mono text-sm font-semibold text-accent">v{entry.version}</span>
                    <span className="font-mono text-xs text-ink-3">{entry.date}</span>
                  </div>
                  <ul className="ml-1 flex list-disc flex-col gap-1 pl-4 text-base text-ink-2">
                    {entry.items.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>

            <div className="mt-6 border-t border-line-subtle pt-4 text-sm text-ink-2">
              <span className="font-medium text-ink-1">문의:</span> {APP_CONTACT.name}
            </div>

            <div className="mt-5 flex justify-end">
              <Btn variant="secondary" size="sm" onClick={() => setOpen(false)}>
                닫기
              </Btn>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
