'use client';

import React, { useMemo } from 'react';

type MarkdownBlock =
  | { type: 'heading'; level: number; text: string }
  | { type: 'paragraph'; text: string }
  | { type: 'blockquote'; text: string }
  | { type: 'unordered-list'; items: string[] }
  | { type: 'ordered-list'; items: string[] }
  | { type: 'task-list'; items: Array<{ checked: boolean; text: string }> }
  | { type: 'code'; language: string; code: string }
  | { type: 'rule' }
  | { type: 'table'; headers: string[]; rows: string[][] };

function isSafeMarkdownHref(rawHref: string): boolean {
  const href = rawHref.trim();
  if (!href) return false;
  if ((href.startsWith('/') && !href.startsWith('//')) || href.startsWith('#')) return true;
  try {
    const url = new URL(href);
    return url.protocol === 'http:' || url.protocol === 'https:' || url.protocol === 'mailto:';
  } catch {
    return false;
  }
}

function parseInlineMarkdown(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const tokenPattern = /(`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*|\*([^*]+)\*)/g;
  let lastIndex = 0;
  let tokenIndex = 0;
  for (const match of text.matchAll(tokenPattern)) {
    if (match.index == null) continue;
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const key = `inline-${tokenIndex}`;
    if (match[2]) {
      nodes.push(
        <code key={key} className="rounded bg-surface-raised px-1 py-0.5 font-mono text-[0.92em] text-ink-1">
          {match[2]}
        </code>,
      );
    } else if (match[3] && match[4]) {
      const label = match[3];
      const href = match[4];
      if (isSafeMarkdownHref(href)) {
        nodes.push(
          <a key={key} href={href.trim()} target="_blank" rel="noopener noreferrer" className="text-accent underline underline-offset-2">
            {label}
          </a>,
        );
      } else {
        nodes.push(`${label} (${href})`);
      }
    } else if (match[5]) {
      nodes.push(
        <strong key={key} className="font-semibold text-ink-1">
          {match[5]}
        </strong>,
      );
    } else if (match[6]) {
      nodes.push(
        <em key={key} className="italic">
          {match[6]}
        </em>,
      );
    }
    lastIndex = match.index + match[0].length;
    tokenIndex += 1;
  }
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

function isTableDivider(line: string): boolean {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

function splitTableCells(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim());
}

function isMarkdownBlockStart(line: string): boolean {
  return (
    /^#{1,4}\s+/.test(line) ||
    /^>\s?/.test(line) ||
    /^[-*+]\s+/.test(line) ||
    /^\d+\.\s+/.test(line) ||
    /^-{3,}\s*$/.test(line) ||
    /^```/.test(line)
  );
}

function parseMarkdownBlocks(content: string): MarkdownBlock[] {
  const lines = content.replace(/\r\n/g, '\n').split('\n');
  const blocks: MarkdownBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (line.trim() === '') {
      index += 1;
      continue;
    }

    if (line.startsWith('```')) {
      const language = line.slice(3).trim();
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith('```')) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push({ type: 'code', language, code: codeLines.join('\n') });
      continue;
    }

    // (.*) 허용: 스트리밍 중 '## '(제목 텍스트 도착 전)도 heading 으로 소비해야 한다 —
    // (.+) 이면 아래 폴백이 한 줄도 소비하지 못해 무한 루프가 된다.
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2].trim() });
      index += 1;
      continue;
    }

    if (/^-{3,}\s*$/.test(line)) {
      blocks.push({ type: 'rule' });
      index += 1;
      continue;
    }

    if (index + 1 < lines.length && line.includes('|') && isTableDivider(lines[index + 1])) {
      const headers = splitTableCells(line);
      const rows: string[][] = [];
      index += 2;
      while (index < lines.length && lines[index].includes('|') && lines[index].trim() !== '') {
        rows.push(splitTableCells(lines[index]));
        index += 1;
      }
      blocks.push({ type: 'table', headers, rows });
      continue;
    }

    if (/^>\s?/.test(line)) {
      const quoteLines: string[] = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) {
        quoteLines.push(lines[index].replace(/^>\s?/, ''));
        index += 1;
      }
      blocks.push({ type: 'blockquote', text: quoteLines.join('\n') });
      continue;
    }

    if (/^[-*+]\s+\[[ xX]\]\s+/.test(line)) {
      const items: Array<{ checked: boolean; text: string }> = [];
      while (index < lines.length && /^[-*+]\s+\[[ xX]\]\s+/.test(lines[index])) {
        const match = /^[-*+]\s+\[([ xX])\]\s+(.+)$/.exec(lines[index]);
        if (match) items.push({ checked: match[1].toLowerCase() === 'x', text: match[2] });
        index += 1;
      }
      blocks.push({ type: 'task-list', items });
      continue;
    }

    if (/^[-*+]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^[-*+]\s+/.test(lines[index]) && !/^[-*+]\s+\[[ xX]\]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^[-*+]\s+/, ''));
        index += 1;
      }
      blocks.push({ type: 'unordered-list', items });
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\d+\.\s+/, ''));
        index += 1;
      }
      blocks.push({ type: 'ordered-list', items });
      continue;
    }

    const paragraphLines: string[] = [];
    while (index < lines.length && lines[index].trim() !== '' && !isMarkdownBlockStart(lines[index])) {
      paragraphLines.push(lines[index]);
      index += 1;
    }
    // 진행 불변식: 어떤 분기와도 어긋난 줄이 와도 최소 한 줄은 소비한다(무한 루프 방지).
    if (paragraphLines.length === 0) {
      paragraphLines.push(lines[index]);
      index += 1;
    }
    blocks.push({ type: 'paragraph', text: paragraphLines.join('\n') });
  }

  return blocks;
}

