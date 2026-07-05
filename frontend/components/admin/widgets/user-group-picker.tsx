'use client';

import { useState } from 'react';
import { useAdminConsoleData } from '../admin-console-tabs';

type MembershipErrors = Partial<Record<'user_id' | 'group_id', string>>;

export function UserGroupPicker() {
  const { state, membershipForm, setMembershipForm, changeMembership } = useAdminConsoleData();
  const [errors, setErrors] = useState<MembershipErrors>({});

  function validate(): MembershipErrors {
    const next: MembershipErrors = {};
    if (!Number(membershipForm.user_id)) next.user_id = '사용자를 선택하세요.';
    if (!Number(membershipForm.group_id)) next.group_id = '그룹을 선택하세요.';
    return next;
  }

  async function submit(action: 'add' | 'remove') {
    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    await changeMembership(action);
  }

  return (
    <div className="mb-4 grid gap-2 rounded-lg border border-slate-100 p-3 text-sm md:grid-cols-4">
      <div>
        <select
          value={membershipForm.user_id}
          onChange={(event) => setMembershipForm((current) => ({ ...current, user_id: event.target.value }))}
          className="w-full rounded-md border border-slate-300 px-2 py-1"
          aria-label="membership user"
        >
          <option value="">사용자 선택</option>
          {state.users.map((user) => <option key={user.id} value={user.id}>{user.username}</option>)}
        </select>
        {errors.user_id ? <p className="mt-1 text-xs text-red-600">{errors.user_id}</p> : null}
      </div>
      <div>
        <select
          value={membershipForm.group_id}
          onChange={(event) => setMembershipForm((current) => ({ ...current, group_id: event.target.value }))}
          className="w-full rounded-md border border-slate-300 px-2 py-1"
          aria-label="membership group"
        >
          <option value="">그룹 선택</option>
          {state.groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
        </select>
        {errors.group_id ? <p className="mt-1 text-xs text-red-600">{errors.group_id}</p> : null}
      </div>
      <button type="button" onClick={() => void submit('add')} className="rounded-md bg-blue-600 px-3 py-2 text-xs font-semibold text-white">그룹 추가</button>
      <button type="button" onClick={() => void submit('remove')} className="rounded-md border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700">그룹 제거</button>
    </div>
  );
}
