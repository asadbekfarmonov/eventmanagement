const { test, expect } = require('@playwright/test');

const proofFile = {
  name: 'proof.png',
  mimeType: 'image/png',
  buffer: Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9sW7xwAAAABJRU5ErkJggg==',
    'base64',
  ),
};

async function openBooking(page) {
  await page.goto('/?tg_id=511308234');
  await page.getByRole('tab', { name: 'Book' }).click();
  await expect(page.locator('#events-list .event-card')).toHaveCount(2);
}

async function openAdmin(page) {
  await page.goto('/?tg_id=7164876915&open_admin=1');
  await expect(page.locator('#admin-area')).toBeVisible();
}

async function selectAdminEventByTitle(page, title) {
  await page.getByRole('tab', { name: 'Events' }).click();
  await expect(page.locator('#admin-section-events')).toBeVisible();
  const value = await page.locator('#admin-event-select').evaluate((select, targetTitle) => {
    const option = Array.from(select.options).find((item) => item.textContent && item.textContent.includes(targetTitle));
    return option ? option.value : '';
  }, title);
  expect(value).not.toBe('');
  await page.locator('#admin-event-select').selectOption(value);
}

async function selectEventByTitle(page, title) {
  const card = page.locator('#events-list .event-card').filter({ hasText: title }).first();
  await expect(card).toBeVisible();
  await card.click();
}

test('booking stays blocked until payment proof is uploaded', async ({ page }) => {
  await openBooking(page);
  await selectEventByTitle(page, 'Playwright Event');

  await page.locator('#boys').fill('1');
  await page.locator('#girls').fill('1');

  await expect(page.locator('.attendee-row')).toHaveCount(2);
  await page.locator('.attendee-row').nth(0).locator('input[data-part="first"]').fill('John');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="surname"]').fill('Doe');
  await page.locator('.attendee-row').nth(1).locator('input[data-part="first"]').fill('Jane');
  await page.locator('.attendee-row').nth(1).locator('input[data-part="surname"]').fill('Doe');

  await expect(page.locator('#summary')).toContainText('Total: 5000.00');
  await expect(page.locator('#submit-booking')).toBeDisabled();

  await page.locator('#payment-proof').setInputFiles(proofFile);
  await expect(page.locator('#submit-booking')).toBeDisabled();
  await expect(page.locator('.terms-box')).toContainText('Booking Terms');

  await page.locator('#terms-accepted').check();
  await expect(page.locator('#submit-booking')).toBeEnabled();
});

test('booking submission shows pending status and appears in my tickets', async ({ page }) => {
  await openBooking(page);
  await selectEventByTitle(page, 'Playwright Event');

  await page.locator('#boys').fill('1');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="first"]').fill('John');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="surname"]').fill('Doe');
  await page.locator('#payment-proof').setInputFiles(proofFile);
  await page.locator('#terms-accepted').check();

  await expect(page.locator('#submit-booking')).toBeEnabled();
  await page.locator('#submit-booking').click();

  await expect(page.locator('#status')).toContainText('Booking sent for review. Code:');
  await expect(page.locator('#boys')).toHaveValue('0');
  await expect(page.locator('#girls')).toHaveValue('0');
  await expect(page.locator('#terms-accepted')).not.toBeChecked();
  await expect(page.locator('#submit-booking')).toBeDisabled();
  await expect(page.locator('#tickets-list')).toContainText('pending_payment_review');
  await expect(page.locator('#tickets-list')).toContainText('Tier: Early Bird');
});

