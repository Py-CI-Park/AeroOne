'use client';

import React from 'react';

import { fetchOfficeJob, fetchOfficeJobs, getOfficeArtifactProxyPath } from '@/lib/api';
import type { OfficeJobArtifact, OfficeJobDetail, OfficeJobListItem, OfficeJobListResponse } from '@/lib/types';
import type { OfficeWorkspaceSelectionMode } from '@/components/office-tools/workspace-context';

const MANIFEST_ARTIFACT_PATH = /^\/api\/v1\/office-tools\/jobs\/[0-9a-f]{32}\/artifacts\/[A-Za-z0-9-][A-Za-z0-9._-]*$/;

type OfficeJobHistoryProps = {
  onJobSelection: (mode: OfficeWorkspaceSelectionMode, job: OfficeJobDetail) => boolean;
};

function formatBytes(value: number) {
  if (!Number.isFinite(value) || value < 0) return '알 수 없음';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatUpdatedAt(value: string) {
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? value : new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeStyle: 'short' }).format(timestamp);
}

function provenanceLabel(job: OfficeJobListItem) {
  if (job.llm_used === true) return '생성 경로: AI 보조 사용';
  if (job.llm_used === false) return '생성 경로: AI 보조 미사용';
  return '생성 경로: 기록 없음';
}

function manifestArtifactLinks(artifacts: OfficeJobArtifact[]) {
  return artifacts.flatMap((artifact) => {
    if (!MANIFEST_ARTIFACT_PATH.test(artifact.download_url)) return [];

    try {
      return [{ ...artifact, href: getOfficeArtifactProxyPath(artifact.download_url) }];
    } catch {
      return [];
    }
  });
}

function ArtifactLinks({ artifacts }: { artifacts: OfficeJobArtifact[] }) {
  const links = manifestArtifactLinks(artifacts);
  if (links.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-3">
      <span className="font-medium text-ink-2">manifest 산출물</span>
      {links.map((artifact) => (
        <a key={artifact.filename} href={artifact.href} className="text-accent underline-offset-2 hover:underline">
          {artifact.filename} ({formatBytes(artifact.size_bytes)})
        </a>
      ))}
    </div>
  );
}

function JobCard({
  job,
  selecting,
  onSelect,
}: {
  job: OfficeJobListItem;
  selecting: boolean;
  onSelect: (mode: OfficeWorkspaceSelectionMode, job: OfficeJobListItem) => void;
}) {
  return (
    <li className="flex flex-col gap-3 rounded-lg border border-ink-3/20 bg-surface-raised p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium text-ink-1">{job.title?.trim() || '제목 없는 작업'}</p>
          <p className="mt-1 text-xs text-ink-3">{job.service} · {job.status}</p>
        </div>
        <time dateTime={job.updated_at} className="text-xs text-ink-3">업데이트 {formatUpdatedAt(job.updated_at)}</time>
      </div>

      <p className="text-xs text-ink-3">{provenanceLabel(job)}</p>
      {job.warnings.length > 0 ? (
        <ul className="rounded-md border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700">
          {job.warnings.map((warning, index) => <li key={`${job.job_id}-${index}`}>경고: {warning}</li>)}
        </ul>
      ) : (
        <p className="text-xs text-ink-3">경고 없음</p>
      )}
      <ArtifactLinks artifacts={job.artifacts} />

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={selecting}
          onClick={() => onSelect('reopen', job)}
          className="rounded-md border border-ink-3/30 px-3 py-1.5 text-sm font-medium text-ink-1 hover:bg-surface-sunken disabled:opacity-50"
        >
          다시 열기
        </button>
        <button
          type="button"
          disabled={selecting}
          onClick={() => onSelect('duplicate', job)}
          className="rounded-md border border-ink-3/30 px-3 py-1.5 text-sm font-medium text-ink-1 hover:bg-surface-sunken disabled:opacity-50"
        >
          설정 복제
        </button>
      </div>
    </li>
  );
}

/** Owner-scoped job history. Selection only publishes local workspace state; it never reruns a job. */
export function OfficeJobHistory({ onJobSelection }: OfficeJobHistoryProps) {
  const [history, setHistory] = React.useState<OfficeJobListResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [selectionError, setSelectionError] = React.useState('');
  const [activeJobId, setActiveJobId] = React.useState<string | null>(null);
  const [selectedJob, setSelectedJob] = React.useState<OfficeJobDetail | null>(null);

  const loadHistory = React.useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setHistory(await fetchOfficeJobs());
    } catch (cause) {
      setHistory(null);
      setError(cause instanceof Error ? cause.message : '작업 이력을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  async function selectJob(mode: OfficeWorkspaceSelectionMode, job: OfficeJobListItem) {
    setActiveJobId(job.job_id);
    setSelectionError('');
    try {
      const detail = await fetchOfficeJob(job.job_id);
      if (!onJobSelection(mode, detail)) {
        setSelectionError('지원하지 않는 작업 서비스라서 이 작업을 열 수 없습니다.');
        return;
      }
      setSelectedJob(detail);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : '작업 상세를 불러오지 못했습니다.';
      setSelectionError(`작업 상세를 불러오지 못했습니다: ${message}`);
    } finally {
      setActiveJobId(null);
    }
  }

  return (
    <section className="flex flex-col gap-4 rounded-xl border border-ink-3/20 bg-surface-sunken/30 p-4" aria-labelledby="office-job-history-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="office-job-history-title" className="font-semibold text-ink-1">내 작업 이력</h2>
          <p className="mt-1 text-sm text-ink-3">현재 계정에서 만든 Office Studio 작업만 표시합니다.</p>
        </div>
        <button
          type="button"
          onClick={() => void loadHistory()}
          disabled={loading}
          className="rounded-md border border-ink-3/30 px-3 py-1.5 text-sm font-medium text-ink-1 hover:bg-surface-raised disabled:opacity-50"
        >
          새로고침
        </button>
      </div>

      <p className="rounded-md border border-ink-3/15 bg-surface-raised px-3 py-2 text-xs text-ink-2">
        설정 복제는 새 작업을 실행하지 않습니다. 원본 파일 또는 텍스트가 이력에 없으면 다시 첨부해야 합니다.
      </p>

      {loading ? <p role="status" className="text-sm text-ink-3">작업 이력을 불러오는 중…</p> : null}
      {error ? <p role="alert" className="text-sm text-red-500">작업 이력을 불러오지 못했습니다: {error}</p> : null}
      {selectionError ? <p role="alert" className="text-sm text-red-500">{selectionError}</p> : null}
      {selectedJob ? (
        <p role="status" className="text-sm text-ink-2">
          {selectedJob.job_id} 작업의 {selectedJob.service} {selectedJob.status} 설정을 현재 작업 공간에 선택했습니다.
        </p>
      ) : null}

      {history ? (
        <>
          <p className="text-xs text-ink-3">
            사용량: 작업 {history.usage.job_count} / {history.usage.max_jobs_per_owner} · 저장소 {formatBytes(history.usage.total_bytes)} / {formatBytes(history.usage.max_bytes_per_owner)}
          </p>
          {history.jobs.length === 0 ? (
            <p className="rounded-md border border-dashed border-ink-3/25 px-3 py-4 text-sm text-ink-3">아직 작업 이력이 없습니다.</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {history.jobs.map((job) => (
                <JobCard key={job.job_id} job={job} selecting={activeJobId === job.job_id} onSelect={selectJob} />
              ))}
            </ul>
          )}
        </>
      ) : null}
    </section>
  );
}
