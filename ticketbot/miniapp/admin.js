const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
if (tg) {
  tg.ready();
  tg.expand();
}

const qs = new URLSearchParams(window.location.search);
const fallbackTgId = Number(qs.get('tg_id') || 0);
const tgId = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id) || fallbackTgId || null;

const el = {
  ident: document.getElementById('admin-ident'),
  status: document.getElementById('status'),
  guestsSearch: document.getElementById('guests-search'),
  guestsSort: document.getElementById('guests-sort'),
  guestsRefresh: document.getElementById('guests-refresh'),
  guestsList: document.getElementById('guests-list'),
  resSearch: document.getElementById('res-search'),
  resRefresh: document.getElementById('res-refresh'),
  reservationSelect: document.getElementById('reservation-select'),
  guestGender: document.getElementById('guest-gender'),
  guestName: document.getElementById('guest-name'),
  guestAdd: document.getElementById('guest-add'),
  eventsRefresh: document.getElementById('events-refresh'),
  eventSelect: document.getElementById('event-select'),
  eventSave: document.getElementById('event-save'),
  title: document.getElementById('ev-title'),
  datetime: document.getElementById('ev-datetime'),
  location: document.getElementById('ev-location'),
  caption: document.getElementById('ev-caption'),
  ebBoy: document.getElementById('ev-eb-boy'),
  ebGirl: document.getElementById('ev-eb-girl'),
  ebQty: document.getElementById('ev-eb-qty'),
  t1Boy: document.getElementById('ev-t1-boy'),
  t1Girl: document.getElementById('ev-t1-girl'),
  t1Qty: document.getElementById('ev-t1-qty'),
  t2Boy: document.getElementById('ev-t2-boy'),
  t2Girl: document.getElementById('ev-t2-girl'),
  t2Qty: document.getElementById('ev-t2-qty'),
};

const state = {
  guestsSort: 'newest',
  guestsSearch: '',
  guests: [],
  reservations: [],
  events: [],
  selectedEventId: null,
};

function setStatus(msg, isError = false) {
  el.status.textContent = msg || '';
  el.status.className = isError ? 'status error' : 'status';
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function detailMessage(err, fallback) {
  if (!err) return fallback;
  if (typeof err === 'string') return err;
  if (err.detail) return err.detail;
  if (err.message) return err.message;
  return fallback;
}

async function apiGet(path, params = {}) {
  const url = new URL(path, window.location.origin);
  if (tgId) url.searchParams.set('tg_id', String(tgId));
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && String(v).trim() !== '') url.searchParams.set(k, String(v));
  });
  const res = await fetch(url.toString(), { cache: 'no-store' });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw data;
  return data;
}