test('discounted attendee requires repost screenshot and updates final total', async ({ page }) => {
  await openBooking(page);
  await selectEventByTitle(page, 'Discount Event');

  await page.locator('#boys').fill('1');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="first"]').fill('John');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="surname"]').fill('Doe');

  await expect(page.locator('#summary')).toContainText('Base total: 2500.00');
  await expect(page.locator('#summary')).toContainText('Instagram repost discount: 1000.00 per guest.');
  await expect(page.locator('.attendee-row').nth(0).locator('input[data-part="repost-file"]')).toBeDisabled();

  await page.locator('.attendee-row').nth(0).locator('input[data-part="repost-check"]').check();
  await expect(page.locator('.attendee-row').nth(0).locator('input[data-part="repost-file"]')).toBeEnabled();
  await expect(page.locator('.attendee-row').nth(0).locator('input[data-part="repost-file"]')).toBeVisible();
  await page.locator('#payment-proof').setInputFiles(proofFile);
  await expect(page.locator('#submit-booking')).toBeDisabled();
  await expect(page.locator('#summary')).toContainText('Upload a repost screenshot for each guest using the discount.');

  await page.locator('.attendee-row').nth(0).locator('input[data-part="repost-file"]').setInputFiles(proofFile);
  await expect(page.locator('#summary')).not.toContainText('Upload a repost screenshot for each guest using the discount.');
  await expect(page.locator('#status')).toHaveText('');
  await expect(page.locator('#summary')).toContainText('Repost discount: 1 x 1000.00 = 1000.00');
  await expect(page.locator('#summary')).toContainText('Final total: 1500.00');
  await expect(page.locator('#submit-booking')).toBeDisabled();

  await page.locator('#terms-accepted').check();
  await expect(page.locator('#submit-booking')).toBeEnabled();
});

test('admin can enable repost discount on existing event and guest sees it', async ({ page }) => {
  await openAdmin(page);

  await selectAdminEventByTitle(page, 'Playwright Event');
  await page.locator('#admin-ev-repost-enabled').selectOption('1');
  await page.locator('#admin-ev-repost-amount').fill('1000');
  await page.locator('#admin-event-save').click();

  await expect(page.locator('#admin-status')).toContainText('Event updated.');
  await expect(page.locator('#admin-ev-repost-enabled')).toHaveValue('1');
  await expect(page.locator('#admin-ev-repost-amount')).toHaveValue('1000');

  await page.goto('/?tg_id=511308234');
  await page.getByRole('tab', { name: 'Book' }).click();
  await expect(page.locator('#events-list .event-card')).toHaveCount(2);
  await selectEventByTitle(page, 'Playwright Event');
  await page.locator('#boys').fill('1');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="first"]').fill('John');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="surname"]').fill('Doe');

  await expect(page.locator('#summary')).toContainText('Instagram repost discount: 1000.00 per guest.');
  await expect(page.locator('.attendee-row').nth(0).locator('input[data-part="repost-check"]')).toBeVisible();
});

test('admin navigation is hidden for non-admins', async ({ page }) => {
  await page.goto('/?tg_id=511308234');

  await expect(page.locator('#admin-open')).toBeHidden();
  await expect(page.locator('#admin-area')).toBeHidden();
});

test('top navigation shows one public section at a time', async ({ page }) => {
  await page.goto('/?tg_id=511308234');

  await expect(page.locator('#main-panel')).toBeVisible();
  await expect(page.locator('#main-panel')).toContainText('We started this because we missed');
  await expect(page.locator('#upcoming-events-list .upcoming-card')).toHaveCount(2);
  await expect(page.locator('.main-carousel-slide img')).toHaveCount(3);
  await expect(page.locator('.main-carousel-slide img').first()).toBeVisible();
  await expect(page.locator('#events-panel')).toBeHidden();
  await expect(page.locator('#tickets-panel')).toBeHidden();
  await expect(page.locator('#contact-panel')).toBeHidden();

  await page.getByRole('tab', { name: 'Book' }).click();
  await expect(page.locator('#main-panel')).toBeHidden();
  await expect(page.locator('#events-panel')).toBeVisible();

  await page.getByRole('tab', { name: 'My tickets' }).click();
  await expect(page.locator('#events-panel')).toBeHidden();
  await expect(page.locator('#tickets-panel')).toBeVisible();

  await page.getByRole('tab', { name: 'Main' }).click();
  await expect(page.locator('#tickets-panel')).toBeHidden();
  await expect(page.locator('#main-panel')).toBeVisible();

  await page.getByRole('tab', { name: 'Contact' }).click();
  await expect(page.locator('#main-panel')).toBeHidden();
  await expect(page.locator('#contact-panel')).toBeVisible();
});

