const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
const qs = new URLSearchParams(window.location.search);
const fallbackTgId = Number(qs.get('tg_id') || 0);
const tgId = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id) || fallbackTgId || null;
const tgInitData = (tg && tg.initData) || '';
const WEB_SESSION_KEY = 'bt_web_session';
const ADMIN_SESSION_KEY = 'bt_admin_session';
let webSessionToken = localStorage.getItem(WEB_SESSION_KEY) || '';
let adminSessionToken = localStorage.getItem(ADMIN_SESSION_KEY) || '';
const autoOpenAdmin = ['1', 'true', 'yes'].includes(
  (qs.get('open_admin') || qs.get('admin') || '').toLowerCase(),
);

const eventsListEl = document.getElementById('events-list');
const eventsEmptyEl = document.getElementById('events-empty');
const attendeesListEl = document.getElementById('attendees-list');
const boysEl = document.getElementById('boys');
const girlsEl = document.getElementById('girls');
const summaryEl = document.getElementById('summary');
const statusEl = document.getElementById('status');
const submitBtn = document.getElementById('submit-booking');
const paymentProofEl = document.getElementById('payment-proof');
const termsAcceptedEl = document.getElementById('terms-accepted');
const refreshBtn = document.getElementById('refresh-events');
const ticketsListEl = document.getElementById('tickets-list');
const ticketsEmptyEl = document.getElementById('tickets-empty');
const ticketsRefreshEl = document.getElementById('tickets-refresh');
const adminOpenStatusEl = document.getElementById('admin-open-status');
const pageTabs = Array.from(document.querySelectorAll('[data-page-tab]'));
const pageSections = Array.from(document.querySelectorAll('[data-page-section]'));
const carouselTrackEl = document.querySelector('.main-carousel-track');
const carouselDots = Array.from(document.querySelectorAll('.main-carousel-dots span'));
const accountPanelEl = document.getElementById('account-panel');
const accountStateEl = document.getElementById('account-state');
const accountStatusEl = document.getElementById('account-status');
const accountNameEl = document.getElementById('account-name');
const accountSurnameEl = document.getElementById('account-surname');
const accountPhoneEl = document.getElementById('account-phone');
const accountEmailEl = document.getElementById('account-email');
const accountHelpEl = document.getElementById('account-help');
const profileCardEl = document.getElementById('profile-card');
const profileNameEl = document.getElementById('profile-name');
const profileEmailEl = document.getElementById('profile-email');
const profilePhoneEl = document.getElementById('profile-phone');
const profileSourceEl = document.getElementById('profile-source');
const accountSaveEl = document.getElementById('account-save');
const accountEditEl = document.getElementById('account-edit');
const accountSendCodeEl = document.getElementById('account-send-code');
const accountCodePanelEl = document.getElementById('account-code-panel');
const accountCodeEl = document.getElementById('account-code');
const accountVerifyEl = document.getElementById('account-verify');
const googleSigninWrapEl = document.getElementById('google-signin-wrap');
const googleSigninButtonEl = document.getElementById('google-signin-button');

const adminEl = {
  open: document.getElementById('admin-open'),
  area: document.getElementById('admin-area'),
  loginPanel: document.getElementById('admin-login-panel'),
  login: document.getElementById('admin-login'),
  password: document.getElementById('admin-password'),
  refreshAll: document.getElementById('admin-refresh-all'),
  ident: document.getElementById('admin-ident'),
  status: document.getElementById('admin-status'),
  tabs: Array.from(document.querySelectorAll('.admin-tab')),
  sections: Array.from(document.querySelectorAll('.admin-section')),
  guestsSearch: document.getElementById('admin-guests-search'),
  guestsSort: document.getElementById('admin-guests-sort'),
  guestsRefresh: document.getElementById('admin-guests-refresh'),
  guestsList: document.getElementById('admin-guests-list'),
  addEventSelect: document.getElementById('admin-add-event-select'),
  guestGender: document.getElementById('admin-guest-gender'),
  guestName: document.getElementById('admin-guest-name'),
  guestSurname: document.getElementById('admin-guest-surname'),
  guestAdd: document.getElementById('admin-guest-add'),
  importEventSelect: document.getElementById('admin-import-event-select'),
  importFile: document.getElementById('admin-import-file'),
  importUpload: document.getElementById('admin-import-upload'),
  exportDownload: document.getElementById('admin-export-download'),
  eventsRefresh: document.getElementById('admin-events-refresh'),
  eventSelect: document.getElementById('admin-event-select'),
  eventSave: document.getElementById('admin-event-save'),
  eventDelete: document.getElementById('admin-event-delete'),
  title: document.getElementById('admin-ev-title'),
  caption: document.getElementById('admin-ev-caption'),
  pay1Title: document.getElementById('admin-ev-pay1-title'),
  pay1Url: document.getElementById('admin-ev-pay1-url'),
  pay2Title: document.getElementById('admin-ev-pay2-title'),
  pay2Url: document.getElementById('admin-ev-pay2-url'),
  pay3Title: document.getElementById('admin-ev-pay3-title'),
  pay3Url: document.getElementById('admin-ev-pay3-url'),
  ebBoy: document.getElementById('admin-ev-eb-boy'),
  ebGirl: document.getElementById('admin-ev-eb-girl'),
  ebQty: document.getElementById('admin-ev-eb-qty'),
  t1Boy: document.getElementById('admin-ev-t1-boy'),
  t1Girl: document.getElementById('admin-ev-t1-girl'),
  t1Qty: document.getElementById('admin-ev-t1-qty'),
  t2Boy: document.getElementById('admin-ev-t2-boy'),
  t2Girl: document.getElementById('admin-ev-t2-girl'),
  t2Qty: document.getElementById('admin-ev-t2-qty'),
  repostEnabled: document.getElementById('admin-ev-repost-enabled'),
  repostAmount: document.getElementById('admin-ev-repost-amount'),
  girlsGroupOfferEnabled: document.getElementById('admin-ev-girls-group-enabled'),
  boysGroupOfferEnabled: document.getElementById('admin-ev-boys-group-enabled'),
};

const state = {
  events: [],
  selectedEventId: null,
  boys: 0,
  girls: 0,
  userProfile: null,
  quote: null,
  quoteSeq: 0,
  quoteLoading: false,
  emailLoginEnabled: false,
  emailCodeSent: false,
  googleClientId: '',
  googleReady: false,
  editingProfile: false,
};

const adminState = {
  ready: false,
  activeSection: 'events',
  guestsSort: 'newest',
  guestsSearch: '',
  guests: [],
  events: [],
  selectedEventId: null,
};

const MISSING_REPOST_PROOF_MESSAGE = 'Upload a repost screenshot for each guest using the discount.';

