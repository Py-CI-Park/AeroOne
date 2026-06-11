import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { HtmlViewer, expandNewsletterArticles, resolveSameDocumentHashTarget } from '@/components/newsletter/html-viewer';

it('renders sandboxed iframe that allows scripts for trusted newsletter content', () => {
  render(<HtmlViewer title="sample" html="<h1>hello</h1>" />);
  const iframe = screen.getByTitle('sample');
  // Newsletter_AI 산출 HTML 은 <script> 로 본문을 주입하므로 allow-scripts 필요.
  // 콘텐츠는 운영자 자체 파이프라인 산출물(신뢰 가능)이라 sandbox 에 허용.
  expect(iframe).toHaveAttribute('sandbox', 'allow-same-origin allow-scripts');
  expect(iframe.getAttribute('sandbox')).toContain('allow-scripts');
  // content(기본) 모드: 바깥 페이지가 스크롤하므로 iframe 자체 스크롤은 끈다.
  expect(iframe).toHaveAttribute('scrolling', 'no');
  // 토글 미요청 시 토글 버튼은 없다(뉴스레터 읽기 화면 외형 불변).
  expect(screen.queryByTestId('html-viewer-fit-toggle')).toBeNull();
});

it('viewport fit gives the iframe its own scroll (no scrolling=no) so a doc TOC stays fixed', () => {
  // 문서/카탈로그/NSA 는 자체 목차(position:fixed/sticky, 100vh)를 가진 HTML 이라
  // iframe 에 자체 viewport(내부 스크롤)가 있어야 단독 실행처럼 목차가 고정된다.
  render(<HtmlViewer title="doc" html="<h1>hi</h1>" fit="viewport" showFitToggle />);
  const iframe = screen.getByTitle('doc');
  // viewport 모드: scrolling="no" 가 아니어야 내부 스크롤이 생긴다.
  expect(iframe.getAttribute('scrolling')).toBeNull();
  expect(iframe.getAttribute('style') ?? '').toContain('calc(100vh');
});
it('viewport fit does not lock the parent page scroll', async () => {
  const originalOverflow = document.body.style.overflow;
  document.body.style.overflow = 'auto';

  render(<HtmlViewer title="doc" html="<h1>hi</h1>" fit="viewport" showFitToggle />);

  await waitFor(() => expect(screen.getByTitle('doc')).toBeInTheDocument());
  expect(document.body.style.overflow).toBe('auto');

  document.body.style.overflow = originalOverflow;
});

it('resolves same-page hash links including absolute app URLs', () => {
  expect(resolveSameDocumentHashTarget('#summary', 'http://localhost:29501/nsa')).toBe('summary');
  expect(resolveSameDocumentHashTarget('/nsa#summary', 'http://localhost:29501/nsa')).toBe('summary');
  expect(resolveSameDocumentHashTarget('http://localhost:29501/nsa#summary', 'http://localhost:29501/nsa')).toBe('summary');
  expect(resolveSameDocumentHashTarget('/documents#summary', 'http://localhost:29501/nsa')).toBeNull();
  expect(resolveSameDocumentHashTarget('https://example.com/nsa#summary', 'http://localhost:29501/nsa')).toBeNull();
});


it('fit toggle switches between viewport(목차 고정) and content(전체 높이)', () => {
  render(<HtmlViewer title="doc" html="<h1>hi</h1>" fit="viewport" showFitToggle />);
  const toggle = screen.getByTestId('html-viewer-fit-toggle');
  const iframe = screen.getByTitle('doc');

  // 시작은 viewport — 버튼은 content 로 가는 라벨을 보여준다.
  expect(toggle).toHaveTextContent('전체 높이로 보기');
  expect(iframe.getAttribute('scrolling')).toBeNull();

  // content 로 전환 → 콘텐츠 높이 + scrolling="no".
  fireEvent.click(toggle);
  expect(toggle).toHaveTextContent('창 높이로 보기');
  expect(screen.getByTitle('doc')).toHaveAttribute('scrolling', 'no');

  // 다시 viewport 로 전환.
  fireEvent.click(toggle);
  expect(toggle).toHaveTextContent('전체 높이로 보기');
  expect(screen.getByTitle('doc').getAttribute('scrolling')).toBeNull();
});

it('opens the raw HTML in a blob URL instead of navigating to the gated app route', () => {
  const originalCreateObjectURL = window.URL.createObjectURL;
  const originalRevokeObjectURL = window.URL.revokeObjectURL;
  const openSpy = vi.spyOn(window, 'open').mockReturnValue({} as Window);
  const createObjectURLMock = vi.fn(() => 'blob:http://localhost:29501/raw-html');
  const revokeObjectURLMock = vi.fn();
  Object.defineProperty(window.URL, 'createObjectURL', { configurable: true, value: createObjectURLMock });
  Object.defineProperty(window.URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURLMock });

  render(<HtmlViewer title="doc" html="<h1>raw</h1>" />);
  fireEvent.click(screen.getByRole('button', { name: '새 창으로 열기' }));

  expect(createObjectURLMock).toHaveBeenCalled();
  expect(openSpy).toHaveBeenCalledWith('blob:http://localhost:29501/raw-html', '_blank');

  Object.defineProperty(window.URL, 'createObjectURL', { configurable: true, value: originalCreateObjectURL });
  Object.defineProperty(window.URL, 'revokeObjectURL', { configurable: true, value: originalRevokeObjectURL });
});

function buildArticleDoc(): Document {
  const doc = document.implementation.createHTMLDocument('news');
  doc.body.innerHTML = `
    <section data-article>
      <header class="article-head" data-accordion-trigger><button class="a-toggle"></button></header>
      <div class="article-body">body 1</div>
    </section>
    <section data-article>
      <header class="article-head" data-accordion-trigger><button class="a-toggle"></button></header>
      <div class="article-body">body 2</div>
    </section>
  `;
  return doc;
}

it('opens every article by default and marks them so they are only opened once', () => {
  const doc = buildArticleDoc();

  const opened = expandNewsletterArticles(doc);

  expect(opened).toBe(2);
  const articles = Array.from(doc.querySelectorAll('[data-article]'));
  for (const article of articles) {
    expect(article.getAttribute('data-open')).toBe('true');
    expect(article.getAttribute('data-aeroone-defopen')).toBe('1');
    expect(article.querySelector('[data-accordion-trigger]')?.getAttribute('aria-expanded')).toBe('true');
  }
});

it('does not re-open an article the user has collapsed (idempotent per article)', () => {
  const doc = buildArticleDoc();
  expandNewsletterArticles(doc);

  // 사용자가 첫 기사를 접음 — 기존 아코디언 토글이 data-open 을 뒤집은 상황.
  const [first] = Array.from(doc.querySelectorAll('[data-article]'));
  first.setAttribute('data-open', 'false');

  // 폴링/Observer 가 다시 호출돼도 마커가 있는 기사는 건드리지 않는다.
  const openedAgain = expandNewsletterArticles(doc);

  expect(openedAgain).toBe(0);
  expect(first.getAttribute('data-open')).toBe('false');
});

it('only expands newly rendered articles on later passes', () => {
  const doc = buildArticleDoc();
  expandNewsletterArticles(doc);

  // JS 가 기사 카드를 뒤늦게 추가 렌더한 경우.
  const late = doc.createElement('section');
  late.setAttribute('data-article', '');
  late.innerHTML = '<header data-accordion-trigger></header><div class="article-body">late</div>';
  doc.body.appendChild(late);

  const opened = expandNewsletterArticles(doc);

  expect(opened).toBe(1);
  expect(late.getAttribute('data-open')).toBe('true');
});