test('homepage leads with upcoming events and Get tickets preselects the event', async ({ page }) => {
  await page.goto('/?tg_id=511308234');
  await expect(page.locator('#main-panel')).toBeVisible();

  const upcomingCards = page.locator('#upcoming-events-list .upcoming-card');
  await expect(upcomingCards).toHaveCount(2);

  const discountCard = upcomingCards.filter({ hasText: 'Discount Event' }).first();
  await expect(discountCard).toContainText('From');
  await expect(discountCard.locator('.upcoming-where')).toContainText('Budapest');
  // No event <img> is rendered from event data (Telegram-only photo_file_id).
  await expect(discountCard.locator('img')).toHaveCount(0);

  await discountCard.getByRole('button', { name: 'Get tickets' }).click();

  await expect(page.locator('#main-panel')).toBeHidden();
  await expect(page.locator('#events-panel')).toBeVisible();

  const activeCard = page.locator('#events-list .event-card.active');
  await expect(activeCard).toHaveCount(1);
  await expect(activeCard).toContainText('Discount Event');
});

test('website visitor registers before booking', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('tab', { name: 'Book' }).click();
  await expect(page.locator('#account-panel')).toBeVisible();

  await page.locator('#account-name').fill('Web');
  await page.locator('#account-surname').fill('Guest');
  await page.locator('#account-email').fill('web.guest@example.invalid');
  await page.locator('#account-phone').fill('+36 20 555 0101');
  await expect(page.locator('#account-send-code')).toBeVisible();
  await page.locator('#account-send-code').click();
  await expect(page.locator('#account-code-panel')).toBeVisible();
  await page.locator('#account-verify').click();

  await expect(page.locator('#profile-card')).toBeVisible();
  await expect(page.locator('#profile-name')).toHaveText('Web Guest');
  await expect(page.locator('#profile-email')).toHaveText('web.guest@example.invalid');
  await expect(page.locator('#profile-phone')).toHaveText('+36 20 555 0101');
  await page.locator('#boys').fill('1');
  await expect(page.locator('input[data-part="first"]').first()).toHaveValue('Web');
  await expect(page.locator('input[data-part="surname"]').first()).toHaveValue('Guest');
});

test('website admin logs in from admin page', async ({ page }) => {
  await page.goto('/admin');

  await expect(page.locator('#admin-area')).toBeVisible();
  await expect(page.locator('#admin-login-panel')).toBeVisible();
  await expect(page.locator('.admin-tabs')).toBeHidden();

  await page.locator('#admin-password').fill('playwright-admin-password');
  await page.locator('#admin-login').click();

  await expect(page.locator('#admin-login-panel')).toBeHidden();
  await expect(page.locator('#admin-ident')).toContainText('website');
  await expect(page.locator('.admin-tabs')).toBeVisible();
  await expect(page.locator('#admin-event-select')).toContainText('Playwright Event');
});

test('admin navigation appears for admins only', async ({ page }) => {
  await page.goto('/?tg_id=7164876915');

  await expect(page.locator('#admin-open')).toBeVisible();
  await page.locator('#admin-open').click();
  await expect(page.locator('#admin-area')).toBeVisible();
  await page.getByRole('tab', { name: 'Check-in' }).click();
  await expect(page.locator('[data-admin-section="checkin"]')).toBeVisible();
  await expect(page.locator('#admin-checkin-token')).toBeVisible();
  await expect(page.locator('#admin-checkin-confirm')).toBeDisabled();
});

