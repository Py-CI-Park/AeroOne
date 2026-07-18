import '@testing-library/jest-dom';

// admin-console-tabs 등 ?tab= 을 window.history.replaceState 로 기록하는 컴포넌트가
// 같은 테스트 파일 안의 이전 테스트에서 남긴 쿼리스트링을 다음 테스트가 물려받지
// 않도록, 매 테스트 뒤 location 을 초기화한다.
afterEach(() => {
  window.history.replaceState(null, '', '/');
});
