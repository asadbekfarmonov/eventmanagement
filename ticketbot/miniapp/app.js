let tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
const qs = new URLSearchParams(window.location.search);
const fallbackTgId = Number(qs.get('tg_id') || 0);
let tgId = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id) || fallbackTgId || null;
let tgInitData = (tg && tg.initData) || '';
const initialCheckinToken = (qs.get('checkin') || '').trim();
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
const upcomingListEl = document.getElementById('upcoming-events-list');
const upcomingEmptyEl = document.getElementById('upcoming-events-empty');
const heroGetTicketsEl = document.getElementById('hero-get-tickets');
const pageTabs = Array.from(document.querySelectorAll('[data-page-tab]'));
const pageSections = Array.from(document.querySelectorAll('[data-page-section]'));
let carouselTrackEl = document.querySelector('.main-carousel-track');
let carouselDots = Array.from(document.querySelectorAll('.main-carousel-dots span'));
const accountPanelEl = document.getElementById('account-panel');
const accountBackdropEl = document.getElementById('account-backdrop');
const accountOpenEl = document.getElementById('account-open');
const accountCloseEl = document.getElementById('account-close');
const accountChipInitialsEl = document.getElementById('account-chip-initials');
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
const accountSaveEl = document.getElementById('account-save');
const accountEditEl = document.getElementById('account-edit');
const accountSendCodeEl = document.getElementById('account-send-code');
const accountLogoutEl = document.getElementById('account-logout');
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
  logout: document.getElementById('admin-logout'),
  reviewsRefresh: document.getElementById('admin-reviews-refresh'),
  reviewsList: document.getElementById('admin-reviews-list'),
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
  scanStart: document.getElementById('admin-scan-start'),
  scanStop: document.getElementById('admin-scan-stop'),
  scanVideo: document.getElementById('admin-scan-video'),
  scanPlaceholder: document.getElementById('admin-scan-placeholder'),
  checkinToken: document.getElementById('admin-checkin-token'),
  checkinLookup: document.getElementById('admin-checkin-lookup'),
  checkinConfirm: document.getElementById('admin-checkin-confirm'),
  checkinResult: document.getElementById('admin-checkin-result'),
  eventsRefresh: document.getElementById('admin-events-refresh'),
  eventSelect: document.getElementById('admin-event-select'),
  eventSave: document.getElementById('admin-event-save'),
  eventDelete: document.getElementById('admin-event-delete'),
  title: document.getElementById('admin-ev-title'),
  when: document.getElementById('admin-ev-when'),
  location: document.getElementById('admin-ev-location'),
  caption: document.getElementById('admin-ev-caption'),
  photo: document.getElementById('admin-ev-photo'),
  photoCurrent: document.getElementById('admin-ev-photo-current'),
  maps: document.getElementById('admin-ev-maps'),
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
  carouselRefresh: document.getElementById('admin-carousel-refresh'),
  carouselFile: document.getElementById('admin-carousel-file'),
  carouselAdd: document.getElementById('admin-carousel-add'),
  carouselList: document.getElementById('admin-carousel-list'),
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
  pendingEmailUpdate: '',
  googleClientId: '',
  googleReady: false,
  editingProfile: false,
  accountOpen: false,
};

const adminState = {
  ready: false,
  activeSection: 'payments',
  guestsSort: 'newest',
  guestsSearch: '',
  guests: [],
  events: [],
  reviews: [],
  selectedEventId: null,
  checkinTicket: null,
  scanStream: null,
  scanTimer: 0,
  scanBusy: false,
};

const MISSING_REPOST_PROOF_MESSAGE = 'Upload a repost screenshot for each guest using the discount.';

// Key for persisting the in-progress booking draft (survives same-tab navigation/reload).
const BOOKING_DRAFT_KEY = 'bt_booking_draft';

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

function isHttpsUrl(value) {
  return /^https:\/\//i.test(String(value || '').trim());
}

// Backend stores 'YYYY-MM-DD HH:MM' (space); the <input type="datetime-local">
// value uses 'YYYY-MM-DDTHH:MM'. Convert both ways (minute precision).
function datetimeToInput(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  return raw.replace(' ', 'T').slice(0, 16);
}

function datetimeFromInput(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  return raw.replace('T', ' ').slice(0, 16);
}

function eventBannerHtml(event, className) {
  const url = event && event.photo_url ? String(event.photo_url) : '';
  if (!url) return '';
  const alt = escapeHtml((event && event.title) || 'Event banner');
  return `<img class="${className}" loading="lazy" src="${escapeHtml(url)}" alt="${alt}">`;
}

function eventMapHtml(event) {
  const mapsUrl = event && event.maps_url ? String(event.maps_url).trim() : '';
  if (!mapsUrl) return '';
  // Only render a map/link for https:// URLs (guards against javascript:/data: schemes).
  if (!isHttpsUrl(mapsUrl)) {
    return '';
  }
  const link = `<a class="event-map-link" href="${escapeHtml(mapsUrl)}" target="_blank" rel="noopener">Open in Google Maps</a>`;
  // A pasted Google Maps embed URL (Share -> "Embed a map") renders the exact pin.
  // A plain share link (maps.app.goo.gl / place) can't be embedded, so fall back to
  // embedding the event location text; the link button still opens the exact pin.
  const isEmbed = /^https:\/\/www\.google\.com\/maps\/embed/i.test(mapsUrl);
  const query = (event && event.location ? String(event.location).trim() : '') || mapsUrl;
  const src = isEmbed
    ? mapsUrl
    : `https://www.google.com/maps?q=${encodeURIComponent(query)}&output=embed`;
  const iframe = `<div class="event-map"><iframe src="${escapeHtml(src)}" loading="lazy" `
    + 'referrerpolicy="no-referrer-when-downgrade" title="Event location map" '
    + 'allowfullscreen></iframe></div>';
  return `${iframe}<div class="event-map-links">${link}</div>`;
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
  if (key === 'book' && !state.userProfile) {
    state.accountOpen = true;
  }
  renderAccountPanel();
}