test('check-in scanner degrades gracefully and the manual paste flow stays wired', async ({ page }) => {
  await page.goto('/?tg_id=7164876915&open_admin=1');
  await expect(page.locator('#admin-area')).toBeVisible();
  await page.getByRole('tab', { name: 'Check-in' }).click();
  await expect(page.locator('#admin-section-checkin')).toBeVisible();

  // The self-hosted jsQR fallback must be reachable as a same-origin script
  // (CSP forbids external CDNs, so this file has to be served from /static).
  const jsqr = await page.request.get('/static/jsqr.js');
  expect(jsqr.status()).toBe(200);
  expect(jsqr.headers()['content-type'] || '').toMatch(/javascript|ecmascript/);
  expect((await jsqr.text()).length).toBeGreaterThan(50000);

  // Headless Chromium has no camera: starting the scanner must surface a clear,
  // actionable message rather than throwing or hanging.
  await page.locator('#admin-scan-start').click();
  const result = page.locator('#admin-checkin-result');
  await expect(result).toContainText(/camera|code/i, { timeout: 15000 });

  // Manual paste + Lookup remains fully functional; an unknown token reports back.
  await page.locator('#admin-checkin-token').fill('does-not-exist-token');
  await page.locator('#admin-checkin-lookup').click();
  await expect(result).toContainText(/not found|failed|Ticket/i, { timeout: 15000 });
  await expect(page.locator('#admin-checkin-confirm')).toBeDisabled();
});

test('homepage shows the empty state when there are no upcoming events', async ({ page }) => {
  await page.route('**/api/events', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    }),
  );

  await page.goto('/?tg_id=511308234');
  await expect(page.locator('#main-panel')).toBeVisible();

  await expect(page.locator('#upcoming-events-list .upcoming-card')).toHaveCount(0);
  const empty = page.locator('#upcoming-events-empty');
  await expect(empty).toBeVisible();
  await expect(empty).toContainText('No upcoming events yet');
});

test('upcoming event title, caption and location are HTML-escaped (no XSS)', async ({ page }) => {
  await page.route('**/api/events', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [
          {
            id: 4242,
            title: '<img src=x onerror="window.__xss=1">Evil Title',
            event_datetime: '2026-05-05 20:00',
            location: '<b>Danger Venue</b>',
            caption: '<script>window.__xssCaption=1</script>Sneaky caption',
            photo_file_id: '',
            repost_discount_enabled: 0,
            repost_discount_amount: 0,
            girls_group_offer_enabled: 0,
            boys_group_offer_enabled: 0,
            tier: { key: 'early', name: 'Early Bird', boy_price: 2500, girl_price: 3000 },
            payment_options: [],
          },
        ],
      }),
    }),
  );

  await page.goto('/?tg_id=511308234');
  await expect(page.locator('#main-panel')).toBeVisible();

  const card = page.locator('#upcoming-events-list .upcoming-card');
  await expect(card).toHaveCount(1);

  // No injected elements from the malicious strings.
  await expect(card.locator('img')).toHaveCount(0);
  await expect(card.locator('b')).toHaveCount(0);
  await expect(card.locator('script')).toHaveCount(0);

  // Payloads survive as escaped literal text.
  await expect(card.locator('.event-title')).toHaveText('<img src=x onerror="window.__xss=1">Evil Title');
  await expect(card.locator('.upcoming-where')).toHaveText('<b>Danger Venue</b>');
  await expect(card.locator('.event-meta')).toContainText('<script>window.__xssCaption=1</script>Sneaky caption');

  // "From" uses the lowest positive price.
  await expect(card.locator('.event-price')).toContainText('From 2500.00 Ft');

  // Neither injected handler executed.
  expect(await page.evaluate(() => window.__xss)).toBeUndefined();
  expect(await page.evaluate(() => window.__xssCaption)).toBeUndefined();
});