function money(value) {
  return Number(value || 0).toFixed(2);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function multilineHtml(value) {
  return escapeHtml(value)
    .replaceAll('\r\n', '\n')
    .replaceAll('\r', '\n')
    .replaceAll('\n', '<br>');
}

function setStatus(msg, isError = false) {
  statusEl.textContent = msg || '';
  statusEl.className = isError ? 'hint error' : 'hint';
}

function setAdminStatus(msg, isError = false) {
  if (!adminEl.status) return;
  adminEl.status.textContent = msg || '';
  adminEl.status.className = isError ? 'hint error' : 'hint';
}

function setAdminOpenStatus(msg, isError = false) {
  if (!adminOpenStatusEl) return;
  adminOpenStatusEl.textContent = msg || '';
  adminOpenStatusEl.className = isError ? 'admin-open-status error' : 'admin-open-status';
}

function clearStatusIfMatches(message) {
  if ((statusEl.textContent || '').trim() === message) {
    setStatus('');
  }
}

function setPageTab(tabKey) {
  const key = tabKey || 'main';
  for (const tab of pageTabs) {
    const active = tab.dataset.pageTab === key;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', active ? 'true' : 'false');
  }
  for (const section of pageSections) {
    section.hidden = section.dataset.pageSection !== key;
  }
  if (key === 'tickets') {
    loadMeAndTickets();
  }
  renderAccountPanel();
}

function setAdminSection(sectionKey) {
  const key = sectionKey || 'events';
  adminState.activeSection = key;
  for (const btn of adminEl.tabs || []) {
    const tabKey = btn.dataset ? btn.dataset.adminTab : '';
    btn.classList.toggle('active', tabKey === key);
  }
  for (const section of adminEl.sections || []) {
    const sectionName = section.dataset ? section.dataset.adminSection : '';
    section.hidden = sectionName !== key;
  }
}

function setAdminLocked(locked) {
  if (!adminEl.area) return;
  adminEl.area.classList.toggle('admin-locked', Boolean(locked));
}

function apiErrorText(err, fallback) {
  if (!err) return fallback;
  if (typeof err === 'string') return err;
  if (err.detail) return err.detail;
  if (err.message) return err.message;
  return fallback;
}

function authHeaders(extra = {}) {
  const headers = { ...extra };
  if (tgInitData) headers['X-Telegram-Init-Data'] = tgInitData;
  if (!tgInitData && webSessionToken) headers.Authorization = `Bearer ${webSessionToken}`;
  return headers;
}

function adminHeaders(extra = {}) {
  const headers = authHeaders(extra);
  if (adminSessionToken) headers['X-Admin-Session'] = adminSessionToken;
  return headers;
}

function hasUserIdentity() {
  return Boolean(tgId || webSessionToken);
}

function setAccountStatus(msg, isError = false) {
  if (!accountStatusEl) return;
  accountStatusEl.textContent = msg || '';
  accountStatusEl.className = isError ? 'hint error' : 'hint';
}

function renderAccountPanel() {
  if (!accountPanelEl) return;
  const registered = Boolean(state.userProfile);
  const needsProfileCompletion = registered && !tgId && !(state.userProfile.phone || '').trim();
  const showEditForm = !registered || needsProfileCompletion || state.editingProfile;
  accountPanelEl.hidden = false;
  if (accountHelpEl) {
    accountHelpEl.textContent = needsProfileCompletion
      ? 'Add your phone number so we can contact you about your booking.'
      : registered
      ? 'Your booking profile is saved here.'
      : state.emailLoginEnabled
      ? 'Enter your details and verify your email. We use it to keep your tickets together.'
      : 'Register once with your phone number. We use it to keep your tickets together when you book from the website.';
  }
  if (profileCardEl) profileCardEl.hidden = !registered;
  if (profileNameEl) {
    profileNameEl.textContent = registered
      ? `${state.userProfile.name || ''} ${state.userProfile.surname || ''}`.trim() || '-'
      : '';
  }
  if (profileEmailEl) profileEmailEl.textContent = registered ? (state.userProfile.email || '-') : '';
  if (profilePhoneEl) profilePhoneEl.textContent = registered ? (state.userProfile.phone || 'Not added yet') : '';
  if (profileSourceEl) profileSourceEl.textContent = registered ? (state.userProfile.source || 'website') : '';
  const formEl = accountNameEl ? accountNameEl.closest('.account-form') : null;
  if (formEl) formEl.hidden = !showEditForm;
  if (accountSaveEl) {
    accountSaveEl.hidden = !showEditForm || (state.emailLoginEnabled && !registered);
    accountSaveEl.textContent = needsProfileCompletion ? 'Save details' : 'Continue';
  }
  if (accountEditEl) accountEditEl.hidden = !registered || showEditForm || Boolean(tgId);
  if (accountSendCodeEl) accountSendCodeEl.hidden = !state.emailLoginEnabled || registered || needsProfileCompletion;
  if (accountCodePanelEl) accountCodePanelEl.hidden = !state.emailLoginEnabled || !state.emailCodeSent;
  if (googleSigninWrapEl) googleSigninWrapEl.hidden = registered || !state.googleClientId;
  if (accountStateEl) {
    if (registered) {
      accountStateEl.textContent = `Signed in as ${state.userProfile.name || ''} ${state.userProfile.surname || ''}`.trim();
    } else if (tgId) {
      accountStateEl.textContent = 'Telegram account';
    } else {
      accountStateEl.textContent = 'Website account';
    }
  }
  if (registered) {
    if (accountNameEl) accountNameEl.value = state.userProfile.name || '';
    if (accountSurnameEl) accountSurnameEl.value = state.userProfile.surname || '';
    if (accountPhoneEl) accountPhoneEl.value = state.userProfile.phone || '';
    if (accountEmailEl) accountEmailEl.value = state.userProfile.email || '';
  }
}

function updateCarouselDots() {
  if (!carouselTrackEl || !carouselDots.length) return;
  const width = carouselTrackEl.clientWidth || 1;
  const index = Math.max(0, Math.min(carouselDots.length - 1, Math.round(carouselTrackEl.scrollLeft / width)));
  carouselDots.forEach((dot, dotIndex) => {
    dot.classList.toggle('active', dotIndex === index);
  });
}

function totalCount() {
  return state.boys + state.girls;
}

function attendeeRows() {
  return Array.from(attendeesListEl.querySelectorAll('.attendee-row'));
}

function attendeeEntries() {
  return attendeeRows().map((row) => ({
    first: (row.querySelector('input[data-part="first"]')?.value || '').trim(),
    surname: (row.querySelector('input[data-part="surname"]')?.value || '').trim(),
  }));
}

function attendeeDiscountSelections() {
  return attendeeRows().map((row, index) => ({
    index,
    checked: Boolean(row.querySelector('input[data-part="repost-check"]')?.checked),
    file: row.querySelector('input[data-part="repost-file"]')?.files?.[0] || null,
  }));
}

function attendeeFullNames() {
  return attendeeEntries().map((entry) => `${entry.first} ${entry.surname}`.trim());
}

function selectedEvent() {
  return state.events.find((e) => e.id === state.selectedEventId) || null;
}

function hasPaymentProof() {
  return Boolean(paymentProofEl && paymentProofEl.files && paymentProofEl.files[0]);
}

function termsAccepted() {
  return Boolean(termsAcceptedEl && termsAcceptedEl.checked);
}

function repostDiscountEnabled(event) {
  return Boolean(event && Number(event.repost_discount_enabled || 0) && Number(event.repost_discount_amount || 0) > 0);
}

function syncRepostValidationStatus() {
  const missingRepostProofs = attendeeDiscountSelections().filter((item) => item.checked && !item.file);
  if (!missingRepostProofs.length) {
    clearStatusIfMatches(MISSING_REPOST_PROOF_MESSAGE);
  }
}

function paymentOptionsHtml(event) {
  const options = Array.isArray(event && event.payment_options) ? event.payment_options : [];
  if (!options.length) return '';
  const rows = options.map((opt) => {
    const title = escapeHtml(opt.title || 'Payment link');
    const url = escapeHtml(opt.url || '');
    return [
      '<div class="payment-link-row">',
      `<a href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>`,
      `<button type="button" class="copy-pay-link" data-url="${url}">Copy</button>`,
      '</div>',
    ].join('');
  });
  return [
    '<div class="payment-links">',
    '<p class="payment-links-title">Payment options</p>',
    ...rows,
    '</div>',
  ].join('');
}

async function copyText(text) {
  if (!text) return false;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_err) {
      // Continue with fallback.
    }
  }
  try {
    const temp = document.createElement('textarea');
    temp.value = text;
    temp.setAttribute('readonly', 'true');
    temp.style.position = 'fixed';
    temp.style.left = '-9999px';
    document.body.appendChild(temp);
    temp.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(temp);
    return ok;
  } catch (_err) {
    return false;
  }
}

