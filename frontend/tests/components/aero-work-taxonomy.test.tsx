import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { TaxonomyWizard } from '@/components/aero-work/taxonomy-wizard';
import { KnowledgeWiki } from '@/components/aero-work/knowledge-wiki';

// G003 분류체계 마법사(gongmuwon §6.6) — 니즈 파악→LLM 분류 검토→적용 3단계와
// 지식위키의 업무 분류 섹션(분류 카드/미분류 목록 분리)을 잠근다.

const proposeTaxonomyMock = vi.fn(async () => ({
  candidates: [
    { name: '예산 편성', description: '연간 예산 편성 관련 문서', file_ids: [1, 2] },
    { name: '출장 정산', description: '출장비 정산 관련 문서', file_ids: [3] },
  ],
  model: 'test-model',
}));
const applyTaxonomyMock = vi.fn(async () => ({ applied: 1 }));
const fetchTaxonomyMock = vi.fn(async () => ({ categories: [] as unknown[] }));
const fetchKnowledgeWikiMock = vi.fn(async () => ({ families: [] as unknown[] }));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    proposeTaxonomy: (...args: unknown[]) => proposeTaxonomyMock(...(args as [])),
    applyTaxonomy: (...args: unknown[]) => applyTaxonomyMock(...(args as [])),
    fetchTaxonomy: (...args: unknown[]) => fetchTaxonomyMock(...(args as [])),
    deleteTaxonomyCategory: vi.fn(async () => undefined),
    fetchKnowledgeWiki: (...args: unknown[]) => fetchKnowledgeWikiMock(...(args as [])),
    summarizeKnowledgeFile: vi.fn(async () => ({ summary: '' })),
  };
});

beforeEach(() => {
  proposeTaxonomyMock.mockClear();
  applyTaxonomyMock.mockClear();
  fetchTaxonomyMock.mockClear();
  fetchKnowledgeWikiMock.mockClear();
});

describe('TaxonomyWizard — 3단계 진행', () => {
  test('입력 → 후보 표시 → 선택 적용 시 applyTaxonomy 인자가 선택분만 반영된다', async () => {
    render(<TaxonomyWizard />);

    fireEvent.change(screen.getByPlaceholderText('기관 (예: OO시청)'), { target: { value: 'OO시청' } });
    fireEvent.change(screen.getByPlaceholderText('부서 (예: 총무과)'), { target: { value: '총무과' } });
    fireEvent.change(screen.getByPlaceholderText(/담당업무/), { target: { value: '예산 편성, 출장 정산' } });
    fireEvent.click(screen.getByRole('button', { name: 'LLM 분류 생성' }));

    expect(await screen.findByDisplayValue('예산 편성')).toBeInTheDocument();
    expect(screen.getByDisplayValue('출장 정산')).toBeInTheDocument();
    expect(proposeTaxonomyMock).toHaveBeenCalledWith(
      { organization: 'OO시청', department: '총무과', duties: '예산 편성, 출장 정산' },
      expect.any(String),
    );

    // 두 번째 후보('출장 정산')는 체크 해제 — 적용 시 첫 번째만 반영돼야 한다.
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[1]);

    fireEvent.click(screen.getByRole('button', { name: '적용' }));

    await waitFor(() => expect(applyTaxonomyMock).toHaveBeenCalled());
    expect(applyTaxonomyMock).toHaveBeenCalledWith(
      [{ name: '예산 편성', description: '연간 예산 편성 관련 문서', file_ids: [1, 2] }],
      expect.any(String),
    );
    expect(await screen.findByText(/분류가 적용됨/)).toBeInTheDocument();
  });

  test('필수 입력 누락 시 오류 메시지를 보이고 propose 를 호출하지 않는다', () => {
    render(<TaxonomyWizard />);
    fireEvent.click(screen.getByRole('button', { name: 'LLM 분류 생성' }));
    expect(screen.getByText('기관·부서·담당업무를 모두 입력할 것.')).toBeInTheDocument();
    expect(proposeTaxonomyMock).not.toHaveBeenCalled();
  });
});

