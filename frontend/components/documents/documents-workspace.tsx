'use client';

import React, { useEffect, useMemo, useState } from 'react';

import { HtmlViewer } from '@/components/newsletter/html-viewer';
import { Icon } from '@/components/ui/icons';
import { ScrollToTop } from '@/components/ui/scroll-to-top';
import { fetchCollectionContent, getCollectionDownloadPath } from '@/lib/api';
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

// 모든 폴더 경로를 모은다 — defaultFoldersOpen=true 일 때만 초기 펼침 집합으로 쓰인다(기본은 접힘).
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

function normalizeSearch(value: string): string {
  return value.trim().toLocaleLowerCase('ko-KR');
}

function recentDocumentKey(collection: string): string {
  return `aeroone.collection.${collection}.recentDocument`;
}

function resolveInitialSelected(
  documents: DocumentListItem[],
  collection: 'document' | 'civil' | 'nsa',
): DocumentListItem | null {
  if (typeof window !== 'undefined') {
    try {
      const recentPath = window.localStorage.getItem(recentDocumentKey(collection));
      const recentDoc = documents.find((doc) => doc.path === recentPath);
      if (recentDoc) {
        return recentDoc;
      }
    } catch {
      // localStorage 접근이 막힌 환경에서는 첫 문서로 안전하게 시작한다.
    }
  }
  return documents[0] ?? null;
}

function DocumentButton({
  doc,
  depth,
  selected,
  onSelect,
  downloadHref,
  onDownload,
}: {
  doc: DocumentListItem;
  depth: number;
  selected: boolean;
  onSelect: (doc: DocumentListItem) => void;
  downloadHref: string;
  onDownload: (doc: DocumentListItem) => void;
}) {
  return (
    <div
      className={`group flex items-center rounded transition-colors ${
        selected
          ? 'bg-surface-sunken font-medium text-ink-1'
          : 'font-regular text-ink-2 hover:bg-surface-sunken hover:text-ink-1'
      }`}
    >
      <button
        type="button"
        data-testid={`doc-item-${doc.path}`}
        aria-current={selected ? 'true' : undefined}
        onClick={() => onSelect(doc)}
        style={{ paddingLeft: 10 + depth * 16 }}
        className="flex min-w-0 flex-1 items-center gap-2 rounded px-2 py-1.5 text-left text-base"
      >
        <span className="text-ink-3">
          <Icon.doc size={14} />
        </span>
        <span className="min-w-0 truncate">{doc.name}</span>
      </button>
      <a
        href={downloadHref}
        download
        data-testid={`doc-download-${doc.path}`}
        onClick={() => onDownload(doc)}
        className="mr-1 inline-flex h-7 w-7 flex-shrink-0 items-center justify-center rounded text-ink-3 opacity-70 transition hover:bg-surface-raised hover:text-ink-1 hover:opacity-100 focus:opacity-100"
        title={`${doc.name} HTML 다운로드`}
        aria-label={`${doc.name} HTML 다운로드`}
      >
        <Icon.download size={13} />
      </a>
    </div>
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
  collection,
  onDownload,
}: {
  node: TreeNode;
  parentPath: string;
  depth: number;
  openFolders: Set<string>;
  onToggle: (path: string) => void;
  selectedPath: string;
  onSelect: (doc: DocumentListItem) => void;
  collection: 'document' | 'civil' | 'nsa';
  onDownload: (doc: DocumentListItem) => void;
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
                collection={collection}
                onDownload={onDownload}
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
          downloadHref={getCollectionDownloadPath(collection, doc.path)}
          onDownload={onDownload}
        />
      ))}
    </div>
  );
}

// 상단 셀렉트용 — 폴더별로 묶는다. documents 는 (folder, name) 정렬돼 들어오므로 삽입 순서가 곧 표시 순서.
function buildSelectGroups(documents: DocumentListItem[]): [string, DocumentListItem[]][] {
  const map = new Map<string, DocumentListItem[]>();
  for (const doc of documents) {
    const key = doc.folder || '';
    const list = map.get(key) ?? [];
    list.push(doc);
    map.set(key, list);
  }
  return Array.from(map.entries());
}

type DocumentsWorkspaceProps = {
  documents: DocumentListItem[];
  collection?: 'document' | 'civil' | 'nsa';
  defaultSidebarOpen?: boolean;
  defaultFoldersOpen?: boolean;
  emptyHint?: React.ReactNode;
};

