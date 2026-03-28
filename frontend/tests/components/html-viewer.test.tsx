import React from 'react';
import { render, screen } from '@testing-library/react';

import { HtmlViewer } from '@/components/newsletter/html-viewer';

it('renders sandboxed iframe without allow-scripts', () => {
  render(<HtmlViewer title="sample" html="<h1>hello</h1>" />);
  const iframe = screen.getByTitle('sample');
  expect(iframe).toHaveAttribute('sandbox', '');
  expect(iframe.getAttribute('sandbox')).not.toContain('allow-scripts');
});
