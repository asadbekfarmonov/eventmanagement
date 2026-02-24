const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
const qs = new URLSearchParams(window.location.search);
const fallbackTgId = Number(qs.get('tg_id') || 0);
const tgId = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id) || fallbackTgId || null;
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
const refreshBtn = document.getElementById('refresh-events');
const debugPayloadEl = document.getElementById('debug-payload');
const ticketsListEl = document.getElementById('tickets-list');
const ticketsEmptyEl = document.getElementById('tickets-empty');
const ticketsRefreshEl = document.getElementById('tickets-refresh');

const adminEl = {
  open: document.getElementById('admin-open'),
  area: document.getElementById('admin-area'),
  refreshAll: document.getElementById('admin-refresh-all'),
  ident: document.getElementById('admin-ident'),
  status: document.getElementById('admin-status'),
  guestsSearch: document.getElementById('admin-guests-search'),
  guestsSort: document.getElementById('admin-guests-sort'),
  guestsRefresh: document.getElementById('admin-guests-refresh'),
  guestsList: document.getElementById('admin-guests-list'),
  addEventSelect: document.getElementById('admin-add-event-select'),
  guestGender: document.getElementById('admin-guest-gender'),
  guestName: document.getElementById('admin-guest-name'),
  guestSurname: document.getElementById('admin-guest-surname'),
  guestAdd: document.getElementById('admin-guest-add'),
  removeEventSelect: document.getElementById('admin-remove-event-select'),
  removeName: document.getElementById('admin-remove-name'),
  removeSurname: document.getElementById('admin-remove-surname'),
  removeByName: document.getElementById('admin-guest-remove-by-name'),
  importEventSelect: document.getElementById('admin-import-event-select'),
  importGender: document.getElementById('admin-import-gender'),
  importFile: document.getElementById('admin-import-file'),
  importUpload: document.getElementById('admin-import-upload'),
  exportDownload: document.getElementById('admin-export-download'),
  eventsRefresh: document.getElementById('admin-events-refresh'),
  eventSelect: document.getElementById('admin-event-select'),
  eventSave: document.getElementById('admin-event-save'),
  title: document.getElementById('admin-ev-title'),
  caption: document.getElementById('admin-ev-caption'),
  ebBoy: document.getElementById('admin-ev-eb-boy'),
  ebGirl: document.getElementById('admin-ev-eb-girl'),
  ebQty: document.getElementById('admin-ev-eb-qty'),
  t1Boy: document.getElementById('admin-ev-t1-boy'),
  t1Girl: document.getElementById('admin-ev-t1-girl'),
  t1Qty: document.getElementById('admin-ev-t1-qty'),
  t2Boy: document.getElementById('admin-ev-t2-boy'),
  t2Girl: document.getElementById('admin-ev-t2-girl'),
  t2Qty: document.getElementById('admin-ev-t2-qty'),
};

const state = {
  events: [],
  selectedEventId: null,
  boys: 0,
  girls: 0,
  userProfile: null,
};

const adminState = {
  ready: false,
  guestsSort: 'newest',
  guestsSearch: '',
  guests: [],
  events: [],
  selectedEventId: null,
};

