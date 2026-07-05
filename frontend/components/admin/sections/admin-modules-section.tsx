'use client';

import { useMemo, useState } from 'react';

import { Badge, moduleToDraft, useAdminConsoleData } from '../admin-console-tabs';
import { compareNumber, compareText, ListFilter, ListState, matchesListQuery, normalizeListQuery, stableSort } from '../widgets/list-filter';

const MODULE_SECTIONS = ['Newsletter', 'Document', 'Development'] as const;
const MODULE_STATUSES = ['active', 'development', 'coming_soon', 'hidden'] as const;
const MODULE_VISIBILITIES = ['public', 'admin'] as const;
const CUSTOM_SECTION_VALUE = '__custom__';
const MAX_SECTION_LENGTH = 40;

type ValidationTarget = 'create' | `module-${number}`;
type ModulePayload = {
  key?: string;
  title: string;
  href: string;
  section: string;
  status: string;
  visibility: string;
  sort_order: number;
};

function isKnownSection(section: string) {
  return MODULE_SECTIONS.includes(section as (typeof MODULE_SECTIONS)[number]);
}

function validateModulePayload(payload: ModulePayload) {
  const errors: string[] = [];
  if ('key' in payload && !payload.key?.trim()) errors.push('key는 필수입니다.');
  if (!payload.title.trim()) errors.push('title은 필수입니다.');
  if (!payload.href.trim()) errors.push('href는 필수입니다.');
  if (!payload.section.trim()) errors.push('section은 필수입니다.');
  if (payload.section.trim().length > MAX_SECTION_LENGTH) errors.push(`section은 ${MAX_SECTION_LENGTH}자 이하로 입력하세요.`);
  if (!Number.isFinite(payload.sort_order)) errors.push('sort_order는 숫자여야 합니다.');
  if (!MODULE_STATUSES.includes(payload.status as (typeof MODULE_STATUSES)[number])) errors.push('status 값이 올바르지 않습니다.');
  if (!MODULE_VISIBILITIES.includes(payload.visibility as (typeof MODULE_VISIBILITIES)[number])) errors.push('visibility 값이 올바르지 않습니다.');
  return errors;
}

function FieldErrors({ errors }: { errors?: string[] }) {
  if (!errors?.length) return null;
  return (
    <ul className="mt-2 space-y-1 text-xs text-rose-600" role="alert">
      {errors.map((error) => <li key={error}>{error}</li>)}
    </ul>
  );
}

function SectionFields({
  label,
  section,
  onChange,
}: {
  label: string;
  section: string;
  onChange: (section: string) => void;
}) {
  const selectValue = isKnownSection(section) ? section : CUSTOM_SECTION_VALUE;
  return (
    <div className="space-y-1">
      <select
        value={selectValue}
        onChange={(event) => onChange(event.target.value === CUSTOM_SECTION_VALUE ? '' : event.target.value)}
        className="w-full rounded-md border border-slate-300 px-2 py-1"
        aria-label={label}
      >
        {MODULE_SECTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
        <option value={CUSTOM_SECTION_VALUE}>커스텀…</option>
      </select>
      {selectValue === CUSTOM_SECTION_VALUE ? (
        <input
          value={section}
          onChange={(event) => onChange(event.target.value)}
          maxLength={MAX_SECTION_LENGTH}
          placeholder="custom section"
          className="w-full rounded-md border border-slate-300 px-2 py-1"
          aria-label={`${label} custom`}
        />
      ) : null}
    </div>
  );
}

function StatusSelect({ value, onChange, label }: { value: string; onChange: (value: string) => void; label: string }) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)} className="rounded-md border border-slate-300 px-2 py-1" aria-label={label}>
      {MODULE_STATUSES.map((status) => <option key={status} value={status}>{status === 'coming_soon' ? 'coming soon' : status}</option>)}
    </select>
  );
}

function VisibilitySelect({ value, onChange, label }: { value: string; onChange: (value: string) => void; label: string }) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)} className="rounded-md border border-slate-300 px-2 py-1" aria-label={label}>
      <option value="public">public</option>
      <option value="admin">admin (operator only)</option>
    </select>
  );
}

