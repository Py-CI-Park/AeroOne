import React from 'react';
import { render } from '@testing-library/react';

import * as api from '@/lib/api';
import { ReadBeacon } from '@/components/newsletter/read-beacon';

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

test('fires the read beacon once on mount', () => {
  const spy = vi.spyOn(api, 'recordNewsletterRead').mockImplementation(() => {});
  render(<ReadBeacon newsletterId={42} />);
  expect(spy).toHaveBeenCalledTimes(1);
  expect(spy).toHaveBeenCalledWith(42);
});

test('does not fire again for the same newsletter within the same session', () => {
  const spy = vi.spyOn(api, 'recordNewsletterRead').mockImplementation(() => {});
  const first = render(<ReadBeacon newsletterId={42} />);
  first.unmount();
  render(<ReadBeacon newsletterId={42} />);
  expect(spy).toHaveBeenCalledTimes(1); // sessionStorage 가드로 중복 발화 차단
});