test('page tabs expose ARIA tab semantics and account dialog manages focus', async ({ page }) => {
  await page.goto('/?tg_id=511308234');

  const mainTab = page.getByRole('tab', { name: 'Main' });
  const bookTab = page.getByRole('tab', { name: 'Book' });
  await expect(mainTab).toHaveAttribute('aria-selected', 'true');
  await expect(bookTab).toHaveAttribute('aria-selected', 'false');
  await expect(bookTab).toHaveAttribute('aria-controls', /events-panel/);

  await bookTab.click();
  await expect(bookTab).toHaveAttribute('aria-selected', 'true');
  await expect(mainTab).toHaveAttribute('aria-selected', 'false');

  // Account dialog: opens as a modal, moves focus in, and restores focus on close.
  await page.getByRole('tab', { name: 'Main' }).click();
  await page.locator('#account-open').click();
  await expect(page.locator('#account-panel')).toBeVisible();
  await expect(page.locator('#account-panel')).toHaveAttribute('aria-modal', 'true');

  const focusInside = await page.evaluate(() =>
    document.getElementById('account-panel').contains(document.activeElement),
  );
  expect(focusInside).toBe(true);

  await page.keyboard.press('Escape');
  await expect(page.locator('#account-panel')).toBeHidden();
  const focusRestored = await page.evaluate(
    () => document.activeElement === document.getElementById('account-open'),
  );
  expect(focusRestored).toBe(true);
});

test('account dialog focus trap wraps with Tab and Shift+Tab', async ({ page }) => {
  // Unregistered visitor: opening the panel shows the multi-field edit form.
  await page.goto('/');
  await page.locator('#account-open').click();
  await expect(page.locator('#account-panel')).toBeVisible();
  await expect(page.locator('#account-name')).toBeVisible();

  const FOCUSABLE =
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
    'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  const count = await page.evaluate((sel) => {
    const panel = document.getElementById('account-panel');
    return Array.from(panel.querySelectorAll(sel)).filter(
      (el) => !el.hidden && !el.closest('[hidden]') && el.offsetParent !== null,
    ).length;
  }, FOCUSABLE);
  expect(count).toBeGreaterThan(1);

  // Focus the LAST focusable, press Tab -> should wrap to the FIRST.
  const wrappedForward = await page.evaluate((sel) => {
    const panel = document.getElementById('account-panel');
    const items = Array.from(panel.querySelectorAll(sel)).filter(
      (el) => !el.hidden && !el.closest('[hidden]') && el.offsetParent !== null,
    );
    items[items.length - 1].focus();
    return document.activeElement === items[items.length - 1];
  }, FOCUSABLE);
  expect(wrappedForward).toBe(true);
  await page.keyboard.press('Tab');
  const onFirst = await page.evaluate((sel) => {
    const panel = document.getElementById('account-panel');
    const items = Array.from(panel.querySelectorAll(sel)).filter(
      (el) => !el.hidden && !el.closest('[hidden]') && el.offsetParent !== null,
    );
    return document.activeElement === items[0];
  }, FOCUSABLE);
  expect(onFirst).toBe(true);

  // Focus the FIRST focusable, press Shift+Tab -> should wrap to the LAST.
  await page.evaluate((sel) => {
    const panel = document.getElementById('account-panel');
    const items = Array.from(panel.querySelectorAll(sel)).filter(
      (el) => !el.hidden && !el.closest('[hidden]') && el.offsetParent !== null,
    );
    items[0].focus();
  }, FOCUSABLE);
  await page.keyboard.press('Shift+Tab');
  const onLast = await page.evaluate((sel) => {
    const panel = document.getElementById('account-panel');
    const items = Array.from(panel.querySelectorAll(sel)).filter(
      (el) => !el.hidden && !el.closest('[hidden]') && el.offsetParent !== null,
    );
    return document.activeElement === items[items.length - 1];
  }, FOCUSABLE);
  expect(onLast).toBe(true);
});

test('opening the account panel from the Book tab works and restores focus on Esc', async ({ page }) => {
  await page.goto('/?tg_id=511308234');
  await page.getByRole('tab', { name: 'Book' }).click();
  await expect(page.locator('#events-panel')).toBeVisible();

  await page.locator('#account-open').click();
  await expect(page.locator('#account-panel')).toBeVisible();
  await expect(page.locator('#account-panel')).toHaveAttribute('aria-modal', 'true');
  const focusInside = await page.evaluate(() =>
    document.getElementById('account-panel').contains(document.activeElement),
  );
  expect(focusInside).toBe(true);

  await page.keyboard.press('Escape');
  await expect(page.locator('#account-panel')).toBeHidden();
  // Book tab still active and focus restored to the opener.
  await expect(page.getByRole('tab', { name: 'Book' })).toHaveAttribute('aria-selected', 'true');
  const restored = await page.evaluate(
    () => document.activeElement === document.getElementById('account-open'),
  );
  expect(restored).toBe(true);
});

