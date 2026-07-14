/**
 * 서버가 만든 ECharts option 에 '실서비스급' 시각 스타일을 입힌다.
 *
 * 서버(pandas 집계)는 데이터(series.data/축 카테고리)만 정확히 넘기고, 색·축·툴팁·
 * 레전드·막대 라운드·선 스무딩 같은 표현은 여기서 통일해 얹는다. 데이터는 절대 바꾸지
 * 않고 표현 속성만 병합한다(불변 — 새 객체 생성).
 *
 * 팔레트는 dataviz 스킬의 검증된 라이트 categorical 세트(고정 순서, cycle 금지)를 쓴다.
 * 미리보기 표면이 흰색이라 라이트 모드 값으로 렌더하고, PNG 도 흰 배경으로 내보낸다.
 */

// dataviz 검증 팔레트(라이트) — 고정 순서. 9번째 계열은 생성하지 않는다(색 재사용 안 함).
export const CATEGORICAL = [
  '#2a78d6', // blue
  '#1baf7a', // aqua
  '#eda100', // yellow
  '#008300', // green
  '#4a3aa7', // violet
  '#e34948', // red
  '#e87ba4', // magenta
  '#eb6834', // orange
];

const SURFACE = '#ffffff';
const INK_PRIMARY = '#0b0b0b';
const INK_SECONDARY = '#52514e';
const GRID_LINE = 'rgba(11,11,11,0.06)';
const AXIS_LINE = 'rgba(11,11,11,0.18)';

type Dict = Record<string, unknown>;