function money(value) {
  return Number(value || 0).toFixed(2);
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

function apiErrorText(err, fallback) {
  if (!err) return fallback;
  if (typeof err === 'string') return err;
  if (err.detail) return err.detail;
  if (err.message) return err.message;
  return fallback;
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

function attendeeFullNames() {
  return attendeeEntries().map((entry) => `${entry.first} ${entry.surname}`.trim());
}

function selectedEvent() {
  return state.events.find((e) => e.id === state.selectedEventId) || null;
}

function renderSummary() {
  const event = selectedEvent();
  if (!event) {
    summaryEl.innerHTML = '<p>Select event and attendee counts.</p>';
    submitBtn.disabled = true;
    return;
  }

  const qty = totalCount();
  const boysCost = state.boys * Number(event.tier.boy_price || 0);
  const girlsCost = state.girls * Number(event.tier.girl_price || 0);
  const total = boysCost + girlsCost;

  summaryEl.innerHTML = [
    `<strong>${event.title}</strong>`,
    `<div>${event.caption || ''}</div>`,
    `<div>Tier: ${event.tier.name}</div>`,
    '<hr>',
    `<div>Boys: ${state.boys} x ${money(event.tier.boy_price)}</div>`,
    `<div>Girls: ${state.girls} x ${money(event.tier.girl_price)}</div>`,
    `<div><strong>Total: ${money(total)}</strong></div>`,
    `<div class="hint">Attendees required: ${qty}</div>`,
  ].join('');

  const rows = attendeeEntries();
  const namesReady = rows.length === qty && rows.every((row) => row.first && row.surname);
  submitBtn.disabled = !(qty > 0 && namesReady);
}

function rebuildAttendees() {
  const qty = totalCount();
  const prev = attendeeEntries();
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
    attendeesListEl.appendChild(row);
  }

  if (qty === 0) {
    attendeesListEl.innerHTML = '<p class="hint">Set boys/girls count first.</p>';
  }

  renderSummary();
}

function selectEvent(eventId) {
  state.selectedEventId = eventId;

  for (const card of eventsListEl.querySelectorAll('.event-card')) {
    card.classList.toggle('active', Number(card.dataset.id) === eventId);
  }
  setStatus('');
  renderSummary();
}

function renderEvents() {
  eventsListEl.innerHTML = '';
  eventsEmptyEl.hidden = state.events.length > 0;

  for (const event of state.events) {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'event-card';
    card.dataset.id = String(event.id);
    card.innerHTML = `
      <p class="event-title">${event.title}</p>
      <p class="event-meta">${event.caption || ''}</p>
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
    if (!resp.ok) throw new Error('Failed to load events');
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
  const qty = totalCount();
  const total = state.boys * Number(event.tier.boy_price || 0) + state.girls * Number(event.tier.girl_price || 0);

  return {
    type: 'booking_draft_v1',
    event_id: event.id,
    boys: state.boys,
    girls: state.girls,
    attendees,
    attendee_parts: attendeeParts,
    tier_key: event.tier.key,
    tier_name: event.tier.name,
    boy_price: Number(event.tier.boy_price || 0),
    girl_price: Number(event.tier.girl_price || 0),
    total_price: total,
    quantity: qty,
  };
}

function submitDraft() {
  const payload = getPayload();
  if (!payload) {
    setStatus('Choose an event first.', true);
    return;
  }

  if (payload.quantity <= 0) {
    setStatus('At least one attendee is required.', true);
    return;
  }

  for (const fullName of payload.attendees) {
    if (!fullName || fullName.split(' ').length < 2) {
      setStatus('Each attendee must have name and surname.', true);
      return;
    }
  }

  const text = JSON.stringify(payload);
  if (tg) {
    tg.sendData(text);
    setStatus('Draft sent. Return to chat and upload payment proof.');
  } else {
    debugPayloadEl.hidden = false;
    debugPayloadEl.value = text;
    setStatus('Not running inside Telegram. Payload preview shown below.');
  }
}

function renderTickets(items) {
  ticketsListEl.innerHTML = '';
  ticketsEmptyEl.hidden = items.length > 0;
  if (!items.length) return;
  for (const item of items) {
    const card = document.createElement('div');
    card.className = 'admin-card';
    card.innerHTML = `
      <p class="admin-card-title">${item.code} | ${item.status}</p>
      <p class="admin-card-meta">${item.event_title}</p>
      <p class="admin-card-meta">Tier: ${item.tier_label} | Boys: ${item.boys} | Girls: ${item.girls} | Total: ${money(item.total_price)}</p>
    `;
    ticketsListEl.appendChild(card);
  }
}

async function loadMeAndTickets() {
  if (!tgId) return;
  try {
    const meUrl = new URL('/api/me', window.location.origin);
    meUrl.searchParams.set('tg_id', String(tgId));
    const meResp = await fetch(meUrl.toString(), { cache: 'no-store' });
    if (meResp.ok) {
      const meData = await meResp.json();
      state.userProfile = meData.profile || null;
      rebuildAttendees();
    }
  } catch (_err) {
    // Optional mini app personalization; ignore failures.
  }

  try {
    const ticketsUrl = new URL('/api/my_tickets', window.location.origin);
    ticketsUrl.searchParams.set('tg_id', String(tgId));
    const resp = await fetch(ticketsUrl.toString(), { cache: 'no-store' });
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

function initTelegram() {
  if (!tg) return;
  tg.ready();
  tg.expand();
}

async function adminGet(path, params = {}) {
  if (!tgId) throw new Error('Cannot detect Telegram user id in Mini App.');
  const url = new URL(path, window.location.origin);
  url.searchParams.set('tg_id', String(tgId));
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && String(v).trim() !== '') {
      url.searchParams.set(k, String(v));
    }
  });
  const res = await fetch(url.toString(), { cache: 'no-store' });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw data;
  return data;
}

async function adminPost(path, body = {}) {
  if (!tgId) throw new Error('Cannot detect Telegram user id in Mini App.');
  const payload = { ...body, tg_id: tgId };
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw data;
  return data;
}

async function adminUpload(path, formData) {
  if (!tgId) throw new Error('Cannot detect Telegram user id in Mini App.');
  formData.set('tg_id', String(tgId));
  const res = await fetch(path, {
    method: 'POST',
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
}

function clearAdminEventForm() {
  adminEl.title.value = '';
  adminEl.caption.value = '';
  adminEl.ebBoy.value = 0;
  adminEl.ebGirl.value = 0;
  adminEl.ebQty.value = 0;
  adminEl.t1Boy.value = 0;
  adminEl.t1Girl.value = 0;
  adminEl.t1Qty.value = 0;
  adminEl.t2Boy.value = 0;
  adminEl.t2Girl.value = 0;
  adminEl.t2Qty.value = 0;
}

function renderAdminGuests() {
  adminEl.guestsList.innerHTML = '';
  if (!adminState.guests.length) {
    adminEl.guestsList.innerHTML = '<p class="hint">No guests found.</p>';
    return;
  }

  for (const guest of adminState.guests) {
    const card = document.createElement('div');
    card.className = 'admin-card';
    card.innerHTML = `
      <div class="admin-card-head">
        <p class="admin-card-title">#${guest.attendee_id} ${guest.full_name} [${guest.gender}]</p>
        <div class="admin-inline-actions">
          <button data-action="rename">Rename</button>
          <button data-action="remove">Remove</button>
        </div>
      </div>
      <p class="admin-card-meta">${guest.event_title} (${guest.event_datetime})</p>
      <p class="admin-card-meta">${guest.reservation_code} | ${guest.reservation_status} | ${guest.buyer_name} ${guest.buyer_surname}</p>
    `;

    const renameBtn = card.querySelector('button[data-action="rename"]');
    const removeBtn = card.querySelector('button[data-action="remove"]');

    renameBtn.addEventListener('click', async () => {
      const nextName = prompt('Enter new full name (Name Surname):', guest.full_name || '');
      if (!nextName) return;
      if (nextName.trim().split(' ').length < 2) {
        setAdminStatus('Name must be in format Name Surname.', true);
        return;
      }
      try {
        const res = await adminPost('/api/admin/guest/rename', {
          attendee_id: guest.attendee_id,
          full_name: nextName.trim(),
        });
        setAdminStatus(res.message || 'Guest renamed.');
        await loadAdminGuests();
      } catch (err) {
        setAdminStatus(apiErrorText(err, 'Failed to rename guest.'), true);
      }
    });

    removeBtn.addEventListener('click', async () => {
      if (!confirm(`Remove ${guest.full_name}?`)) return;
      try {
        const res = await adminPost('/api/admin/guest/remove', {
          attendee_id: guest.attendee_id,
        });
        setAdminStatus(res.message || 'Guest removed.');
        await loadAdminGuests();
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
  populateEventSelect(adminEl.removeEventSelect, adminState.events);
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
    limit: 40,
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
  try {
    const data = await adminGet('/api/admin/bootstrap');
    adminState.ready = true;
    adminEl.ident.textContent = `Admin Telegram ID: ${data.tg_id}`;
    setAdminStatus('Admin access granted.');
    return true;
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Admin access denied.'), true);
    return false;
  }
}

async function openAdminMode() {
  const ok = await ensureAdmin();
  if (!ok) return;
  adminEl.area.hidden = false;
  adminEl.open.classList.add('active');
  await refreshAdminAll();
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

async function removeAdminGuestByName() {
  const eventId = Number(adminEl.removeEventSelect.value || 0);
  const name = adminEl.removeName.value.trim();
  const surname = adminEl.removeSurname.value.trim();
  if (!eventId) {
    setAdminStatus('Choose event first.', true);
    return;
  }
  if (!name || !surname) {
    setAdminStatus('Name and surname are required for removal.', true);
    return;
  }
  try {
    const res = await adminPost('/api/admin/guest/remove_by_name', {
      event_id: eventId,
      name,
      surname,
    });
    adminEl.removeName.value = '';
    adminEl.removeSurname.value = '';
    setAdminStatus(res.message || 'Guest removed.');
    await Promise.all([loadAdminGuests(), loadAdminEvents()]);
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Failed to remove guest.'), true);
  }
}

async function importGuestsXlsx() {
  const eventId = Number(adminEl.importEventSelect.value || 0);
  const gender = adminEl.importGender.value || 'girl';
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
  formData.set('gender', gender);
  formData.set('file', file);
  try {
    const res = await adminUpload('/api/admin/guest/import_xlsx', formData);
    const msg = `Import complete. Added: ${res.added || 0}, Skipped: ${res.skipped || 0}.`;
    setAdminStatus(msg);
    await Promise.all([loadAdminGuests(), loadAdminEvents()]);
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Failed to import guests.'), true);
  }
}

function exportGuestsXlsx() {
  if (!tgId) {
    setAdminStatus('Cannot detect Telegram user id in Mini App.', true);
    return;
  }
  const url = new URL('/api/admin/guest/export_xlsx', window.location.origin);
  url.searchParams.set('tg_id', String(tgId));
  window.open(url.toString(), '_blank', 'noopener,noreferrer');
}

async function saveAdminEvent() {
  const eventId = Number(adminEl.eventSelect.value || 0);
  const title = adminEl.title.value.trim();
  const caption = adminEl.caption.value.trim();
  const payload = {
    title,
    caption,
    early_boy: adminEl.ebBoy.value,
    early_girl: adminEl.ebGirl.value,
    early_qty: adminEl.ebQty.value,
    tier1_boy: adminEl.t1Boy.value,
    tier1_girl: adminEl.t1Girl.value,
    tier1_qty: adminEl.t1Qty.value,
    tier2_boy: adminEl.t2Boy.value,
    tier2_girl: adminEl.t2Girl.value,
    tier2_qty: adminEl.t2Qty.value,
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
    await loadAdminEvents();
    if (res && res.event && res.event.id) {
      adminState.selectedEventId = Number(res.event.id);
      adminEl.eventSelect.value = String(res.event.id);
      fillAdminEventForm(res.event);
    }
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Failed to save event.'), true);
  }
}

boysEl.addEventListener('input', () => {
  state.boys = Math.max(0, Number(boysEl.value || 0));
  rebuildAttendees();
});

girlsEl.addEventListener('input', () => {
  state.girls = Math.max(0, Number(girlsEl.value || 0));
  rebuildAttendees();
});

submitBtn.addEventListener('click', submitDraft);
refreshBtn.addEventListener('click', fetchEvents);

if (adminEl.open) {
  adminEl.open.addEventListener('click', openAdminMode);
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
if (adminEl.removeByName) {
  adminEl.removeByName.addEventListener('click', removeAdminGuestByName);
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
if (ticketsRefreshEl) {
  ticketsRefreshEl.addEventListener('click', loadMeAndTickets);
}

initTelegram();
rebuildAttendees();
fetchEvents();
loadMeAndTickets();
if (autoOpenAdmin && adminEl.open) {
  openAdminMode().catch((err) => {
    setAdminStatus(apiErrorText(err, 'Admin access denied.'), true);
  });
}
