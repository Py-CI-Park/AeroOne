'use client';

import type { Permission } from '@/lib/types';

type PermissionCheckboxGridProps = {
  permissions: Permission[];
  value: string[];
  onChange: (value: string[]) => void;
  label?: string;
};

function groupPermissionKey(key: string): string {
  return key.split('.')[0] || '기타';
}

export function PermissionCheckboxGrid({ permissions, value, onChange, label = '권한' }: PermissionCheckboxGridProps) {
  const selected = new Set(value);
  const groups = permissions.reduce<Record<string, string[]>>((acc, permission) => {
    const group = groupPermissionKey(permission.key);
    acc[group] = acc[group] ?? [];
    acc[group].push(permission.key);
    return acc;
  }, {});

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
        {Object.entries(groups).map(([group, keys]) => (
          <div key={group} className="space-y-1">
            <p className="text-[11px] font-semibold uppercase text-slate-400">{group}</p>
            {keys.sort().map((key) => (
              <label key={key} className="flex items-center gap-2 text-xs text-slate-700">
                <input
                  type="checkbox"
                  checked={selected.has(key)}
                  onChange={(event) => toggle(key, event.target.checked)}
                  aria-label={`${label} ${key}`}
                />
                <span className="font-mono">{key}</span>
              </label>
            ))}
          </div>
        ))}
      </div>
    </fieldset>
  );
}
