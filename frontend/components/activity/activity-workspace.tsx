'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';

import { Btn, Tag } from '@/components/ui/primitives';
import { ApiError, fetchAuthActivity } from '@/lib/api';
import type { AuthActivityResponse } from '@/lib/types';

const LOGIN_NEXT_HREF = '/login?next=%2Factivity';

const ROLE_LABEL: Record<AuthActivityResponse['identity']['role'], string> = {
  admin: '관리자',
  user: '사용자',
  pending: '승인 대기',
};

const AUTH_EVENT_KIND_LABEL: Record<'login' | 'logout', string> = {
  login: '로그인',
  logout: '로그아웃',
};

const AUTH_EVENT_OUTCOME_LABEL: Record<'success' | 'failure', string> = {
  success: '성공',
  failure: '실패',
};

const AI_REQUEST_STATUS_LABEL: Record<'completed' | 'failed', string> = {
  completed: '완료',
  failed: '실패',
};

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date);
}

function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

export function ActivityWorkspace() {
  const [data, setData] = useState<AuthActivityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [unauthorized, setUnauthorized] = useState(false);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const retry = useCallback(() => {
    setReloadKey((key) => key + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setUnauthorized(false);
    setError('');
    fetchAuthActivity()
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (isUnauthorized(err)) {
          setUnauthorized(true);
        } else {
          setError(err instanceof Error ? err.message : '활동 정보를 불러오지 못했습니다.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (loading) {
    return (
      <div
        data-testid="activity-loading"
        className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-3"
      >
        활동 정보를 불러오는 중…
      </div>
    );
  }

  if (unauthorized) {
    return (
      <div
        data-testid="activity-unauthorized"
        className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2"
      >
        로그인이 필요합니다.
        <div className="mt-3">
          <Link href={LOGIN_NEXT_HREF} className="text-accent underline underline-offset-2">
            로그인 페이지로 이동
          </Link>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        data-testid="activity-error"
        className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2"
      >
        <div className="break-words">{error}</div>
        <div className="mt-3">
          <Btn data-testid="activity-retry" onClick={retry}>
            다시 시도
          </Btn>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const roleLabel = ROLE_LABEL[data.identity.role] ?? data.identity.role;

  return (
    <div className="flex w-full min-w-0 flex-col gap-8">
      <section aria-labelledby="activity-identity-heading" className="min-w-0">
        <h2 id="activity-identity-heading" className="mb-3 text-lg font-semibold text-ink-1">
          식별 정보
        </h2>
        <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
          <div className="min-w-0">
            <dt className="text-ink-3">아이디</dt>
            <dd className="break-words text-ink-1" data-testid="activity-username">
              {data.identity.username}
            </dd>
          </div>
          {data.identity.display_name ? (
            <div className="min-w-0">
              <dt className="text-ink-3">표시 이름</dt>
              <dd className="break-words text-ink-1" data-testid="activity-display-name">
                {data.identity.display_name}
              </dd>
            </div>
          ) : null}
          <div className="min-w-0">
            <dt className="text-ink-3">역할</dt>
            <dd className="text-ink-1" data-testid="activity-role">
              {roleLabel}
            </dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="activity-sessions-heading" className="min-w-0">
        <h2 id="activity-sessions-heading" className="mb-3 text-lg font-semibold text-ink-1">
          활성 세션
        </h2>
        {data.active_sessions.length === 0 ? (
          <p className="text-sm text-ink-3" data-testid="activity-sessions-empty">
            활성 세션이 없습니다.
          </p>
        ) : (
          <ul className="flex flex-col gap-2" data-testid="activity-sessions-list">
            {data.active_sessions.map((session, index) => (
              <li
                key={`${session.device_label}-${index}`}
                className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-line-subtle bg-surface-raised px-3 py-2 text-sm"
              >
                <span
                  className={`break-words ${session.state === 'current' ? 'font-semibold text-ink-1' : 'text-ink-2'}`}
                >
                  {session.device_label}
                </span>
                {session.state === 'current' ? (
                  <span data-testid="activity-session-current-badge">
                    <Tag tone="accent">현재 세션</Tag>
                  </span>
                ) : null}
                <span className="break-words text-ink-3">{formatDateTime(session.last_activity_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="activity-auth-events-heading" className="min-w-0">
        <h2 id="activity-auth-events-heading" className="mb-3 text-lg font-semibold text-ink-1">
          로그인 기록
        </h2>
        {data.auth_events.length === 0 ? (
          <p className="text-sm text-ink-3" data-testid="activity-auth-events-empty">
            로그인 기록이 없습니다.
          </p>
        ) : (
          <div className="w-full min-w-0 overflow-x-auto">
            <table className="w-full min-w-0 text-left text-sm" data-testid="activity-auth-events-table">
              <thead>
                <tr className="text-ink-3">
                  <th scope="col" className="py-1 pr-4 font-medium">
                    구분
                  </th>
                  <th scope="col" className="py-1 pr-4 font-medium">
                    결과
                  </th>
                  <th scope="col" className="py-1 font-medium">
                    시각
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.auth_events.map((event, index) => (
                  <tr key={index} className="border-t border-line-subtle">
                    <td className="break-words py-1 pr-4 text-ink-1">{AUTH_EVENT_KIND_LABEL[event.kind]}</td>
                    <td className={`break-words py-1 pr-4 ${event.outcome === 'failure' ? 'text-danger' : 'text-ink-1'}`}>
                      {AUTH_EVENT_OUTCOME_LABEL[event.outcome]}
                    </td>
                    <td className="break-words py-1 text-ink-3">{formatDateTime(event.occurred_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="activity-ai-requests-heading" className="min-w-0">
        <h2 id="activity-ai-requests-heading" className="mb-3 text-lg font-semibold text-ink-1">
          AI 요청
        </h2>
        {data.ai_requests.length === 0 ? (
          <p className="text-sm text-ink-3" data-testid="activity-ai-requests-empty">
            AI 요청 기록이 없습니다.
          </p>
        ) : (
          <div className="w-full min-w-0 overflow-x-auto">
            <table className="w-full min-w-0 text-left text-sm" data-testid="activity-ai-requests-table">
              <thead>
                <tr className="text-ink-3">
                  <th scope="col" className="py-1 pr-4 font-medium">
                    상태
                  </th>
                  <th scope="col" className="py-1 pr-4 font-medium">
                    모듈
                  </th>
                  <th scope="col" className="py-1 font-medium">
                    시각
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.ai_requests.map((request, index) => (
                  <tr key={index} className="border-t border-line-subtle">
                    <td className={`break-words py-1 pr-4 ${request.status === 'failed' ? 'text-danger' : 'text-ink-1'}`}>
                      {AI_REQUEST_STATUS_LABEL[request.status]}
                    </td>
                    <td className="break-words py-1 pr-4 text-ink-2">{request.module_key ?? '—'}</td>
                    <td className="break-words py-1 text-ink-3">{formatDateTime(request.occurred_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="activity-modules-heading" className="min-w-0">
        <h2 id="activity-modules-heading" className="mb-3 text-lg font-semibold text-ink-1">
          이용 가능 모듈
        </h2>
        {data.accessible_modules.length === 0 ? (
          <p className="text-sm text-ink-3" data-testid="activity-modules-empty">
            이용 가능한 모듈이 없습니다.
          </p>
        ) : (
          <ul className="flex flex-wrap gap-2" data-testid="activity-modules-list">
            {data.accessible_modules.map((module) => (
              <li key={module.key}>
                <Tag className="break-words">{module.label}</Tag>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export { LOGIN_NEXT_HREF };
