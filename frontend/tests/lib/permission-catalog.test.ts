import { describePermission, groupPermissionsByCategory } from '@/lib/permission-catalog';

test('Office Studio 권한은 범위가 명시된 메타데이터와 그룹으로 표시된다', () => {
  const officeUse = {
    key: 'office.use',
    label: 'Office Studio 사용',
    description: '보고서·차트·다이어그램 생성과 본인 산출물 관리를 사용합니다.',
    category: 'Office Studio',
  };
  const adminOfficeManage = {
    key: 'admin.office.manage',
    label: 'Office Studio 보존·격리 관리',
    description: '만료 작업 purge, 작업 격리 보관함 인벤토리·복원·삭제, 미해결 복구 증적 인벤토리·비가역 폐기, 운영 스토리지 회계 현황을 관리합니다.',
    category: 'Office Studio',
  };

  expect(describePermission('office.use')).toEqual(officeUse);
  expect(describePermission('admin.office.manage')).toEqual(adminOfficeManage);
  expect(groupPermissionsByCategory(['office.use', 'admin.office.manage'])).toEqual([
    {
      category: 'Office Studio',
      entries: [adminOfficeManage, officeUse],
    },
  ]);
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
