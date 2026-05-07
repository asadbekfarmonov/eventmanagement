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
  await expect(page.locator('#events-list .event-card')).toHaveCount(2);
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
  await expect(page.locator('#submit-booking')).toBeEnabled();
});

test('booking submission shows pending status and appears in my tickets', async ({ page }) => {
  await openBooking(page);
  await selectEventByTitle(page, 'Playwright Event');

  await page.locator('#boys').fill('1');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="first"]').fill('John');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="surname"]').fill('Doe');
  await page.locator('#payment-proof').setInputFiles(proofFile);

  await expect(page.locator('#submit-booking')).toBeEnabled();
  await page.locator('#submit-booking').click();

  await expect(page.locator('#tickets-list')).toContainText('pending_payment_review');
  await expect(page.locator('#tickets-list')).toContainText('Playwright Event');
});

test('discounted attendee requires repost screenshot and updates final total', async ({ page }) => {
  await openBooking(page);
  await selectEventByTitle(page, 'Discount Event');

  await page.locator('#boys').fill('1');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="first"]').fill('John');
  await page.locator('.attendee-row').nth(0).locator('input[data-part="surname"]').fill('Doe');

  await expect(page.locator('#summary')).toContainText('Base total: 2500.00');
  await expect(page.locator('#summary')).toContainText('Repost discount available: 1000.00 per attendee.');

  await page.locator('.attendee-row').nth(0).locator('input[data-part="repost-check"]').check();
  await expect(page.locator('.attendee-row').nth(0).locator('input[data-part="repost-file"]')).toBeVisible();
  await page.locator('#payment-proof').setInputFiles(proofFile);
  await expect(page.locator('#submit-booking')).toBeDisabled();

  await page.locator('.attendee-row').nth(0).locator('input[data-part="repost-file"]').setInputFiles(proofFile);
  await expect(page.locator('#summary')).toContainText('Repost discount: 1 x 1000.00 = 1000.00');
  await expect(page.locator('#summary')).toContainText('Final total: 1500.00');
  await expect(page.locator('#submit-booking')).toBeEnabled();
});