export function AdminModulesSection() {
  const { state, moduleDrafts, setModuleDrafts, moduleForm, setModuleForm, saveModule, toggleModule, removeModule, createModule } = useAdminConsoleData();
  const [validationErrors, setValidationErrors] = useState<Partial<Record<ValidationTarget, string[]>>>({});
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('sort-order-asc');
  const visibleModules = useMemo(() => {
    const query = normalizeListQuery(search);
    const filtered = state.modules.filter((module) => matchesListQuery(query, [module.key, module.title, module.section, module.status, module.href]));
    return stableSort(filtered, (a, b) => {
      if (sort === 'title-asc') return compareText(a.title, b.title) || compareText(a.key, b.key) || a.id - b.id;
      if (sort === 'section-asc') return compareText(a.section, b.section) || compareNumber(a.sort_order, b.sort_order) || compareText(a.key, b.key) || a.id - b.id;
      if (sort === 'key-desc') return compareText(b.key, a.key) || a.id - b.id;
      return compareNumber(a.sort_order, b.sort_order) || compareText(a.key, b.key) || a.id - b.id;
    });
  }, [search, sort, state.modules]);

  const setErrors = (target: ValidationTarget, errors: string[]) => {
    setValidationErrors((current) => {
      const next = { ...current };
      if (errors.length) next[target] = errors;
      else delete next[target];
      return next;
    });
  };

  const validateAndSave = async (module: (typeof state.modules)[number]) => {
    const draft = moduleDrafts[module.id] ?? moduleToDraft(module);
    const target: ValidationTarget = `module-${module.id}`;
    const errors = validateModulePayload(draft);
    setErrors(target, errors);
    if (errors.length) return;
    await saveModule(module);
  };

  const validateAndCreate = async () => {
    const errors = validateModulePayload(moduleForm);
    setErrors('create', errors);
    if (errors.length) return;
    await createModule();
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-semibold">대시보드 모듈 DB 관리</h2><Badge tone="green">CRUD / reorder / status</Badge></div>
      <ListFilter
        id="admin-modules"
        searchLabel="모듈 검색"
        searchPlaceholder="key / title / section"
        searchValue={search}
        onSearchChange={setSearch}
        sortLabel="모듈 정렬"
        sortValue={sort}
        onSortChange={setSort}
        sortOptions={[
          { value: 'sort-order-asc', label: 'sort_order 오름차순' },
          { value: 'title-asc', label: 'title 오름차순' },
          { value: 'section-asc', label: 'section 오름차순' },
          { value: 'key-desc', label: 'key 내림차순' },
        ]}
        totalCount={state.modules.length}
        filteredCount={visibleModules.length}
      />
      <ListState loading={state.busy === 'refresh'} error={state.error} totalCount={state.modules.length} filteredCount={visibleModules.length} emptyMessage="등록된 모듈이 없습니다." noMatchesMessage="검색 조건에 맞는 모듈이 없습니다." />
      <div className="grid gap-3 xl:grid-cols-2">
        {visibleModules.map((module) => {
          const draft = moduleDrafts[module.id] ?? moduleToDraft(module);
          const errorKey: ValidationTarget = `module-${module.id}`;
          return (
            <div key={module.key} className="rounded-lg border border-slate-100 p-3 text-sm">
              <div className="mb-2 flex items-center justify-between gap-2"><strong>{module.key}</strong><Badge tone={draft.is_enabled ? 'green' : 'amber'}>{draft.is_enabled ? 'enabled' : 'disabled'}</Badge></div>
              <div className="grid gap-2 md:grid-cols-2">
                <input value={draft.title} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, title: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${module.key} title`} />
                <SectionFields label={`${module.key} section`} section={draft.section} onChange={(section) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, section } }))} />
                <input value={draft.href} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, href: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${module.key} href`} />
                <StatusSelect value={draft.status} onChange={(status) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, status } }))} label={`${module.key} status`} />
                <input value={draft.badge} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, badge: event.target.value } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${module.key} badge`} />
                <input type="number" value={Number.isFinite(draft.sort_order) ? draft.sort_order : ''} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, sort_order: event.target.value === '' ? Number.NaN : Number(event.target.value) } }))} className="rounded-md border border-slate-300 px-2 py-1" aria-label={`${module.key} sort order`} />
              </div>
              <textarea value={draft.description ?? ''} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, description: event.target.value } }))} className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1" rows={2} aria-label={`${module.key} description`} />
              <label className="mt-2 inline-flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={draft.is_external} onChange={(event) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, is_external: event.target.checked } }))} /> external</label>
              <label className="mt-2 ml-3 inline-flex items-center gap-2 text-xs text-slate-600">audience<VisibilitySelect value={draft.visibility} onChange={(visibility) => setModuleDrafts((current) => ({ ...current, [module.id]: { ...draft, visibility } }))} label={`${module.key} visibility`} /></label>
              <FieldErrors errors={validationErrors[errorKey]} />
              <div className="mt-2 flex gap-2"><button type="button" disabled={state.busy === `module-${module.id}`} onClick={() => void validateAndSave(module)} className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">저장</button><button type="button" disabled={state.busy === `module-${module.id}`} onClick={() => void toggleModule(module)} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-40">{draft.is_enabled ? '비활성화' : '활성화'}</button><button type="button" disabled={state.busy === `module-${module.id}`} onClick={() => void removeModule(module)} className="rounded-md border border-rose-300 px-3 py-1.5 text-xs font-semibold text-rose-600 disabled:opacity-40">삭제</button></div>
            </div>
          );
        })}
      </div>
      <div className="mt-4 rounded-lg border border-dashed border-slate-300 p-3 text-sm">
        <p className="mb-2 font-semibold text-slate-700">새 모듈 추가</p>
        <div className="grid gap-2 md:grid-cols-3">
          <input value={moduleForm.key} onChange={(event) => setModuleForm((current) => ({ ...current, key: event.target.value }))} placeholder="key" className="rounded-md border border-slate-300 px-2 py-1" aria-label="new module key" />
          <input value={moduleForm.title} onChange={(event) => setModuleForm((current) => ({ ...current, title: event.target.value }))} placeholder="title" className="rounded-md border border-slate-300 px-2 py-1" aria-label="new module title" />
          <SectionFields label="new module section" section={moduleForm.section} onChange={(section) => setModuleForm((current) => ({ ...current, section }))} />
          <input value={moduleForm.href} onChange={(event) => setModuleForm((current) => ({ ...current, href: event.target.value }))} placeholder="href" className="rounded-md border border-slate-300 px-2 py-1" aria-label="new module href" />
          <StatusSelect value={moduleForm.status} onChange={(status) => setModuleForm((current) => ({ ...current, status }))} label="new module status" />
          <VisibilitySelect value={moduleForm.visibility} onChange={(visibility) => setModuleForm((current) => ({ ...current, visibility }))} label="new module visibility" />
        </div>
        <FieldErrors errors={validationErrors.create} />
        <button type="button" disabled={state.busy === 'module-create'} onClick={() => void validateAndCreate()} className="mt-2 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">모듈 추가</button>
      </div>
    </section>
  );
}