function setAdminSection(sectionKey) {
  const key = sectionKey || 'events';
  if (adminState.activeSection === 'checkin' && key !== 'checkin') {
    stopScanner();
  }
  adminState.activeSection = key;
  for (const btn of adminEl.tabs || []) {
    const tabKey = btn.dataset ? btn.dataset.adminTab : '';
    const active = tabKey === key;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
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
  return headers;
}

function adminHeaders(extra = {}) {
  return authHeaders(extra);
}

function hasUserIdentity() {
  return Boolean(tgId || state.userProfile);
}

function setAccountStatus(msg, isError = false) {
  if (!accountStatusEl) return;
  accountStatusEl.textContent = msg || '';
  accountStatusEl.className = isError ? 'hint error' : 'hint';
}

function closeAccountPanel() {
  state.accountOpen = false;
  state.editingProfile = false;
  state.emailCodeSent = false;
  renderAccountPanel();
  setAccountStatus('');
}

function resetAccountPanelState() {
  state.accountOpen = false;
  state.editingProfile = false;
  state.emailCodeSent = false;
  setAccountStatus('');
}

async function logoutWebsiteAccount() {
  try {
    await fetch('/api/web/logout', { method: 'POST', headers: authHeaders() });
  } catch (_err) {
    // Best-effort: proceed to clear local state even if the network call fails.
  }
  state.userProfile = null;
  resetAccountPanelState();
  renderAccountPanel();
  closeAccountPanel();
  renderTickets([]);
  if (ticketsEmptyEl) {
    ticketsEmptyEl.textContent = 'Register in the Book section to see your tickets here.';
    ticketsEmptyEl.hidden = false;
  }
  setStatus('You have been logged out.');
}

let accountPanelWasOpen = false;
let accountOpenerEl = null;

const ACCOUNT_FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function getAccountFocusable() {
  if (!accountPanelEl) return [];
  return Array.from(accountPanelEl.querySelectorAll(ACCOUNT_FOCUSABLE_SELECTOR)).filter(
    (el) => !el.hidden && !el.closest('[hidden]') && el.offsetParent !== null,
  );
}

function focusFirstAccountControl() {
  const focusables = getAccountFocusable();
  const target = focusables[0] || accountCloseEl;
  if (target && typeof target.focus === 'function') {
    target.focus();
  }
}

function restoreAccountOpener() {
  const target = accountOpenerEl || accountOpenEl;
  if (target && typeof target.focus === 'function') {
    target.focus();
  }
  accountOpenerEl = null;
}

function renderAccountPanel() {
  if (!accountPanelEl) return;
  const registered = Boolean(state.userProfile);
  const needsProfileCompletion = registered && !tgId && !(state.userProfile.phone || '').trim();
  const showEditForm = !registered || needsProfileCompletion || state.editingProfile;
  if (accountOpenEl) {
    accountOpenEl.setAttribute('aria-expanded', state.accountOpen ? 'true' : 'false');
    accountOpenEl.classList.toggle('active', Boolean(state.accountOpen));
  }
  if (accountChipInitialsEl) {
    const name = registered
      ? `${state.userProfile.name || ''} ${state.userProfile.surname || ''}`.trim()
      : 'Budapest Tunderi';
    const initials = name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join('')
      .toUpperCase();
    accountChipInitialsEl.textContent = initials || 'BT';
  }
  accountPanelEl.hidden = !state.accountOpen && !state.emailCodeSent;
  if (accountBackdropEl) accountBackdropEl.hidden = accountPanelEl.hidden;
  document.body.classList.toggle('account-open', !accountPanelEl.hidden);
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
  const formEl = accountNameEl ? accountNameEl.closest('.account-form') : null;
  if (formEl) formEl.hidden = !showEditForm;
  if (accountSaveEl) {
    accountSaveEl.hidden = !showEditForm || (state.emailLoginEnabled && !registered);
    accountSaveEl.textContent = needsProfileCompletion ? 'Save details' : 'Continue';
  }
  if (accountEditEl) accountEditEl.hidden = !registered || showEditForm || Boolean(tgId);
  if (accountSendCodeEl) accountSendCodeEl.hidden = !state.emailLoginEnabled || registered || needsProfileCompletion;
  if (accountLogoutEl) accountLogoutEl.hidden = !registered || Boolean(tgId);
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
  const isOpen = !accountPanelEl.hidden;
  accountPanelEl.setAttribute('aria-modal', isOpen ? 'true' : 'false');
  if (isOpen && !accountPanelWasOpen) {
    const active = document.activeElement;
    accountOpenerEl =
      active && active !== document.body && !accountPanelEl.contains(active)
        ? active
        : accountOpenEl;
    focusFirstAccountControl();
  } else if (!isOpen && accountPanelWasOpen) {
    restoreAccountOpener();
  }
  accountPanelWasOpen = isOpen;
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

function onBookingFieldChange() {
  renderSummary();
  saveBookingDraft();
}

function buildBookingDraft() {
  const event = selectedEvent();
  if (!event) return null;
  const attendees = attendeeRows().map((row) => ({
    first: (row.querySelector('input[data-part="first"]')?.value || '').trim(),
    surname: (row.querySelector('input[data-part="surname"]')?.value || '').trim(),
    repostChecked: Boolean(row.querySelector('input[data-part="repost-check"]')?.checked),
  }));
  return {
    eventId: event.id,
    boys: state.boys,
    girls: state.girls,
    attendees,
    termsAccepted: termsAccepted(),
  };
}

function saveBookingDraft() {
  // Only persist once an event is selected; guard storage for private mode.
  try {
    const draft = buildBookingDraft();
    if (!draft) return;
    sessionStorage.setItem(BOOKING_DRAFT_KEY, JSON.stringify(draft));
  } catch (_err) {
    // Ignore storage failures (private mode / disabled storage).
  }
}

function loadBookingDraft() {
  try {
    const raw = sessionStorage.getItem(BOOKING_DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed;
  } catch (_err) {
    return null;
  }
}

function clearBookingDraft() {
  try {
    sessionStorage.removeItem(BOOKING_DRAFT_KEY);
  } catch (_err) {
    // Ignore storage failures.
  }
}

function restoreBookingDraft() {
  const draft = loadBookingDraft();
  if (!draft) return false;
  const eventId = Number(draft.eventId);
  const exists = state.events.some((event) => Number(event.id) === eventId);
  if (!exists) {
    // The saved event is gone; drop the stale draft.
    clearBookingDraft();
    return false;
  }
  state.boys = Math.max(0, Number(draft.boys || 0));
  state.girls = Math.max(0, Number(draft.girls || 0));
  if (boysEl) boysEl.value = state.boys;
  if (girlsEl) girlsEl.value = state.girls;
  // selectEvent marks the active card, rebuilds attendee rows, and refreshes the quote.
  selectEvent(eventId);
  const rows = attendeeRows();
  const attendees = Array.isArray(draft.attendees) ? draft.attendees : [];
  rows.forEach((row, index) => {
    const info = attendees[index];
    if (!info) return;
    const firstInput = row.querySelector('input[data-part="first"]');
    const surnameInput = row.querySelector('input[data-part="surname"]');
    if (firstInput) firstInput.value = info.first || '';
    if (surnameInput) surnameInput.value = info.surname || '';
    const repostCheck = row.querySelector('input[data-part="repost-check"]');
    if (repostCheck && info.repostChecked) {
      repostCheck.checked = true;
      // Re-run the checkbox handler so the screenshot field is revealed/enabled.
      repostCheck.dispatchEvent(new Event('change'));
    }
  });
  if (termsAcceptedEl) termsAcceptedEl.checked = Boolean(draft.termsAccepted);
  refreshQuote();
  renderSummary();
  saveBookingDraft();
  return true;
}

function paymentOptionsHtml(event) {
  const options = Array.isArray(event && event.payment_options) ? event.payment_options : [];
  if (!options.length) return '';
  const isLinkable = (value) => /^(https?:\/\/|tel:|mailto:)/i.test(String(value || '').trim());
  const rows = options.map((opt) => {
    const rawUrl = (opt.url || '').trim();
    const title = escapeHtml(opt.title || 'Payment option');
    const url = escapeHtml(rawUrl);
    const valueHtml = isLinkable(rawUrl)
      ? `<a href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>`
      : `<span class="payment-plain">${title}: ${url}</span>`;
    return [
      '<div class="payment-link-row">',
      valueHtml,
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
  const summaryBanner = eventBannerHtml(event, 'summary-banner');
  const summaryMap = eventMapHtml(event);

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
  const boysCountForDiscount = Number(state.boys || 0);
  let repostersBoys = 0;
  let repostersGirls = 0;
  selectedDiscounts.forEach((item) => {
    if (Number(item.index) < boysCountForDiscount) {
      repostersBoys += 1;
    } else {
      repostersGirls += 1;
    }
  });
  const nonRepostersBoys = Math.max(0, boysCountForDiscount - repostersBoys);
  const nonRepostersGirls = Math.max(0, Number(state.girls || 0) - repostersGirls);
  const freedRepostersGirls = Math.max(0, girlsGroupFreeCount - nonRepostersGirls);
  const freedRepostersBoys = Math.max(0, boysGroupFreeCount - nonRepostersBoys);
  const appliedDiscountAmount = Math.min(
    baseTotal,
    groupDiscountAmount
      + discountUnitAmount * (repostersGirls - freedRepostersGirls)
      + discountUnitAmount * (repostersBoys - freedRepostersBoys),
  );
  const namesReady = rows.length === qty && rows.every((row) => row.first && row.surname);
  if (qty <= 0) {
    const paymentSection = paymentOptionsHtml(event);
    const repostHint = repostEligible
      ? `<div class="hint">Instagram repost discount: ${money(discountUnitAmount)} per guest.</div>`
      : '';
    summaryEl.innerHTML = [
      summaryBanner,
      `<strong>${safeTitle}</strong>`,
      `<div>${safeCaption}</div>`,
      '<hr>',
      '<div>Boys: 0</div>',
      '<div>Girls: 0</div>',
      '<div><strong>Total: 0.00</strong></div>',
      '<div class="hint">Guests required: 0</div>',
      repostHint,
      paymentSection,
      summaryMap,
    ].join('');
    submitBtn.disabled = true;
    return;
  }

  if (state.quoteLoading) {
    const paymentSection = paymentOptionsHtml(event);
    summaryEl.innerHTML = [
      summaryBanner,
      `<strong>${safeTitle}</strong>`,
      `<div>${safeCaption}</div>`,
      '<hr>',
      '<div>Calculating your price...</div>',
      paymentSection,
      summaryMap,
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
      summaryBanner,
      `<strong>${safeTitle}</strong>`,
      `<div>${safeCaption}</div>`,
      '<hr>',
      '<div class="hint">Price is not available yet. Refresh or adjust the group size.</div>',
      paymentSection,
      summaryMap,
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
    summaryBanner,
    `<strong>${safeTitle}</strong>`,
    `<div>${safeCaption}</div>`,
    '<hr>',
    ...breakdownHtml,
    ...repostSummary,
    `<div class="hint">Guests required: ${qty}</div>`,
    repostMissingHint,
    paymentSection,
    summaryMap,
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

    firstInput.addEventListener('input', onBookingFieldChange);
    surnameInput.addEventListener('input', onBookingFieldChange);

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
        saveBookingDraft();
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
  saveBookingDraft();
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

function formatEventDateTime(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  const parsed = new Date(raw.replace(' ', 'T'));
  if (Number.isNaN(parsed.getTime())) return raw;
  try {
    return parsed.toLocaleString(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch (err) {
    return raw;
  }
}

function eventCaptionExcerpt(caption, maxLength = 140) {
  const text = String(caption || '').replace(/\s+/g, ' ').trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).trim()}\u2026`;
}

function eventFromPrice(event) {
  const tier = (event && event.tier) || {};
  const prices = [Number(tier.boy_price), Number(tier.girl_price)].filter(
    (value) => Number.isFinite(value) && value > 0,
  );
  return prices.length ? Math.min(...prices) : 0;
}

function goToBookingForEvent(eventId) {
  setPageTab('book');
  selectEvent(eventId);
  const target = document.getElementById('events-panel');
  if (target && target.scrollIntoView) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function renderUpcomingEvents() {
  if (!upcomingListEl) return;
  upcomingListEl.innerHTML = '';
  const events = Array.isArray(state.events) ? state.events : [];
  if (upcomingEmptyEl) {
    upcomingEmptyEl.hidden = events.length > 0;
  }

  for (const event of events) {
    const card = document.createElement('article');
    card.className = 'event-card upcoming-card';
    card.dataset.id = String(event.id);

    const parts = [];
    const bannerHtml = eventBannerHtml(event, 'upcoming-banner');
    if (bannerHtml) {
      parts.push(bannerHtml);
    }
    parts.push(`<p class="event-title">${escapeHtml(event.title || '')}</p>`);
    const when = formatEventDateTime(event.event_datetime);
    if (when) {
      parts.push(`<p class="upcoming-when">${escapeHtml(when)}</p>`);
    }
    if (event.location) {
      parts.push(`<p class="upcoming-where">${escapeHtml(event.location)}</p>`);
    }
    parts.push(`<p class="event-price">From ${money(eventFromPrice(event))} Ft</p>`);
    const excerpt = eventCaptionExcerpt(event.caption);
    if (excerpt) {
      parts.push(`<p class="event-meta">${escapeHtml(excerpt)}</p>`);
    }
    card.innerHTML = parts.join('');

    const cta = document.createElement('button');
    cta.type = 'button';
    cta.className = 'primary upcoming-cta';
    cta.textContent = 'Get tickets';
    cta.addEventListener('click', () => goToBookingForEvent(event.id));
    card.appendChild(cta);

    upcomingListEl.appendChild(card);
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
    renderUpcomingEvents();
    if (state.events.length > 0) {
      // Restore an in-progress booking draft if its event still exists;
      // otherwise default to the first event.
      if (!restoreBookingDraft()) {
        selectEvent(state.events[0].id);
      }
    }
    setStatus('');
  } catch (err) {
    setStatus(err.message || 'Could not load events.', true);
    renderUpcomingEvents();
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
  const girlsGroupFreeCount = quoteMatches ? Number(state.quote.girls_group_free_count || 0) : 0;
  const boysGroupFreeCount = quoteMatches ? Number(state.quote.boys_group_free_count || 0) : 0;
  const discountUnitAmount = repostDiscountEnabled(event) ? Number(event.repost_discount_amount || 0) : 0;
  const discountedAttendeeIndexes = discountSelections.filter((item) => item.checked).map((item) => item.index);
  const discountAmount = discountedAttendeeIndexes.length * discountUnitAmount;
  const boysCountForDiscount = Number(state.boys || 0);
  let repostersBoys = 0;
  let repostersGirls = 0;
  discountedAttendeeIndexes.forEach((index) => {
    if (Number(index) < boysCountForDiscount) {
      repostersBoys += 1;
    } else {
      repostersGirls += 1;
    }
  });
  const nonRepostersBoys = Math.max(0, boysCountForDiscount - repostersBoys);
  const nonRepostersGirls = Math.max(0, Number(state.girls || 0) - repostersGirls);
  const freedRepostersGirls = Math.max(0, girlsGroupFreeCount - nonRepostersGirls);
  const freedRepostersBoys = Math.max(0, boysGroupFreeCount - nonRepostersBoys);
  const combinedDiscount = Math.min(
    baseTotal,
    groupDiscountAmount
      + discountUnitAmount * (repostersGirls - freedRepostersGirls)
      + discountUnitAmount * (repostersBoys - freedRepostersBoys),
  );
  const total = Math.max(0, baseTotal - combinedDiscount);

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
    state.accountOpen = true;
    renderAccountPanel();
    return;
  }
  if (!tgId && state.userProfile && !(state.userProfile.phone || '').trim()) {
    setStatus('Add your phone number before booking.', true);
    state.accountOpen = true;
    renderAccountPanel();
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
    const successMessage = `Booking sent for review. Code: ${data.code || '-'}`;
    // Booking succeeded: drop the saved draft so a later reload starts fresh.
    clearBookingDraft();
    if (paymentProofEl) paymentProofEl.value = '';
    if (termsAcceptedEl) termsAcceptedEl.checked = false;
    state.boys = 0;
    state.girls = 0;
    state.quote = null;
    state.quoteLoading = false;
    state.quoteSeq += 1;
    if (boysEl) boysEl.value = 0;
    if (girlsEl) girlsEl.value = 0;
    rebuildAttendees();
    await Promise.all([fetchEvents(), loadMeAndTickets()]);
    setStatus(successMessage);
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
    const statusKey = (item.status || '').trim().toLowerCase();
    const isPending = statusKey === 'pending_payment_review';
    const adminNote = (item.admin_note || '').trim();
    const noteLabel = statusKey === 'rejected' ? 'Rejection reason' : 'Note from organizers';
    const noteHtml = adminNote
      ? `<p class="admin-card-meta ticket-admin-note"><strong>${escapeHtml(noteLabel)}:</strong> ${multilineHtml(adminNote)}</p>`
      : '';
    const cancelHtml = isPending
      ? `<button type="button" class="ticket-cancel-btn" data-cancel-code="${escapeHtml(item.code || '')}">Cancel booking</button>`
      : '';
    const tickets = Array.isArray(item.tickets) ? item.tickets : [];
    const ticketHtml = tickets.length
      ? tickets.map((ticket) => {
        const safeName = escapeHtml(ticket.full_name || '');
        const checked = Boolean(ticket.checked_in);
        const qr = ticket.qr_url
          ? `<img class="ticket-qr" src="${escapeHtml(ticket.qr_url)}" alt="QR code for ${safeName}" loading="lazy" />`
          : '<div class="ticket-qr-placeholder">QR appears after approval</div>';
        const checkedText = checked
          ? `Checked in${ticket.checked_in_at ? ` at ${escapeHtml(ticket.checked_in_at)}` : ''}`
          : 'Not checked in';
        return `
          <div class="ticket-pass">
            ${qr}
            <div>
              <p class="ticket-pass-name">${safeName}</p>
              <p class="admin-card-meta">${escapeHtml(checkedText)}</p>
            </div>
          </div>
        `;
      }).join('')
      : '';
    card.innerHTML = `
      <p class="admin-card-title">${safeCode} | ${safeStatus}</p>
      <p class="admin-card-meta">${safeEventTitle}</p>
      <p class="admin-card-meta">Tier: ${safeTierLabel} | Boys: ${safeBoys} | Girls: ${safeGirls} | Total: ${money(item.total_price)}</p>
      ${noteHtml}
      ${ticketHtml}
      ${cancelHtml}
    `;
    const cancelBtn = card.querySelector('.ticket-cancel-btn');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => cancelWebBooking(cancelBtn.dataset.cancelCode));
    }
    ticketsListEl.appendChild(card);
  }
}

async function cancelWebBooking(code) {
  const bookingCode = (code || '').trim();
  if (!bookingCode) return;
  const confirmed = window.confirm(
    'Cancel this booking? This releases your reserved tickets and cannot be undone.'
  );
  if (!confirmed) return;
  try {
    const cancelUrl = new URL('/api/web/cancel', window.location.origin);
    if (tgId) cancelUrl.searchParams.set('tg_id', String(tgId));
    const resp = await fetch(cancelUrl.toString(), {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ code: bookingCode }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      setStatus(data.detail || 'Could not cancel this booking.', true);
      return;
    }
    setStatus(data.message || 'Booking cancelled.');
    await loadMeAndTickets();
    await fetchEvents();
  } catch (_err) {
    setStatus('Could not cancel this booking.', true);
  }
}

async function loadMeAndTickets() {
  // Always probe /api/me so a valid web-session cookie (Google/email login) is
  // restored after a page reload, even when we start with no client-side identity.
  let authed = false;
  try {
    const meUrl = new URL('/api/me', window.location.origin);
    if (tgId) meUrl.searchParams.set('tg_id', String(tgId));
    const meResp = await fetch(meUrl.toString(), { cache: 'no-store', headers: authHeaders() });
    if (meResp.ok) {
      const meData = await meResp.json();
      state.userProfile = meData.profile || null;
      authed = Boolean(state.userProfile);
      renderAccountPanel();
      rebuildAttendees();
    } else if (meResp.status === 401 || meResp.status === 403) {
      // Not logged in (or blocked): treat as logged-out.
      state.userProfile = null;
      renderAccountPanel();
    }
  } catch (_err) {
    // Ignore network errors; fall through to the logged-out empty state.
  }

  if (!authed) {
    renderTickets([]);
    if (ticketsEmptyEl) {
      ticketsEmptyEl.textContent = 'Register in the Book section to see your tickets here.';
      ticketsEmptyEl.hidden = false;
    }
    return;
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
    email: accountEmailEl && accountEmailEl.value ? accountEmailEl.value.trim() : '',
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
      body: JSON.stringify({
        name: payload.name,
        surname: payload.surname,
        phone: payload.phone,
      }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw data;
    state.userProfile = data.profile || null;

    const currentEmail = ((data.profile && data.profile.email) || '').trim().toLowerCase();
    const requestedEmail = payload.email.trim().toLowerCase();
    if (updatingProfile && requestedEmail && requestedEmail !== currentEmail) {
      const emailResp = await fetch('/api/web/email/start', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ email: requestedEmail }),
      });
      const emailData = await emailResp.json().catch(() => ({}));
      if (!emailResp.ok) throw emailData;
      state.pendingEmailUpdate = requestedEmail;
      state.emailCodeSent = true;
      state.editingProfile = true;
      state.accountOpen = true;
      if (accountCodeEl && emailData.dev_code) accountCodeEl.value = emailData.dev_code;
      setAccountStatus(`Code sent to ${requestedEmail}. Enter it below to update your email.`);
      renderAccountPanel();
      return;
    }

    state.pendingEmailUpdate = '';
    state.editingProfile = false;
    state.emailCodeSent = false;
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
  state.userProfile = data.profile || null;
  state.emailCodeSent = false;
  state.pendingEmailUpdate = '';
  state.accountOpen = true;
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
  const email = state.pendingEmailUpdate || (accountEmailEl && accountEmailEl.value ? accountEmailEl.value.trim() : '');
  const code = accountCodeEl && accountCodeEl.value ? accountCodeEl.value.trim() : '';
  if (!email || !code) {
    setAccountStatus('Enter the code from your email.', true);
    return;
  }

  if (accountVerifyEl) accountVerifyEl.disabled = true;
  setAccountStatus('Verifying code...');
  try {
    const endpoint = state.pendingEmailUpdate ? '/api/web/email/verify' : '/api/web/login/verify';
    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ email, code }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw data;
    if (state.pendingEmailUpdate) {
      state.userProfile = data.profile || state.userProfile;
      state.emailCodeSent = false;
      state.pendingEmailUpdate = '';
      state.editingProfile = false;
      state.accountOpen = false;
      setAccountStatus('Email verified.');
      renderAccountPanel();
      await loadMeAndTickets();
    } else {
      await finishWebsiteLogin(data, 'Verified. You can book now.');
    }
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
    await finishWebsiteLogin(data, 'Google login complete. You can book now.');
  } catch (err) {
    setAccountStatus(apiErrorText(err, 'Google sign-in failed.'), true);
  }
}

function initTelegram() {
  if (!tg) return;
  tg.ready();
  tg.expand();
}

// The Telegram SDK is injected asynchronously by tg-init.js only inside a
// Telegram context, so it may become available after this script runs.
// Re-read window.Telegram and refresh identity-dependent views when it does.
function applyTelegramContext() {
  const webApp = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  if (!webApp || webApp === tg) return;
  tg = webApp;
  tgId = (tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id) || fallbackTgId || null;
  tgInitData = tg.initData || '';
  initTelegram();
  fetchEvents();
  loadMeAndTickets();
  checkAdminAvailability();
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
  if (adminEl.when) adminEl.when.value = datetimeToInput(event.event_datetime || '');
  if (adminEl.location) adminEl.location.value = event.location || '';
  adminEl.caption.value = event.caption || '';
  const pay = event.payment || {};
  adminEl.pay1Title.value = pay.payment1_title || '';
  adminEl.pay1Url.value = pay.payment1_url || '';
  adminEl.pay2Title.value = pay.payment2_title || '';
  adminEl.pay2Url.value = pay.payment2_url || '';
  adminEl.pay3Title.value = pay.payment3_title || '';
  adminEl.pay3Url.value = pay.payment3_url || '';
  if (adminEl.maps) adminEl.maps.value = event.maps_url || '';
  if (adminEl.photo) adminEl.photo.value = '';
  if (adminEl.photoCurrent) {
    const bannerUrl = event.photo_url || '';
    if (bannerUrl) {
      adminEl.photoCurrent.src = bannerUrl;
      adminEl.photoCurrent.hidden = false;
    } else {
      adminEl.photoCurrent.removeAttribute('src');
      adminEl.photoCurrent.hidden = true;
    }
  }
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
  if (adminEl.when) adminEl.when.value = '';
  if (adminEl.location) adminEl.location.value = '';
  adminEl.caption.value = '';
  adminEl.pay1Title.value = '';
  adminEl.pay1Url.value = '';
  adminEl.pay2Title.value = '';
  adminEl.pay2Url.value = '';
  adminEl.pay3Title.value = '';
  adminEl.pay3Url.value = '';
  if (adminEl.maps) adminEl.maps.value = '';
  if (adminEl.photo) adminEl.photo.value = '';
  if (adminEl.photoCurrent) {
    adminEl.photoCurrent.removeAttribute('src');
    adminEl.photoCurrent.hidden = true;
  }
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
            <button type="button" data-action="rename">Rename</button>
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

    const renameBtn = card.querySelector('button[data-action="rename"]');
    if (renameBtn) {
      renameBtn.addEventListener('click', async () => {
        const current = guest.full_name || '';
        const input = window.prompt('Enter new name (Name Surname):', current);
        if (input === null) return;
        const nextName = input.trim().replace(/\s+/g, ' ');
        if (nextName.split(' ').filter(Boolean).length < 2) {
          setAdminStatus('Please enter a full name: Name Surname.', true);
          return;
        }
        try {
          const res = await adminPost('/api/admin/guest/rename', {
            attendee_id: guest.attendee_id,
            full_name: nextName,
          });
          setAdminStatus(res.message || 'Guest renamed.');
          await loadAdminGuests();
        } catch (err) {
          setAdminStatus(apiErrorText(err, 'Failed to rename guest.'), true);
        }
      });
    }

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

function reviewProofHtml(item) {
  const url = item.proof_url;
  if (!url) {
    return `<p class="hint">${escapeHtml(item.proof_note || 'No payment proof available.')}</p>`;
  }
  const safeUrl = escapeHtml(url);
  const lower = String(url).toLowerCase().split('?')[0];
  const isImage = /\.(jpg|jpeg|png)$/.test(lower);
  if (isImage) {
    return `<a href="${safeUrl}" target="_blank" rel="noopener"><img src="${safeUrl}" loading="lazy" alt="Payment proof" class="admin-proof-thumb" /></a>`;
  }
  return `<a href="${safeUrl}" target="_blank" rel="noopener">View payment proof</a>`;
}

function reviewRepostProofsHtml(item) {
  const proofs = Array.isArray(item.repost_proofs) ? item.repost_proofs : [];
  const rows = proofs
    .filter((proof) => proof && proof.url)
    .map((proof) => {
      const safeName = escapeHtml(proof.full_name || '');
      const safeUrl = escapeHtml(proof.url);
      const lower = String(proof.url).toLowerCase().split('?')[0];
      const isImage = /\.(jpg|jpeg|png)$/.test(lower);
      const media = isImage
        ? `<a href="${safeUrl}" target="_blank" rel="noopener"><img src="${safeUrl}" loading="lazy" alt="Repost proof for ${safeName}" class="admin-proof-thumb" /></a>`
        : `<a href="${safeUrl}" target="_blank" rel="noopener">View repost proof</a>`;
      return `<div class="admin-repost-proof"><p class="admin-card-meta">Repost: ${safeName}</p>${media}</div>`;
    })
    .join('');
  if (!rows) return '';
  return `<div class="admin-repost-proofs">${rows}</div>`;
}

function renderAdminReviews() {
  if (!adminEl.reviewsList) return;
  adminEl.reviewsList.innerHTML = '';
  if (!adminState.reviews.length) {
    adminEl.reviewsList.innerHTML = '<p class="hint">No pending payments.</p>';
    return;
  }
  for (const item of adminState.reviews) {
    const attendees = Array.isArray(item.attendees) ? item.attendees : [];
    const attendeeHtml = attendees.length ? attendees.map((n) => escapeHtml(n)).join(', ') : '-';
    const base = Number(item.base_total_price || 0);
    const group = Number(item.group_discount_amount || 0);
    const disc = Number(item.discount_amount || 0);
    const applied = Math.max(group, disc);
    const total = Number(item.total_price || 0);
    const card = document.createElement('div');
    card.className = 'admin-card';
    card.innerHTML = `
      <div class="admin-card-head">
        <p class="admin-card-title">${escapeHtml(item.code || '')}</p>
        <div class="admin-inline-actions">
          <button type="button" data-action="approve">Approve</button>
          <button type="button" data-action="reject-toggle">Reject</button>
        </div>
      </div>
      <div>
        <p class="admin-card-meta">${escapeHtml(item.event_title || '')} (${escapeHtml(item.event_datetime || '')})</p>
        <p class="admin-card-meta">${escapeHtml(item.buyer_name || '')} ${escapeHtml(item.buyer_surname || '')} | ${escapeHtml(item.buyer_phone || '')}</p>
        <p class="admin-card-meta">Boys: ${escapeHtml(String(item.boys ?? 0))} | Girls: ${escapeHtml(String(item.girls ?? 0))}</p>
        <p class="admin-card-meta">Base: ${escapeHtml(base.toFixed(2))} | Discount: ${escapeHtml(applied.toFixed(2))} | Total: ${escapeHtml(total.toFixed(2))}</p>
        <p class="admin-card-meta">Guests: ${attendeeHtml}</p>
        <div class="admin-proof">${reviewProofHtml(item)}</div>
        ${reviewRepostProofsHtml(item)}
        <div class="admin-reject-box" hidden>
          <label>Rejection note<input type="text" data-role="reject-note" placeholder="Reason for rejection" /></label>
          <button type="button" data-action="reject-confirm">Confirm reject</button>
        </div>
      </div>
    `;

    const approveBtn = card.querySelector('button[data-action="approve"]');
    const rejectToggle = card.querySelector('button[data-action="reject-toggle"]');
    const rejectBox = card.querySelector('.admin-reject-box');
    const noteInput = card.querySelector('input[data-role="reject-note"]');
    const rejectConfirm = card.querySelector('button[data-action="reject-confirm"]');

    if (approveBtn) {
      approveBtn.addEventListener('click', async () => {
        try {
          const res = await adminPost('/api/admin/reservation/approve', {
            reservation_id: item.reservation_id,
          });
          setAdminStatus(res.message || 'Reservation approved.');
          await Promise.all([loadAdminReviews(), loadAdminGuests(), loadAdminEvents()]);
        } catch (err) {
          setAdminStatus(apiErrorText(err, 'Failed to approve reservation.'), true);
        }
      });
    }
    if (rejectToggle && rejectBox) {
      rejectToggle.addEventListener('click', () => {
        rejectBox.hidden = !rejectBox.hidden;
        if (!rejectBox.hidden && noteInput) noteInput.focus();
      });
    }
    if (rejectConfirm) {
      rejectConfirm.addEventListener('click', async () => {
        const note = noteInput ? noteInput.value.trim() : '';
        if (!note) {
          setAdminStatus('Rejection note is required.', true);
          return;
        }
        try {
          const res = await adminPost('/api/admin/reservation/reject', {
            reservation_id: item.reservation_id,
            note,
          });
          setAdminStatus(res.message || 'Reservation rejected.');
          await Promise.all([loadAdminReviews(), loadAdminGuests(), loadAdminEvents()]);
        } catch (err) {
          setAdminStatus(apiErrorText(err, 'Failed to reject reservation.'), true);
        }
      });
    }

    adminEl.reviewsList.appendChild(card);
  }
}

async function loadAdminReviews() {
  const data = await adminGet('/api/admin/reservation/pending');
  adminState.reviews = Array.isArray(data.items) ? data.items : [];
  renderAdminReviews();
}

function renderAdminCarousel(items) {
  if (!adminEl.carouselList) return;
  const list = Array.isArray(items) ? items : [];
  if (!list.length) {
    adminEl.carouselList.innerHTML = '<p class="hint">No carousel photos yet. The homepage shows the default photos.</p>';
    return;
  }
  adminEl.carouselList.innerHTML = list.map((item) => {
    const url = escapeHtml((item && item.url) || '');
    const id = Number((item && item.id) || 0);
    return `
      <div class="admin-carousel-item">
        <img src="${url}" alt="Carousel photo" loading="lazy" />
        <button type="button" class="admin-carousel-delete" data-carousel-id="${id}">Delete</button>
      </div>
    `;
  }).join('');
}

async function loadAdminCarousel() {
  if (!adminEl.carouselList) return;
  try {
    const data = await adminGet('/api/carousel');
    renderAdminCarousel(data && data.items);
  } catch (err) {
    adminEl.carouselList.innerHTML = `<p class="hint error">${escapeHtml(apiErrorText(err, 'Failed to load carousel.'))}</p>`;
  }
}

async function addAdminCarouselPhoto() {
  if (!adminEl.carouselFile) return;
  const file = adminEl.carouselFile.files && adminEl.carouselFile.files[0];
  if (!file) {
    setAdminStatus('Choose a JPG or PNG image first.', true);
    return;
  }
  if (adminEl.carouselAdd) adminEl.carouselAdd.disabled = true;
  setAdminStatus('Uploading photo...');
  try {
    const formData = new FormData();
    formData.set('file', file);
    await adminUpload('/api/admin/carousel', formData);
    if (adminEl.carouselFile) adminEl.carouselFile.value = '';
    await loadAdminCarousel();
    loadHomepageCarousel();
    setAdminStatus('Carousel photo added.');
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Failed to add carousel photo.'), true);
  } finally {
    if (adminEl.carouselAdd) adminEl.carouselAdd.disabled = false;
  }
}

async function deleteAdminCarouselPhoto(id) {
  const imageId = Number(id || 0);
  if (!imageId) return;
  setAdminStatus('Deleting photo...');
  try {
    await adminPost('/api/admin/carousel/delete', { id: imageId });
    await loadAdminCarousel();
    loadHomepageCarousel();
    setAdminStatus('Carousel photo deleted.');
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Failed to delete carousel photo.'), true);
  }
}

async function refreshAdminAll() {
  await Promise.all([loadAdminReviews(), loadAdminGuests(), loadAdminEvents(), loadAdminCarousel()]);
}

function renderCheckinResult(ticket, message = '', isError = false) {
  if (!adminEl.checkinResult) return;
  if (!ticket) {
    adminEl.checkinResult.innerHTML = `<p class="hint${isError ? ' error' : ''}">${escapeHtml(message || 'No ticket selected.')}</p>`;
    if (adminEl.checkinConfirm) adminEl.checkinConfirm.disabled = true;
    return;
  }
  const approved = (ticket.reservation_status || '').toLowerCase() === 'approved';
  const checked = Boolean(ticket.checked_in);
  const statusClass = checked ? 'checked' : (approved ? 'ready' : 'blocked');
  const statusText = checked
    ? `Already checked in${ticket.checked_in_at ? ` at ${ticket.checked_in_at}` : ''}`
    : (approved ? 'Ready to check in' : `Cannot check in: ${ticket.reservation_status}`);
  adminEl.checkinResult.innerHTML = `
    <div class="checkin-card ${statusClass}">
      <p class="eyebrow">${escapeHtml(ticket.event_title || '')}</p>
      <h3>${escapeHtml(ticket.full_name || '')}</h3>
      <p>${escapeHtml(statusText)}</p>
      <p class="admin-card-meta">${escapeHtml(ticket.reservation_code || '')} | ${escapeHtml(ticket.event_datetime || '')}</p>
      ${message ? `<p class="hint${isError ? ' error' : ''}">${escapeHtml(message)}</p>` : ''}
    </div>
  `;
  if (adminEl.checkinConfirm) {
    adminEl.checkinConfirm.disabled = checked || !approved;
  }
}

function normalizeScannedToken(value) {
  const raw = (value || '').trim();
  if (!raw) return '';
  try {
    const parsed = new URL(raw, window.location.origin);
    const parts = parsed.pathname.split('/').filter(Boolean);
    if (parts.length >= 2 && parts[parts.length - 2] === 'checkin') {
      return decodeURIComponent(parts[parts.length - 1]);
    }
    return parsed.searchParams.get('token') || raw;
  } catch (_err) {
    return raw.startsWith('/checkin/') ? decodeURIComponent(raw.split('/checkin/', 1)[1].split('?', 1)[0]) : raw;
  }
}

async function lookupCheckinToken(rawToken) {
  const token = normalizeScannedToken(rawToken || (adminEl.checkinToken ? adminEl.checkinToken.value : ''));
  if (!token) {
    renderCheckinResult(null, 'Paste or scan a ticket first.', true);
    return null;
  }
  if (adminEl.checkinToken) adminEl.checkinToken.value = token;
  try {
    const data = await adminGet('/api/admin/checkin/lookup', { token });
    adminState.checkinTicket = data.ticket || null;
    renderCheckinResult(adminState.checkinTicket);
    return adminState.checkinTicket;
  } catch (err) {
    adminState.checkinTicket = null;
    renderCheckinResult(null, apiErrorText(err, 'Ticket lookup failed.'), true);
    return null;
  }
}

async function confirmCheckin() {
  const token = normalizeScannedToken(adminEl.checkinToken ? adminEl.checkinToken.value : '');
  if (!token) {
    renderCheckinResult(null, 'Paste or scan a ticket first.', true);
    return;
  }
  if (adminEl.checkinConfirm) adminEl.checkinConfirm.disabled = true;
  try {
    const data = await adminPost('/api/admin/checkin', { token });
    adminState.checkinTicket = data.ticket || null;
    renderCheckinResult(adminState.checkinTicket, data.message || 'Checked in.');
    await loadAdminGuests();
  } catch (err) {
    renderCheckinResult(adminState.checkinTicket, apiErrorText(err, 'Check-in failed.'), true);
  }
}

function stopScanner() {
  window.clearInterval(adminState.scanTimer);
  adminState.scanTimer = 0;
  adminState.scanBusy = false;
  if (adminState.scanStream) {
    for (const track of adminState.scanStream.getTracks()) {
      track.stop();
    }
  }
  adminState.scanStream = null;
  if (adminEl.scanVideo) {
    adminEl.scanVideo.pause();
    adminEl.scanVideo.srcObject = null;
    adminEl.scanVideo.hidden = true;
  }
  if (adminEl.scanPlaceholder) adminEl.scanPlaceholder.hidden = false;
  if (adminEl.scanStop) adminEl.scanStop.hidden = true;
  if (adminEl.scanStart) adminEl.scanStart.disabled = false;
}

// Lazily inject the self-hosted jsQR decoder (CSP-safe, same-origin, load once).
let jsqrLoadPromise = null;
function loadJsQr() {
  if (window.jsQR) return Promise.resolve(window.jsQR);
  if (jsqrLoadPromise) return jsqrLoadPromise;
  jsqrLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = '/static/jsqr.js';
    script.async = true;
    script.addEventListener('load', () => {
      if (window.jsQR) {
        resolve(window.jsQR);
      } else {
        jsqrLoadPromise = null;
        reject(new Error('QR decoder failed to initialise.'));
      }
    });
    script.addEventListener('error', () => {
      jsqrLoadPromise = null;
      reject(new Error('Could not load the QR decoder.'));
    });
    document.head.appendChild(script);
  });
  return jsqrLoadPromise;
}

// getUserMedia requires a secure context (https) except on localhost.
function isSecureScanContext() {
  if (window.isSecureContext) return true;
  const host = window.location.hostname;
  return window.location.protocol === 'https:' || host === 'localhost' || host === '127.0.0.1';
}

function scannerErrorMessage(err) {
  const name = err && err.name ? err.name : '';
  if (name === 'NotAllowedError' || name === 'SecurityError') {
    return 'Camera permission was denied. Allow camera access or paste the ticket code.';
  }
  if (name === 'NotFoundError' || name === 'OverconstrainedError' || name === 'DevicesNotFoundError') {
    return 'No camera found on this device. Paste the ticket code instead.';
  }
  return apiErrorText(err, 'Could not start camera scanner.');
}

async function startScanner() {
  if (!adminEl.scanVideo) return;
  // A secure context is required for camera access on every modern browser.
  if (!isSecureScanContext() || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    renderCheckinResult(null, 'Camera needs a secure (https) connection. Use the ticket code box.', true);
    return;
  }
  const hasBarcodeDetector = 'BarcodeDetector' in window;
  if (adminEl.scanStart) adminEl.scanStart.disabled = true;

  // Acquire the rear camera first so permission errors get precise messaging.
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' } },
      audio: false,
    });
  } catch (err) {
    stopScanner();
    renderCheckinResult(null, scannerErrorMessage(err), true);
    return;
  }

  // Pick a per-frame decoder: native BarcodeDetector when available (Chrome/
  // Android), otherwise the self-hosted jsQR fallback (iOS Safari, Firefox).
  let detectFrame;
  try {
    if (hasBarcodeDetector) {
      const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
      detectFrame = async () => {
        const codes = await detector.detect(adminEl.scanVideo);
        return codes && codes[0] && codes[0].rawValue ? codes[0].rawValue : '';
      };
    } else {
      let jsQR;
      try {
        jsQR = await loadJsQr();
      } catch (_loadErr) {
        stopScanner();
        renderCheckinResult(
          null,
          'Camera QR scanning is not available here. Scan the QR with your phone camera app, or paste the ticket code.',
          true,
        );
        return;
      }
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      detectFrame = async () => {
        const video = adminEl.scanVideo;
        const width = video.videoWidth;
        const height = video.videoHeight;
        if (!width || !height) return '';
        canvas.width = width;
        canvas.height = height;
        ctx.drawImage(video, 0, 0, width, height);
        const frame = ctx.getImageData(0, 0, width, height);
        const result = jsQR(frame.data, width, height, { inversionAttempts: 'dontInvert' });
        return result && result.data ? result.data : '';
      };
    }
  } catch (err) {
    stopScanner();
    renderCheckinResult(null, scannerErrorMessage(err), true);
    return;
  }

  try {
    adminState.scanStream = stream;
    adminEl.scanVideo.srcObject = stream;
    adminEl.scanVideo.hidden = false;
    if (adminEl.scanPlaceholder) adminEl.scanPlaceholder.hidden = true;
    if (adminEl.scanStop) adminEl.scanStop.hidden = false;
    await adminEl.scanVideo.play();
    adminState.scanTimer = window.setInterval(async () => {
      if (adminState.scanBusy || !adminEl.scanVideo || adminEl.scanVideo.readyState < 2) return;
      adminState.scanBusy = true;
      try {
        const value = await detectFrame();
        if (value) {
          stopScanner();
          await lookupCheckinToken(value);
        }
      } catch (_err) {
        // Keep scanning; camera frames can fail transiently.
      } finally {
        adminState.scanBusy = false;
      }
    }, 400);
  } catch (err) {
    stopScanner();
    renderCheckinResult(null, scannerErrorMessage(err), true);
  }
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
  try {
    const data = await adminGet('/api/admin/bootstrap');
    adminState.ready = true;
    adminEl.ident.textContent = data.source === 'website'
      ? 'Admin session: website'
      : `Admin Telegram ID: ${data.tg_id}`;
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
  if (adminEl.open) adminEl.open.classList.add('active');
  setAdminOpenStatus('');
  setAdminSection(adminState.activeSection || 'payments');
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

async function logoutAdmin() {
  try {
    await fetch('/api/admin/logout', { method: 'POST', headers: adminHeaders() });
  } catch (_err) {
    /* best-effort: clear local state regardless */
  }
  adminState.ready = false;
  setAdminLocked(true);
  if (adminEl.loginPanel) adminEl.loginPanel.hidden = false;
  if (adminEl.open) adminEl.open.classList.remove('active');
  setAdminStatus('Logged out.');
  setPageTab('main');
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
  const whenVal = adminEl.when ? datetimeFromInput(adminEl.when.value) : '';
  const locVal = adminEl.location ? adminEl.location.value.trim() : '';
  const mapsVal = adminEl.maps ? adminEl.maps.value.trim() : '';
  const payload = {
    title,
    caption,
    maps_url: mapsVal,
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
  if (whenVal && !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(whenVal)) {
    setAdminStatus('Date & time must be in YYYY-MM-DD HH:MM format.', true);
    return;
  }
  if (mapsVal && !/^https:\/\//i.test(mapsVal) && !/<iframe[^>]*\ssrc=/i.test(mapsVal)) {
    setAdminStatus('Google Maps: paste an https link or the "Embed a map" code.', true);
    return;
  }

  try {
    let res;
    if (eventId) {
      const updates = { ...payload };
      if (whenVal) updates.datetime = whenVal;
      if (locVal) updates.location = locVal;
      res = await adminPost('/api/admin/event/update', {
        event_id: eventId,
        updates,
      });
      setAdminStatus(res.message || 'Event updated.');
    } else {
      const createBody = { ...payload };
      if (whenVal) createBody.event_datetime = whenVal;
      if (locVal) createBody.location = locVal;
      res = await adminPost('/api/admin/event/create_simple', createBody);
      setAdminStatus(res.message || 'Event created.');
    }
    const savedId = res && res.event && res.event.id ? Number(res.event.id) : 0;
    if (savedId) {
      adminState.selectedEventId = savedId;
    }
    const bannerFile = adminEl.photo && adminEl.photo.files && adminEl.photo.files[0];
    if (savedId && bannerFile) {
      const formData = new FormData();
      formData.set('event_id', String(savedId));
      formData.set('file', bannerFile);
      try {
        await adminUpload('/api/admin/event/photo', formData);
        setAdminStatus('Event saved and banner uploaded.');
        if (adminEl.photo) adminEl.photo.value = '';
      } catch (uploadErr) {
        setAdminStatus(apiErrorText(uploadErr, 'Event saved but banner upload failed.'), true);
      }
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
  saveBookingDraft();
});

girlsEl.addEventListener('input', () => {
  state.girls = Math.max(0, Number(girlsEl.value || 0));
  rebuildAttendees();
  refreshQuote();
  saveBookingDraft();
});

submitBtn.addEventListener('click', submitDraft);
refreshBtn.addEventListener('click', fetchEvents);
if (paymentProofEl) {
  paymentProofEl.addEventListener('change', renderSummary);
}
if (termsAcceptedEl) {
  termsAcceptedEl.addEventListener('change', onBookingFieldChange);
}
if (accountSaveEl) {
  accountSaveEl.addEventListener('click', registerWebsiteAccount);
}
if (accountOpenEl) {
  accountOpenEl.addEventListener('click', () => {
    state.accountOpen = !state.accountOpen;
    renderAccountPanel();
    setAccountStatus('');
  });
}
if (accountCloseEl) {
  accountCloseEl.addEventListener('click', closeAccountPanel);
}
if (accountBackdropEl) {
  accountBackdropEl.addEventListener('click', closeAccountPanel);
}
if (accountPanelEl) {
  accountPanelEl.addEventListener('keydown', (event) => {
    if (event.key !== 'Tab' || accountPanelEl.hidden) return;
    const focusables = getAccountFocusable();
    if (!focusables.length) {
      event.preventDefault();
      return;
    }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;
    if (event.shiftKey) {
      if (active === first || !accountPanelEl.contains(active)) {
        event.preventDefault();
        last.focus();
      }
    } else if (active === last || !accountPanelEl.contains(active)) {
      event.preventDefault();
      first.focus();
    }
  });
}
document.addEventListener('click', (event) => {
  if (!accountPanelEl || accountPanelEl.hidden) return;
  const target = event.target;
  if (accountPanelEl.contains(target) || (accountOpenEl && accountOpenEl.contains(target))) return;
  if (target && target.closest && target.closest('[data-page-tab]')) return;
  closeAccountPanel();
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && accountPanelEl && !accountPanelEl.hidden) {
    closeAccountPanel();
  }
});
if (accountEditEl) {
  accountEditEl.addEventListener('click', () => {
    state.editingProfile = true;
    state.accountOpen = true;
    renderAccountPanel();
    setAccountStatus('');
  });
}
if (accountSendCodeEl) {
  accountSendCodeEl.addEventListener('click', sendWebsiteLoginCode);
}
if (accountLogoutEl) {
  accountLogoutEl.addEventListener('click', logoutWebsiteAccount);
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
if (heroGetTicketsEl) {
  heroGetTicketsEl.addEventListener('click', () => {
    setPageTab('main');
    const target = document.getElementById('upcoming-events');
    if (target && target.scrollIntoView) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
}
let carouselScrollWired = false;
function wireCarousel() {
  carouselTrackEl = document.querySelector('.main-carousel-track');
  carouselDots = Array.from(document.querySelectorAll('.main-carousel-dots span'));
  if (!carouselTrackEl || !carouselDots.length) return;
  if (!carouselScrollWired) {
    let carouselFrame = 0;
    carouselTrackEl.addEventListener('scroll', () => {
      window.cancelAnimationFrame(carouselFrame);
      carouselFrame = window.requestAnimationFrame(updateCarouselDots);
    }, { passive: true });
    window.addEventListener('resize', updateCarouselDots);
    carouselScrollWired = true;
  }
  carouselDots.forEach((dot, index) => {
    dot.addEventListener('click', () => {
      carouselTrackEl.scrollTo({
        left: carouselTrackEl.clientWidth * index,
        behavior: 'smooth',
      });
    });
  });
  updateCarouselDots();
}
wireCarousel();

async function loadHomepageCarousel() {
  if (!carouselTrackEl) return;
  let items = [];
  try {
    const res = await fetch('/api/carousel', { cache: 'no-store' });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data && Array.isArray(data.items)) items = data.items;
  } catch (_err) {
    return;
  }
  // No configured images -> keep the default static slides/dots as-is.
  if (!items.length) return;
  const dotsEl = document.querySelector('.main-carousel-dots');
  if (!dotsEl) return;
  const track = carouselTrackEl;
  track.innerHTML = '';
  dotsEl.innerHTML = '';
  items.forEach((item, index) => {
    const slide = document.createElement('div');
    slide.className = 'main-carousel-slide';
    const img = document.createElement('img');
    img.setAttribute('loading', 'lazy');
    img.setAttribute('decoding', 'async');
    img.setAttribute('alt', 'Budapest Tunderi photo');
    img.setAttribute('src', String((item && item.url) || ''));
    slide.appendChild(img);
    track.appendChild(slide);
    const dot = document.createElement('span');
    if (index === 0) dot.className = 'active';
    dotsEl.appendChild(dot);
  });
  wireCarousel();
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
if (adminEl.logout) {
  adminEl.logout.addEventListener('click', logoutAdmin);
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
      resetAccountPanelState();
      setPageTab(key);
    });
  }
}
const footerTermsLink = document.getElementById('footer-terms-link');
if (footerTermsLink) {
  footerTermsLink.addEventListener('click', (event) => {
    event.preventDefault();
    resetAccountPanelState();
    setPageTab('book');
    const termsDetails = document.querySelector('.terms-box details');
    if (termsDetails) {
      termsDetails.open = true;
      termsDetails.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
}
if (adminEl.tabs && adminEl.tabs.length) {
  for (const tabBtn of adminEl.tabs) {
    tabBtn.addEventListener('click', () => {
      const tabKey = tabBtn.dataset ? tabBtn.dataset.adminTab : '';
      const key = tabKey || 'payments';
      setAdminSection(key);
      if (key === 'payments') {
        loadAdminReviews().catch((err) => setAdminStatus(apiErrorText(err, 'Failed to load payments.'), true));
      } else if (key === 'carousel') {
        loadAdminCarousel().catch((err) => setAdminStatus(apiErrorText(err, 'Failed to load carousel.'), true));
      }
    });
  }
}
if (adminEl.carouselAdd) {
  adminEl.carouselAdd.addEventListener('click', addAdminCarouselPhoto);
}
if (adminEl.carouselRefresh) {
  adminEl.carouselRefresh.addEventListener('click', () => {
    loadAdminCarousel().catch((err) => setAdminStatus(apiErrorText(err, 'Failed to refresh carousel.'), true));
  });
}
if (adminEl.carouselList) {
  adminEl.carouselList.addEventListener('click', (event) => {
    const target = event.target && event.target.closest ? event.target.closest('button.admin-carousel-delete') : null;
    if (!target) return;
    event.preventDefault();
    deleteAdminCarouselPhoto(target.getAttribute('data-carousel-id'));
  });
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
if (adminEl.reviewsRefresh) {
  adminEl.reviewsRefresh.addEventListener('click', async () => {
    try {
      await loadAdminReviews();
      setAdminStatus('Payments refreshed.');
    } catch (err) {
      setAdminStatus(apiErrorText(err, 'Failed to refresh payments.'), true);
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
if (adminEl.scanStart) {
  adminEl.scanStart.addEventListener('click', startScanner);
}
if (adminEl.scanStop) {
  adminEl.scanStop.addEventListener('click', stopScanner);
}
if (adminEl.checkinLookup) {
  adminEl.checkinLookup.addEventListener('click', () => lookupCheckinToken());
}
if (adminEl.checkinConfirm) {
  adminEl.checkinConfirm.addEventListener('click', confirmCheckin);
}
if (adminEl.checkinToken) {
  adminEl.checkinToken.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') lookupCheckinToken();
  });
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
setAdminSection('payments');
setAdminLocked(true);
renderAccountPanel();
updateCarouselDots();
loadHomepageCarousel();
rebuildAttendees();
loadAuthConfig();
fetchEvents();
loadMeAndTickets();
if (autoOpenAdmin) {
  openAdminMode().catch((err) => {
    setAdminStatus(apiErrorText(err, 'Admin access denied.'), true);
  });
} else {
  checkAdminAvailability();
}
if (window.Telegram && window.Telegram.WebApp) {
  applyTelegramContext();
} else {
  window.addEventListener('tg-sdk-ready', applyTelegramContext, { once: true });
}
if (initialCheckinToken && adminEl.checkinToken) {
  adminEl.checkinToken.value = initialCheckinToken;
  openAdminMode()
    .then(() => {
      setAdminSection('checkin');
      return lookupCheckinToken(initialCheckinToken);
    })
    .catch((err) => {
      setAdminStatus(apiErrorText(err, 'Admin access denied.'), true);
    });
}