test('admin tab switching toggles aria-selected and shows the correct section', async ({ page }) => {
  await page.goto('/?tg_id=7164876915&open_admin=1');
  await expect(page.locator('#admin-area')).toBeVisible();

  const eventsTab = page.getByRole('tab', { name: 'Events' });
  const guestsTab = page.getByRole('tab', { name: 'Guests' });
  const checkinTab = page.getByRole('tab', { name: 'Check-in' });

  const paymentsTab = page.getByRole('tab', { name: 'Payments' });

  // Default: Payments selected and its section visible.
  await expect(paymentsTab).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#admin-section-payments')).toBeVisible();
  await expect(page.locator('#admin-section-events')).toBeHidden();

  // Switch to Events.
  await eventsTab.click();
  await expect(eventsTab).toHaveAttribute('aria-selected', 'true');
  await expect(paymentsTab).toHaveAttribute('aria-selected', 'false');
  await expect(page.locator('#admin-section-events')).toBeVisible();
  await expect(page.locator('#admin-section-guests')).toBeHidden();

  // Switch to Guests.
  await guestsTab.click();
  await expect(guestsTab).toHaveAttribute('aria-selected', 'true');
  await expect(eventsTab).toHaveAttribute('aria-selected', 'false');
  await expect(page.locator('#admin-section-guests')).toBeVisible();
  await expect(page.locator('#admin-section-events')).toBeHidden();

  // Switch to Check-in.
  await checkinTab.click();
  await expect(checkinTab).toHaveAttribute('aria-selected', 'true');
  await expect(guestsTab).toHaveAttribute('aria-selected', 'false');
  await expect(page.locator('#admin-section-checkin')).toBeVisible();
  await expect(page.locator('#admin-section-guests')).toBeHidden();
});

test('website visitor never requests telegram.org', async ({ page }) => {
  const telegramRequests = [];
  page.on('request', (request) => {
    if (request.url().includes('telegram.org')) {
      telegramRequests.push(request.url());
    }
  });

  // Plain website visitor: no Telegram context (no tgWebAppData / proxy).
  await page.goto('/');
  await expect(page.locator('#upcoming-events')).toBeVisible();
  // The app must be usable without the Telegram SDK being loaded.
  await page.getByRole('tab', { name: 'Book' }).click();
  await expect(page.locator('#events-list .event-card')).toHaveCount(2);

  expect(telegramRequests).toEqual([]);
});


test('admin can set event date-time and location from the web form', async ({ page }) => {
  await openAdmin(page);
  await selectAdminEventByTitle(page, 'Discount Event');

  await page.locator('#admin-ev-when').fill('2026-09-15 20:30');
  await page.locator('#admin-ev-location').fill('Akvarium Klub');
  await page.locator('#admin-event-save').click();

  await expect(page.locator('#admin-status')).toContainText('Event updated.');
  await expect(page.locator('#admin-ev-when')).toHaveValue('2026-09-15 20:30');
  await expect(page.locator('#admin-ev-location')).toHaveValue('Akvarium Klub');
});

test('admin rejects an invalid date-time before saving', async ({ page }) => {
  await openAdmin(page);
  await selectAdminEventByTitle(page, 'Discount Event');

  await page.locator('#admin-ev-when').fill('15/09/2026 20:30');
  await page.locator('#admin-event-save').click();

  await expect(page.locator('#admin-status')).toContainText('YYYY-MM-DD HH:MM');
});

