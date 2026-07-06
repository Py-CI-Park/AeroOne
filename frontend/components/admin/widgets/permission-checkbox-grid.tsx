'use client';

import type { Permission } from '@/lib/types';
import { groupPermissionsByCategory } from '@/lib/permission-catalog';

type PermissionCheckboxGridProps = {
  permissions: Permission[];
  value: string[];
  onChange: (value: string[]) => void;
  label?: string;
};


export function PermissionCheckboxGrid({ permissions, value, onChange, label = '권한' }: PermissionCheckboxGridProps) {
  const selected = new Set(value);
  const groups = groupPermissionsByCategory(permissions.map((permission) => permission.key));

  function toggle(key: string, checked: boolean) {
    const next = new Set(selected);
    if (checked) next.add(key);
    else next.delete(key);
    onChange(Array.from(next).sort());
  }

  return (
    <fieldset className="rounded-md border border-slate-200 p-2 md:col-span-2">
      <legend className="px-1 text-xs font-semibold text-slate-600">{label}</legend>
      {permissions.length === 0 ? <p className="text-xs text-slate-500">사용 가능한 권한이 없습니다.</p> : null}
      <div className="grid gap-3 md:grid-cols-2">
        {groups.map((group) => (
          <div key={group.category} className="space-y-1">
            <p className="text-[11px] font-semibold text-slate-500">{group.category}</p>
            {group.entries.map((entry) => (
              <label key={entry.key} className="flex items-start gap-2 text-xs text-slate-700" title={entry.description || entry.key}>
                <input
                  type="checkbox"
                  checked={selected.has(entry.key)}
                  onChange={(event) => toggle(entry.key, event.target.checked)}
                  aria-label={`${label} ${entry.key}`}
                  className="mt-0.5"
                />
                <span>
                  <span className="block font-semibold text-slate-700">{entry.label}</span>
                  <span className="block font-mono text-[11px] text-slate-500">{entry.key}</span>
                  {entry.description ? <span className="block text-[11px] text-slate-500">{entry.description}</span> : null}
                </span>
              </label>
            ))}
          </div>
        ))}
      </div>
    </fieldset>
  );
}
