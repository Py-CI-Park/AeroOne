import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import { ScrollToTop } from '@/components/ui/scroll-to-top';

function setScrollY(value: number) {
  Object.defineProperty(window, 'scrollY', { value, configurable: true });
}

test('appears only after scrolling past the threshold and scrolls to top on click', () => {
  const scrollTo = vi.fn();
  window.scrollTo = scrollTo as unknown as typeof window.scrollTo;

  setScrollY(0);
  render(<ScrollToTop threshold={300} />);

  // 초기(맨 위)에는 버튼이 없다.
  expect(screen.queryByTestId('scroll-to-top')).not.toBeInTheDocument();

  // 임계값을 넘으면 버튼이 나타난다.
  setScrollY(400);
  fireEvent.scroll(window);
  const button = screen.getByRole('button', { name: '맨 위로' });
  expect(button).toBeInTheDocument();

  // 누르면 부드럽게 맨 위로 스크롤한다.
  fireEvent.click(button);
  expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });

  // 다시 위로 올라오면 버튼이 사라진다.
  setScrollY(0);
  fireEvent.scroll(window);
  expect(screen.queryByTestId('scroll-to-top')).not.toBeInTheDocument();
});