test('admin can review and approve a pending payment', async ({ page }) => {
  // Seed a pending reservation through the public booking flow.
  await openBooking(page);
  await selectEventByTitle(page, 'Playwright Event');
  await page.locator('#boys').fill('1');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="first"]').fill('Pending');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="surname"]').fill('Guest');
  await page.locator('#payment-proof').setInputFiles(proofFile);
  await page.locator('#terms-accepted').check();
  await expect(page.locator('#submit-booking')).toBeEnabled();
  await page.locator('#submit-booking').click();
  await expect(page.locator('#status')).toContainText('Booking sent for review. Code:');
  const statusText = (await page.locator('#status').textContent()) || '';
  const code = (statusText.match(/Code:\s*([A-Za-z0-9-]+)/) || [])[1];
  expect(code).toBeTruthy();

  // Admin opens the dashboard; Payments is the default section.
  await openAdmin(page);
  await expect(page.locator('#admin-section-payments')).toBeVisible();
  const card = page.locator('#admin-reviews-list .admin-card').filter({ hasText: code });
  await expect(card).toBeVisible();
  await expect(card.locator('.admin-proof-thumb')).toBeVisible();

  await card.locator('button[data-action="approve"]').click();
  await expect(page.locator('#admin-status')).toContainText('approved');
  await expect(page.locator('#admin-reviews-list')).not.toContainText(code);
});

test('admin can log out and returns to the main page', async ({ page }) => {
  await openAdmin(page);
  await expect(page.locator('.admin-tabs')).toBeVisible();

  await page.locator('#admin-logout').click();

  await expect(page.locator('#main-panel')).toBeVisible();
  await expect(page.locator('.admin-tabs')).toBeHidden();
});

test('web user can cancel a pending booking from My tickets', async ({ page }) => {
  await openBooking(page);
  await selectEventByTitle(page, 'Playwright Event');

  await page.locator('#boys').fill('1');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="first"]').fill('Cancel');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="surname"]').fill('Me');
  await page.locator('#payment-proof').setInputFiles(proofFile);
  await page.locator('#terms-accepted').check();
  await expect(page.locator('#submit-booking')).toBeEnabled();
  await page.locator('#submit-booking').click();

  await expect(page.locator('#status')).toContainText('Booking sent for review. Code:');
  const statusText = await page.locator('#status').textContent();
  const code = (statusText.match(/Code:\s*([A-Za-z0-9-]+)/) || [])[1];
  expect(code).toBeTruthy();
  await expect(page.locator('#tickets-list')).toContainText('pending_payment_review');

  // Open the My tickets tab so the ticket cards (and their buttons) are visible.
  await page.getByRole('tab', { name: 'My tickets' }).click();
  await expect(page.locator('#tickets-panel')).toBeVisible();

  // Scope to the card for the booking we just created (the shared e2e DB may hold others).
  const card = page.locator('#tickets-list .admin-card').filter({ hasText: code });
  await expect(card).toHaveCount(1);
  const cancelBtn = card.locator('.ticket-cancel-btn');
  await expect(cancelBtn).toHaveCount(1);

  page.once('dialog', (dialog) => dialog.accept());
  await cancelBtn.click();

  // After cancel + reload, this booking's card shows cancelled with no cancel button.
  const cancelledCard = page.locator('#tickets-list .admin-card').filter({ hasText: code });
  await expect(cancelledCard).toContainText('cancelled');
  await expect(cancelledCard.locator('.ticket-cancel-btn')).toHaveCount(0);
});

test('website account shows a Log out button that returns to the logged-out state', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('tab', { name: 'Book' }).click();
  await expect(page.locator('#account-panel')).toBeVisible();

  await page.locator('#account-name').fill('Logout');
  await page.locator('#account-surname').fill('Tester');
  await page.locator('#account-email').fill('logout.tester@example.invalid');
  await page.locator('#account-phone').fill('+36 20 555 0202');
  await page.locator('#account-send-code').click();
  await expect(page.locator('#account-code-panel')).toBeVisible();
  await page.locator('#account-verify').click();

  await expect(page.locator('#profile-card')).toBeVisible();
  await expect(page.locator('#account-logout')).toBeVisible();

  await page.locator('#account-logout').click();

  // Back to logged-out state: profile hidden, the registration form is shown again.
  await page.locator('#account-open').click();
  await expect(page.locator('#profile-card')).toBeHidden();
  await expect(page.locator('#account-logout')).toBeHidden();
  await expect(page.locator('#account-name')).toBeVisible();
});

