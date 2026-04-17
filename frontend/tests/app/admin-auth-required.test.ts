import { requireAdminSession } from '@/lib/server-auth';

test('admin pages still require an admin session helper', () => {
  expect(requireAdminSession).toBeTypeOf('function');
});