function renderSummary() {
  const event = selectedEvent();
  if (!event) {
    summaryEl.innerHTML = '<p>Choose an event and add your group size.</p>';
    submitBtn.disabled = true;
    return;
  }

  const qty = totalCount();
  const safeTitle = escapeHtml(event.title || '');
  const safeCaption = multilineHtml(event.caption || '');

  const rows = attendeeEntries();
  const repostSelections = attendeeDiscountSelections();
  const repostEligible = repostDiscountEnabled(event);
  const discountUnitAmount = repostEligible ? Number(event.repost_discount_amount || 0) : 0;
  const selectedDiscounts = repostEligible ? repostSelections.filter((item) => item.checked) : [];
  const missingRepostProofs = selectedDiscounts.filter((item) => !item.file);
  const discountAmount = selectedDiscounts.length * discountUnitAmount;
  const quote = state.quote;
  const baseTotal = Number(quote && quote.base_total_price !== undefined ? quote.base_total_price : (quote ? quote.total_price : 0));
  const girlsGroupOfferEnabled = Boolean(event && Number(event.girls_group_offer_enabled || 0));
  const boysGroupOfferEnabled = Boolean(event && Number(event.boys_group_offer_enabled || 0));
  const girlsGroupFreeCount = Number(quote && quote.girls_group_free_count ? quote.girls_group_free_count : 0);
  const boysGroupFreeCount = Number(quote && quote.boys_group_free_count ? quote.boys_group_free_count : 0);
  const girlsGroupDiscountAmount = Number(quote && quote.girls_group_discount_amount ? quote.girls_group_discount_amount : 0);
  const boysGroupDiscountAmount = Number(quote && quote.boys_group_discount_amount ? quote.boys_group_discount_amount : 0);
  const groupDiscountAmount = Number(quote && quote.group_discount_amount ? quote.group_discount_amount : 0);
  const appliedDiscountAmount = Math.max(groupDiscountAmount, discountAmount);
  const namesReady = rows.length === qty && rows.every((row) => row.first && row.surname);
  if (qty <= 0) {
    const paymentSection = paymentOptionsHtml(event);
    const repostHint = repostEligible
      ? `<div class="hint">Instagram repost discount: ${money(discountUnitAmount)} per guest.</div>`
      : '';
    summaryEl.innerHTML = [
      `<strong>${safeTitle}</strong>`,
      `<div>${safeCaption}</div>`,
      '<hr>',
      '<div>Boys: 0</div>',
      '<div>Girls: 0</div>',
      '<div><strong>Total: 0.00</strong></div>',
      '<div class="hint">Guests required: 0</div>',
      repostHint,
      paymentSection,
    ].join('');
    submitBtn.disabled = true;
    return;
  }

  if (state.quoteLoading) {
    const paymentSection = paymentOptionsHtml(event);
    summaryEl.innerHTML = [
      `<strong>${safeTitle}</strong>`,
      `<div>${safeCaption}</div>`,
      '<hr>',
      '<div>Calculating your price...</div>',
      paymentSection,
    ].join('');
    submitBtn.disabled = true;
    return;
  }

  const quoteMatches = quote
    && Number(quote.event_id) === Number(event.id)
    && Number(quote.boys) === Number(state.boys)
    && Number(quote.girls) === Number(state.girls);
  if (!quoteMatches) {
    const paymentSection = paymentOptionsHtml(event);
    summaryEl.innerHTML = [
      `<strong>${safeTitle}</strong>`,
      `<div>${safeCaption}</div>`,
      '<hr>',
      '<div class="hint">Price is not available yet. Refresh or adjust the group size.</div>',
      paymentSection,
    ].join('');
    submitBtn.disabled = true;
    return;
  }

  const breakdownRows = Array.isArray(quote.breakdown) ? quote.breakdown : [];
  const breakdownHtml = breakdownRows.map((row) => {
    const boysPart = `Boys: ${row.boys} x ${money(row.boy_price)}`;
    const girlsPart = `Girls: ${row.girls} x ${money(row.girl_price)}`;
    return `<div>${row.tier_name}: ${boysPart} | ${girlsPart} | Subtotal: ${money(row.subtotal)}</div>`;
  });
  const finalTotal = Math.max(0, baseTotal - appliedDiscountAmount);
  const repostHint = repostEligible
    ? `<div class="hint">Instagram repost discount: ${money(discountUnitAmount)} per guest.</div>`
    : '';
  const groupSummary = [
    `<div>Base total: ${money(baseTotal)}</div>`,
    girlsGroupOfferEnabled ? `<div>Girls 2+1: ${girlsGroupFreeCount} free = ${money(girlsGroupDiscountAmount)}</div>` : '',
    boysGroupOfferEnabled ? `<div>Boys 3+1: ${boysGroupFreeCount} free = ${money(boysGroupDiscountAmount)}</div>` : '',
    (girlsGroupOfferEnabled || boysGroupOfferEnabled) ? `<div>Group offer discount total: ${money(groupDiscountAmount)}</div>` : '',
  ].filter(Boolean);
  const repostSummary = repostEligible
    ? [
        repostHint,
        ...groupSummary,
        `<div>Repost discount: ${selectedDiscounts.length} x ${money(discountUnitAmount)} = ${money(discountAmount)}</div>`,
        `<div>Applied discount: ${money(appliedDiscountAmount)}</div>`,
        `<div><strong>Final total: ${money(finalTotal)}</strong></div>`,
      ]
    : [
        ...groupSummary,
        (girlsGroupOfferEnabled || boysGroupOfferEnabled) ? `<div>Applied discount: ${money(appliedDiscountAmount)}</div>` : '',
        `<div><strong>Total: ${money(quote.total_price)}</strong></div>`,
      ];
  const repostMissingHint = repostEligible && missingRepostProofs.length
    ? `<div class="hint error">${MISSING_REPOST_PROOF_MESSAGE}</div>`
    : '';

  const paymentSection = paymentOptionsHtml(event);
  summaryEl.innerHTML = [
    `<strong>${safeTitle}</strong>`,
    `<div>${safeCaption}</div>`,
    '<hr>',
    ...breakdownHtml,
    ...repostSummary,
    `<div class="hint">Guests required: ${qty}</div>`,
    repostMissingHint,
    paymentSection,
  ].join('');
  submitBtn.disabled = !(
    qty > 0
    && namesReady
    && hasPaymentProof()
    && termsAccepted()
    && missingRepostProofs.length === 0
    && hasUserIdentity()
  );
}

async function refreshQuote() {
  const event = selectedEvent();
  const qty = totalCount();
  state.quote = null;
  if (!event || qty <= 0) {
    state.quoteLoading = false;
    renderSummary();
    return;
  }

  const seq = state.quoteSeq + 1;
  state.quoteSeq = seq;
  state.quoteLoading = true;
  renderSummary();
  try {
    const resp = await fetch('/api/quote', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        event_id: event.id,
        boys: state.boys,
        girls: state.girls,
      }),
    });
    const data = await resp.json().catch(() => ({}));
    if (seq !== state.quoteSeq) return;
    if (!resp.ok) throw data;
    state.quote = data;
    setStatus('');
  } catch (err) {
    if (seq !== state.quoteSeq) return;
    setStatus(apiErrorText(err, 'Failed to calculate quote.'), true);
    state.quote = null;
  } finally {
    if (seq === state.quoteSeq) {
      state.quoteLoading = false;
      renderSummary();
    }
  }
}

