import { beautifyEChartsOption, CATEGORICAL } from '@/lib/echarts-beautify';

test('applies the validated categorical palette and preserves series data', () => {
  const out = beautifyEChartsOption({
    xAxis: { type: 'category', data: ['A', 'B'] },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', name: '매출', data: [1240, 860] }],
  });
  expect(out.color).toEqual(CATEGORICAL);
  const series = out.series as Array<Record<string, unknown>>;
  // 데이터는 그대로 보존한다.
  expect(series[0].data).toEqual([1240, 860]);
  expect(series[0].name).toBe('매출');
});

test('rounds bar tops and gradients a single bar series', () => {
  const out = beautifyEChartsOption({
    xAxis: { type: 'category', data: ['A'] },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: [1] }],
  });
  const item = (out.series as Array<Record<string, unknown>>)[0].itemStyle as Record<string, unknown>;
  expect(item.borderRadius).toEqual([6, 6, 0, 0]);
  // 단일 막대는 세로 그라디언트 색을 받는다.
  expect(item.color).toMatchObject({ type: 'linear' });
});

test('does not gradient bars when multiple series exist', () => {
  const out = beautifyEChartsOption({
    xAxis: { type: 'category', data: ['A'] },
    yAxis: { type: 'value' },
    series: [
      { type: 'bar', data: [1] },
      { type: 'bar', data: [2] },
    ],
  });
  const item = (out.series as Array<Record<string, unknown>>)[0].itemStyle as Record<string, unknown>;
  expect(item.borderRadius).toEqual([6, 6, 0, 0]);
  expect(item.color).toBeUndefined();
  // 계열이 2개 이상이면 레전드를 붙인다.
  expect(out.legend).toBeTruthy();
});

test('stacked bar segments get a surface gap and flatter radius', () => {
  const out = beautifyEChartsOption({
    xAxis: { type: 'category', data: ['서울', '부산'] },
    yAxis: { type: 'value' },
    series: [
      { type: 'bar', name: '온라인', data: [10, 7], stack: 'total' },
      { type: 'bar', name: '오프라인', data: [5, 3], stack: 'total' },
    ],
  });
  const item = (out.series as Array<Record<string, unknown>>)[0].itemStyle as Record<string, unknown>;
  // 누적 세그먼트는 완만한 라운드 + 표면색 테두리로 2px 틈을 준다(그룹/단일과 구분).
  expect(item.borderRadius).toBe(2);
  expect(item.borderColor).toBe('#ffffff');
  expect(item.borderWidth).toBeCloseTo(1.5);
});

test('smooths a line series and keeps area gradient opacity', () => {
  const out = beautifyEChartsOption({
    xAxis: { type: 'category', data: ['A', 'B'] },
    yAxis: { type: 'value' },
    series: [{ type: 'line', data: [1, 2], areaStyle: {} }],
  });
  const series = (out.series as Array<Record<string, unknown>>)[0];
  expect(series.smooth).toBeTruthy();
  expect((series.areaStyle as Record<string, unknown>).opacity).toBeCloseTo(0.16);
});

test('pie charts get item tooltip and rounded borders, no cartesian grid', () => {
  const out = beautifyEChartsOption({
    series: [{ type: 'pie', data: [{ name: 'A', value: 1 }] }],
  });
  expect((out.tooltip as Record<string, unknown>).trigger).toBe('item');
  const item = (out.series as Array<Record<string, unknown>>)[0].itemStyle as Record<string, unknown>;
  expect(item.borderRadius).toBe(6);
  expect(out.grid).toBeUndefined();
});

test('cartesian charts get a containLabel grid and axis-trigger tooltip', () => {
  const out = beautifyEChartsOption({
    xAxis: { type: 'category', data: ['A'] },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: [1] }],
  });
  expect((out.grid as Record<string, unknown>).containLabel).toBe(true);
  expect((out.tooltip as Record<string, unknown>).trigger).toBe('axis');
});

test('title is enlarged/bold at the top and the option renders on a white background', () => {
  const out = beautifyEChartsOption({
    title: { text: '지역별 채널 매출 구성(누적)', left: 'center' },
    xAxis: { type: 'category', data: ['서울'] },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', name: 'a', data: [1] }],
  });
  const title = out.title as Record<string, unknown>;
  expect(title.text).toBe('지역별 채널 매출 구성(누적)');
  expect((title.textStyle as Record<string, unknown>).fontSize).toBe(18);
  expect((title.textStyle as Record<string, unknown>).fontWeight).toBe(700);
  expect(out.backgroundColor).toBe('#ffffff');
});

test('multi-series legend sits below the title (no overlap) and the grid leaves room', () => {
  const out = beautifyEChartsOption({
    title: { text: 't', left: 'center' },
    xAxis: { type: 'category', data: ['A'] },
    yAxis: { type: 'value' },
    series: [
      { type: 'bar', name: '온라인', data: [1], stack: 'total' },
      { type: 'bar', name: '오프라인', data: [2], stack: 'total' },
    ],
  });
  // 제목(top 10) 아래로 레전드(top 40)를 내려 겹치지 않게 하고, 플롯은 그보다 더 아래(top 78)에서 시작.
  expect((out.legend as Record<string, unknown>).top).toBe(40);
  expect((out.grid as Record<string, unknown>).top).toBe(78);
});

test('pie legend moves to the bottom so it never collides with the title', () => {
  const out = beautifyEChartsOption({
    title: { text: '채널 비중', left: 'center' },
    series: [{ type: 'pie', data: [{ name: 'A', value: 1 }, { name: 'B', value: 2 }] }],
  });
  expect((out.legend as Record<string, unknown>).bottom).toBe(6);
});
