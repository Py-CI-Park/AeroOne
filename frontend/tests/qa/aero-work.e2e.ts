import { test, expect, type Page } from '@playwright/test';
import path from 'node:path';

// Aero Work 핵심 플로 E2E (G007) — 이미 가동 중인 라이브 서버(프런트 :29501, 백엔드 :18437,
// Ollama gemma4:12b·nomic-embed 라이브)를 대상으로 5막 시나리오를 수행한다.
// 1막 로그인 → /aero-work 진입·7탭 렌더
// 2막 업무대화 멀티인텐트 → 일정 등록 메시지 + HWPX 버튼
// 3막 일정 탭 이벤트 확인 + 문서작성 탭 HWPX 생성·다운로드
// 4막 지식폴더 등록(재사용)·색인 대기 + 키워드 검색
// 5막 문서작성 최종 저장 요청 → 승인 대기 → 승인 → 다운로드
//
// 실 LLM 호출(합성·오케스트레이션) 구간은 90s+ 여유를 두고 waitForResponse 로 완료를 기다린다.

const ADMIN_USERNAME = 'admin';
const ADMIN_PASSWORD = 'AeroOneAdmin2026Secure';
const ARTIFACT_DIR = path.resolve(process.cwd(), '..', 'artifacts', 'qa', 'ultragoal', 'G007');
const SAMPLE_DOCS_PATH = path.resolve(process.cwd(), '..', 'artifacts', 'qa', 'aero-work-sample-docs');

const NAV_LABELS = ['홈', '업무대화', '일정', '문서작성', '내 지식폴더', '실행기록', '환경설정'];

test.describe.configure({ mode: 'serial' });

async function login(page: Page) {
  await page.goto('/login?next=%2Faero-work', { waitUntil: 'networkidle' });
  await page.locator('input[autocomplete="username"]').fill(ADMIN_USERNAME);
  await page.locator('input[autocomplete="current-password"]').fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await page.waitForURL((url) => url.pathname === '/aero-work', { timeout: 30_000 });
  await page.waitForLoadState('networkidle');
}

function nav(page: Page) {
  return page.getByRole('navigation', { name: 'Aero Work 메뉴' });
}

async function gotoTab(page: Page, label: string) {
  await nav(page).getByRole('button', { name: label, exact: true }).click();
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: path.join(ARTIFACT_DIR, `e2e-${name}.png`), fullPage: true });
}

type Folder = { id: number; name: string; path: string; status: string };

