import { expect, test } from '@playwright/test';

const user = { id: 'user-a', email: 'alex@example.test', display_name: 'Alex', avatar_url: null, timezone: 'UTC', is_active: true };
const tandems = [
  { id: 't1', name: 'Sunday table', created_by: 'user-a', timezone: 'UTC', created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z' },
  { id: 't2', name: 'Weekend circle', created_by: 'user-a', timezone: 'UTC', created_at: '2025-01-01T00:00:00Z', updated_at: '2025-01-01T00:00:00Z' },
];
const members = {
  t1: [{ user_id: 'user-a', display_name: 'Alex', role: 'OWNER', joined_at: '2024-01-01T00:00:00Z' }, { user_id: 'user-b', display_name: 'Bea', role: 'MEMBER', joined_at: '2024-01-02T00:00:00Z' }],
  t2: [{ user_id: 'user-a', display_name: 'Alex', role: 'OWNER', joined_at: '2025-01-01T00:00:00Z' }, { user_id: 'user-c', display_name: 'Casey', role: 'MEMBER', joined_at: '2025-01-02T00:00:00Z' }],
};
const media = [{ id: 'media-1', memory_id: 'memory-1', content_type: 'image/webp', byte_size: 10, width: 800, height: 500, created_at: '2024-09-10T00:00:00Z', display_order: 0, url: '/placeholder-movie.svg' }];
const memory = {
  id: 'memory-1', tandem_id: 't1', tandem_name: 'Sunday table', category: 'trip', title: 'Coast weekend', local_date: '2024-09-10', end_date: '2024-09-12', occurred_at: null, timezone: 'UTC', notes: 'The long way home.', rating: null, created_by: 'user-a', created_at: '2024-09-10T00:00:00Z', updated_at: '2024-09-10T00:00:00Z', version: 1, nostalgia_eligible: true, schema_version: 1, metadata: { destination: 'The coast' }, participants: members.t1.map(({ user_id, display_name }) => ({ user_id, display_name })), tags: ['coast'], media, reflections: [{ id: 'reflection-1', user_id: 'user-b', display_name: 'Bea', rating: 9, note: 'Still makes me smile.', reaction: 'nostalgic', created_at: '2024-09-10T00:00:00Z', updated_at: '2024-09-10T00:00:00Z' }], my_reflection: null,
};

function json(route, body, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installAuthenticatedApi(page) {
  let deleted = true;
  let invitationStatus = 'PENDING';
  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === '/api/me') return json(route, user);
    if (path === '/api/me/tandems') return json(route, tandems);
    if (path === '/api/me/preferences') return json(route, { timezone: 'UTC', anniversary_notifications_enabled: true, anniversary_email_enabled: true, notification_hour: 9 });
    if (path === '/api/me/notifications') return json(route, { items: [], unread_count: 0 });
    if (path === '/api/me/memories') return json(route, { items: [memory], offset: 0, limit: 50, next_offset: null });
    if (path === '/api/me/on-this-day') return json(route, { today: '2026-09-10', timezone: 'UTC', anniversaries: [], fallback: memory });
    if (path === '/api/me/rediscovery/shuffle') return json(route, { memory });
    if (path === '/api/me/rediscovery/year-review') return json(route, { year: 2025, memory_count: 4, months_represented: ['September', 'October'] });
    if (path === '/api/me/rediscovery/collections') return json(route, { items: [{ key: 'coast', title: 'Coast memories', memory_ids: ['memory-1'] }] });
    if (path === '/api/invitations/invite-ref' && request.method() === 'GET') return json(route, { id: 'invite-1', tandem_id: 't1', tandem_name: 'Sunday table', invited_email: 'friend@example.test', status: invitationStatus, expires_at: '2026-10-01T00:00:00Z', inviter_name: 'Alex', memory_count: 4, earliest_memory_date: '2024-09-10' });
    if (path === '/api/invitations/invite-ref/accept' && request.method() === 'POST') { invitationStatus = 'ACCEPTED'; return json(route, { tandem_id: 't1', tandem_name: 'Sunday table', status: 'ACCEPTED' }); }
    if (path.match(/^\/api\/tandems\/(t1|t2)\/members$/)) return json(route, members[url.pathname.split('/')[3]]);
    if (path.match(/^\/api\/tandems\/(t1|t2)\/memories$/)) return json(route, { items: [memory], offset: 0, limit: 50, next_offset: null });
    if (path.match(/^\/api\/tandems\/(t1|t2)\/memories\/memory-1$/) && request.method() === 'GET') return json(route, memory);
    if (path === '/api/tandems/t1/memories/deleted') return json(route, { items: deleted ? [{ ...memory, deleted_at: '2026-09-10T00:00:00Z', deletion_expires_at: '2026-10-10T00:00:00Z' }] : [] });
    if (path === '/api/tandems/t1/memories/memory-1/restore') { deleted = false; return json(route, memory); }
    if (path === '/api/tandems/t1/memories/memory-1/permanent') { deleted = false; return json(route, null, 204); }
    if (path === '/api/tandems/t1/memories/memory-1/reflections/me') return json(route, { id: 'reflection-me', user_id: 'user-a', display_name: 'Alex', rating: 8, note: 'A keeper.', reaction: 'loved', created_at: '2026-09-10T00:00:00Z', updated_at: '2026-09-10T00:00:00Z' });
    if (path.match(/^\/api\/tandems\/(t1|t2)\/memories\/duplicates$/)) return json(route, [{ id: 'memory-1', title: 'Coast weekend', local_date: '2024-09-10', category: 'trip' }]);
    if (path === '/api/integrations/movies/search') return json(route, { items: [{ tmdb_id: 123, title: 'The Last Sunday', original_title: 'The Last Sunday', release_date: '2024-01-01', release_year: 2024, poster_url: '/placeholder-movie.svg', backdrop_url: '/placeholder-movie.svg', overview: 'A compact provider result.', genres: ['Drama'], runtime_minutes: 100 }] });
    if (path === '/api/tandems/t1/preferences' && request.method() === 'GET') return json(route, { tandem_id: 't1', resurfacing_enabled: true, routine_notifications_enabled: true });
    if (path === '/api/tandems/t1/preferences' && request.method() === 'PATCH') return json(route, { tandem_id: 't1', resurfacing_enabled: false, routine_notifications_enabled: true });
    if (path === '/api/tandems/t1/invitations' && request.method() === 'GET') return json(route, [{ id: 'invite-1', tandem_id: 't1', tandem_name: 'Sunday table', invited_email: 'friend@example.test', status: 'PENDING', expires_at: '2026-10-01T00:00:00Z' }]);
    if (path === '/api/tandems/t1/invitations' && request.method() === 'POST') return json(route, { reference: 'invite-ref', invited_email: 'friend@example.test', memory_count: 4, earliest_memory_date: '2024-09-10' }, 201);
    if (path === '/api/tandems/t1/memories' && request.method() === 'POST') return json(route, memory, 201);
    if (path === '/api/tandems/t1/memories/memory-1' && request.method() === 'DELETE') { deleted = true; return json(route, null, 204); }
    return route.continue();
  });
}

