import { recordNewsletterRead } from '@/lib/api';

test('recordNewsletterRead sends a body-less beacon to the browser API base', () => {
  const sendBeacon = vi.fn(() => true);
  Object.defineProperty(navigator, 'sendBeacon', { value: sendBeacon, configurable: true });

  recordNewsletterRead(7);

  expect(sendBeacon).toHaveBeenCalledTimes(1);
  expect(sendBeacon).toHaveBeenCalledWith('http://localhost:18437/api/v1/newsletters/7/read');
});
