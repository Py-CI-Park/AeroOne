import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';

import { DocumentPanel } from '@/components/aero-work/document-panel';
import {
  composeAeroWorkDocument,
  downloadSavedAeroWorkDocument,
  fetchSavedAeroWorkDocuments,
  generateAeroWorkDocx,
  generateAeroWorkHwpx,
  previewAeroWorkDocument,
  streamAeroWorkCompose,
} from '@/lib/api';

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
    composeAeroWorkDocument: vi.fn(async () => ({ paragraphs: ['재생성된 문단1', '재생성된 문단2'], truncated: false })),
    streamAeroWorkCompose: vi.fn(),
    generateAeroWorkDocx: vi.fn(async () => new Blob()),
    generateAeroWorkHwpx: vi.fn(async () => new Blob()),
    downloadSavedAeroWorkDocument: vi.fn(async () => new Blob()),
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
    vi.mocked(generateAeroWorkDocx).mockClear();
    vi.mocked(generateAeroWorkHwpx).mockClear();
    vi.mocked(downloadSavedAeroWorkDocument).mockClear();
    vi.mocked(fetchSavedAeroWorkDocuments).mockResolvedValue({ documents: [] });
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

  test('빠르게 연속으로 변경하면 늦게 도착한 이전 미리보기 응답이 최신 렌더를 덮어쓰지 않는다(M1)', async () => {
    vi.useFakeTimers();
    let resolveFirst: (value: { html: string }) => void = () => {};
    let resolveSecond: (value: { html: string }) => void = () => {};
    const first = new Promise<{ html: string }>((resolve) => {
      resolveFirst = resolve;
    });
    const second = new Promise<{ html: string }>((resolve) => {
      resolveSecond = resolve;
    });
    vi.mocked(previewAeroWorkDocument).mockImplementationOnce(() => first).mockImplementationOnce(() => second);

    render(<DocumentPanel />);
    fireEvent.click(screen.getByLabelText('종이 미리보기'));

    fireEvent.change(screen.getByPlaceholderText(/본문을 입력하세요/), { target: { value: '첫 번째' } });
    await advance500();

    fireEvent.change(screen.getByPlaceholderText(/본문을 입력하세요/), { target: { value: '두 번째' } });
    await advance500();

    expect(previewAeroWorkDocument).toHaveBeenCalledTimes(2);

    // 두 번째(최신) 요청이 먼저 응답한다.
    await act(async () => {
      resolveSecond({ html: '<p>두 번째 결과</p>' });
      await Promise.resolve();
      await Promise.resolve();
    });
    const paper = screen.getByTestId('paper-preview');
    expect(paper.innerHTML).toContain('두 번째 결과');

    // 첫 번째(구) 요청이 뒤늦게 도착해도 최신 화면을 덮어쓰지 않아야 한다.
    await act(async () => {
      resolveFirst({ html: '<p>첫 번째 결과(구)</p>' });
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(paper.innerHTML).toContain('두 번째 결과');
    expect(paper.innerHTML).not.toContain('첫 번째 결과(구)');
  });

  test('미리보기 API 실패 시 오류 문구를 표시한다(L5)', async () => {
    vi.useFakeTimers();
    vi.mocked(previewAeroWorkDocument).mockRejectedValueOnce(new Error('boom'));

    render(<DocumentPanel />);
    fireEvent.change(screen.getByPlaceholderText(/본문을 입력하세요/), { target: { value: 'x' } });
    fireEvent.click(screen.getByLabelText('종이 미리보기'));
    await advance500();

    expect(previewAeroWorkDocument).toHaveBeenCalled();
    expect(screen.getByText('미리보기 생성 실패.')).toBeInTheDocument();
  });

  test('수정 지시 재생성 스트림이 실패(onError)하면 비스트리밍 composeAeroWorkDocument 로 폴백한다(L5)', async () => {
    vi.useFakeTimers();
    vi.mocked(streamAeroWorkCompose).mockImplementation(async (_payload, _csrf, handlers) => {
      handlers.onError('스트림 실패');
    });
    vi.mocked(composeAeroWorkDocument).mockResolvedValueOnce({
      paragraphs: ['폴백 문단1', '폴백 문단2'],
      truncated: false,
    });

    render(<DocumentPanel />);
    fireEvent.change(screen.getByPlaceholderText(/본문을 입력하세요/), {
      target: { value: '첫 문단\n둘째 문단' },
    });
    fireEvent.click(screen.getByLabelText('종이 미리보기'));
    await advance500();
    fireEvent.change(screen.getByPlaceholderText(/수정해줘/), { target: { value: '더 격식있게 고쳐줘' } });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '지시 반영 재생성' }));
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(composeAeroWorkDocument).toHaveBeenCalled();
    expect(screen.getByPlaceholderText(/본문을 입력하세요/)).toHaveValue('폴백 문단1\n폴백 문단2');
  });

  test('재생성 결과 문단 수가 이전의 50% 미만으로 급감하면 인라인 확인 후에만 교체한다(M3)', async () => {
    vi.useFakeTimers();
    vi.mocked(streamAeroWorkCompose).mockImplementation(async (_payload, _csrf, handlers) => {
      handlers.onDone(['짧아진 결과']);
    });

    render(<DocumentPanel />);
    fireEvent.change(screen.getByPlaceholderText(/본문을 입력하세요/), {
      target: { value: '문단1\n문단2\n문단3\n문단4' },
    });
    fireEvent.click(screen.getByLabelText('종이 미리보기'));
    await advance500();
    fireEvent.change(screen.getByPlaceholderText(/수정해줘/), { target: { value: '요약해줘' } });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '지시 반영 재생성' }));
      await Promise.resolve();
      await Promise.resolve();
    });

    // 4개 -> 1개(25%, 50% 미만) 이므로 즉시 교체되지 않고 확인 UI 가 떠야 한다.
    expect(screen.getByTestId('revision-drop-confirm')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/본문을 입력하세요/)).toHaveValue('문단1\n문단2\n문단3\n문단4');

    fireEvent.click(screen.getByRole('button', { name: '교체' }));
    expect(screen.getByPlaceholderText(/본문을 입력하세요/)).toHaveValue('짧아진 결과');
  });
  test('Word 생성 버튼은 DOCX API를 호출하고 기존 HWPX 버튼은 HWPX API를 호출한다', async () => {
    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:document') });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });

    try {
      render(<DocumentPanel />);
      fireEvent.change(screen.getByPlaceholderText('문서 제목'), { target: { value: '출장 보고' } });
      fireEvent.change(screen.getByPlaceholderText(/본문을 입력하세요/), { target: { value: '본문' } });

      await act(async () => {
        fireEvent.click(screen.getByTestId('docx-generate-button'));
        await Promise.resolve();
      });
      expect(generateAeroWorkDocx).toHaveBeenCalledWith(
        { title: '출장 보고', body: '본문', format: 'onepage' },
        expect.any(String),
      );
      expect(generateAeroWorkHwpx).not.toHaveBeenCalled();

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'HWPX 생성·다운로드' }));
        await Promise.resolve();
      });
      expect(generateAeroWorkHwpx).toHaveBeenCalledWith(
        { title: '출장 보고', body: '본문', format: 'onepage' },
        expect.any(String),
      );
      expect(anchorClick).toHaveBeenCalledTimes(2);
    } finally {
      anchorClick.mockRestore();
      Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: originalCreateObjectURL });
      Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: originalRevokeObjectURL });
    }
  });

  test('승인된 저장 문서의 Word 버튼은 DOCX 다운로드를 요청한다', async () => {
    vi.mocked(fetchSavedAeroWorkDocuments).mockResolvedValueOnce({
      documents: [{ id: 17, title: '승인 문서', format: 'onepage', status: 'approved', created_at: '2026-07-21T00:00:00Z' }],
    });
    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:document') });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });

    try {
      render(<DocumentPanel />);
      fireEvent.click(await screen.findByTestId('docx-download-button-17'));
      await act(async () => {
        await Promise.resolve();
      });

      expect(downloadSavedAeroWorkDocument).toHaveBeenCalledWith(17, 'docx');
      expect(anchorClick).toHaveBeenCalledOnce();
    } finally {
      anchorClick.mockRestore();
      Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: originalCreateObjectURL });
      Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: originalRevokeObjectURL });
    }
  });
});
