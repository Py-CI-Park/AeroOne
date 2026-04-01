import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { ImportPanel } from '@/components/admin/import-panel';
import * as api from '@/lib/api';

vi.spyOn(api, 'syncNewsletters').mockResolvedValue({ created: 1, updated: 0, deactivated: 0, skipped: 0, issues: 1 });

test('shows sync result after click', async () => {
  render(<ImportPanel />);
  fireEvent.click(screen.getByRole('button', { name: 'Import / Sync 실행' }));
  expect(await screen.findByText('created: 1')).toBeInTheDocument();
});
