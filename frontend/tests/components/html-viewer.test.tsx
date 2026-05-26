import React from 'react';
import { render, screen } from '@testing-library/react';

import { HtmlViewer, expandNewsletterArticles } from '@/components/newsletter/html-viewer';

it('renders sandboxed iframe that allows scripts for trusted newsletter content', () => {
  render(<HtmlViewer title="sample" html="<h1>hello</h1>" />);
  const iframe = screen.getByTitle('sample');
  // Newsletter_AI 산출 HTML 은 <script> 로 본문을 주입하므로 allow-scripts 필요.
  // 콘텐츠는 운영자 자체 파이프라인 산출물(신뢰 가능)이라 sandbox 에 허용.
  expect(iframe).toHaveAttribute('sandbox', 'allow-same-origin allow-scripts');
  expect(iframe.getAttribute('sandbox')).toContain('allow-scripts');
  expect(iframe).toHaveAttribute('scrolling', 'no');
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
