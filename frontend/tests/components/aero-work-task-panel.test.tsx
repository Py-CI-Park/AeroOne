import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { TaskPanel } from '@/components/aero-work/task-panel';
import type { AeroWorkTask } from '@/lib/api';

const TASK: AeroWorkTask = {
  id: 7,
  title: '주간 보고서 작성',
  status: 'todo',
  due_date: '2099-01-31',
  tags: '보고, 주간',
  created_at: '2026-07-21T09:00:00',
  updated_at: '2026-07-21T09:00:00',
  done_at: null,
};

const fetchAeroWorkTasksMock = vi.fn();
const createAeroWorkTaskMock = vi.fn();
const updateAeroWorkTaskMock = vi.fn();
const deleteAeroWorkTaskMock = vi.fn();
const getCsrfCookieMock = vi.fn(() => 'csrf-token');

vi.mock('@/lib/api', () => ({
  fetchAeroWorkTasks: (...args: unknown[]) => fetchAeroWorkTasksMock(...args),
  createAeroWorkTask: (...args: unknown[]) => createAeroWorkTaskMock(...args),
  updateAeroWorkTask: (...args: unknown[]) => updateAeroWorkTaskMock(...args),
  deleteAeroWorkTask: (...args: unknown[]) => deleteAeroWorkTaskMock(...args),
}));

vi.mock('@/lib/cookies', () => ({
  getCsrfCookie: () => getCsrfCookieMock(),
}));

beforeEach(() => {
  fetchAeroWorkTasksMock.mockReset();
  createAeroWorkTaskMock.mockReset();
  updateAeroWorkTaskMock.mockReset();
  deleteAeroWorkTaskMock.mockReset();
  getCsrfCookieMock.mockClear();
  fetchAeroWorkTasksMock.mockResolvedValue({ tasks: [TASK] });
  createAeroWorkTaskMock.mockResolvedValue(TASK);
  updateAeroWorkTaskMock.mockResolvedValue(TASK);
  deleteAeroWorkTaskMock.mockResolvedValue(undefined);
});

describe('TaskPanel', () => {
  test('목록의 제목, 상태, 마감일과 태그를 렌더한다', async () => {
    render(<TaskPanel />);

    expect(await screen.findByText('주간 보고서 작성')).toBeInTheDocument();
    expect(screen.getByTestId('task-item')).toHaveTextContent('할일');
    expect(screen.getByText('마감 2099-01-31')).toBeInTheDocument();
    expect(screen.getByText('태그: 보고, 주간')).toBeInTheDocument();
    expect(screen.getByTestId('task-panel')).toBeInTheDocument();
    expect(screen.getByTestId('task-item')).toBeInTheDocument();
  });

  test('새 할 일을 제출하면 CSRF 토큰과 함께 생성 API를 호출한다', async () => {
    render(<TaskPanel />);
    await screen.findByText('주간 보고서 작성');

    fireEvent.change(screen.getByPlaceholderText('할 일 제목'), { target: { value: '회의 자료 준비' } });
    fireEvent.change(screen.getByLabelText('마감일(선택)'), { target: { value: '2026-08-01' } });
    fireEvent.change(screen.getByPlaceholderText('예산, 보고'), { target: { value: '회의, 준비' } });
    fireEvent.submit(screen.getByTestId('task-create-form'));

    await waitFor(() => {
      expect(createAeroWorkTaskMock).toHaveBeenCalledWith(
        { title: '회의 자료 준비', due_date: '2026-08-01', tags: '회의, 준비' },
        'csrf-token',
      );
    });
  });

  test('상태 선택을 바꾸면 PATCH API를 호출한다', async () => {
    render(<TaskPanel />);
    await screen.findByText('주간 보고서 작성');

    fireEvent.change(screen.getByLabelText('주간 보고서 작성 상태'), { target: { value: 'doing' } });

    await waitFor(() => {
      expect(updateAeroWorkTaskMock).toHaveBeenCalledWith(7, { status: 'doing' }, 'csrf-token');
    });
  });

  test('삭제를 누르면 삭제 API를 호출한다', async () => {
    render(<TaskPanel />);
    await screen.findByText('주간 보고서 작성');

    fireEvent.click(screen.getByRole('button', { name: '삭제' }));

    await waitFor(() => {
      expect(deleteAeroWorkTaskMock).toHaveBeenCalledWith(7, 'csrf-token');
    });
  });

  test('할 일이 없으면 빈 상태 메시지를 보인다', async () => {
    fetchAeroWorkTasksMock.mockResolvedValue({ tasks: [] });
    render(<TaskPanel />);

    expect(await screen.findByText('표시할 할 일이 없음. 위에서 새 할 일을 추가할 것.')).toBeInTheDocument();
  });
});
