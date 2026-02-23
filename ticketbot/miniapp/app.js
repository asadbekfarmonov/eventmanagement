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
  resSearch: document.getElementById('admin-res-search'),
  resRefresh: document.getElementById('admin-res-refresh'),
  reservationSelect: document.getElementById('admin-reservation-select'),
  guestGender: document.getElementById('admin-guest-gender'),
  guestName: document.getElementById('admin-guest-name'),
  guestAdd: document.getElementById('admin-guest-add'),
  eventsRefresh: document.getElementById('admin-events-refresh'),
  eventSelect: document.getElementById('admin-event-select'),
  eventSave: document.getElementById('admin-event-save'),
  title: document.getElementById('admin-ev-title'),
  datetime: document.getElementById('admin-ev-datetime'),
  location: document.getElementById('admin-ev-location'),
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
};

const adminState = {
  ready: false,
  guestsSort: 'newest',
  guestsSearch: '',
  guests: [],
  reservations: [],
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

function attendeeInputs() {
  return Array.from(attendeesListEl.querySelectorAll('input'));
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
    `<div>${event.event_datetime} | ${event.location}</div>`,
    `<div>Tier: ${event.tier.name}</div>`,
    '<hr>',
    `<div>Boys: ${state.boys} x ${money(event.tier.boy_price)}</div>`,
    `<div>Girls: ${state.girls} x ${money(event.tier.girl_price)}</div>`,
    `<div><strong>Total: ${money(total)}</strong></div>`,
    `<div class="hint">Attendees required: ${qty}</div>`,
  ].join('');

  const names = attendeeInputs().map((x) => x.value.trim());
  const namesReady = names.length === qty && names.every((name) => name.includes(' '));
  submitBtn.disabled = !(qty > 0 && namesReady);
}

function rebuildAttendees() {
  const qty = totalCount();
  const prev = attendeeInputs().map((x) => x.value.trim());
  attendeesListEl.innerHTML = '';

  for (let i = 0; i < qty; i += 1) {
    const wrap = document.createElement('label');
    wrap.textContent = `Attendee #${i + 1} full name`;

    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Name Surname';
    input.value = prev[i] || '';
    input.addEventListener('input', renderSummary);

    wrap.appendChild(input);
    attendeesListEl.appendChild(wrap);
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
      <p class="event-meta">${event.event_datetime}<br>${event.location}</p>
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
  const attendees = attendeeInputs().map((x) => x.value.trim());
  const qty = totalCount();
  const total = state.boys * Number(event.tier.boy_price || 0) + state.girls * Number(event.tier.girl_price || 0);

  return {
    type: 'booking_draft_v1',
    event_id: event.id,
    boys: state.boys,
    girls: state.girls,
    attendees,
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
      setStatus('Each attendee must be in format Name Surname.', true);
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

function fillAdminEventForm(event) {
  if (!event) return;
  adminEl.title.value = event.title || '';
  adminEl.datetime.value = event.event_datetime || '';
  adminEl.location.value = event.location || '';
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
        await Promise.all([loadAdminGuests(), loadAdminReservations()]);
      } catch (err) {
        setAdminStatus(apiErrorText(err, 'Failed to remove guest.'), true);
      }
    });

    adminEl.guestsList.appendChild(card);
  }
}

function renderAdminReservations() {
  adminEl.reservationSelect.innerHTML = '';
  if (!adminState.reservations.length) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'No active reservations';
    adminEl.reservationSelect.appendChild(opt);
    return;
  }
  for (const reservation of adminState.reservations) {
    const opt = document.createElement('option');
    opt.value = reservation.reservation_code;
    opt.textContent = `${reservation.reservation_code} | ${reservation.event_title} | ${reservation.buyer_name} ${reservation.buyer_surname}`;
    adminEl.reservationSelect.appendChild(opt);
  }
}

function renderAdminEvents() {
  const prev = adminState.selectedEventId;
  adminEl.eventSelect.innerHTML = '';

  for (const event of adminState.events) {
    const opt = document.createElement('option');
    opt.value = String(event.id);
    opt.textContent = `#${event.id} ${event.title} (${event.event_datetime})`;
    adminEl.eventSelect.appendChild(opt);
  }

  if (!adminState.events.length) return;
  const selected = adminState.events.find((e) => e.id === prev) || adminState.events[0];
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

async function loadAdminReservations() {
  const data = await adminGet('/api/admin/reservations', {
    search: adminEl.resSearch.value.trim(),
    limit: 25,
  });
  adminState.reservations = Array.isArray(data.items) ? data.items : [];
  renderAdminReservations();
}

async function loadAdminEvents() {
  const data = await adminGet('/api/admin/events');
  adminState.events = Array.isArray(data.items) ? data.items : [];
  renderAdminEvents();
}

async function refreshAdminAll() {
  await Promise.all([loadAdminGuests(), loadAdminReservations(), loadAdminEvents()]);
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
  const reservationCode = adminEl.reservationSelect.value;
  const gender = adminEl.guestGender.value;
  const fullName = adminEl.guestName.value.trim();
  if (!reservationCode) {
    setAdminStatus('Choose reservation first.', true);
    return;
  }
  if (fullName.split(' ').length < 2) {
    setAdminStatus('Name must be in format Name Surname.', true);
    return;
  }
  try {
    const res = await adminPost('/api/admin/guest/add', {
      reservation_code: reservationCode,
      gender,
      full_name: fullName,
    });
    adminEl.guestName.value = '';
    setAdminStatus(res.message || 'Guest added.');
    await Promise.all([loadAdminGuests(), loadAdminReservations()]);
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Failed to add guest.'), true);
  }
}

async function saveAdminEvent() {
  const eventId = Number(adminEl.eventSelect.value || 0);
  if (!eventId) {
    setAdminStatus('Select event first.', true);
    return;
  }

  const updates = {
    title: adminEl.title.value.trim(),
    datetime: adminEl.datetime.value.trim(),
    location: adminEl.location.value.trim(),
    caption: adminEl.caption.value.trim(),
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

  try {
    const res = await adminPost('/api/admin/event/update', {
      event_id: eventId,
      updates,
    });
    setAdminStatus(res.message || 'Event updated.');
    await loadAdminEvents();
  } catch (err) {
    setAdminStatus(apiErrorText(err, 'Failed to update event.'), true);
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
if (adminEl.resRefresh) {
  adminEl.resRefresh.addEventListener('click', async () => {
    try {
      await loadAdminReservations();
      setAdminStatus('Reservations refreshed.');
    } catch (err) {
      setAdminStatus(apiErrorText(err, 'Failed to load reservations.'), true);
    }
  });
}
if (adminEl.guestAdd) {
  adminEl.guestAdd.addEventListener('click', addAdminGuest);
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
    adminState.selectedEventId = eventId;
    const event = adminState.events.find((item) => item.id === eventId);
    fillAdminEventForm(event || null);
  });
}
if (adminEl.eventSave) {
  adminEl.eventSave.addEventListener('click', saveAdminEvent);
}

initTelegram();
rebuildAttendees();
fetchEvents();
if (autoOpenAdmin && adminEl.open) {
  openAdminMode().catch((err) => {
    setAdminStatus(apiErrorText(err, 'Admin access denied.'), true);
  });
}
