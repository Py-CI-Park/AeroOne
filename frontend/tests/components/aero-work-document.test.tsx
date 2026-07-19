import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';

import { DocumentPanel } from '@/components/aero-work/document-panel';
import { composeAeroWorkDocument, previewAeroWorkDocument, streamAeroWorkCompose } from '@/lib/api';

// G005 gongmuwon §5.3 양식(종이) 미리보기 — '종이 미리보기' 토글이 서버 근사 렌더(HTML)를
// 요청·표시하고, '수정 지시' 재생성 루프가 instruction/previous_paragraphs 를 정확히 전달하며,
// 서버가 만든 HTML(사용자 입력은 escape 되어 있다는 전제)만 dangerouslySetInnerHTML 로
// 렌더해도 <script> 등 실행 가능한 태그가 주입되지 않음을 고정한다.

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    fetchSavedAeroWorkDocuments: vi.fn(async () => ({ documents: [] })),
    previewAeroWorkDocument: vi.fn(async () => ({
      html: '<div style="font-weight:bold">제목</div><p>본문 문단</p>',
    })),
    composeAeroWorkDocument: vi.fn(async () => ({ paragraphs: ['재생성된 문단1', '재생성된 문단2'] })),
    streamAeroWorkCompose: vi.fn(),
  };
});

async function advance500() {
  await act(async () => {
    vi.advanceTimersByTime(500);
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe('DocumentPanel — 종이 미리보기(G005)', () => {
  afterEach(() => {
    vi.mocked(previewAeroWorkDocument).mockClear();
    vi.mocked(composeAeroWorkDocument).mockClear();
    vi.mocked(streamAeroWorkCompose).mockReset();
    vi.useRealTimers();
  });

  test('토글을 켜면 현재 제목/본문으로 preview API 를 호출하고 반환 HTML 을 렌더한다', async () => {
    vi.useFakeTimers();
    render(<DocumentPanel />);

    fireEvent.change(screen.getByPlaceholderText('문서 제목'), { target: { value: '출장 보고' } });
    fireEvent.change(screen.getByPlaceholderText(/본문을 입력하세요/), { target: { value: '첫 문단' } });
    fireEvent.click(screen.getByLabelText('종이 미리보기'));

    await advance500();

    expect(previewAeroWorkDocument).toHaveBeenCalledWith(
      { format_id: 'onepage', title: '출장 보고', paragraphs: ['첫 문단'] },
      expect.any(String),
    );

    const paper = screen.getByTestId('paper-preview');
    expect(paper.innerHTML).toContain('본문 문단');
  });

  test('수정 지시 반영 재생성은 instruction·previous_paragraphs 를 전달하고 완료 시 본문을 교체·지시 입력을 비운다', async () => {
    vi.useFakeTimers();
    vi.mocked(streamAeroWorkCompose).mockImplementation(async (payload, _csrf, handlers) => {
      expect(payload).toMatchObject({
        title: '출장 보고',
        instruction: '더 격식있게 고쳐줘',
        previous_paragraphs: ['첫 문단', '둘째 문단'],
      });
      handlers.onDone(['재생성 문단1', '재생성 문단2']);
    });

    render(<DocumentPanel />);

    fireEvent.change(screen.getByPlaceholderText('문서 제목'), { target: { value: '출장 보고' } });
    fireEvent.change(screen.getByPlaceholderText(/본문을 입력하세요/), {
      target: { value: '첫 문단\n둘째 문단' },
    });
    fireEvent.click(screen.getByLabelText('종이 미리보기'));
    await advance500();
    expect(previewAeroWorkDocument).toHaveBeenCalled();

    fireEvent.change(screen.getByPlaceholderText(/수정해줘/), { target: { value: '더 격식있게 고쳐줘' } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '지시 반영 재생성' }));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(streamAeroWorkCompose).toHaveBeenCalled();
    expect(screen.getByPlaceholderText(/본문을 입력하세요/)).toHaveValue('재생성 문단1\n재생성 문단2');
    expect(screen.getByPlaceholderText(/수정해줘/)).toHaveValue('');
  });

  test('서버가 이스케이프한 HTML 만 렌더하며 사용자 입력에서 온 <script> 는 실행 가능한 형태로 주입되지 않는다', async () => {
    vi.useFakeTimers();
    vi.mocked(previewAeroWorkDocument).mockResolvedValueOnce({
      html: '<p>&lt;script&gt;alert(1)&lt;/script&gt; 사용자 입력 이스케이프됨</p>',
    });

    render(<DocumentPanel />);
    fireEvent.change(screen.getByPlaceholderText(/본문을 입력하세요/), { target: { value: 'x' } });
    fireEvent.click(screen.getByLabelText('종이 미리보기'));
    await advance500();
    expect(previewAeroWorkDocument).toHaveBeenCalled();

    const paper = screen.getByTestId('paper-preview');
    expect(paper.querySelector('script')).toBeNull();
    expect(paper.textContent).toContain('<script>alert(1)</script>');
  });
});
