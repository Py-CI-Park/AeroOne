import {
  ALLOWED_ATTACHMENT_EXTENSIONS,
  MAX_ATTACHMENT_COUNT,
  MAX_ATTACHMENT_TOTAL_CHARS,
  isAllowedAttachmentName,
  readAttachmentFile,
  totalAttachmentChars,
  validateAttachments,
} from '@/components/ai/ai-attachments';

test('isAllowedAttachmentName accepts only .md/.txt/.csv (case-insensitive)', () => {
  expect(isAllowedAttachmentName('notes.md')).toBe(true);
  expect(isAllowedAttachmentName('notes.TXT')).toBe(true);
  expect(isAllowedAttachmentName('data.CSV')).toBe(true);
  expect(isAllowedAttachmentName('report.pdf')).toBe(false);
  expect(isAllowedAttachmentName('script.js')).toBe(false);
  expect(isAllowedAttachmentName('no-extension')).toBe(false);
});

test('ALLOWED_ATTACHMENT_EXTENSIONS matches the documented contract', () => {
  expect(ALLOWED_ATTACHMENT_EXTENSIONS).toEqual(['.md', '.txt', '.csv']);
});

test('totalAttachmentChars sums content length across attachments', () => {
  expect(totalAttachmentChars([{ name: 'a.txt', content: 'abc' }, { name: 'b.txt', content: 'de' }])).toBe(5);
  expect(totalAttachmentChars([])).toBe(0);
});

test('validateAttachments passes for an empty or small valid set', () => {
  expect(validateAttachments([])).toBe('');
  expect(validateAttachments([{ name: 'a.md', content: 'hello' }])).toBe('');
});

test('validateAttachments rejects more than the max attachment count', () => {
  const attachments = Array.from({ length: MAX_ATTACHMENT_COUNT + 1 }, (_, i) => ({ name: `f${i}.txt`, content: 'x' }));
  expect(validateAttachments(attachments)).toContain(`최대 ${MAX_ATTACHMENT_COUNT}개`);
});

test('validateAttachments rejects a disallowed extension', () => {
  expect(validateAttachments([{ name: 'a.md', content: 'x' }, { name: 'evil.exe', content: 'y' }])).toContain('evil.exe');
});

test('validateAttachments rejects when the combined content exceeds the character limit', () => {
  const attachments = [{ name: 'a.txt', content: 'x'.repeat(MAX_ATTACHMENT_TOTAL_CHARS + 1) }];
  const message = validateAttachments(attachments);
  expect(message).toContain('너무 큽니다');
});

test('validateAttachments accepts content exactly at the character limit boundary', () => {
  const attachments = [{ name: 'a.txt', content: 'x'.repeat(MAX_ATTACHMENT_TOTAL_CHARS) }];
  expect(validateAttachments(attachments)).toBe('');
});

test('readAttachmentFile resolves the file name and text content via FileReader', async () => {
  const file = new File(['첨부 본문'], 'note.md', { type: 'text/markdown' });
  const attachment = await readAttachmentFile(file);
  expect(attachment).toEqual({ name: 'note.md', content: '첨부 본문' });
});