function rebuildAttendees() {
  const qty = totalCount();
  const prev = attendeeRows().map((row) => ({
    first: (row.querySelector('input[data-part="first"]')?.value || '').trim(),
    surname: (row.querySelector('input[data-part="surname"]')?.value || '').trim(),
    repostChecked: Boolean(row.querySelector('input[data-part="repost-check"]')?.checked),
  }));
  const event = selectedEvent();
  const repostEligible = repostDiscountEnabled(event);
  const discountUnitAmount = repostEligible ? Number(event.repost_discount_amount || 0) : 0;
  attendeesListEl.innerHTML = '';

  for (let i = 0; i < qty; i += 1) {
    const row = document.createElement('div');
    row.className = 'attendee-row';

    const firstWrap = document.createElement('label');
    firstWrap.textContent = `Attendee #${i + 1} Name`;
    const firstInput = document.createElement('input');
    firstInput.type = 'text';
    firstInput.placeholder = 'Name';
    firstInput.dataset.part = 'first';

    const surnameWrap = document.createElement('label');
    surnameWrap.textContent = 'Surname';
    const surnameInput = document.createElement('input');
    surnameInput.type = 'text';
    surnameInput.placeholder = 'Surname';
    surnameInput.dataset.part = 'surname';

    const existing = prev[i] || {};
    if (existing.first || existing.surname) {
      firstInput.value = existing.first || '';
      surnameInput.value = existing.surname || '';
    } else if (i === 0 && state.userProfile) {
      firstInput.value = state.userProfile.name || '';
      surnameInput.value = state.userProfile.surname || '';
    }

    firstInput.addEventListener('input', renderSummary);
    surnameInput.addEventListener('input', renderSummary);

    firstWrap.appendChild(firstInput);
    surnameWrap.appendChild(surnameInput);
    row.appendChild(firstWrap);
    row.appendChild(surnameWrap);

    if (repostEligible) {
      const repostWrap = document.createElement('div');
      repostWrap.className = 'attendee-repost';

      const repostToggle = document.createElement('label');
      const repostCheck = document.createElement('input');
      repostCheck.type = 'checkbox';
      repostCheck.dataset.part = 'repost-check';
      repostCheck.checked = Boolean(existing.repostChecked);
      repostToggle.appendChild(repostCheck);
      repostToggle.append(` Instagram repost discount (${money(discountUnitAmount)})`);

      const repostFileWrap = document.createElement('label');
      repostFileWrap.textContent = 'Repost screenshot';
      repostFileWrap.hidden = !repostCheck.checked;
      repostFileWrap.dataset.part = 'repost-file-wrap';
      const repostFile = document.createElement('input');
      repostFile.type = 'file';
      repostFile.accept = 'image/png,image/jpeg';
      repostFile.dataset.part = 'repost-file';
      repostFile.disabled = !repostCheck.checked;
      repostFileWrap.appendChild(repostFile);

      repostCheck.addEventListener('change', () => {
        repostFileWrap.hidden = !repostCheck.checked;
        repostFile.disabled = !repostCheck.checked;
        if (!repostCheck.checked) {
          repostFile.value = '';
        }
        syncRepostValidationStatus();
        renderSummary();
      });
      repostFile.addEventListener('change', () => {
        syncRepostValidationStatus();
        renderSummary();
      });

      repostWrap.appendChild(repostToggle);
      repostWrap.appendChild(repostFileWrap);
      row.appendChild(repostWrap);
    }

    attendeesListEl.appendChild(row);
  }

  if (qty === 0) {
    attendeesListEl.innerHTML = '<p class="hint">Add the group size first.</p>';
  }

  renderSummary();
}

function selectEvent(eventId) {
  state.selectedEventId = eventId;

  for (const card of eventsListEl.querySelectorAll('.event-card')) {
    card.classList.toggle('active', Number(card.dataset.id) === eventId);
  }
  setStatus('');
  rebuildAttendees();
  refreshQuote();
}

function renderEvents() {
  eventsListEl.innerHTML = '';
  eventsEmptyEl.hidden = state.events.length > 0;

  for (const event of state.events) {
    const safeTitle = escapeHtml(event.title || '');
    const safeCaption = multilineHtml(event.caption || '');
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'event-card';
    card.dataset.id = String(event.id);
    card.innerHTML = `
      <p class="event-title">${safeTitle}</p>
      <p class="event-meta">${safeCaption}</p>
      <p class="event-price">${event.tier.name} | Boys ${money(event.tier.boy_price)} | Girls ${money(event.tier.girl_price)}</p>
    `;
    card.addEventListener('click', () => selectEvent(event.id));
    eventsListEl.appendChild(card);
  }
}

async function fetchEvents() {
  setStatus('Loading events...');
  try {
    const resp = await fetch('/api/events', { cache: 'no-store' });
    if (!resp.ok) throw new Error('Could not load events.');
    const data = await resp.json();
    state.events = Array.isArray(data.items) ? data.items : [];
    renderEvents();
    if (state.events.length > 0) {
      selectEvent(state.events[0].id);
    }
    setStatus('');
  } catch (err) {
    setStatus(err.message || 'Could not load events.', true);
  }
}

function getPayload() {
  const event = selectedEvent();
  if (!event) return null;
  const attendees = attendeeFullNames();
  const attendeeParts = attendeeEntries();
  const discountSelections = attendeeDiscountSelections();
  const qty = totalCount();
  const quoteMatches = state.quote && Number(state.quote.event_id) === Number(event.id);
  const baseTotal = quoteMatches
    ? Number(state.quote.base_total_price !== undefined ? state.quote.base_total_price : (state.quote.total_price || 0))
    : 0;
  const groupDiscountAmount = quoteMatches ? Number(state.quote.group_discount_amount || 0) : 0;
  const discountUnitAmount = repostDiscountEnabled(event) ? Number(event.repost_discount_amount || 0) : 0;
  const discountedAttendeeIndexes = discountSelections.filter((item) => item.checked).map((item) => item.index);
  const discountAmount = discountedAttendeeIndexes.length * discountUnitAmount;
  const total = Math.max(0, baseTotal - Math.max(groupDiscountAmount, discountAmount));

  return {
    type: 'booking_draft_v1',
    event_id: event.id,
    boys: state.boys,
    girls: state.girls,
    attendees,
    attendee_parts: attendeeParts,
    discounted_attendee_indexes: discountedAttendeeIndexes,
    group_discount_amount: groupDiscountAmount,
    discount_unit_amount: discountUnitAmount,
    discount_amount: discountAmount,
    tier_key: event.tier ? event.tier.key : '',
    tier_name: event.tier ? event.tier.name : '',
    boy_price: event.tier ? Number(event.tier.boy_price || 0) : 0,
    girl_price: event.tier ? Number(event.tier.girl_price || 0) : 0,
    base_total_price: baseTotal,
    total_price: total,
    quantity: qty,
  };
}

