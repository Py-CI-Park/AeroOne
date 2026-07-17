import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { AiComposer } from '@/components/ai/ai-composer';

function noop() {}

function renderComposer(overrides: Partial<React.ComponentProps<typeof AiComposer>> = {}) {
  const onAttachmentsChange = vi.fn();
  const props: React.ComponentProps<typeof AiComposer> = {
    input: '',
    onInputChange: noop,
    onSubmit: (event) => event.preventDefault(),
    canSubmit: true,
    pending: false,
    onStop: noop,
    onRegenerate: noop,
    hasMessages: false,
    useSearch: false,
    onToggleSearch: noop,
    scope: { document: true, civil: true, nsa: false },
    onToggleScope: noop,
    nsaUnlocked: false,
    attachments: [],
    onAttachmentsChange,
    attachmentError: '',
    ...overrides,
  };
  render(<AiComposer {...props} />);
  return { onAttachmentsChange };
}

test('selecting a file through the clip button reads its text and reports it as an attachment', async () => {
  const { onAttachmentsChange } = renderComposer();

  const file = new File(['첨부 내용'], 'notes.txt', { type: 'text/plain' });
  const input = screen.getByLabelText('첨부 파일 선택') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [file] } });

  await waitFor(() =>
    expect(onAttachmentsChange).toHaveBeenCalledWith([{ name: 'notes.txt', content: '첨부 내용' }]),
  );
});

test('dropping a disallowed file surfaces an inline error and does not add an attachment', async () => {
  const { onAttachmentsChange } = renderComposer();

  const dropZone = screen.getByTestId('ai-chat-input').parentElement as HTMLElement;
  const file = new File(['data'], 'malware.exe', { type: 'application/octet-stream' });
  fireEvent.drop(dropZone, { dataTransfer: { files: [file] } });

  expect(await screen.findByText(/malware\.exe/)).toBeInTheDocument();
  expect(onAttachmentsChange).not.toHaveBeenCalled();
});

test('existing attachments render as removable chips', () => {
  const { onAttachmentsChange } = renderComposer({
    attachments: [{ name: 'a.md', content: 'x' }, { name: 'b.csv', content: 'y' }],
  });

  expect(screen.getByTestId('ai-attachments')).toHaveTextContent('a.md');
  expect(screen.getByTestId('ai-attachments')).toHaveTextContent('b.csv');

  fireEvent.click(screen.getByRole('button', { name: '첨부 제거: a.md' }));
  expect(onAttachmentsChange).toHaveBeenCalledWith([{ name: 'b.csv', content: 'y' }]);
});

test('an attachment limit error passed from the parent is displayed', () => {
  renderComposer({ attachmentError: '첨부는 최대 5개까지 가능합니다.' });
  expect(screen.getByRole('alert')).toHaveTextContent('첨부는 최대 5개까지 가능합니다.');
});