export function MarkdownMessage({ content }: { content: string }) {
  const blocks = useMemo(() => parseMarkdownBlocks(content), [content]);
  return (
    <div data-testid="ai-markdown-message" className="space-y-3 leading-7 text-ink-1">
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`;
        if (block.type === 'heading') {
          const headingClass = "mt-1 text-base font-semibold text-ink-1";
          const headingContent = parseInlineMarkdown(block.text);
          if (block.level <= 1) return <h3 key={key} className={headingClass}>{headingContent}</h3>;
          if (block.level === 2) return <h4 key={key} className={headingClass}>{headingContent}</h4>;
          if (block.level === 3) return <h5 key={key} className={headingClass}>{headingContent}</h5>;
          return <h6 key={key} className={headingClass}>{headingContent}</h6>;
        }
        if (block.type === 'paragraph') {
          return (
            <p key={key} className="whitespace-pre-wrap">
              {parseInlineMarkdown(block.text)}
            </p>
          );
        }
        if (block.type === 'blockquote') {
          return (
            <blockquote key={key} className="border-l-4 border-accent/50 bg-surface-raised px-3 py-2 text-ink-2">
              <p className="whitespace-pre-wrap">{parseInlineMarkdown(block.text)}</p>
            </blockquote>
          );
        }
        if (block.type === 'unordered-list') {
          return (
            <ul key={key} className="ml-5 list-disc space-y-1">
              {block.items.map((item, itemIndex) => (
                <li key={`${key}-${itemIndex}`}>{parseInlineMarkdown(item)}</li>
              ))}
            </ul>
          );
        }
        if (block.type === 'ordered-list') {
          return (
            <ol key={key} className="ml-5 list-decimal space-y-1">
              {block.items.map((item, itemIndex) => (
                <li key={`${key}-${itemIndex}`}>{parseInlineMarkdown(item)}</li>
              ))}
            </ol>
          );
        }
        if (block.type === 'task-list') {
          return (
            <ul key={key} className="space-y-1">
              {block.items.map((item, itemIndex) => (
                <li key={`${key}-${itemIndex}`} className="flex gap-2">
                  <input type="checkbox" checked={item.checked} readOnly disabled className="mt-1" />
                  <span>{parseInlineMarkdown(item.text)}</span>
                </li>
              ))}
            </ul>
          );
        }
        if (block.type === 'code') {
          return (
            <pre key={key} className="overflow-x-auto rounded-lg bg-[#0f172a] p-3 text-xs leading-6 text-slate-100">
              {block.language ? <div className="mb-2 text-[10px] uppercase tracking-wide text-slate-400">{block.language}</div> : null}
              <code>{block.code}</code>
            </pre>
          );
        }
        if (block.type === 'table') {
          return (
            <div key={key} className="overflow-x-auto rounded-lg border border-line-subtle">
              <table className="min-w-full border-collapse text-sm">
                <thead className="bg-surface-sunken">
                  <tr>
                    {block.headers.map((header, cellIndex) => (
                      <th key={`${key}-h-${cellIndex}`} className="border-b border-line-subtle px-3 py-2 text-left font-semibold">
                        {parseInlineMarkdown(header)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={`${key}-r-${rowIndex}`} className="border-t border-line-subtle">
                      {block.headers.map((_header, cellIndex) => (
                        <td key={`${key}-r-${rowIndex}-${cellIndex}`} className="px-3 py-2 align-top">
                          {parseInlineMarkdown(row[cellIndex] ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return <hr key={key} className="border-line-subtle" />;
      })}
    </div>
  );
}