test('admin can rename a guest from the web guest list', async ({ page }) => {
  // Seed an approved reservation so the attendee appears in the guest list.
  await openBooking(page);
  await selectEventByTitle(page, 'Playwright Event');
  await page.locator('#boys').fill('1');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="first"]').fill('RenameMe');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="surname"]').fill('Guest');
  await page.locator('#payment-proof').setInputFiles(proofFile);
  await page.locator('#terms-accepted').check();
  await expect(page.locator('#submit-booking')).toBeEnabled();
  await page.locator('#submit-booking').click();
  await expect(page.locator('#status')).toContainText('Booking sent for review. Code:');
  const statusText = (await page.locator('#status').textContent()) || '';
  const code = (statusText.match(/Code:\s*([A-Za-z0-9-]+)/) || [])[1];
  expect(code).toBeTruthy();

  await openAdmin(page);
  const reviewCard = page.locator('#admin-reviews-list .admin-card').filter({ hasText: code });
  await expect(reviewCard).toBeVisible();
  await reviewCard.locator('button[data-action="approve"]').click();
  await expect(page.locator('#admin-status')).toContainText('approved');

  // Open the Guests tab and locate the renamed-to-be guest card.
  await page.getByRole('tab', { name: 'Guests' }).click();
  await expect(page.locator('#admin-section-guests')).toBeVisible();
  const guestCard = page.locator('#admin-guests-list .admin-card').filter({ hasText: 'RenameMe Guest' });
  await expect(guestCard).toBeVisible();

  const renameBtn = guestCard.locator('button[data-action="rename"]');
  await expect(renameBtn).toBeVisible();

  // Accept the prompt with a valid full name.
  page.once('dialog', (dialog) => dialog.accept('Renamed Person'));
  await renameBtn.click();

  await expect(page.locator('#admin-status')).toContainText('updated');
  const renamedCard = page.locator('#admin-guests-list .admin-card').filter({ hasText: 'Renamed Person' });
  await expect(renamedCard).toBeVisible();
});

test('footer Booking terms link opens the terms from another tab', async ({ page }) => {
  await page.goto('/?tg_id=511308234');
  // Start on the main page (Book sections hidden).
  await expect(page.locator('#summary-panel')).toBeHidden();

  await page.locator('#footer-terms-link').click();

  // Navigates to Book and reveals the terms section.
  await expect(page.getByRole('tab', { name: 'Book' })).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#summary-panel')).toBeVisible();
  const termsOpen = await page.locator('.terms-box details').evaluate((el) => el.open);
  expect(termsOpen).toBe(true);
});

test('website session persists across a page reload', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('tab', { name: 'Book' }).click();
  await expect(page.locator('#account-panel')).toBeVisible();

  await page.locator('#account-name').fill('Reload');
  await page.locator('#account-surname').fill('Persist');
  await page.locator('#account-email').fill('reload.persist@example.invalid');
  await page.locator('#account-phone').fill('+36 20 555 0303');
  await page.locator('#account-send-code').click();
  await expect(page.locator('#account-code-panel')).toBeVisible();
  await page.locator('#account-verify').click();

  await expect(page.locator('#profile-card')).toBeVisible();
  await expect(page.locator('#profile-email')).toHaveText('reload.persist@example.invalid');

  // Regression: after a reload the cookie session must be restored (the app must
  // probe /api/me on load), not fall back to the logged-out "log in again" state.
  await page.reload();
  // The account chip initials reflect the restored profile ("Reload Persist" -> "RP").
  await expect(page.locator('#account-chip-initials')).toHaveText('RP');

  await page.locator('#account-open').click();
  await expect(page.locator('#profile-card')).toBeVisible();
  await expect(page.locator('#profile-email')).toHaveText('reload.persist@example.invalid');
  // The registration/edit form is not shown because we are still logged in.
  await expect(page.locator('#account-name')).toBeHidden();
});