async function apiPost(path, body = {}) {
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

function fillEventForm(event) {
  if (!event) return;
  el.title.value = event.title || '';
  el.datetime.value = event.event_datetime || '';
  el.location.value = event.location || '';
  el.caption.value = event.caption || '';
  const p = event.prices || {};
  el.ebBoy.value = p.early_boy ?? 0;
  el.ebGirl.value = p.early_girl ?? 0;
  el.ebQty.value = p.early_qty ?? 0;
  el.t1Boy.value = p.tier1_boy ?? 0;
  el.t1Girl.value = p.tier1_girl ?? 0;
  el.t1Qty.value = p.tier1_qty ?? 0;
  el.t2Boy.value = p.tier2_boy ?? 0;
  el.t2Girl.value = p.tier2_girl ?? 0;
  el.t2Qty.value = p.tier2_qty ?? 0;
}

function renderGuests() {
  el.guestsList.innerHTML = '';
  if (!state.guests.length) {
    el.guestsList.innerHTML = '<p class="hint">No guests found.</p>';
    return;
  }
  for (const g of state.guests) {
    const safeFullName = escapeHtml(g.full_name);
    const safeGender = escapeHtml(g.gender);
    const safeEventTitle = escapeHtml(g.event_title);
    const safeEventDatetime = escapeHtml(g.event_datetime);
    const safeCode = escapeHtml(g.reservation_code);
    const safeStatus = escapeHtml(g.reservation_status);
    const safeBuyerName = escapeHtml(g.buyer_name);
    const safeBuyerSurname = escapeHtml(g.buyer_surname);
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <h3>#${g.attendee_id} ${safeFullName} <small>[${safeGender}]</small></h3>
      <div class="meta">${safeEventTitle} (${safeEventDatetime})</div>
      <div class="meta">${safeCode} | ${safeStatus} | Buyer: ${safeBuyerName} ${safeBuyerSurname}</div>
      <label>Full Name<input data-act="full-name" type="text" placeholder="Name Surname"></label>
      <div class="actions">
        <button data-act="rename" data-id="${g.attendee_id}">Rename</button>
        <button data-act="remove" data-id="${g.attendee_id}">Remove</button>
      </div>
    `;
    const renameInput = card.querySelector('[data-act="full-name"]');
    if (renameInput) renameInput.value = g.full_name || '';
    const renameBtn = card.querySelector('[data-act="rename"]');
    const removeBtn = card.querySelector('[data-act="remove"]');
    if (!renameBtn || !removeBtn) {
      el.guestsList.appendChild(card);
      continue;
    }
    renameBtn.addEventListener('click', async () => {
      const nextName = (renameInput?.value || '').trim();
      if (!nextName || nextName.split(' ').length < 2) {
        setStatus('Name must be in format Name Surname.', true);
        return;
      }
      try {
        const res = await apiPost('/api/admin/guest/rename', { attendee_id: g.attendee_id, full_name: nextName.trim() });
        setStatus(res.message || 'Guest renamed.');
        await loadGuests();
      } catch (err) {
        setStatus(detailMessage(err, 'Failed to rename guest.'), true);
      }
    });
    removeBtn.addEventListener('click', async () => {
      try {
        const res = await apiPost('/api/admin/guest/remove', { attendee_id: g.attendee_id });
        setStatus(res.message || 'Guest removed.');
        await Promise.all([loadGuests(), loadEvents()]);
      } catch (err) {
        setStatus(detailMessage(err, 'Failed to remove guest.'), true);
      }
    });
    el.guestsList.appendChild(card);
  }
}

function renderReservations() {
  el.reservationSelect.innerHTML = '';
  if (!state.reservations.length) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'No active reservations found';
    el.reservationSelect.appendChild(opt);
    return;
  }
  for (const r of state.reservations) {
    const opt = document.createElement('option');
    opt.value = r.reservation_code;
    opt.textContent = `${r.reservation_code} | ${r.event_title} | ${r.buyer_name} ${r.buyer_surname}`;
    el.reservationSelect.appendChild(opt);
  }
}

function renderEvents() {
  const prev = state.selectedEventId;
  el.eventSelect.innerHTML = '';
  for (const event of state.events) {
    const opt = document.createElement('option');
    opt.value = String(event.id);
    opt.textContent = `#${event.id} ${event.title} (${event.event_datetime})`;
    el.eventSelect.appendChild(opt);
  }
  if (!state.events.length) {
    fillEventForm(null);
    return;
  }
  const picked = state.events.find((e) => e.id === prev) || state.events[0];
  state.selectedEventId = picked.id;
  el.eventSelect.value = String(picked.id);
  fillEventForm(picked);
}

async function loadGuests() {
  const data = await apiGet('/api/admin/guests', {
    sort_by: state.guestsSort,
    search: state.guestsSearch,
    limit: 40,
  });
  state.guests = Array.isArray(data.items) ? data.items : [];
  renderGuests();
}

async function loadReservations() {
  const data = await apiGet('/api/admin/reservations', {
    search: el.resSearch.value.trim(),
    limit: 25,
  });
  state.reservations = Array.isArray(data.items) ? data.items : [];
  renderReservations();
}

async function loadEvents() {
  const data = await apiGet('/api/admin/events');
  state.events = Array.isArray(data.items) ? data.items : [];
  renderEvents();
}

async function saveEvent() {
  const eventId = Number(el.eventSelect.value || 0);
  if (!eventId) {
    setStatus('Select event first.', true);
    return;
  }
  const updates = {
    title: el.title.value.trim(),
    datetime: el.datetime.value.trim(),
    location: el.location.value.trim(),
    caption: el.caption.value.trim(),
    early_boy: el.ebBoy.value,
    early_girl: el.ebGirl.value,
    early_qty: el.ebQty.value,
    tier1_boy: el.t1Boy.value,
    tier1_girl: el.t1Girl.value,
    tier1_qty: el.t1Qty.value,
    tier2_boy: el.t2Boy.value,
    tier2_girl: el.t2Girl.value,
    tier2_qty: el.t2Qty.value,
  };
  try {
    const res = await apiPost('/api/admin/event/update', { event_id: eventId, updates });
    setStatus(res.message || 'Event updated.');
    await loadEvents();
  } catch (err) {
    setStatus(detailMessage(err, 'Failed to update event.'), true);
  }
}

async function addGuest() {
  const reservationCode = el.reservationSelect.value;
  const gender = el.guestGender.value;
  const fullName = el.guestName.value.trim();
  if (!reservationCode) {
    setStatus('Choose reservation first.', true);
    return;
  }
  if (!fullName || fullName.split(' ').length < 2) {
    setStatus('Name must be in format Name Surname.', true);
    return;
  }
  try {
    const res = await apiPost('/api/admin/guest/add', {
      reservation_code: reservationCode,
      gender,
      full_name: fullName,
    });
    setStatus(res.message || 'Guest added.');
    el.guestName.value = '';
    await loadGuests();
    await loadReservations();
  } catch (err) {
    setStatus(detailMessage(err, 'Failed to add guest.'), true);
  }
}

async function bootstrap() {
  if (!tgId) {
    setStatus('Cannot detect Telegram user. Open this page from Telegram.', true);
    return;
  }
  el.ident.textContent = `Telegram ID: ${tgId}`;
  try {
    await apiGet('/api/admin/bootstrap');
    setStatus('Admin session ready.');
    await Promise.all([loadGuests(), loadReservations(), loadEvents()]);
  } catch (err) {
    setStatus(detailMessage(err, 'Admin access denied.'), true);
  }
}

el.guestsRefresh.addEventListener('click', async () => {
  try {
    await loadGuests();
    setStatus('Guests refreshed.');
  } catch (err) {
    setStatus(detailMessage(err, 'Failed to load guests.'), true);
  }
});

el.guestsSort.addEventListener('change', async () => {
  state.guestsSort = el.guestsSort.value;
  try {
    await loadGuests();
  } catch (err) {
    setStatus(detailMessage(err, 'Failed to sort guests.'), true);
  }
});

el.guestsSearch.addEventListener('change', async () => {
  state.guestsSearch = el.guestsSearch.value.trim();
  try {
    await loadGuests();
  } catch (err) {
    setStatus(detailMessage(err, 'Failed to search guests.'), true);
  }
});

el.resRefresh.addEventListener('click', async () => {
  try {
    await loadReservations();
    setStatus('Reservations loaded.');
  } catch (err) {
    setStatus(detailMessage(err, 'Failed to load reservations.'), true);
  }
});

el.guestAdd.addEventListener('click', addGuest);
el.eventsRefresh.addEventListener('click', async () => {
  try {
    await loadEvents();
    setStatus('Events loaded.');
  } catch (err) {
    setStatus(detailMessage(err, 'Failed to load events.'), true);
  }
});

el.eventSelect.addEventListener('change', () => {
  const eventId = Number(el.eventSelect.value || 0);
  state.selectedEventId = eventId;
  const event = state.events.find((e) => e.id === eventId);
  fillEventForm(event || null);
});

el.eventSave.addEventListener('click', saveEvent);

bootstrap();