test('Aero Work 핵심 플로 5막', async ({ page }) => {
  test.setTimeout(600_000);

  // ---- 1막: 로그인 → /aero-work 진입 · 7탭 렌더 확인 ----
  await login(page);
  await expect(page.getByRole('heading', { name: /홈|오늘의 브리핑/ }).first()).toBeVisible();
  const navBar = nav(page);
  await expect(navBar).toBeVisible();
  for (const label of NAV_LABELS) {
    await expect(navBar.getByRole('button', { name: label, exact: true }), `nav 탭 "${label}" 렌더 확인`).toBeVisible();
  }
  await expect(navBar.getByRole('button')).toHaveCount(7);
  await shot(page, 'act1-login-nav');

  // ---- 2막: 업무대화 멀티인텐트 → 일정 등록 메시지 + HWPX 버튼 확인 ----
  await gotoTab(page, '업무대화');
  await expect(page.getByRole('button', { name: '업무 명령 (일정·문서·지식)' })).toHaveClass(/bg-accent/);
  const chatInput = page.locator('input[placeholder="예: 내일 오전 10시 회의 등록하고 그 내용으로 보고서 작성해줘"]');
  await expect(chatInput).toBeVisible();
  await chatInput.fill('내일 오전 9시 월간보고 등록하고 그 내용으로 시행문 작성해줘');
  const [orchestrateResponse] = await Promise.all([
    page.waitForResponse(
      (resp) => resp.url().includes('/api/frontend/aero-work/orchestrate') && resp.request().method() === 'POST',
      { timeout: 120_000 },
    ),
    page.getByRole('button', { name: '보내기' }).click(),
  ]);
  expect(orchestrateResponse.status(), '멀티인텐트 오케스트레이션 응답 200').toBe(200);
  const orchestratePayload = await orchestrateResponse.json();
  expect(
    Array.isArray(orchestratePayload.results) && orchestratePayload.results.length >= 2,
    `멀티인텐트(일정+문서) 결과 최소 2건 기대, 실제 ${JSON.stringify(orchestratePayload.results?.map((r: { kind: string }) => r.kind))}`,
  ).toBe(true);
  await expect(page.getByRole('button', { name: '보내기' })).not.toHaveText('처리 중…', { timeout: 10_000 });
  await expect(page.getByText('월간보고').first(), '업무대화 로그에 일정 등록 메시지(월간보고) 표시').toBeVisible();
  const chatHwpxButton = page.getByRole('button', { name: 'HWPX 생성·다운로드' }).first();
  await expect(chatHwpxButton, '업무대화 응답에 HWPX 생성·다운로드 버튼 표시').toBeVisible();
  await shot(page, 'act2-chat-multi-intent');

  // ---- 3막: 일정 탭 이벤트 확인 ----
  await gotoTab(page, '일정');
  await expect(page.getByText('월간보고').first(), '일정 탭에 등록된 이벤트(월간보고) 표시').toBeVisible({ timeout: 15_000 });
  await shot(page, 'act3a-schedule-event');

  // ---- 3막(계속): 문서작성 탭에서 HWPX 생성·다운로드 (응답 200 · 파일명 확인) ----
  await gotoTab(page, '문서작성');
  const docTitle = `E2E 문서작성 검증 ${Date.now()}`;
  await page.locator('input[placeholder="문서 제목"]').fill(docTitle);
  await page.locator('textarea[placeholder="본문을 입력하세요. 한 줄이 한 문단이 됩니다."]').fill('E2E 검증용 본문 1문단.\nE2E 검증용 본문 2문단.');
  const [hwpxResponse, download] = await Promise.all([
    page.waitForResponse(
      (resp) => resp.url().includes('/api/frontend/aero-work/document/hwpx') && resp.request().method() === 'POST',
      { timeout: 60_000 },
    ),
    page.waitForEvent('download', { timeout: 60_000 }),
    page.getByRole('button', { name: 'HWPX 생성·다운로드' }).click(),
  ]);
  expect(hwpxResponse.status(), 'HWPX 생성 응답 200').toBe(200);
  expect(download.suggestedFilename(), 'HWPX 다운로드 파일명이 문서 제목과 일치').toBe(`${docTitle}.hwpx`);
  await expect(page.getByText('HWPX 파일을 내려받았음.')).toBeVisible();
  await shot(page, 'act3b-document-hwpx-download');

  // ---- 4막: 지식폴더 등록(기등록 시 재사용) + 색인 대기 + 키워드 검색 ----
  await gotoTab(page, '내 지식폴더');
  const foldersResponse = await page.request.get('/api/frontend/aero-work/knowledge/folders');
  expect(foldersResponse.status(), '지식폴더 목록 조회 200').toBe(200);
  const foldersPayload = (await foldersResponse.json()) as { folders: Folder[] };
  const normalizedSamplePath = SAMPLE_DOCS_PATH.toLowerCase();
  let sampleFolder = foldersPayload.folders.find((f) => f.path.toLowerCase() === normalizedSamplePath);

  if (!sampleFolder) {
    await page.locator('input[placeholder="이름(선택)"]').fill('G007 샘플 지식폴더');
    await page.locator('input[placeholder="D:\\\\업무\\\\지식자료 또는 /srv/kb"]').fill(SAMPLE_DOCS_PATH);
    await page.getByRole('button', { name: '등록' }).click();
    await expect.poll(
      async () => {
        const resp = await page.request.get('/api/frontend/aero-work/knowledge/folders');
        const payload = (await resp.json()) as { folders: Folder[] };
        sampleFolder = payload.folders.find((f) => f.path.toLowerCase() === normalizedSamplePath);
        return sampleFolder != null;
      },
      { message: '샘플 지식폴더 등록 확인', timeout: 30_000 },
    ).toBe(true);
    await page.reload({ waitUntil: 'networkidle' });
  }

  if (sampleFolder && sampleFolder.status !== 'ready') {
    const folderRow = page.locator('li', { hasText: sampleFolder.name });
    await folderRow.getByRole('button', { name: /재색인|색인 중…/ }).click();
    await expect.poll(
      async () => {
        const resp = await page.request.get('/api/frontend/aero-work/knowledge/folders');
        const payload = (await resp.json()) as { folders: Folder[] };
        const updated = payload.folders.find((f) => f.id === sampleFolder!.id);
        return updated?.status ?? 'unknown';
      },
      { message: '샘플 지식폴더 색인 완료(ready) 대기', timeout: 120_000, intervals: [2_000] },
    ).toBe('ready');
    await page.reload({ waitUntil: 'networkidle' });
    await gotoTab(page, '내 지식폴더');
  }

  await page.getByRole('button', { name: '키워드 검색' }).click();
  await page.locator('select').first().selectOption('all');
  await page.locator('input[placeholder="예: 출장 정산 규정, 보안 서약서 절차"]').fill('예산');
  const [searchResponse] = await Promise.all([
    page.waitForResponse(
      (resp) => resp.url().includes('/api/frontend/aero-work/knowledge/keyword-search') && resp.request().method() === 'POST',
      { timeout: 30_000 },
    ),
    page.getByRole('button', { name: '검색', exact: true }).click(),
  ]);
  expect(searchResponse.status(), '키워드 검색 응답 200').toBe(200);
  const searchPayload = await searchResponse.json();
  expect(Array.isArray(searchPayload.hits) && searchPayload.hits.length >= 1, `키워드 검색 결과 최소 1건 기대, 실제 ${searchPayload.hits?.length}`).toBe(true);
  await expect(page.getByText(/일치 \d+회/).first(), '키워드 검색 결과에 "일치 N회" 라벨 표시').toBeVisible();
  await shot(page, 'act4-knowledge-search');

  // ---- 5막: 문서작성 제목/본문 → 최종 저장 요청 → 승인 대기 → 승인 → 다운로드 ----
  await gotoTab(page, '문서작성');
  const approvalTitle = `E2E 승인 플로 검증 ${Date.now()}`;
  await page.locator('input[placeholder="문서 제목"]').fill(approvalTitle);
  await page.locator('textarea[placeholder="본문을 입력하세요. 한 줄이 한 문단이 됩니다."]').fill('승인 플로 검증용 본문 1문단.\n승인 플로 검증용 본문 2문단.');
  const [saveRequestResponse] = await Promise.all([
    page.waitForResponse(
      (resp) => resp.url().includes('/api/frontend/aero-work/document/save-request') && resp.request().method() === 'POST',
      { timeout: 30_000 },
    ),
    page.getByRole('button', { name: '최종 저장 요청' }).click(),
  ]);
  expect(saveRequestResponse.status(), '최종 저장 요청 응답 201/200').toBeLessThan(300);
  await expect(page.getByText('최종 저장을 요청했음 — 아래 목록에서 승인 후 내려받으세요.')).toBeVisible();
  const savedRow = page.locator('li', { hasText: approvalTitle });
  await expect(savedRow, '승인 대기 문서가 저장 목록에 표시').toBeVisible();
  await expect(savedRow.getByText('승인 대기'), '승인 대기 상태 배지 확인').toBeVisible();
  await shot(page, 'act5a-save-request-pending');

  const [approveResponse] = await Promise.all([
    page.waitForResponse(
      (resp) => /\/api\/frontend\/aero-work\/document\/saved\/\d+\/approve$/.test(resp.url()) && resp.request().method() === 'POST',
      { timeout: 30_000 },
    ),
    savedRow.getByRole('button', { name: '승인' }).click(),
  ]);
  expect(approveResponse.status(), '문서 승인 응답 200').toBe(200);
  await expect(savedRow.getByText('승인됨'), '승인 후 상태 배지가 승인됨으로 전환').toBeVisible();
  const approvedDownloadButton = savedRow.getByRole('button', { name: 'HWPX' });
  await expect(approvedDownloadButton, '승인 후 HWPX 다운로드 버튼 활성').toBeVisible();
  const [approvedDownload] = await Promise.all([
    page.waitForEvent('download', { timeout: 30_000 }),
    approvedDownloadButton.click(),
  ]);
  expect(approvedDownload.suggestedFilename(), '승인된 문서 다운로드 파일명 확인').toBe(`${approvalTitle}.hwpx`);
  await shot(page, 'act5b-approved-download');
});
