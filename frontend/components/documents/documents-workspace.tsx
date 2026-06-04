'use client';

import React, { useEffect, useMemo, useState } from 'react';

import { HtmlViewer } from '@/components/newsletter/html-viewer';
import { Icon } from '@/components/ui/icons';
import { ScrollToTop } from '@/components/ui/scroll-to-top';
import { fetchDocumentContent } from '@/lib/api';
import type { DocumentListItem } from '@/lib/types';

// 폴더 경로("a/b/c")를 중첩 트리로 묶는다. 루트 문서(folder="")는 트리 최상단에 둔다.
type TreeNode = {
  folders: Map<string, TreeNode>;
  docs: DocumentListItem[];
};

function buildTree(documents: DocumentListItem[]): TreeNode {
  const root: TreeNode = { folders: new Map(), docs: [] };
  for (const doc of documents) {
    let node = root;
    if (doc.folder) {
      for (const segment of doc.folder.split('/')) {
        const next = node.folders.get(segment) ?? { folders: new Map(), docs: [] };
        node.folders.set(segment, next);
        node = next;
      }
    }
    node.docs.push(doc);
  }
  return root;
}

// 기본은 모든 폴더 펼침 — 운영자가 넣은 문서가 처음부터 한눈에 보이게 한다(이후 접기 가능).
function collectFolderPaths(documents: DocumentListItem[]): string[] {
  const paths = new Set<string>();
  for (const doc of documents) {
    if (!doc.folder) {
      continue;
    }
    const segments = doc.folder.split('/');
    for (let depth = 1; depth <= segments.length; depth += 1) {
      paths.add(segments.slice(0, depth).join('/'));
    }
  }
  return Array.from(paths);
}

function DocumentButton({
  doc,
  depth,
  selected,
  onSelect,
}: {
  doc: DocumentListItem;
  depth: number;
  selected: boolean;
  onSelect: (doc: DocumentListItem) => void;
}) {
  return (
    <button
      type="button"
      data-testid={`doc-item-${doc.path}`}
      aria-current={selected ? 'true' : undefined}
      onClick={() => onSelect(doc)}
      style={{ paddingLeft: 10 + depth * 16 }}
      className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-base transition-colors ${
        selected
          ? 'bg-surface-sunken font-medium text-ink-1'
          : 'font-regular text-ink-2 hover:bg-surface-sunken hover:text-ink-1'
      }`}
    >
      <span className="text-ink-3">
        <Icon.doc size={14} />
      </span>
      <span className="min-w-0 truncate">{doc.name}</span>
    </button>
  );
}

function FolderTree({
  node,
  parentPath,
  depth,
  openFolders,
  onToggle,
  selectedPath,
  onSelect,
}: {
  node: TreeNode;
  parentPath: string;
  depth: number;
  openFolders: Set<string>;
  onToggle: (path: string) => void;
  selectedPath: string;
  onSelect: (doc: DocumentListItem) => void;
}) {
  const folderNames = Array.from(node.folders.keys()).sort((a, b) => a.localeCompare(b));
  return (
    <div className="flex flex-col gap-0.5">
      {folderNames.map((name) => {
        const path = parentPath ? `${parentPath}/${name}` : name;
        const open = openFolders.has(path);
        const child = node.folders.get(name)!;
        return (
          <div key={path}>
            <button
              type="button"
              data-testid={`doc-folder-${path}`}
              aria-expanded={open}
              onClick={() => onToggle(path)}
              style={{ paddingLeft: 10 + depth * 16 }}
              className="flex w-full items-center gap-1.5 rounded px-2 py-1.5 text-left text-base font-medium text-ink-1 transition-colors hover:bg-surface-sunken"
            >
              <span className={`text-ink-3 transition-transform duration-[120ms] ${open ? 'rotate-90' : ''}`}>
                <Icon.chevR size={11} />
              </span>
              <span className="min-w-0 truncate">{name}</span>
            </button>
            {open ? (
              <FolderTree
                node={child}
                parentPath={path}
                depth={depth + 1}
                openFolders={openFolders}
                onToggle={onToggle}
                selectedPath={selectedPath}
                onSelect={onSelect}
              />
            ) : null}
          </div>
        );
      })}
      {node.docs.map((doc) => (
        <DocumentButton
          key={doc.path}
          doc={doc}
          depth={depth}
          selected={doc.path === selectedPath}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

export function DocumentsWorkspace({ documents }: { documents: DocumentListItem[] }) {
  const tree = useMemo(() => buildTree(documents), [documents]);
  const [openFolders, setOpenFolders] = useState<Set<string>>(() => new Set(collectFolderPaths(documents)));
  const [selected, setSelected] = useState<DocumentListItem | null>(documents[0] ?? null);
  const [html, setHtml] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!selected) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError('');
    fetchDocumentContent(selected.path)
      .then((payload) => {
        if (!cancelled) {
          setHtml(payload.content_html);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setHtml('');
          setError(err instanceof Error ? err.message : '문서를 불러오지 못했습니다.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  function toggleFolder(path: string) {
    setOpenFolders((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }

  return (
    <div data-testid="documents-workspace" className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
      {/* 좌측 — 폴더 트리(접을 수 있음) */}
      <aside className="flex flex-col gap-2">
        <nav
          data-testid="documents-tree"
          aria-label="문서 목록"
          className="rounded-2xl border border-line-subtle bg-surface-raised p-2"
        >
          <FolderTree
            node={tree}
            parentPath=""
            depth={0}
            openFolders={openFolders}
            onToggle={toggleFolder}
            selectedPath={selected?.path ?? ''}
            onSelect={setSelected}
          />
        </nav>
      </aside>

      {/* 우측 — 선택한 문서 본문(sandbox iframe 뷰어) */}
      <section className="min-w-0">
        {error ? (
          <div className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-2">
            문서를 불러오지 못했습니다.
            <div className="mt-2 text-xs text-ink-3">{error}</div>
          </div>
        ) : loading && !html ? (
          <div
            data-testid="documents-loading"
            className="rounded-lg border border-dashed border-line bg-surface-raised p-8 text-sm text-ink-3"
          >
            문서를 불러오는 중…
          </div>
        ) : selected ? (
          <HtmlViewer title={selected.name} html={html} />
        ) : null}
        <ScrollToTop />
      </section>
    </div>
  );
}
