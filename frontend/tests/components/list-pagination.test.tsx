import { fireEvent, render, screen } from '@testing-library/react';
import { ListPagination, paginate } from '@/components/admin/widgets/list-filter';

test('paginate slices exact pages and clamps out-of-range pages', () => {
  const items = [1, 2, 3, 4, 5];

  expect(paginate(items, 0, 2)).toEqual({ pageItems: [1, 2], page: 0, totalPages: 3 });
  expect(paginate(items, 1, 2)).toEqual({ pageItems: [3, 4], page: 1, totalPages: 3 });
  expect(paginate(items, 2, 2)).toEqual({ pageItems: [5], page: 2, totalPages: 3 });
  expect(paginate(items, -1, 2)).toEqual({ pageItems: [1, 2], page: 0, totalPages: 3 });
  expect(paginate(items, 99, 2)).toEqual({ pageItems: [5], page: 2, totalPages: 3 });
});

test('paginate returns all items on page 0 when pageSize is not positive', () => {
  expect(paginate(['a', 'b'], 3, 0)).toEqual({ pageItems: ['a', 'b'], page: 0, totalPages: 1 });
  expect(paginate(['a', 'b'], 3, -1)).toEqual({ pageItems: ['a', 'b'], page: 0, totalPages: 1 });
});

test('ListPagination disables boundary buttons and reports current page', () => {
  const onPageChange = vi.fn();
  const { rerender } = render(<ListPagination id="login-events" page={0} totalPages={3} onPageChange={onPageChange} />);

  expect(screen.getByText('페이지 1 / 3')).toBeInTheDocument();
  expect(screen.getByRole('navigation', { name: 'login-events 페이지 이동' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '이전 페이지' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '다음 페이지' })).not.toBeDisabled();

  fireEvent.click(screen.getByRole('button', { name: '다음 페이지' }));
  expect(onPageChange).toHaveBeenCalledWith(1);

  rerender(<ListPagination id="login-events" page={2} totalPages={3} onPageChange={onPageChange} />);
  expect(screen.getByText('페이지 3 / 3')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '이전 페이지' })).not.toBeDisabled();
  expect(screen.getByRole('button', { name: '다음 페이지' })).toBeDisabled();
});
