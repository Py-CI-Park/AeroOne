import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { UsageGuide } from '@/components/office-tools/usage-guide';
import { StepSection } from '@/components/office-tools/step-section';

const WAYS = [
  { badge: '① 예제', title: '예제로 시작', detail: '누르면 바로 생성됩니다.' },
  { badge: '② 데이터', title: '파일 또는 정형 텍스트', detail: '파일을 올리거나 붙여넣습니다.' },
  { badge: '③ 목적', title: '서술형 입력', detail: '자연어로 적습니다.' },
];

test('usage guide is open by default and lists all three input ways', () => {
  render(<UsageGuide intro="세 가지 방법" ways={WAYS} output="산출물 설명" />);

  expect(screen.getByText('사용 방법')).toBeInTheDocument();
  expect(screen.getByText('예제로 시작')).toBeInTheDocument();
  expect(screen.getByText('파일 또는 정형 텍스트')).toBeInTheDocument();
  expect(screen.getByText('서술형 입력')).toBeInTheDocument();
  expect(screen.getByText('산출물 설명')).toBeInTheDocument();
});

test('usage guide collapses when the header is toggled', async () => {
  const user = userEvent.setup();
  render(<UsageGuide intro="세 가지 방법" ways={WAYS} output="산출물 설명" />);

  await user.click(screen.getByRole('button', { name: /사용 방법/ }));
  expect(screen.queryByText('예제로 시작')).not.toBeInTheDocument();
});

test('step section marks the number badge done with a check', () => {
  const { rerender } = render(
    <StepSection n={2} title="데이터 입력">
      <span>child</span>
    </StepSection>,
  );
  // 미완료 상태에서는 번호가 보인다.
  expect(screen.getByText('2')).toBeInTheDocument();

  rerender(
    <StepSection n={2} title="데이터 입력" done>
      <span>child</span>
    </StepSection>,
  );
  // 완료 상태에서는 번호 대신 체크(svg)로 바뀐다.
  expect(screen.queryByText('2')).not.toBeInTheDocument();
});