async function submitDraft() {
  const payload = getPayload();
  if (!payload) {
    setStatus('Choose an event first.', true);
    return;
  }

  if (payload.quantity <= 0) {
    setStatus('Add at least one guest.', true);
    return;
  }

  for (const fullName of payload.attendees) {
    if (!fullName || fullName.split(' ').length < 2) {
      setStatus('Each guest needs a name and surname.', true);
      return;
    }
  }

  const quoteReady = state.quote
    && Number(state.quote.event_id) === Number(payload.event_id)
    && Number(state.quote.boys) === Number(payload.boys)
    && Number(state.quote.girls) === Number(payload.girls);
  if (!quoteReady) {
    setStatus('Price is still loading. Try again in a moment.', true);
    return;
  }

  if (!hasUserIdentity()) {
    setStatus('Register your details before booking.', true);
    if (accountPanelEl) accountPanelEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }
  if (!tgId && state.userProfile && !(state.userProfile.phone || '').trim()) {
    setStatus('Add your phone number before booking.', true);
    renderAccountPanel();
    if (accountPanelEl) accountPanelEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }
  const discountSelections = attendeeDiscountSelections();
  const missingRepostProofs = discountSelections.filter((item) => item.checked && !item.file);
  if (missingRepostProofs.length) {
    setStatus(MISSING_REPOST_PROOF_MESSAGE, true);
    return;
  }
  const paymentFile = paymentProofEl && paymentProofEl.files ? paymentProofEl.files[0] : null;
  if (!paymentFile) {
    setStatus('Upload payment proof first.', true);
    return;
  }
  if (!termsAccepted()) {
    setStatus('Accept the booking terms before booking.', true);
    return;
  }

  const formData = new FormData();
  if (tgId) formData.set('tg_id', String(tgId));
  formData.set('event_id', String(payload.event_id));
  formData.set('boys', String(payload.boys));
  formData.set('girls', String(payload.girls));
  formData.set('attendees', JSON.stringify(payload.attendees));
  formData.set('discounted_attendee_indexes', JSON.stringify(payload.discounted_attendee_indexes || []));
  formData.set('terms_accepted', 'true');
  formData.set('file', paymentFile);
  for (const item of discountSelections) {
    if (item.checked && item.file) {
      formData.set(`repost_file_${item.index}`, item.file);
    }
  }

  submitBtn.disabled = true;
  setStatus('Sending booking...');
  try {
    const resp = await fetch('/api/book_with_payment', {
      method: 'POST',
      headers: authHeaders(),
      body: formData,
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(apiErrorText(data, 'Booking failed.'));
    }
    setStatus(`Booking sent for review. Code: ${data.code || '-'}`);
    if (paymentProofEl) paymentProofEl.value = '';
    await Promise.all([fetchEvents(), loadMeAndTickets()]);
  } catch (err) {
    setStatus(apiErrorText(err, 'Booking failed.'), true);
  } finally {
    renderSummary();
  }
}

function renderTickets(items) {
  ticketsListEl.innerHTML = '';
  ticketsEmptyEl.hidden = items.length > 0;
  if (!items.length) return;
  for (const item of items) {
    const card = document.createElement('div');
    card.className = 'admin-card';
    const safeCode = escapeHtml(item.code || '');
    const safeStatus = escapeHtml(item.status || '');
    const safeEventTitle = escapeHtml(item.event_title || '');
    const safeTierLabel = escapeHtml(item.tier_label || '');
    const safeBoys = escapeHtml(item.boys ?? 0);
    const safeGirls = escapeHtml(item.girls ?? 0);
    card.innerHTML = `
      <p class="admin-card-title">${safeCode} | ${safeStatus}</p>
      <p class="admin-card-meta">${safeEventTitle}</p>
      <p class="admin-card-meta">Tier: ${safeTierLabel} | Boys: ${safeBoys} | Girls: ${safeGirls} | Total: ${money(item.total_price)}</p>
    `;
    ticketsListEl.appendChild(card);
  }
}

async function loadMeAndTickets() {
  if (!hasUserIdentity()) {
    renderAccountPanel();
    renderTickets([]);
    if (ticketsEmptyEl) {
      ticketsEmptyEl.textContent = 'Register in the Book section to see your tickets here.';
      ticketsEmptyEl.hidden = false;
    }
    return;
  }
  try {
    const meUrl = new URL('/api/me', window.location.origin);
    if (tgId) meUrl.searchParams.set('tg_id', String(tgId));
    const meResp = await fetch(meUrl.toString(), { cache: 'no-store', headers: authHeaders() });
    if (meResp.ok) {
      const meData = await meResp.json();
      state.userProfile = meData.profile || null;
      renderAccountPanel();
      rebuildAttendees();
    }
  } catch (_err) {
    // Optional mini app personalization; ignore failures.
  }

  try {
    const ticketsUrl = new URL('/api/my_tickets', window.location.origin);
    if (tgId) ticketsUrl.searchParams.set('tg_id', String(tgId));
    const resp = await fetch(ticketsUrl.toString(), { cache: 'no-store', headers: authHeaders() });
    if (!resp.ok) {
      ticketsEmptyEl.hidden = false;
      return;
    }
    const data = await resp.json();
    const items = Array.isArray(data.items) ? data.items : [];
    renderTickets(items);
  } catch (_err) {
    ticketsEmptyEl.hidden = false;
  }
}

async function loadAuthConfig() {
  try {
    const resp = await fetch('/api/web/auth_config', { cache: 'no-store' });
    const data = await resp.json().catch(() => ({}));
    if (resp.ok) {
      state.emailLoginEnabled = Boolean(data.email_login_enabled);
      state.googleClientId = data.google_client_id || '';
      renderAccountPanel();
      ensureGoogleSignin();
    }
  } catch (_err) {
    state.emailLoginEnabled = false;
  }
}

function ensureGoogleSignin() {
  if (!state.googleClientId || state.googleReady || !googleSigninButtonEl) return;
  const start = () => {
    if (!window.google || !window.google.accounts || !window.google.accounts.id) return;
    window.google.accounts.id.initialize({
      client_id: state.googleClientId,
      callback: handleGoogleCredential,
    });
    window.google.accounts.id.renderButton(googleSigninButtonEl, {
      theme: 'outline',
      size: 'large',
      width: Math.min(360, Math.max(220, googleSigninButtonEl.clientWidth || 280)),
      text: 'continue_with',
      shape: 'rectangular',
    });
    state.googleReady = true;
    renderAccountPanel();
  };
  if (window.google && window.google.accounts && window.google.accounts.id) {
    start();
    return;
  }
  let script = document.querySelector('script[data-google-identity]');
  if (!script) {
    script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.dataset.googleIdentity = '1';
    script.onload = start;
    document.head.appendChild(script);
  } else {
    script.addEventListener('load', start, { once: true });
  }
}

async function registerWebsiteAccount() {
  if (!accountNameEl || !accountSurnameEl || !accountPhoneEl) return;
  const payload = {
    name: accountNameEl.value.trim(),
    surname: accountSurnameEl.value.trim(),
    phone: accountPhoneEl.value.trim(),
  };
  if (!payload.name || !payload.surname || !payload.phone) {
    setAccountStatus('Add your name, surname, and phone number.', true);
    return;
  }

  if (accountSaveEl) accountSaveEl.disabled = true;
  setAccountStatus('Saving your details...');
  try {
    const updatingProfile = Boolean(state.userProfile);
    const resp = await fetch(updatingProfile ? '/api/web/profile' : '/api/web/register', {
      method: updatingProfile ? 'PUT' : 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw data;
    webSessionToken = data.session_token || webSessionToken;
    if (webSessionToken) localStorage.setItem(WEB_SESSION_KEY, webSessionToken);
    state.userProfile = data.profile || null;
    state.editingProfile = false;
    setAccountStatus('Saved. You can book now.');
    renderAccountPanel();
    rebuildAttendees();
    await loadMeAndTickets();
  } catch (err) {
    setAccountStatus(apiErrorText(err, 'Could not save your details.'), true);
  } finally {
    if (accountSaveEl) accountSaveEl.disabled = false;
  }
}

async function finishWebsiteLogin(data, message) {
  webSessionToken = data.session_token || '';
  if (webSessionToken) localStorage.setItem(WEB_SESSION_KEY, webSessionToken);
  state.userProfile = data.profile || null;
  state.emailCodeSent = false;
  setAccountStatus(message || 'Signed in. You can book now.');
  renderAccountPanel();
  rebuildAttendees();
  await loadMeAndTickets();
}

function emailLoginPayload() {
  return {
    name: (accountNameEl && accountNameEl.value ? accountNameEl.value : '').trim(),
    surname: (accountSurnameEl && accountSurnameEl.value ? accountSurnameEl.value : '').trim(),
    email: (accountEmailEl && accountEmailEl.value ? accountEmailEl.value : '').trim(),
    phone: (accountPhoneEl && accountPhoneEl.value ? accountPhoneEl.value : '').trim(),
  };
}

async function sendWebsiteLoginCode() {
  const payload = emailLoginPayload();
  if (!payload.name || !payload.surname || !payload.email || !payload.phone) {
    setAccountStatus('Add your name, surname, email, and phone number.', true);
    return;
  }

  if (accountSendCodeEl) accountSendCodeEl.disabled = true;
  setAccountStatus('Sending code...');
  try {
    const resp = await fetch('/api/web/login/start', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw data;
    state.emailCodeSent = true;
    if (accountCodeEl && data.dev_code) accountCodeEl.value = data.dev_code;
    setAccountStatus('Code sent. Check your email.');
    renderAccountPanel();
  } catch (err) {
    setAccountStatus(apiErrorText(err, 'Could not send the code.'), true);
  } finally {
    if (accountSendCodeEl) accountSendCodeEl.disabled = false;
  }
}

async function verifyWebsiteLoginCode() {
  const email = accountEmailEl && accountEmailEl.value ? accountEmailEl.value.trim() : '';
  const code = accountCodeEl && accountCodeEl.value ? accountCodeEl.value.trim() : '';
  if (!email || !code) {
    setAccountStatus('Enter the code from your email.', true);
    return;
  }

  if (accountVerifyEl) accountVerifyEl.disabled = true;
  setAccountStatus('Verifying code...');
  try {
    const resp = await fetch('/api/web/login/verify', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ email, code }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw data;
    await finishWebsiteLogin(data, 'Verified. You can book now.');
  } catch (err) {
    setAccountStatus(apiErrorText(err, 'Could not verify the code.'), true);
  } finally {
    if (accountVerifyEl) accountVerifyEl.disabled = false;
  }
}

async function handleGoogleCredential(response) {
  const credential = response && response.credential ? response.credential : '';
  if (!credential) {
    setAccountStatus('Google sign-in did not return a token.', true);
    return;
  }
  setAccountStatus('Signing in with Google...');
  try {
    const resp = await fetch('/api/web/login/google', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        credential,
        phone: accountPhoneEl && accountPhoneEl.value ? accountPhoneEl.value.trim() : '',
      }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw data;
    await finishWebsiteLogin(data, 'Signed in with Google. You can book now.');
  } catch (err) {
    setAccountStatus(apiErrorText(err, 'Google sign-in failed.'), true);
  }
}

function initTelegram() {
  if (!tg) return;
  tg.ready();
  tg.expand();
}

async function adminGet(path, params = {}) {
  const url = new URL(path, window.location.origin);
  if (tgId) url.searchParams.set('tg_id', String(tgId));
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && String(v).trim() !== '') {
      url.searchParams.set(k, String(v));
    }
  });
  const res = await fetch(url.toString(), { cache: 'no-store', headers: adminHeaders() });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw data;
  return data;
}

async function adminPost(path, body = {}) {
  const payload = { ...body };
  if (tgId) payload.tg_id = tgId;
  const res = await fetch(path, {
    method: 'POST',
    headers: adminHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw data;
  return data;
}

async function adminUpload(path, formData) {
  if (tgId) formData.set('tg_id', String(tgId));
  const res = await fetch(path, {
    method: 'POST',
    headers: adminHeaders(),
    body: formData,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw data;
  return data;
}

function fillAdminEventForm(event) {
  if (!event) return;
  adminEl.title.value = event.title || '';
  adminEl.caption.value = event.caption || '';
  const pay = event.payment || {};
  adminEl.pay1Title.value = pay.payment1_title || '';
  adminEl.pay1Url.value = pay.payment1_url || '';
  adminEl.pay2Title.value = pay.payment2_title || '';
  adminEl.pay2Url.value = pay.payment2_url || '';
  adminEl.pay3Title.value = pay.payment3_title || '';
  adminEl.pay3Url.value = pay.payment3_url || '';
  const p = event.prices || {};
  adminEl.ebBoy.value = p.early_boy ?? 0;
  adminEl.ebGirl.value = p.early_girl ?? 0;
  adminEl.ebQty.value = p.early_qty ?? 0;
  adminEl.t1Boy.value = p.tier1_boy ?? 0;
  adminEl.t1Girl.value = p.tier1_girl ?? 0;
  adminEl.t1Qty.value = p.tier1_qty ?? 0;
  adminEl.t2Boy.value = p.tier2_boy ?? 0;
  adminEl.t2Girl.value = p.tier2_girl ?? 0;
  adminEl.t2Qty.value = p.tier2_qty ?? 0;
  adminEl.repostEnabled.value = Number(p.repost_discount_enabled || 0) ? '1' : '0';
  adminEl.repostAmount.value = p.repost_discount_amount ?? 0;
  adminEl.girlsGroupOfferEnabled.value = Number(p.girls_group_offer_enabled || 0) ? '1' : '0';
  adminEl.boysGroupOfferEnabled.value = Number(p.boys_group_offer_enabled || 0) ? '1' : '0';
}

function clearAdminEventForm() {
  adminEl.title.value = '';
  adminEl.caption.value = '';
  adminEl.pay1Title.value = '';
  adminEl.pay1Url.value = '';
  adminEl.pay2Title.value = '';
  adminEl.pay2Url.value = '';
  adminEl.pay3Title.value = '';
  adminEl.pay3Url.value = '';
  adminEl.ebBoy.value = 0;
  adminEl.ebGirl.value = 0;
  adminEl.ebQty.value = 0;
  adminEl.t1Boy.value = 0;
  adminEl.t1Girl.value = 0;
  adminEl.t1Qty.value = 0;
  adminEl.t2Boy.value = 0;
  adminEl.t2Girl.value = 0;
  adminEl.t2Qty.value = 0;
  adminEl.repostEnabled.value = '0';
  adminEl.repostAmount.value = 0;
  adminEl.girlsGroupOfferEnabled.value = '0';
  adminEl.boysGroupOfferEnabled.value = '0';
}

function renderAdminGuests() {
  adminEl.guestsList.innerHTML = '';
  if (!adminState.guests.length) {
    adminEl.guestsList.innerHTML = '<p class="hint">No guests found.</p>';
    return;
  }

  for (const guest of adminState.guests) {
    const safeFullName = escapeHtml(guest.full_name);
    const safeGender = escapeHtml(guest.gender);
    const genderBadge = guest.gender && guest.gender !== 'unknown' ? ` [${safeGender}]` : '';
    const safeEventTitle = escapeHtml(guest.event_title);
    const safeEventDatetime = escapeHtml(guest.event_datetime);
    const safeCode = escapeHtml(guest.reservation_code);
    const safeStatus = escapeHtml(guest.reservation_status);
    const safeBuyerName = escapeHtml(guest.buyer_name);
    const safeBuyerSurname = escapeHtml(guest.buyer_surname);
    const card = document.createElement('div');
    card.className = 'admin-card';
    card.innerHTML = `
      <div class="admin-card-head">
        <p class="admin-card-title">#${guest.attendee_id} ${safeFullName}${genderBadge}</p>
        <div class="admin-inline-actions">
            <button type="button" data-action="remove">Remove</button>
        </div>
      </div>
      <div>
        <p class="admin-card-meta">${safeEventTitle} (${safeEventDatetime})</p>
        <p class="admin-card-meta">${safeCode} | ${safeStatus} | ${safeBuyerName} ${safeBuyerSurname}</p>
      </div>
    `;

    const removeBtn = card.querySelector('button[data-action="remove"]');
    if (!removeBtn) {
      adminEl.guestsList.appendChild(card);
      continue;
    }

    removeBtn.addEventListener('click', async () => {
      try {
        const res = await adminPost('/api/admin/guest/remove', {
          attendee_id: guest.attendee_id,
        });
        setAdminStatus(res.message || 'Guest removed.');
        await Promise.all([loadAdminGuests(), loadAdminEvents()]);
      } catch (err) {
        setAdminStatus(apiErrorText(err, 'Failed to remove guest.'), true);
      }
    });

    adminEl.guestsList.appendChild(card);
  }
}

function populateEventSelect(selectEl, events, options = {}) {
  const allowCreate = Boolean(options.allowCreate);
  const preferId = Number(options.preferId || 0);
  if (!selectEl) return;
  const prevRaw = selectEl.value;
  const prev = Number(prevRaw || 0);
  selectEl.innerHTML = '';
  if (allowCreate) {
    const createOpt = document.createElement('option');
    createOpt.value = '';
    createOpt.textContent = '+ Create New Event';
    selectEl.appendChild(createOpt);
  }
  for (const event of events) {
    const opt = document.createElement('option');
    opt.value = String(event.id);
    opt.textContent = `#${event.id} ${event.title}`;
    selectEl.appendChild(opt);
  }
  if (!events.length) {
    if (allowCreate) selectEl.value = '';
    return;
  }

  let next = 0;
  if (preferId > 0 && events.some((ev) => ev.id === preferId)) {
    next = preferId;
  } else if (allowCreate && prevRaw === '') {
    next = 0;
  } else if (events.some((ev) => ev.id === prev)) {
    next = prev;
  } else {
    next = events[0].id;
  }
  selectEl.value = next > 0 ? String(next) : '';
}

function renderAdminEvents() {
  const prev = adminState.selectedEventId;
  populateEventSelect(adminEl.eventSelect, adminState.events, { allowCreate: true, preferId: prev });
  populateEventSelect(adminEl.addEventSelect, adminState.events);
  populateEventSelect(adminEl.importEventSelect, adminState.events);

  if (!adminState.events.length) {
    adminState.selectedEventId = null;
    clearAdminEventForm();
    return;
  }

  const eventId = Number(adminEl.eventSelect.value || 0);
  if (!eventId) {
    adminState.selectedEventId = null;
    clearAdminEventForm();
    return;
  }

  const selected = adminState.events.find((e) => e.id === eventId) || adminState.events[0];
  adminState.selectedEventId = selected.id;
  adminEl.eventSelect.value = String(selected.id);
  fillAdminEventForm(selected);
}

async function loadAdminGuests() {
  const data = await adminGet('/api/admin/guests', {
    sort_by: adminState.guestsSort,
    search: adminState.guestsSearch,
  });
  adminState.guests = Array.isArray(data.items) ? data.items : [];
  renderAdminGuests();
}

async function loadAdminEvents() {
  const data = await adminGet('/api/admin/events');
  adminState.events = Array.isArray(data.items) ? data.items : [];
  renderAdminEvents();
}

async function refreshAdminAll() {
  await Promise.all([loadAdminGuests(), loadAdminEvents()]);
}

async function ensureAdmin() {
  if (adminState.ready) return true;
  setAdminOpenStatus('Checking admin access...');
  try {
    const data = await adminGet('/api/admin/bootstrap');
    adminState.ready = true;
    setAdminLocked(false);
    if (adminEl.loginPanel) adminEl.loginPanel.hidden = true;
    adminEl.ident.textContent = data.source === 'website'
      ? 'Admin session: website'
      : `Admin Telegram ID: ${data.tg_id}`;
    setAdminStatus('Admin mode ready.');
    setAdminOpenStatus('');
    return true;
  } catch (err) {
    const message = apiErrorText(err, 'Admin access denied.');
    if (autoOpenAdmin && adminEl.loginPanel) {
      setPageTab('admin');
      setAdminLocked(true);
      adminEl.loginPanel.hidden = false;
      setAdminOpenStatus('');
      setAdminStatus('Log in to continue.');
      return false;
    }
    setAdminStatus(message, true);
    setAdminOpenStatus(message, true);
    return false;
  }
}

async function checkAdminAvailability() {
  if (!adminEl.open) return false;
  if (adminSessionToken) {
    adminEl.open.hidden = false;
    return true;
  }
  if (!tgId) {
    adminEl.open.hidden = true;
    return false;
  }
  try {
    const data = await adminGet('/api/admin/bootstrap');
    adminState.ready = true;
    adminEl.ident.textContent = `Admin Telegram ID: ${data.tg_id}`;
    adminEl.open.hidden = false;
    setAdminStatus('Admin mode ready.');
    return true;
  } catch (_err) {
    adminEl.open.hidden = true;
    return false;
  }
}

async function openAdminMode() {
  const ok = await ensureAdmin();
  if (!ok) return;
  setAdminLocked(false);
  setPageTab('admin');
  adminEl.open.classList.add('active');
  setAdminOpenStatus('');
  setAdminSection(adminState.activeSection || 'events');
  await refreshAdminAll();
}

async function loginAdmin() {
  const password = adminEl.password ? adminEl.password.value : '';
  if (!password.trim()) {
    setAdminStatus('Enter admin password.', true);
    return;
  }
  if (adminEl.login) adminEl.login.disabled = true;
  setAdminStatus('Logging in...');
  try {
    const res = await fetch('/api/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw data;
    adminSessionToken = data.admin_session || '';
    if (adminSessionToken) localStorage.setItem(ADMIN_SESSION_KEY, adminSessionToken);
    if (adminEl.password) adminEl.password.value = '';
    if (adminEl.open) adminEl.open.hidden = false;
    adminState.ready = false;
    await openAdminMode();
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Admin login failed.'), true);
  } finally {
    if (adminEl.login) adminEl.login.disabled = false;
  }
}

async function addAdminGuest() {
  const eventId = Number(adminEl.addEventSelect.value || 0);
  const gender = adminEl.guestGender.value;
  const name = adminEl.guestName.value.trim();
  const surname = adminEl.guestSurname.value.trim();
  if (!eventId) {
    setAdminStatus('Choose event first.', true);
    return;
  }
  if (!name || !surname) {
    setAdminStatus('Name and surname are required.', true);
    return;
  }
  try {
    const res = await adminPost('/api/admin/guest/add_by_event', {
      event_id: eventId,
      gender,
      name,
      surname,
    });
    adminEl.guestName.value = '';
    adminEl.guestSurname.value = '';
    setAdminStatus(res.message || 'Guest added.');
    await Promise.all([loadAdminGuests(), loadAdminEvents()]);
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Failed to add guest.'), true);
  }
}

async function importGuestsXlsx() {
  const eventId = Number(adminEl.importEventSelect.value || 0);
  const file = adminEl.importFile.files && adminEl.importFile.files[0];
  if (!eventId) {
    setAdminStatus('Choose event first.', true);
    return;
  }
  if (!file) {
    setAdminStatus('Choose .xlsx file first.', true);
    return;
  }
  const formData = new FormData();
  formData.set('event_id', String(eventId));
  formData.set('file', file);
  try {
    const res = await adminUpload('/api/admin/guest/import_xlsx', formData);
    let msg = `Import complete. Added: ${res.added || 0}, Skipped: ${res.skipped || 0}.`;
    if (Array.isArray(res.errors) && res.errors.length) {
      msg += ` ${res.errors.slice(0, 3).join(' | ')}`;
    }
    setAdminStatus(msg);
    await Promise.all([loadAdminGuests(), loadAdminEvents()]);
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Failed to import guests.'), true);
  }
}

async function exportGuestsXlsx() {
  const url = new URL('/api/admin/guest/export_xlsx', window.location.origin);
  if (tgId) url.searchParams.set('tg_id', String(tgId));
  try {
    const resp = await fetch(url.toString(), { headers: adminHeaders(), cache: 'no-store' });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw data;
    }
    const blob = await resp.blob();
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = 'guests_export.xlsx';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
    setAdminStatus('Guest list exported.');
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Failed to export guests.'), true);
  }
}

async function saveAdminEvent() {
  const eventId = Number(adminEl.eventSelect.value || 0);
  const title = adminEl.title.value.trim();
  const caption = adminEl.caption.value.trim();
  const payload = {
    title,
    caption,
    payment1_title: adminEl.pay1Title.value.trim(),
    payment1_url: adminEl.pay1Url.value.trim(),
    payment2_title: adminEl.pay2Title.value.trim(),
    payment2_url: adminEl.pay2Url.value.trim(),
    payment3_title: adminEl.pay3Title.value.trim(),
    payment3_url: adminEl.pay3Url.value.trim(),
    early_boy: adminEl.ebBoy.value,
    early_girl: adminEl.ebGirl.value,
    early_qty: adminEl.ebQty.value,
    tier1_boy: adminEl.t1Boy.value,
    tier1_girl: adminEl.t1Girl.value,
    tier1_qty: adminEl.t1Qty.value,
    tier2_boy: adminEl.t2Boy.value,
    tier2_girl: adminEl.t2Girl.value,
    tier2_qty: adminEl.t2Qty.value,
    repost_discount_enabled: adminEl.repostEnabled.value === '1',
    repost_discount_amount: adminEl.repostAmount.value,
    girls_group_offer_enabled: adminEl.girlsGroupOfferEnabled.value === '1',
    boys_group_offer_enabled: adminEl.boysGroupOfferEnabled.value === '1',
  };

  if (!title) {
    setAdminStatus('Title is required.', true);
    return;
  }

  try {
    let res;
    if (eventId) {
      res = await adminPost('/api/admin/event/update', {
        event_id: eventId,
        updates: payload,
      });
      setAdminStatus(res.message || 'Event updated.');
    } else {
      res = await adminPost('/api/admin/event/create_simple', payload);
      setAdminStatus(res.message || 'Event created.');
    }
    if (res && res.event && res.event.id) {
      adminState.selectedEventId = Number(res.event.id);
    }
    await loadAdminEvents();
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Failed to save event.'), true);
  }
}

async function deleteAdminEvent() {
  const eventId = Number(adminEl.eventSelect.value || 0);
  if (!eventId) {
    setAdminStatus('Select an event first.', true);
    return;
  }
  const target = adminState.events.find((item) => Number(item.id) === eventId);
  const label = target && target.title ? `"${target.title}"` : `#${eventId}`;
  const confirmed = window.confirm(
    `Delete event ${label}? This will permanently remove all related bookings and guests.`,
  );
  if (!confirmed) return;

  try {
    const res = await adminPost('/api/admin/event/delete', { event_id: eventId });
    setAdminStatus(res.message || 'Event deleted.');
    adminState.selectedEventId = null;
    await refreshAdminAll();
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Failed to delete event.'), true);
  }
}

boysEl.addEventListener('input', () => {
  state.boys = Math.max(0, Number(boysEl.value || 0));
  rebuildAttendees();
  refreshQuote();
});

girlsEl.addEventListener('input', () => {
  state.girls = Math.max(0, Number(girlsEl.value || 0));
  rebuildAttendees();
  refreshQuote();
});

submitBtn.addEventListener('click', submitDraft);
refreshBtn.addEventListener('click', fetchEvents);
if (paymentProofEl) {
  paymentProofEl.addEventListener('change', renderSummary);
}
if (termsAcceptedEl) {
  termsAcceptedEl.addEventListener('change', renderSummary);
}
if (accountSaveEl) {
  accountSaveEl.addEventListener('click', registerWebsiteAccount);
}
if (accountEditEl) {
  accountEditEl.addEventListener('click', () => {
    state.editingProfile = true;
    renderAccountPanel();
    setAccountStatus('');
  });
}
if (accountSendCodeEl) {
  accountSendCodeEl.addEventListener('click', sendWebsiteLoginCode);
}
if (accountVerifyEl) {
  accountVerifyEl.addEventListener('click', verifyWebsiteLoginCode);
}
if (accountCodeEl) {
  accountCodeEl.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      verifyWebsiteLoginCode();
    }
  });
}
if (carouselTrackEl && carouselDots.length) {
  let carouselFrame = 0;
  carouselTrackEl.addEventListener('scroll', () => {
    window.cancelAnimationFrame(carouselFrame);
    carouselFrame = window.requestAnimationFrame(updateCarouselDots);
  }, { passive: true });
  carouselDots.forEach((dot, index) => {
    dot.addEventListener('click', () => {
      carouselTrackEl.scrollTo({
        left: carouselTrackEl.clientWidth * index,
        behavior: 'smooth',
      });
    });
  });
  window.addEventListener('resize', updateCarouselDots);
}
if (summaryEl) {
  summaryEl.addEventListener('click', async (event) => {
    const target = event.target && event.target.closest ? event.target.closest('button.copy-pay-link') : null;
    if (!target) return;
    event.preventDefault();
    const url = (target.getAttribute('data-url') || '').trim();
    if (!url) return;
    const copied = await copyText(url);
    if (copied) {
      setStatus('Payment link copied.');
    } else {
      setStatus('Could not copy it. Open the payment link directly.', true);
    }
  });
}

if (adminEl.open) {
  adminEl.open.addEventListener('click', openAdminMode);
}
if (adminEl.login) {
  adminEl.login.addEventListener('click', loginAdmin);
}
if (adminEl.password) {
  adminEl.password.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') loginAdmin();
  });
}
if (pageTabs.length) {
  for (const tab of pageTabs) {
    tab.addEventListener('click', () => {
      const key = tab.dataset.pageTab || 'main';
      if (key === 'admin') {
        openAdminMode();
        return;
      }
      setPageTab(key);
    });
  }
}
if (adminEl.tabs && adminEl.tabs.length) {
  for (const tabBtn of adminEl.tabs) {
    tabBtn.addEventListener('click', () => {
      const tabKey = tabBtn.dataset ? tabBtn.dataset.adminTab : '';
      setAdminSection(tabKey || 'events');
    });
  }
}
if (adminEl.refreshAll) {
  adminEl.refreshAll.addEventListener('click', async () => {
    try {
      await refreshAdminAll();
      setAdminStatus('Admin data refreshed.');
    } catch (err) {
      setAdminStatus(apiErrorText(err, 'Failed to refresh admin data.'), true);
    }
  });
}
if (adminEl.guestsRefresh) {
  adminEl.guestsRefresh.addEventListener('click', async () => {
    try {
      await loadAdminGuests();
      setAdminStatus('Guests refreshed.');
    } catch (err) {
      setAdminStatus(apiErrorText(err, 'Failed to refresh guests.'), true);
    }
  });
}
if (adminEl.guestsSort) {
  adminEl.guestsSort.addEventListener('change', async () => {
    adminState.guestsSort = adminEl.guestsSort.value;
    try {
      await loadAdminGuests();
    } catch (err) {
      setAdminStatus(apiErrorText(err, 'Failed to sort guests.'), true);
    }
  });
}
if (adminEl.guestsSearch) {
  adminEl.guestsSearch.addEventListener('change', async () => {
    adminState.guestsSearch = adminEl.guestsSearch.value.trim();
    try {
      await loadAdminGuests();
    } catch (err) {
      setAdminStatus(apiErrorText(err, 'Failed to search guests.'), true);
    }
  });
}
if (adminEl.guestAdd) {
  adminEl.guestAdd.addEventListener('click', addAdminGuest);
}
if (adminEl.importUpload) {
  adminEl.importUpload.addEventListener('click', importGuestsXlsx);
}
if (adminEl.exportDownload) {
  adminEl.exportDownload.addEventListener('click', exportGuestsXlsx);
}
if (adminEl.eventsRefresh) {
  adminEl.eventsRefresh.addEventListener('click', async () => {
    try {
      await loadAdminEvents();
      setAdminStatus('Events refreshed.');
    } catch (err) {
      setAdminStatus(apiErrorText(err, 'Failed to load events.'), true);
    }
  });
}
if (adminEl.eventSelect) {
  adminEl.eventSelect.addEventListener('change', () => {
    const eventId = Number(adminEl.eventSelect.value || 0);
    if (!eventId) {
      adminState.selectedEventId = null;
      clearAdminEventForm();
      return;
    }
    adminState.selectedEventId = eventId;
    const event = adminState.events.find((item) => item.id === eventId);
    fillAdminEventForm(event || null);
  });
}
if (adminEl.eventSave) {
  adminEl.eventSave.addEventListener('click', saveAdminEvent);
}
if (adminEl.eventDelete) {
  adminEl.eventDelete.addEventListener('click', deleteAdminEvent);
}
if (ticketsRefreshEl) {
  ticketsRefreshEl.addEventListener('click', loadMeAndTickets);
}

initTelegram();
setPageTab('main');
setAdminSection('events');
setAdminLocked(true);
renderAccountPanel();
updateCarouselDots();
rebuildAttendees();
loadAuthConfig();
fetchEvents();
loadMeAndTickets();
if (autoOpenAdmin && adminEl.open) {
  openAdminMode().catch((err) => {
    setAdminStatus(apiErrorText(err, 'Admin access denied.'), true);
  });
} else {
  checkAdminAvailability();
}