export function DocumentsWorkspace({
  documents,
  collection = 'document',
  defaultSidebarOpen = false,
  defaultFoldersOpen = false,
  emptyHint,
}: DocumentsWorkspaceProps) {
  const [selected, setSelected] = useState<DocumentListItem | null>(() =>
    resolveInitialSelected(documents, collection),
  );
  const [searchTerm, setSearchTerm] = useState('');
  const normalizedSearch = normalizeSearch(searchTerm);
  const filteredDocuments = useMemo(() => {
    if (!normalizedSearch) {
      return documents;
    }
    return documents.filter((doc) =>
      normalizeSearch(`${doc.name} ${doc.folder} ${doc.path}`).includes(normalizedSearch),
    );
  }, [documents, normalizedSearch]);
  const tree = useMemo(() => buildTree(filteredDocuments), [filteredDocuments]);
  const selectGroups = useMemo(() => buildSelectGroups(filteredDocuments), [filteredDocuments]);
  const [openFolders, setOpenFolders] = useState<Set<string>>(() =>
    defaultFoldersOpen ? new Set(collectFolderPaths(documents)) : new Set(),
  );
  // 좌측 목록을 접어 뷰어가 전체 폭을 쓰게 한다. 접으면 상단 셀렉트로 문서를 고른다(위치 위로 이동).
  const [sidebarOpen, setSidebarOpen] = useState(defaultSidebarOpen);
  const [html, setHtml] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [downloadNotice, setDownloadNotice] = useState('');

  useEffect(() => {
    if (!selected) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError('');
    fetchCollectionContent(collection, selected.path)
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
  }, [selected, collection]);

  useEffect(() => {
    if (!selected && documents.length > 0) {
      setSelected(resolveInitialSelected(documents, collection));
      return;
    }
    if (selected && !documents.some((doc) => doc.path === selected.path)) {
      setSelected(resolveInitialSelected(documents, collection));
    }
  }, [documents, selected, collection]);

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

  function selectDocument(doc: DocumentListItem) {
    setSelected(doc);
    setDownloadNotice('');
    try {
      window.localStorage.setItem(recentDocumentKey(collection), doc.path);
    } catch {
      // 최근 문서 저장 실패는 열람 자체를 막지 않는다.
    }
  }

  function selectByPath(path: string) {
    const doc = documents.find((item) => item.path === path);
    if (doc) {
      selectDocument(doc);
    }
  }

  function handleDownload(doc: DocumentListItem) {
    setDownloadNotice(`${doc.name} 다운로드를 시작했습니다.`);
  }

  const selectedInFiltered = selected
    ? filteredDocuments.some((doc) => doc.path === selected.path)
    : false;
  const selectedDownloadHref = selected ? getCollectionDownloadPath(collection, selected.path) : '';

  return (
    <div data-testid="documents-workspace" className="flex flex-col gap-3">
      {/* 상단 컨트롤 — 목록 접기/펼치기 토글 + (접었을 때) 상단 문서 셀렉트 */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          data-testid="documents-sidebar-toggle"
          aria-expanded={sidebarOpen}
          aria-label={sidebarOpen ? '문서 목록 접기' : '문서 목록 펼치기'}
          onClick={() => setSidebarOpen((open) => !open)}
          className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-2 text-base font-medium text-accent-on shadow-sm transition-colors hover:bg-accent-hover"
        >
          {sidebarOpen ? <Icon.chevL size={13} /> : <Icon.list size={14} />}
          {sidebarOpen ? '목록 접기' : '목록 펼치기'}
        </button>

        <label className="min-w-[180px] flex-1 sm:max-w-xs">
          <span className="sr-only">문서 검색</span>
          <input
            type="search"
            data-testid="documents-search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="파일명·폴더 검색"
            className="w-full rounded border border-line-subtle bg-surface-raised px-2.5 py-1.5 text-base text-ink-1 placeholder:text-ink-3"
          />
        </label>

        {!sidebarOpen ? (
          <select
            data-testid="documents-select"
            aria-label="문서 선택"
            value={selectedInFiltered ? selected?.path ?? '' : ''}
            onChange={(event) => selectByPath(event.target.value)}
            className="min-w-0 max-w-full rounded border border-line-subtle bg-surface-raised px-2 py-1.5 text-base text-ink-1"
          >
            {!selectedInFiltered ? <option value="">검색 결과에서 선택</option> : null}
            {selectGroups.map(([folder, items]) => (
              <optgroup key={folder || '__root'} label={folder || '기본'}>
                {items.map((doc) => (
                  <option key={doc.path} value={doc.path}>
                    {doc.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        ) : null}

        {selected ? (
          <a
            href={selectedDownloadHref}
            download
            data-testid="documents-selected-download"
            onClick={() => selected && handleDownload(selected)}
            className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-line-subtle bg-surface-raised px-2.5 py-1.5 text-sm text-ink-2 transition-colors hover:bg-surface-sunken hover:text-ink-1"
            title={`${selected.name} HTML 다운로드`}
            aria-label={`${selected.name} HTML 다운로드`}
          >
            <Icon.download size={13} />
            <span className="truncate">HTML 다운로드 · {selected.name}</span>
          </a>
        ) : null}

        <span className="text-xs text-ink-3" data-testid="documents-search-count">
          {filteredDocuments.length}/{documents.length}개 표시
        </span>
      </div>

      {downloadNotice ? (
        <p data-testid="documents-download-notice" className="text-xs text-accent">
          {downloadNotice}
        </p>
      ) : null}

      {normalizedSearch && filteredDocuments.length === 0 ? (
        <div className="rounded-lg border border-dashed border-line bg-surface-raised p-6 text-sm text-ink-2">
          검색 결과가 없습니다. 다른 파일명이나 폴더명을 입력하세요.
        </div>
      ) : null}

      <div
        className={`grid gap-5 ${sidebarOpen ? 'lg:grid-cols-[280px_minmax(0,1fr)]' : 'grid-cols-1'}`}
      >
        {/* 좌측 — 폴더 트리(펼쳤을 때만 렌더; 접으면 뷰어가 전체 폭) */}
        {sidebarOpen ? (
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
                onSelect={selectDocument}
                collection={collection}
                onDownload={handleDownload}
              />
            </nav>
          </aside>
        ) : null}

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
            <HtmlViewer title={selected.name} html={html} fit="viewport" showFitToggle />
          ) : null}
          <ScrollToTop />
        </section>
      </div>
    </div>
  );
}
