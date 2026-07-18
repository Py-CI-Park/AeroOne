import type { AiAttachment } from '@/lib/types';

// 계약: 첨부 개수 ≤5, 합계 content ≤200,000자, 확장자는 .md/.txt/.csv 만 허용한다.
export const MAX_ATTACHMENT_COUNT = 5;
export const MAX_ATTACHMENT_TOTAL_CHARS = 200000;
// FileReader 전체 읽기 전에 파일 크기를 선차단한다 — 대용량 파일이 탭을 얼리지 않게.
// (UTF-8 텍스트 200,000자 상한이므로 바이트 기준 여유치 800KB 이상은 읽을 필요가 없다.)
export const MAX_ATTACHMENT_FILE_BYTES = 800_000;
export const ALLOWED_ATTACHMENT_EXTENSIONS = ['.md', '.txt', '.csv'] as const;

export function isAllowedAttachmentName(name: string): boolean {
  const lower = name.toLowerCase();
  return ALLOWED_ATTACHMENT_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function totalAttachmentChars(attachments: AiAttachment[]): number {
  return attachments.reduce((sum, attachment) => sum + attachment.content.length, 0);
}

/**
 * 첨부 목록이 전송 한도를 넘지 않는지 사전 검증한다. 초과 시 사용자에게 보여줄 안내
 * 문자열을 반환하고(전송을 막는다), 문제가 없으면 빈 문자열을 반환한다.
 */
export function validateAttachments(attachments: AiAttachment[]): string {
  if (attachments.length > MAX_ATTACHMENT_COUNT) {
    return `첨부는 최대 ${MAX_ATTACHMENT_COUNT}개까지 가능합니다.`;
  }
  const invalid = attachments.find((attachment) => !isAllowedAttachmentName(attachment.name));
  if (invalid) {
    return `${invalid.name}: .md/.txt/.csv 파일만 첨부할 수 있습니다.`;
  }
  const total = totalAttachmentChars(attachments);
  if (total > MAX_ATTACHMENT_TOTAL_CHARS) {
    return `첨부 내용이 너무 큽니다(${total.toLocaleString()}자). 합계 ${MAX_ATTACHMENT_TOTAL_CHARS.toLocaleString()}자 이하로 줄여 주세요.`;
  }
  return '';
}

// 브라우저 File -> 텍스트 첨부. FileReader 는 콜백 기반이라 Promise 로 감싼다.
// 전체 읽기 전에 file.size 를 선차단해 대용량 파일이 메인 스레드를 얼리지 않게 한다.
export function readAttachmentFile(file: File): Promise<AiAttachment> {
  return new Promise((resolve, reject) => {
    if (file.size > MAX_ATTACHMENT_FILE_BYTES) {
      reject(new Error(`${file.name}: 파일이 너무 큽니다(${Math.round(file.size / 1024).toLocaleString()}KB). 800KB 이하만 첨부할 수 있습니다.`));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      resolve({ name: file.name, content: typeof reader.result === 'string' ? reader.result : '' });
    };
    reader.onerror = () => reject(reader.error ?? new Error(`파일을 읽지 못했습니다: ${file.name}`));
    reader.readAsText(file);
  });
}

/** 같은 이름의 첨부는 마지막 것만 남긴다(칩 key 충돌·중복 컨텍스트 방지). */
export function dedupeAttachmentsByName(attachments: AiAttachment[]): AiAttachment[] {
  const byName = new Map<string, AiAttachment>();
  for (const attachment of attachments) byName.set(attachment.name, attachment);
  return Array.from(byName.values());
}

export async function readAttachmentFiles(files: File[]): Promise<AiAttachment[]> {
  return Promise.all(files.map((file) => readAttachmentFile(file)));
}
