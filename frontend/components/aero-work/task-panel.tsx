'use client';

import { FormEvent, useCallback, useEffect, useState } from 'react';

import {
  createAeroWorkTask,
  deleteAeroWorkTask,
  fetchAeroWorkTasks,
  updateAeroWorkTask,
  type AeroWorkTask,
} from '@/lib/api';
import { getCsrfCookie } from '@/lib/cookies';

type TaskFilter = 'all' | 'todo' | 'doing' | 'done' | 'overdue';

type TaskForm = {
  title: string;
  dueDate: string;
  tags: string;
};

const EMPTY_FORM: TaskForm = { title: '', dueDate: '', tags: '' };

const FILTERS: Array<{ value: TaskFilter; label: string }> = [
  { value: 'all', label: '전체' },
  { value: 'todo', label: '할일' },
  { value: 'doing', label: '진행' },
  { value: 'done', label: '완료' },
  { value: 'overdue', label: '기한지난' },
];

const STATUS_LABEL: Record<AeroWorkTask['status'], string> = {
  todo: '할일',
  doing: '진행',
  done: '완료',
};

function isOverdue(task: AeroWorkTask): boolean {
  return task.status !== 'done' && task.due_date !== null && task.due_date < new Date().toISOString().slice(0, 10);
}

export function TaskPanel() {
  const [tasks, setTasks] = useState<AeroWorkTask[]>([]);
  const [filter, setFilter] = useState<TaskFilter>('all');
  const [form, setForm] = useState<TaskForm>(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (selectedFilter: TaskFilter) => {
    setLoading(true);
    try {
      const data = await fetchAeroWorkTasks(
        selectedFilter === 'all' ? undefined : selectedFilter === 'overdue' ? { overdue: true } : { status: selectedFilter },
      );
      setTasks(data.tasks);
      setError(null);
    } catch {
      setError('할 일을 불러오지 못했음. 로그인 상태를 확인할 것.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(filter);
  }, [filter, load]);

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const title = form.title.trim();
    if (!title) return;

    setSaving(true);
    setError(null);
    try {
      await createAeroWorkTask(
        { title, due_date: form.dueDate || null, tags: form.tags.trim() },
        getCsrfCookie(),
      );
      setForm(EMPTY_FORM);
      await load(filter);
    } catch {
      setError('할 일 저장에 실패했음.');
    } finally {
      setSaving(false);
    }
  };

  const handleStatusChange = async (task: AeroWorkTask, status: AeroWorkTask['status']) => {
    if (status === task.status) return;
    setError(null);
    try {
      await updateAeroWorkTask(task.id, { status }, getCsrfCookie());
      await load(filter);
    } catch {
      setError('상태 변경에 실패했음.');
    }
  };

  const handleDoneToggle = async (task: AeroWorkTask) => {
    await handleStatusChange(task, task.status === 'done' ? 'todo' : 'done');
  };

  const handleDelete = async (task: AeroWorkTask) => {
    setError(null);
    try {
      await deleteAeroWorkTask(task.id, getCsrfCookie());
      await load(filter);
    } catch {
      setError('할 일 삭제에 실패했음.');
    }
  };

  return (
    <section className="mt-4 space-y-4" data-testid="task-panel">
      {error ? (
        <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-600" role="alert">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-1" aria-label="할 일 상태 필터">
        {FILTERS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            onClick={() => setFilter(value)}
            aria-pressed={filter === value}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              filter === value ? 'bg-accent text-accent-on' : 'bg-surface-sunken text-ink-2 hover:bg-accent-soft'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <form onSubmit={handleCreate} className="rounded-xl border border-line-subtle bg-surface-base p-4" data-testid="task-create-form">
        <p className="text-sm font-semibold text-ink-1">새 할 일</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <input
            value={form.title}
            onChange={(event) => setForm((previous) => ({ ...previous, title: event.target.value }))}
            placeholder="할 일 제목"
            maxLength={300}
            required
            className="sm:col-span-2 rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1"
          />
          <label className="flex flex-col gap-1 text-xs text-ink-3">
            마감일(선택)
            <input
              type="date"
              value={form.dueDate}
              onChange={(event) => setForm((previous) => ({ ...previous, dueDate: event.target.value }))}
              className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-ink-3">
            태그(쉼표로 구분, 선택)
            <input
              value={form.tags}
              onChange={(event) => setForm((previous) => ({ ...previous, tags: event.target.value }))}
              placeholder="예산, 보고"
              className="rounded-lg border border-line-subtle bg-surface-raised px-3 py-2 text-sm text-ink-1"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={saving || !form.title.trim()}
          className="mt-3 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-on disabled:opacity-50"
        >
          {saving ? '저장 중…' : '할 일 추가'}
        </button>
      </form>

      <div>
        <p className="text-sm font-semibold text-ink-1">할 일 목록</p>
        {loading ? (
          <p className="mt-2 text-sm text-ink-3">불러오는 중…</p>
        ) : tasks.length === 0 ? (
          <p className="mt-2 rounded-lg border border-dashed border-line-subtle bg-surface-base px-3 py-4 text-sm text-ink-3">
            표시할 할 일이 없음. 위에서 새 할 일을 추가할 것.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {tasks.map((task) => {
              const overdue = isOverdue(task);
              return (
                <li
                  key={task.id}
                  data-testid="task-item"
                  className={`flex flex-wrap items-center gap-3 rounded-lg border px-3 py-2 ${
                    overdue ? 'border-rose-500/50 bg-rose-500/10' : 'border-line-subtle bg-surface-base'
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink-1">{task.title}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-1 text-xs text-ink-3">
                      <span className="rounded-full bg-surface-sunken px-2 py-0.5">{STATUS_LABEL[task.status]}</span>
                      {overdue ? <span className="rounded-full bg-rose-500/15 px-2 py-0.5 font-medium text-rose-600">기한 지남</span> : null}
                      {task.due_date ? <span>마감 {task.due_date}</span> : <span>마감일 없음</span>}
                      {task.tags ? <span>태그: {task.tags}</span> : null}
                    </div>
                  </div>
                  <select
                    value={task.status}
                    onChange={(event) => void handleStatusChange(task, event.target.value as AeroWorkTask['status'])}
                    aria-label={`${task.title} 상태`}
                    className="rounded-lg border border-line-subtle bg-surface-raised px-2 py-1.5 text-xs text-ink-1"
                  >
                    <option value="todo">할일</option>
                    <option value="doing">진행</option>
                    <option value="done">완료</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => void handleDoneToggle(task)}
                    className="rounded px-2 py-1 text-xs text-ink-2 hover:bg-surface-sunken"
                  >
                    {task.status === 'done' ? '완료 취소' : '완료 처리'}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDelete(task)}
                    className="rounded px-2 py-1 text-xs text-rose-600 hover:bg-rose-500/10"
                  >
                    삭제
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