async function selectTandem(page, name = 'Sunday table') {
  await page.locator('.top-tandem-switcher').click();
  await page.getByRole('menuitem', { name: new RegExp(name) }).click();
}

test.describe('Tandem V1 authenticated acceptance', () => {
  test('scopes navigation, simplified capture, TMDb selection, participants, and duplicate warning', async ({ page }) => {
    await installAuthenticatedApi(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Your shared story, lately.' })).toBeVisible();
    await selectTandem(page);
    await expect(page.getByText('Keep finding your way back.')).toBeVisible();
    await expect(page.getByText('Sunday table').first()).toBeVisible();
    await page.getByRole('button', { name: 'Add memory' }).first().click();
    await page.getByRole('button', { name: /Movie/ }).click();
    await expect(page.getByRole('dialog', { name: /Add a movie/ })).toBeVisible();
    await expect(page.getByText(/Visible to 2 members/)).toBeVisible();
    await page.getByLabel('Add to').selectOption('t2');
    await expect(page.getByText(/Adding to Weekend circle/)).toBeVisible();
    await page.getByLabel('Search for a movie').fill('Sunday');
    await expect(page.getByRole('button', { name: /The Last Sunday/ })).toBeVisible();
    await page.getByRole('button', { name: /The Last Sunday/ }).click();
    await expect(page.getByText(/Saved TMDb snapshot/)).toBeVisible();
    await page.getByRole('button', { name: 'More details' }).click();
    await expect(page.getByText('Who was there?', { exact: true })).toBeVisible();
    await expect(page.getByRole('checkbox', { name: 'Alex' })).toBeChecked();
    await expect(page.getByRole('alert')).toContainText('This looks similar');
    await page.screenshot({ path: 'test-results/acceptance-scoped-today-and-capture.png', fullPage: true });
  });

  test('invitation history, copy success, acceptance, reflections, reactions, and recovery', async ({ page }) => {
    await installAuthenticatedApi(page);
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write'], { origin: 'http://127.0.0.1:4173' });
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Your shared story, lately.' })).toBeVisible();
    await selectTandem(page);
    await page.getByRole('button', { name: 'People & settings' }).click();
    await expect(page.getByRole('heading', { name: 'People & settings' })).toBeVisible();
    await page.getByLabel('Invite someone').fill('friend@example.test');
    await page.getByRole('button', { name: 'Create invite' }).click();
    await expect(page.getByText('Invitation history')).toBeVisible();
    await page.getByRole('button', { name: 'Copy link' }).click();
    await expect(page.getByRole('button', { name: 'Copied' })).toBeVisible();
    await expect(page.getByText('Invite link copied.')).toBeVisible();
    await page.goto('/?invite=invite-ref');
    await expect(page.getByRole('heading', { name: 'Join Sunday table' })).toBeVisible();
    await expect(page.getByText(/4 existing memories/)).toBeVisible();
    await page.getByRole('button', { name: /Accept invitation/ }).click();
    await expect(page.getByRole('heading', { name: 'Join Sunday table' })).toBeHidden();
    await selectTandem(page);
    await page.getByRole('button', { name: 'Coast weekend', exact: true }).first().click();
    await expect(page.getByRole('heading', { name: 'Add a personal reflection' })).toBeVisible();
    await page.getByLabel('Rating').fill('8');
    await page.getByLabel('Reaction').selectOption('loved');
    await page.getByLabel('Reflection').fill('A keeper.');
    await page.getByRole('button', { name: 'Save my reflection' }).click();
    await expect(page.getByText('Your reflection is saved.')).toBeVisible();
    await page.getByRole('button', { name: /Delete$/ }).click();
    await expect(page.getByRole('dialog', { name: /Recently Deleted/ })).toBeVisible();
    await page.getByRole('button', { name: 'Move to Recently Deleted' }).click();
    await page.getByRole('button', { name: 'Recently Deleted' }).click();
    await expect(page.getByRole('heading', { name: 'Recently Deleted' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Coast weekend' })).toBeVisible();
    await page.getByRole('button', { name: 'Restore' }).click();
    await expect(page.getByText('Nothing waiting here.')).toBeVisible();
    await page.screenshot({ path: 'test-results/acceptance-recovery-and-reflection.png', fullPage: true });
  });

  test('mode/search state, calendar trip range, rediscovery, preferences, and destructive modal', async ({ page }) => {
    await installAuthenticatedApi(page);
    await page.setViewportSize({ width: 1600, height: 900 });
    await page.goto('/memories?view=gallery&q=Coast');
    await expect(page.getByRole('heading', { name: 'Memories' })).toBeVisible();
    await expect(page.getByPlaceholder('Search your memories')).toHaveValue('Coast');
    await page.getByRole('button', { name: 'Coast weekend', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Coast weekend' })).toBeVisible();
    await page.getByRole('button', { name: 'Back to Memories' }).click();
    await expect(page).toHaveURL(/\/memories\?view=gallery&q=Coast/);
    await expect(page.getByPlaceholder('Search your memories')).toHaveValue('Coast');
    await page.goto('/calendar');
    await expect(page.getByRole('heading', { name: 'Calendar' })).toBeVisible();
    await page.goto('/memory/memory-1');
    await expect(page.getByText(/September 10, 2024 – September 12, 2024/)).toBeVisible();
    await page.goto('/');
    await selectTandem(page);
    await expect(page.getByText('A memory worth revisiting')).toBeVisible();
    await expect(page.getByText('Last year')).toBeVisible();
    await expect(page.getByText('Coast memories')).toBeVisible();
    await page.getByRole('button', { name: 'People & settings' }).click();
    await expect(page.getByText('Resurface memories from this Tandem')).toBeVisible();
    await expect(page.getByText('Routine Tandem notifications')).toBeVisible();
    await page.getByRole('button', { name: 'Delete Tandem' }).click();
    await expect(page.getByRole('dialog', { name: /Delete Sunday table/ })).toBeVisible();
    await page.getByRole('button', { name: 'Cancel' }).click();
    await page.screenshot({ path: 'test-results/acceptance-rediscovery-and-management.png', fullPage: true });
  });
});