function isDict(value: unknown): value is Dict {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

// 단일 막대 계열용 세로 그라디언트(위가 밝고 아래가 진하게). echarts 는 plain 객체 색을 받는다.
function verticalGradient(base: string): Dict {
  return {
    type: 'linear',
    x: 0,
    y: 0,
    x2: 0,
    y2: 1,
    colorStops: [
      { offset: 0, color: base },
      { offset: 1, color: base + 'b3' }, // 아래쪽만 살짝 투명(70%)해 입체감
    ],
  };
}

function styleSeries(series: unknown, singleBar: boolean): unknown {
  if (!isDict(series)) return series;
  const type = series.type;
  const itemStyle = isDict(series.itemStyle) ? series.itemStyle : {};

  if (type === 'bar') {
    // 누적 막대는 세그먼트 사이에 2px 표면 틈을 줘 경계를 또렷이 하고(둥근 모서리는 완만하게),
    // 그룹/단일 막대는 윗면만 둥글게 해 데이터 끝을 강조한다(dataviz 마크 규격).
    const stacked = typeof series.stack === 'string' || series.stack === true;
    return {
      ...series,
      barMaxWidth: 46,
      itemStyle: {
        borderRadius: stacked ? 2 : [6, 6, 0, 0],
        ...(stacked ? { borderColor: SURFACE, borderWidth: 1.5 } : {}),
        ...(singleBar ? { color: verticalGradient(CATEGORICAL[0]) } : {}),
        ...itemStyle,
      },
      emphasis: { focus: 'series', itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.15)' } },
    };
  }

  if (type === 'line') {
    const isArea = isDict(series.areaStyle) || series.areaStyle === true;
    return {
      ...series,
      smooth: 0.35,
      showSymbol: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: { width: 2.5, ...(isDict(series.lineStyle) ? series.lineStyle : {}) },
      emphasis: { focus: 'series' },
      ...(isArea
        ? { areaStyle: { opacity: 0.16, ...(isDict(series.areaStyle) ? series.areaStyle : {}) } }
        : {}),
    };
  }

  if (type === 'pie') {
    return {
      ...series,
      radius: series.radius ?? ['38%', '62%'],
      // 제목(위)·레전드(아래)와 겹치지 않게 도넛을 살짝 위로 올린다.
      center: series.center ?? ['50%', '46%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: SURFACE, borderWidth: 2, borderRadius: 6, ...itemStyle },
      label: { color: INK_PRIMARY, ...(isDict(series.label) ? series.label : {}) },
      emphasis: { scaleSize: 6, label: { fontWeight: 'bold' } },
    };
  }

  if (type === 'scatter') {
    return {
      ...series,
      symbolSize: series.symbolSize ?? 12,
      itemStyle: { opacity: 0.85, borderColor: SURFACE, borderWidth: 1, ...itemStyle },
      emphasis: { focus: 'series' },
    };
  }

  return series;
}

function styleAxis(axis: unknown): unknown {
  const apply = (a: unknown): unknown => {
    if (!isDict(a)) return a;
    const isValue = a.type === 'value';
    return {
      ...a,
      axisLine: { lineStyle: { color: AXIS_LINE }, ...(isDict(a.axisLine) ? a.axisLine : {}) },
      axisTick: { show: false, ...(isDict(a.axisTick) ? a.axisTick : {}) },
      axisLabel: { color: INK_SECONDARY, ...(isDict(a.axisLabel) ? a.axisLabel : {}) },
      splitLine: isValue
        ? { lineStyle: { color: GRID_LINE, type: 'dashed' }, ...(isDict(a.splitLine) ? a.splitLine : {}) }
        : (a.splitLine ?? { show: false }),
      nameTextStyle: { color: INK_SECONDARY, ...(isDict(a.nameTextStyle) ? a.nameTextStyle : {}) },
    };
  };
  return Array.isArray(axis) ? axis.map(apply) : apply(axis);
}

export function beautifyEChartsOption(option: Record<string, unknown>): Record<string, unknown> {
  const seriesList = Array.isArray(option.series) ? option.series : [];
  const types = seriesList.map((item) => (isDict(item) ? item.type : undefined));
  const hasMultiple = seriesList.length > 1;
  const isCartesian = types.some((t) => t === 'bar' || t === 'line' || t === 'scatter');
  const anyPie = types.includes('pie');
  const singleBar = seriesList.length === 1 && types[0] === 'bar';

  const styledSeries = seriesList.map((item) => styleSeries(item, singleBar));

  const tooltip: Dict = {
    trigger: anyPie ? 'item' : 'axis',
    ...(anyPie ? {} : { axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(42,120,214,0.06)' } } }),
    backgroundColor: 'rgba(255,255,255,0.98)',
    borderColor: 'rgba(11,11,11,0.08)',
    borderWidth: 1,
    padding: [8, 12],
    textStyle: { color: INK_PRIMARY, fontSize: 12 },
    extraCssText: 'box-shadow:0 6px 20px rgba(0,0,0,0.12);border-radius:8px;',
    ...(isDict(option.tooltip) ? option.tooltip : {}),
  };

  // 레전드는 제목과 겹치지 않게 배치한다. 파이는 하단, 다계열 직교좌표는 제목 아래(top 40).
  let legend: unknown = option.legend;
  if (anyPie) {
    legend = { bottom: 6, icon: 'circle', itemWidth: 10, itemHeight: 10, itemGap: 14, textStyle: { color: INK_SECONDARY, fontSize: 12 } };
  } else if (hasMultiple) {
    legend = {
      type: 'scroll',
      top: 40,
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 12,
      itemGap: 16,
      textStyle: { color: INK_SECONDARY, fontSize: 12 },
      ...(isDict(option.legend) ? option.legend : {}),
    };
  }

  // 제목은 크고 굵게, 위쪽 중앙. 서버는 text/left 만 주므로 표현(크기·색)만 여기서 얹는다.
  const title = isDict(option.title)
    ? {
        top: 10,
        left: 'center',
        textStyle: { color: INK_PRIMARY, fontSize: 18, fontWeight: 700 },
        ...option.title,
      }
    : option.title;

  // 제목(≈34) + (다계열이면 레전드 ≈24) 만큼 위 여백을 확보해 플롯과 겹치지 않게 한다.
  const gridTop = hasMultiple ? 78 : 52;

  return {
    ...option,
    color: CATEGORICAL,
    backgroundColor: SURFACE,
    animationDuration: 700,
    animationEasing: 'cubicOut',
    textStyle: { fontFamily: 'inherit', color: INK_SECONDARY },
    title,
    tooltip,
    legend,
    grid: isCartesian
      ? {
          left: 12,
          right: 24,
          top: gridTop,
          bottom: 12,
          containLabel: true,
          ...(isDict(option.grid) ? option.grid : {}),
        }
      : option.grid,
    xAxis: isCartesian && option.xAxis ? styleAxis(option.xAxis) : option.xAxis,
    yAxis: isCartesian && option.yAxis ? styleAxis(option.yAxis) : option.yAxis,
    series: styledSeries,
  };
}
