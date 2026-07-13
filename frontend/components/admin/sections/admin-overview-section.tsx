'use client';

import type { ReactNode } from 'react';

import { Badge, useAdminConsoleData } from '../admin-console-tabs';
import type { AdminOverviewModuleRef, AdminOverviewWindowCount } from '@/lib/types';

function StatCard({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase text-ink-3">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
      {hint ? <p className="text-sm text-ink-3">{hint}</p> : null}
    </div>
  );
}

function windowHint(window: AdminOverviewWindowCount, unit = '건') {
  const sign = window.delta > 0 ? '+' : '';
  return `이전 ${window.prior}${unit} · ${sign}${window.delta}${unit}`;
}

function ModuleBucket({ title, tone, modules }: { title: string; tone: 'red' | 'amber' | 'blue' | 'green'; modules: AdminOverviewModuleRef[] }) {
  return (
    <div className="rounded-lg border border-slate-100 p-3 text-sm">
      <div className="mb-2 flex items-center justify-between gap-2">
        <strong>{title}</strong>
        <Badge tone={tone}>{modules.length}개</Badge>
      </div>
      {modules.length === 0 ? (
        <p className="text-xs text-ink-3">없음</p>
      ) : (
        <ul className="space-y-1">
          {modules.map((module) => (
            <li key={module.key} className="flex items-center justify-between gap-2 text-xs text-slate-600">
              <span>{module.label}</span>
              <span className="font-mono text-ink-3">{module.key}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AdminOverviewSection() {
  const { state } = useAdminConsoleData();
  const overview = state.overview;

  if (!overview) {
    if (state.busy === 'refresh') {
      return (
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm text-ink-3" role="status" aria-live="polite">개요를 불러오는 중입니다.</p>
        </section>
      );
    }
    if (state.error) {
      return (
        <section className="rounded-xl border border-red-200 bg-red-50 p-4 shadow-sm">
          <p className="text-sm text-red-700" role="alert">{state.error}</p>
        </section>
      );
    }
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-sm text-ink-3">표시할 개요 데이터가 없습니다.</p>
      </section>
    );
  }

  const { users, logins, ai, sessions, modules, system, recent_audit: recentAudit } = overview;
  const recentAuditVisible = recentAudit.slice(0, 10);

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink-3">
        <span>생성 시각 {overview.generated_at}</span>
        <span>비교 기준(anchor) {overview.anchor}</span>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">사용자 통계</h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label="전체 사용자" value={users.total} hint={`활성 ${users.active} · 비활성 ${users.inactive}`} />
          <StatCard label="역할 구성" value={`admin ${users.roles.admin}`} hint={`user ${users.roles.user} · pending ${users.roles.pending}`} />
          <StatCard label="신규 가입" value={users.created.current} hint={windowHint(users.created, '명')} />
          <StatCard label="활성 세션 / 사용자" value={`${sessions.active_session_count} / ${sessions.active_user_count}`} hint="세션 수 / 접속 사용자 수" />
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">로그인 활동 (24h)</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <StatCard label="로그인 성공" value={logins.success.current} hint={windowHint(logins.success)} />
          <StatCard label="로그인 실패" value={logins.failure.current} hint={windowHint(logins.failure)} />
          <StatCard label="로그아웃" value={logins.logout.current} hint={windowHint(logins.logout)} />
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">AI 요청</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <StatCard label="AI 요청 총" value={ai.total.current} hint={windowHint(ai.total)} />
          <StatCard label="AI 요청 실패" value={ai.failure.current} hint={windowHint(ai.failure)} />
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">모듈 게이트 현황</h2>
        <p className="mb-2 text-xs text-ink-3">전체 {modules.total}개</p>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <ModuleBucket title="이용 불가" tone="red" modules={modules.buckets.unavailable} />
          <ModuleBucket title="예정" tone="amber" modules={modules.buckets.coming} />
          <ModuleBucket title="개발 중" tone="blue" modules={modules.buckets.development} />
          <ModuleBucket title="활성" tone="green" modules={modules.buckets.active} />
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">시스템</h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <StatCard label="버전 / 모드" value={`v${system.app_version}`} hint={system.app_env} />
          <StatCard label="데이터베이스 종류" value={system.database_kind} />
          <StatCard label="뉴스레터" value={system.newsletter_count} />
          <StatCard label="자산 상태" value={`${system.asset_health.ok} OK`} hint={`누락 ${system.asset_health.missing} · checksum ${system.asset_health.checksum_mismatch} · 설정 ${system.asset_health.misconfig}`} />
          <StatCard label="읽음 집계" value={system.read_summary.total_reads} hint={`행 ${system.read_summary.rows}개`} />
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">최근 감사 (최대 10건)</h2>
        {recentAuditVisible.length === 0 ? (
          <p className="text-sm text-ink-3">최근 감사 이벤트가 없습니다.</p>
        ) : (
          <div className="space-y-2">
            {recentAuditVisible.map((event) => (
              <div key={event.id} className="rounded-lg border border-slate-100 px-3 py-2 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-ink-3">{event.action}</span>
                  <Badge>{event.status}</Badge>
                </div>
                <p className="mt-1 text-slate-600">{event.target_type ?? '-'}</p>
                <p className="mt-1 text-xs text-ink-3">{event.created_at}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
