import { describePermission, groupPermissionsByCategory, PERMISSION_CATALOG } from '@/lib/permission-catalog';

test('permission catalog covers the admin permission taxonomy', () => {
  expect(Object.keys(PERMISSION_CATALOG)).toHaveLength(31);
});

test('describePermission returns Korean metadata for known keys', () => {
  expect(describePermission('admin.rbac.manage')).toMatchObject({
    key: 'admin.rbac.manage',
    label: 'RBAC 관리',
    category: '권한/RBAC',
  });
});

test('describePermission returns a safe fallback for unknown keys', () => {
  expect(describePermission('totally.unknown.key')).toEqual({
    key: 'totally.unknown.key',
    label: 'totally.unknown.key',
    description: '',
    category: '기타',
  });
});

test('groupPermissionsByCategory orders entries deterministically with 기타 last', () => {
  expect(groupPermissionsByCategory(['totally.unknown.key', 'ai.use', 'admin.rbac.manage', 'ai.history.manage_own'])).toEqual([
    {
      category: '권한/RBAC',
      entries: [describePermission('admin.rbac.manage')],
    },
    {
      category: 'AI 사용',
      entries: [describePermission('ai.history.manage_own'), describePermission('ai.use')],
    },
    {
      category: '기타',
      entries: [describePermission('totally.unknown.key')],
    },
  ]);
});
