import React from 'react';
import { render, screen } from '@testing-library/react';

import { HtmlViewer } from '@/components/newsletter/html-viewer';

it('renders sandboxed iframe that allows scripts for trusted newsletter content', () => {
  render(<HtmlViewer title="sample" html="<h1>hello</h1>" />);
  const iframe = screen.getByTitle('sample');
  // Newsletter_AI 산출 HTML 은 <script> 로 본문을 주입하므로 allow-scripts 필요.
  // 콘텐츠는 운영자 자체 파이프라인 산출물(신뢰 가능)이라 sandbox 에 허용.
  expect(iframe).toHaveAttribute('sandbox', 'allow-same-origin allow-scripts');
  expect(iframe.getAttribute('sandbox')).toContain('allow-scripts');
  expect(iframe).toHaveAttribute('scrolling', 'no');
});
