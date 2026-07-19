import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { KnowledgePanel } from '@/components/aero-work/knowledge-panel';
import { highlightMatches } from '@/components/aero-work/knowledge-wiki';

// G002 실사 결함 회귀 고정 — 키워드 검색 라벨('일치 N회'/'검색 방식' 캡션)과
// 위키 <mark> 즉시 강조가 다시 '유사도' 오표기/미강조로 퇴행하지 않도록 잠근다.

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchKnowledgeFolders: vi.fn(async () => ({
      folders: [
        {
          id: 1,
          name: '공무 샘플 지식',
          path: 'D:\\kb',
          status: 'ready',
          file_count: 4,
          chunk_count: 4,
          last_indexed_at: null,
          last_error: null,
        },
      ],
    })),
    keywordSearchKnowledge: vi.fn(async () => ({
      hits: [
        {
          folder_id: 1,
          folder_name: '공무 샘플 지식',
          rel_path: '2026-예산편성-지침.md',
          chunk_index: 0,
          content: '예산 편성 원칙 … 예산 요구서 … 예산 심의회',
          score: 3,
        },
      ],
      model: 'keyword',
    })),
    searchKnowledge: vi.fn(async () => ({
      hits: [
        {
          folder_id: 1,
          folder_name: '공무 샘플 지식',
          rel_path: '2026-예산편성-지침.md',
          chunk_index: 0,
          content: '예산 편성 원칙',
          score: 0.721,
        },
      ],
      model: 'nomic-embed-text',
    })),
    fetchKnowledgeWiki: vi.fn(async () => ({ families: [] })),
  };
});

describe('highlightMatches — 위키 키워드 즉시 강조', () => {
  test('일치 구간을 mark 로 감싼다(다중 일치 + 대소문자 무시)', () => {
    const { container } = render(<p>{highlightMatches('예산안과 Budget 과 budget', 'budget')}</p>);
    const marks = container.querySelectorAll('mark');
    expect(marks).toHaveLength(2);
    expect(marks[0]).toHaveTextContent('Budget');
    expect(marks[1]).toHaveTextContent('budget');
  });

  test('빈 term·무일치는 원문을 그대로 반환한다', () => {
    const empty = render(<p>{highlightMatches('예산편성', '  ')}</p>);
    expect(empty.container.querySelectorAll('mark')).toHaveLength(0);
    expect(empty.container.textContent).toBe('예산편성');

    const miss = render(<p>{highlightMatches('예산편성', '워크숍')}</p>);
    expect(miss.container.querySelectorAll('mark')).toHaveLength(0);
    expect(miss.container.textContent).toBe('예산편성');
  });
});

describe('KnowledgePanel — 검색 결과 라벨', () => {
  test('키워드 모드는 일치 횟수 라벨과 즉시 검색 캡션을 쓴다', async () => {
    render(<KnowledgePanel />);
    await waitFor(() => expect(screen.getAllByText('공무 샘플 지식').length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole('button', { name: '키워드 검색' }));
    fireEvent.change(screen.getByPlaceholderText(/출장 정산 규정/), { target: { value: '예산' } });
    fireEvent.click(screen.getByRole('button', { name: '검색' }));

    await waitFor(() => expect(screen.getByText('일치 3회')).toBeInTheDocument());
    expect(screen.queryByText(/유사도 [0-9]/)).not.toBeInTheDocument();
    expect(screen.getByText('검색 방식: 키워드(즉시)')).toBeInTheDocument();
    expect(screen.queryByText(/임베딩 모델/)).not.toBeInTheDocument();
  });

  test('의미 모드는 유사도 라벨과 임베딩 모델 캡션을 유지한다', async () => {
    render(<KnowledgePanel />);
    await waitFor(() => expect(screen.getAllByText('공무 샘플 지식').length).toBeGreaterThan(0));

    fireEvent.change(screen.getByPlaceholderText(/출장 정산 규정/), { target: { value: '예산' } });
    fireEvent.click(screen.getByRole('button', { name: '검색' }));

    await waitFor(() => expect(screen.getByText('유사도 0.721')).toBeInTheDocument());
    expect(screen.getByText('임베딩 모델: nomic-embed-text')).toBeInTheDocument();
  });
});
