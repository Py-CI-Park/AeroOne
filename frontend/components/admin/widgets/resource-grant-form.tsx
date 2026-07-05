'use client';

import { ALLOWED_COLLECTIONS } from '@/lib/collection-proxy';
import { useMemo, useState } from 'react';
import { useAdminConsoleData } from '../admin-console-tabs';

export const RESOURCE_SAFE_PERMISSION_KEYS: Record<string, string[]> = {
  collection: ['collections.nsa.read', 'collections.read'],
};

// resource_id 검증은 backend is_valid_resource_id 정책과 동일하게 맞춘다(제출 전 인라인 차단).
function isValidResourceId(resourceId: string): boolean {
  if (resourceId !== resourceId.trim() || !resourceId || resourceId.length > 100) return false;
  if (resourceId.includes('..') || ['*', '/', '\\'].some((char) => resourceId.includes(char))) return false;
  return ![...resourceId].some((char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127);
}

type GrantErrors = Partial<Record<'subject_id' | 'resource_id' | 'permission_key', string>>;

export function ResourceGrantForm() {
  const { state, grantForm, setGrantForm, saveResourceGrant } = useAdminConsoleData();
  const [errors, setErrors] = useState<GrantErrors>({});
  const safePermissionKeys = RESOURCE_SAFE_PERMISSION_KEYS[grantForm.resource_type] ?? [];
  const subjects = grantForm.subject_type === 'user' ? state.users : state.groups;
  const subjectLabel = grantForm.subject_type === 'user' ? '사용자' : '그룹';
  const offeredResourceIds = useMemo(() => Array.from(new Set(['nsa', ...ALLOWED_COLLECTIONS])), []);

  function validate(): GrantErrors {
    const next: GrantErrors = {};
    if (!Number(grantForm.subject_id)) next.subject_id = `${subjectLabel}를 선택하세요.`;
    const resourceId = grantForm.resource_id;
    if (!resourceId.trim()) next.resource_id = '리소스 ID는 필수입니다.';
    else if (!isValidResourceId(resourceId)) next.resource_id = '리소스 ID에 공백/경로/특수문자를 사용할 수 없습니다.';
    if (!safePermissionKeys.includes(grantForm.permission_key)) next.permission_key = '허용된 리소스 권한을 선택하세요.';
    return next;
  }

  function updateResourceType(resource_type: string) {
    const nextPermissions = RESOURCE_SAFE_PERMISSION_KEYS[resource_type] ?? [];
    setGrantForm((current) => ({
      ...current,
      resource_type,
      permission_key: nextPermissions.includes(current.permission_key) ? current.permission_key : nextPermissions[0] ?? '',
    }));
  }

  async function submit() {
    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    await saveResourceGrant();
  }

  return (
    <div className="mb-4 grid gap-2 rounded-lg border border-slate-100 p-3 text-sm md:grid-cols-5">
      <select
        value={grantForm.subject_type}
        onChange={(event) => setGrantForm((current) => ({ ...current, subject_type: event.target.value as 'user' | 'group', subject_id: '' }))}
        className="rounded-md border border-slate-300 px-2 py-1"
        aria-label="grant subject type"
      >
        <option value="user">user</option>
        <option value="group">group</option>
      </select>
      <div>
        <select
          value={grantForm.subject_id}
          onChange={(event) => setGrantForm((current) => ({ ...current, subject_id: event.target.value }))}
          className="w-full rounded-md border border-slate-300 px-2 py-1"
          aria-label="grant subject"
        >
          <option value="">{subjectLabel} 선택</option>
          {subjects.map((subject) => (
            <option key={subject.id} value={subject.id}>{'username' in subject ? subject.username : subject.name}</option>
          ))}
        </select>
        {errors.subject_id ? <p className="mt-1 text-xs text-red-600">{errors.subject_id}</p> : null}
      </div>
      <select
        value={grantForm.resource_type}
        onChange={(event) => updateResourceType(event.target.value)}
        className="rounded-md border border-slate-300 px-2 py-1"
        aria-label="grant resource type"
      >
        <option value="collection">collection</option>
      </select>
      <div>
        <input
          list="admin-resource-grant-collection-ids"
          placeholder="resource id"
          value={grantForm.resource_id}
          onChange={(event) => setGrantForm((current) => ({ ...current, resource_id: event.target.value }))}
          className="w-full rounded-md border border-slate-300 px-2 py-1"
          aria-label="grant resource id"
        />
        <datalist id="admin-resource-grant-collection-ids">
          {offeredResourceIds.map((id) => <option key={id} value={id} />)}
        </datalist>
        {errors.resource_id ? <p className="mt-1 text-xs text-red-600">{errors.resource_id}</p> : null}
      </div>
      <div>
        <select
          value={safePermissionKeys.includes(grantForm.permission_key) ? grantForm.permission_key : ''}
          onChange={(event) => setGrantForm((current) => ({ ...current, permission_key: event.target.value }))}
          className="w-full rounded-md border border-slate-300 px-2 py-1"
          aria-label="grant permission key"
        >
          <option value="">리소스 권한 선택</option>
          {safePermissionKeys.map((key) => <option key={key} value={key}>{key}</option>)}
        </select>
        {errors.permission_key ? <p className="mt-1 text-xs text-red-600">{errors.permission_key}</p> : null}
      </div>
      <button
        type="button"
        onClick={() => setGrantForm((current) => ({ ...current, resource_type: 'collection', resource_id: 'nsa', permission_key: 'collections.nsa.read' }))}
        className="rounded-md border border-blue-200 px-3 py-2 text-xs font-semibold text-blue-700"
      >
        NSA 열람권 부여
      </button>
      <button type="button" onClick={() => void submit()} className="rounded-md bg-slate-900 px-3 py-2 text-xs font-semibold text-white md:col-span-4">리소스 권한 부여</button>
    </div>
  );
}