describe('KnowledgeWiki — 업무 분류 섹션', () => {
  test('분류가 없으면 마법사 시작 배너를 보이고, 위키 목록은 색인 없음 문구를 유지한다', async () => {
    render(<KnowledgeWiki />);
    await waitFor(() => expect(fetchTaxonomyMock).toHaveBeenCalled());
    expect(await screen.findByText(/업무 분류가 아직 없음/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '분류체계 마법사 시작' })).toBeInTheDocument();
    expect(await screen.findByText('색인된 문서가 없음. 폴더를 등록·색인하면 여기에 정리됨.')).toBeInTheDocument();
  });

  test('분류가 있으면 분류 카드로 그룹핑하고 미분류 문서만 기존 목록에 남긴다', async () => {
    fetchTaxonomyMock.mockResolvedValueOnce({
      categories: [
        {
          id: 10,
          name: '예산 편성',
          description: '연간 예산 편성 관련 문서',
          sort_order: 0,
          files: [{ id: 1, rel_path: '2026-예산편성-지침.md', folder_name: '공무 샘플 지식', summary: '' }],
        },
      ],
    });
    fetchKnowledgeWikiMock.mockResolvedValueOnce({
      families: [
        {
          base: 'doc-a',
          representative: {
            id: 1,
            summary: '',
            folder_id: 1,
            folder_name: '공무 샘플 지식',
            rel_path: '2026-예산편성-지침.md',
            chunk_count: 3,
            is_latest: true,
          },
          items: [
            {
              id: 1,
              summary: '',
              folder_id: 1,
              folder_name: '공무 샘플 지식',
              rel_path: '2026-예산편성-지침.md',
              chunk_count: 3,
              is_latest: true,
            },
          ],
          has_versions: false,
        },
        {
          base: 'doc-b',
          representative: {
            id: 2,
            summary: '',
            folder_id: 1,
            folder_name: '공무 샘플 지식',
            rel_path: '2026-출장정산-양식.md',
            chunk_count: 2,
            is_latest: true,
          },
          items: [
            {
              id: 2,
              summary: '',
              folder_id: 1,
              folder_name: '공무 샘플 지식',
              rel_path: '2026-출장정산-양식.md',
              chunk_count: 2,
              is_latest: true,
            },
          ],
          has_versions: false,
        },
      ],
    });

    render(<KnowledgeWiki />);

    expect(await screen.findByText('업무 분류')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '분류 재구성' })).toBeInTheDocument();
    expect(screen.getByText('연간 예산 편성 관련 문서')).toBeInTheDocument();

    // 분류 카드 안에는 배정된 파일(예산편성-지침)만, 위키 목록에는 미분류 파일(출장정산-양식)만 남는다.
    const category = screen.getByText('예산 편성').closest('li')!;
    expect(category).toHaveTextContent('2026-예산편성-지침.md');
    expect(category).not.toHaveTextContent('2026-출장정산-양식.md');
    expect(screen.getByText('2026-출장정산-양식.md')).toBeInTheDocument();
  });

  test('비대표 판본이 분류에 배정되면 대표 문서도 미분류 목록에서 함께 빠진다(M2 중복 제거 확장)', async () => {
    fetchTaxonomyMock.mockResolvedValueOnce({
      categories: [
        {
          id: 11,
          name: '출장업무',
          description: '',
          sort_order: 0,
          // 비대표 판본(v1, id=102)만 분류에 배정됨 — 대표(id=101)는 분류 files 에 없다.
          files: [{ id: 102, rel_path: '2025-출장규정-v1.md', folder_name: '규정', summary: '' }],
        },
      ],
    });
    fetchKnowledgeWikiMock.mockResolvedValueOnce({
      families: [
        {
          base: 'doc-c',
          representative: {
            id: 101,
            summary: '',
            folder_id: 1,
            folder_name: '규정',
            rel_path: '2025-출장규정-v2.md',
            chunk_count: 2,
            is_latest: true,
          },
          items: [
            {
              id: 101,
              summary: '',
              folder_id: 1,
              folder_name: '규정',
              rel_path: '2025-출장규정-v2.md',
              chunk_count: 2,
              is_latest: true,
            },
            {
              id: 102,
              summary: '',
              folder_id: 1,
              folder_name: '규정',
              rel_path: '2025-출장규정-v1.md',
              chunk_count: 1,
              is_latest: false,
            },
          ],
          has_versions: true,
        },
      ],
    });

    render(<KnowledgeWiki />);

    expect(await screen.findByText('업무 분류')).toBeInTheDocument();
    // 대표(v2)도 판본 이력(v1)이 분류에 배정된 이상 미분류 목록에 중복 노출되지 않는다.
    expect(screen.queryByText('2025-출장규정-v2.md')).not.toBeInTheDocument();
    expect(screen.queryByText('색인된 문서가 없음. 폴더를 등록·색인하면 여기에 정리됨.')).not.toBeInTheDocument();
    expect(screen.getByText('미분류 문서가 없음.')).toBeInTheDocument();
  });

  test('분류 카드의 파일 항목에 요약이 있으면 1줄 표시한다(M2)', async () => {
    fetchTaxonomyMock.mockResolvedValueOnce({
      categories: [
        {
          id: 12,
          name: '예산업무',
          description: '',
          sort_order: 0,
          files: [
            {
              id: 201,
              rel_path: '2026-예산편성-지침.md',
              folder_name: '공무 샘플 지식',
              summary: '예산 편성 기준과 집행 절차 요약',
            },
          ],
        },
      ],
    });
    fetchKnowledgeWikiMock.mockResolvedValueOnce({ families: [] });

    render(<KnowledgeWiki />);

    expect(await screen.findByText('예산업무')).toBeInTheDocument();
    expect(screen.getByText('예산 편성 기준과 집행 절차 요약')).toBeInTheDocument();
  });

  test('분류 삭제 실패 시 인라인 오류 문구를 보인다(L5)', async () => {
    const { deleteTaxonomyCategory } = await import('@/lib/api');
    (deleteTaxonomyCategory as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('boom'));
    fetchTaxonomyMock.mockResolvedValueOnce({
      categories: [
        { id: 13, name: '예산업무', description: '', sort_order: 0, files: [] },
      ],
    });
    fetchKnowledgeWikiMock.mockResolvedValueOnce({ families: [] });

    render(<KnowledgeWiki />);

    expect(await screen.findByText('예산업무')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '분류 삭제' }));

    expect(await screen.findByText('분류 삭제 실패 — 다시 시도할 것.')).toBeInTheDocument();
  });
});
