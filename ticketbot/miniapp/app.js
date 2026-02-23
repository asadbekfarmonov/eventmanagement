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

const state = {
  events: [],
  selectedEventId: null,
  selectedEvent: null,
  boys: 0,
  girls: 0,
};

function money(value) {
  return Number(value || 0).toFixed(2);
}

function setStatus(msg, isError = false) {
  statusEl.textContent = msg || '';
  statusEl.className = isError ? 'hint error' : 'hint';
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
  state.selectedEvent = selectedEvent();

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
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
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
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  if (!tg) return;
  tg.ready();
  tg.expand();
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

initTelegram();
rebuildAttendees();
fetchEvents();
