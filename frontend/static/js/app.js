// ═══════════════════════════════════════════════════════════
// OrderBot — app.js
// All 6 Input Roles integrated:
//   5.2 Context (External Knowledge) — pre-fetch indicator
//   5.3 Memory (short/long/episodic) — sidebar panels
//   5.5 Environment/Runtime Context  — live env grid
//   5.6 System Instructions/Policies — guardrail indicator
//   5.5 Interaction State            — state bar / slot filling
//   A2A Agent-to-Agent Messages      — handoff log
// ═══════════════════════════════════════════════════════════

// ─── State ────────────────────────────────────────────────
const SESSION_ID = 'sess_' + Math.random().toString(36).slice(2, 10);
let conversationHistory = [];
let isWaiting = false;
let userLocation = null;
let selectedRestaurant = null;
let selectedHotel = null;

// ─── DOM refs ─────────────────────────────────────────────
const chatMessages       = document.getElementById('chatMessages');
const userInput          = document.getElementById('userInput');
const sendBtn            = document.getElementById('sendBtn');
const clearBtn           = document.getElementById('clearBtn');
const menuBtn            = document.getElementById('menuBtn');
const orderContainer     = document.getElementById('orderCardContainer');
const orderCardBody      = document.getElementById('orderCardBody');
const closeCard          = document.getElementById('closeCard');
const sidebar            = document.getElementById('sidebar');
const getLocationBtn     = document.getElementById('getLocationBtn');
const locIconBtn         = document.getElementById('locIconBtn');
const locationDisplay    = document.getElementById('locationDisplay');
const mapPanel           = document.getElementById('mapPanel');
const mapIframe          = document.getElementById('mapIframe');
const closeMap           = document.getElementById('closeMap');
const historyBtn         = document.getElementById('historyBtn');
const historyPanel       = document.getElementById('historyPanel');
const historyBody        = document.getElementById('historyBody');
const closeHistory       = document.getElementById('closeHistory');

// Input role DOM refs
const envTime            = document.getElementById('envTime');
const envZone            = document.getElementById('envZone');
const envDevice          = document.getElementById('envDevice');
const envSession         = document.getElementById('envSession');
const memoryToggle       = document.getElementById('memoryToggle');
const memoryBody         = document.getElementById('memoryBody');
const stateBar           = document.getElementById('stateBar');
const stateSlots         = document.getElementById('stateSlots');
const stateClose         = document.getElementById('stateClose');
const guardrailIndicator = document.getElementById('guardrailIndicator');
const contextBar         = document.getElementById('contextBar');
const contextText        = document.getElementById('contextText');
const contextClose       = document.getElementById('contextClose');
const agentLog           = document.getElementById('agentLog');
const agentLogBody       = document.getElementById('agentLogBody');
const agentLogClose      = document.getElementById('agentLogClose');

// ═══════════════════════════════════════════════════════════
// 5.5 ENVIRONMENT / RUNTIME CONTEXT — auto-detect + send
// ═══════════════════════════════════════════════════════════

function detectAndSendEnv() {
  const tz     = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata';
  const locale = navigator.language || 'en-IN';
  const device = /Mobi|Android/i.test(navigator.userAgent) ? 'mobile' : 'desktop';

  const env = { session_id: SESSION_ID, timezone: tz, locale, device, platform: 'web' };

  updateEnvGrid(tz, device);

  fetch('/api/env', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(env)
  }).catch(() => {});
}

function updateEnvGrid(tz, device) {
  const now = new Date();
  const timeStr = now.toLocaleTimeString('en-US', {
    hour: '2-digit', minute: '2-digit',
    timeZone: tz, hour12: false
  });
  envTime.textContent    = timeStr;
  envZone.textContent    = tz.split('/').pop().replace('_', ' ');
  envDevice.textContent  = device || 'web';
  envSession.textContent = SESSION_ID.slice(5, 11);
}

function startEnvClock() {
  const tz     = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata';
  const device = /Mobi|Android/i.test(navigator.userAgent) ? 'mobile' : 'desktop';
  setInterval(() => updateEnvGrid(tz, device), 30000);
}

// ═══════════════════════════════════════════════════════════
// 5.3 MEMORY — fetch and render sidebar panels
// ═══════════════════════════════════════════════════════════

async function fetchAndRenderMemory() {
  try {
    const res = await fetch(`/api/memory/${SESSION_ID}`);
    if (!res.ok) return;
    const data = await res.json();
    renderShortTermMemory(data.short_term || []);
    renderLongTermMemory(data.long_term_preferences || {});
    renderEpisodicMemory(data.episodic || []);
  } catch (e) {}
}

function renderShortTermMemory(turns) {
  const el = document.getElementById('memShort');
  if (!turns.length) {
    el.innerHTML = '<p class="mem-empty">No messages yet</p>';
    return;
  }
  el.innerHTML = turns.slice(-8).map(t => `
    <div class="mem-entry">
      <span class="mem-role ${t.role}">${t.role}</span>
      <div>${escapeHtml(t.content.slice(0, 60))}${t.content.length > 60 ? '…' : ''}</div>
    </div>`).join('');
}

function renderLongTermMemory(prefs) {
  const el = document.getElementById('memLong');
  const entries = Object.entries(prefs);
  if (!entries.length) {
    el.innerHTML = '<p class="mem-empty">No preferences stored</p>';
    return;
  }
  el.innerHTML = entries.map(([k, v]) => `
    <div class="mem-pref">
      <span class="mem-pref-key">${escapeHtml(k)}</span>
      <span class="mem-pref-val">${escapeHtml(String(Array.isArray(v) ? v.join(', ') : v).slice(0, 20))}</span>
    </div>`).join('');
}

function renderEpisodicMemory(episodes) {
  const el = document.getElementById('memEpisodic');
  if (!episodes.length) {
    el.innerHTML = '<p class="mem-empty">No task history yet</p>';
    return;
  }
  el.innerHTML = episodes.slice(-5).map(ep => `
    <div class="mem-episode">
      <span class="ep-agent">[${ep.agent}]</span>
      <div>${escapeHtml((ep.task || '').slice(0, 50))}${(ep.task || '').length > 50 ? '…' : ''}</div>
      <span class="ep-outcome">→ ${ep.outcome}</span>
    </div>`).join('');
}

document.querySelectorAll('.mem-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.mem-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const target = tab.dataset.tab;
    document.getElementById('memShort').classList.toggle('hidden', target !== 'short');
    document.getElementById('memLong').classList.toggle('hidden', target !== 'long');
    document.getElementById('memEpisodic').classList.toggle('hidden', target !== 'episodic');
  });
});

memoryToggle.addEventListener('click', () => {
  memoryBody.classList.toggle('collapsed');
  memoryToggle.classList.toggle('collapsed');
});

// ═══════════════════════════════════════════════════════════
// 5.6 GUARDRAIL INDICATOR
// ═══════════════════════════════════════════════════════════

function setGuardrailViolated(violated) {
  if (violated) {
    guardrailIndicator.classList.add('violated');
    guardrailIndicator.querySelector('.guardrail-label').textContent = 'Blocked';
    setTimeout(() => {
      guardrailIndicator.classList.remove('violated');
      guardrailIndicator.querySelector('.guardrail-label').textContent = 'Policies Active';
    }, 4000);
  }
}

// ═══════════════════════════════════════════════════════════
// 5.5 INTERACTION STATE BAR (Dialogue Control / Slot Filling)
// ═══════════════════════════════════════════════════════════

const WORKFLOW_SLOTS = {
  hotel_booking: [
    { key: 'hotel',    label: 'Hotel' },
    { key: 'room',     label: 'Room' },
    { key: 'check_in', label: 'Check-in' },
    { key: 'check_out',label: 'Check-out' },
    { key: 'guests',   label: 'Guests' },
  ],
  food_delivery: [
    { key: 'restaurant', label: 'Restaurant' },
    { key: 'items',      label: 'Items' },
  ],
  order_booking: [
    { key: 'items',  label: 'Items' },
    { key: 'total',  label: 'Total' },
  ],
};

let currentSlotState = {};

function updateStateBar(agentUsed, replyText) {
  const slots = WORKFLOW_SLOTS[agentUsed];
  if (!slots) { stateBar.style.display = 'none'; return; }

  if (agentUsed === 'hotel_booking') {
    if (selectedHotel) currentSlotState.hotel = selectedHotel.name;
    if (/standard|deluxe|suite|executive/i.test(replyText)) {
      const m = replyText.match(/\b(standard|deluxe|suite|executive)\b/i);
      if (m) currentSlotState.room = m[1];
    }
    if (/check.in/i.test(replyText)) {
      const m = replyText.match(/Check-in[:\s]+([^\n<br>]+)/i);
      if (m) currentSlotState.check_in = m[1].trim().slice(0,10);
    }
    if (/check.out/i.test(replyText)) {
      const m = replyText.match(/Check-out[:\s]+([^\n<br>]+)/i);
      if (m) currentSlotState.check_out = m[1].trim().slice(0,10);
    }
    if (/guests?[:\s]+(\d+)/i.test(replyText)) {
      currentSlotState.guests = replyText.match(/guests?[:\s]+(\d+)/i)[1];
    }
  }

  if (agentUsed === 'food_delivery') {
    if (selectedRestaurant) currentSlotState.restaurant = selectedRestaurant.name;
    if (/order confirmed/i.test(replyText)) currentSlotState.items = '✓';
  }

  if (agentUsed === 'order_booking') {
    if (/total[:\s]+₹([\d.]+)/i.test(replyText)) {
      currentSlotState.total = '₹' + replyText.match(/total[:\s]+₹([\d.]+)/i)[1];
    }
    if (/items?[:\s]+([^\n]+)/i.test(replyText)) {
      currentSlotState.items = '✓';
    }
  }

  stateSlots.innerHTML = slots.map(s => {
    const val = currentSlotState[s.key];
    const cls = val ? 'filled' : 'waiting';
    return `
      <div class="state-slot ${cls}">
        <span class="slot-key">${s.label}</span>
        <span class="slot-val ${cls}">${val || '?'}</span>
      </div>`;
  }).join('');

  stateBar.style.display = 'block';
}

stateClose.addEventListener('click', () => {
  stateBar.style.display = 'none';
  currentSlotState = {};
});

// ═══════════════════════════════════════════════════════════
// A2A AGENT-TO-AGENT HANDOFF LOG
// ═══════════════════════════════════════════════════════════

let lastAgent = null;

function logAgentHop(fromAgent, toAgent, hopType = 'route') {
  if (!fromAgent || fromAgent === toAgent) return;

  agentLog.style.display = 'block';
  const now = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });

  const hop = document.createElement('div');
  hop.className = 'agent-hop';
  hop.innerHTML = `
    <span class="agent-hop-from">${fromAgent}</span>
    <span class="agent-hop-arrow">→</span>
    <span class="agent-hop-to">${toAgent}</span>
    <span class="agent-hop-type">${hopType}</span>
    <span class="agent-hop-time">${now}</span>`;

  agentLogBody.appendChild(hop);
  agentLogBody.scrollTop = agentLogBody.scrollHeight;

  const hops = agentLogBody.querySelectorAll('.agent-hop');
  if (hops.length > 10) hops[0].remove();
}

agentLogClose.addEventListener('click', () => { agentLog.style.display = 'none'; });

// ═══════════════════════════════════════════════════════════
// 5.2 CONTEXT PRE-FETCH INDICATOR
// ═══════════════════════════════════════════════════════════

const CONTEXT_KEYWORDS = [
  'cancel', 'status', 'order', 'last order', 'track',
  'hotel', 'booking', 'history', 'my order', 'recent'
];

function maybeShowContextBar(message) {
  const lower = message.toLowerCase();
  const matched = CONTEXT_KEYWORDS.find(kw => lower.includes(kw));
  if (matched) {
    contextText.textContent = `Fetching context: ${matched} records from DB...`;
    contextBar.style.display = 'flex';
    setTimeout(() => { contextBar.style.display = 'none'; }, 3000);
  }
}

contextClose.addEventListener('click', () => { contextBar.style.display = 'none'; });

// ═══════════════════════════════════════════════════════════
// LOCATION
// ═══════════════════════════════════════════════════════════

function requestLocation() {
  if (!navigator.geolocation) {
    addBotMessage("⚠️ Your browser doesn't support GPS. Try Chrome or Firefox.", "error");
    return;
  }
  getLocationBtn.disabled = true;
  getLocationBtn.textContent = "Getting location...";
  locIconBtn.textContent = "⏳";

  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;
      try {
        const resp = await fetch(`/api/location?lat=${lat}&lng=${lng}&session_id=${SESSION_ID}`, {
          method: 'POST'
        });
        const data = await resp.json();
        userLocation = { lat, lng, address: data.address || `${lat.toFixed(4)}, ${lng.toFixed(4)}` };
        locationDisplay.innerHTML = `<span class="loc-text">📍 ${userLocation.address}</span>`;
        locationDisplay.classList.add('has-location');
        getLocationBtn.textContent = "Update Location";
        getLocationBtn.disabled = false;
        locIconBtn.textContent = "📍";
        locIconBtn.classList.add('active');
        addBotMessage(data.reply || `📍 Got your location!\n\nNow try:\n• "Find restaurants near me"\n• "Search hotels nearby"`, "location_agent");
        conversationHistory.push({ role: 'assistant', content: `Location set: ${userLocation.address}` });
      } catch (e) {
        userLocation = { lat, lng, address: `${lat.toFixed(4)}, ${lng.toFixed(4)}` };
        locationDisplay.innerHTML = `<span class="loc-text">📍 ${userLocation.address}</span>`;
        locationDisplay.classList.add('has-location');
        getLocationBtn.textContent = "Update Location";
        getLocationBtn.disabled = false;
        locIconBtn.classList.add('active');
        addBotMessage(`📍 Location captured!`, "location_agent");
      }
    },
    (err) => {
      getLocationBtn.disabled = false;
      getLocationBtn.textContent = "Share My Location";
      locIconBtn.textContent = "📍";
      const msgs = { 1: "Location access denied.", 2: "Location unavailable.", 3: "Location timed out." };
      addBotMessage(`⚠️ ${msgs[err.code] || "Couldn't get location."}`, "error");
    },
    { timeout: 10000, enableHighAccuracy: true }
  );
}

getLocationBtn.addEventListener('click', requestLocation);
locIconBtn.addEventListener('click', requestLocation);

// ═══════════════════════════════════════════════════════════
// QUICK BUTTONS
// ═══════════════════════════════════════════════════════════

document.querySelectorAll('.quick-btn[data-msg]').forEach(btn => {
  btn.addEventListener('click', () => {
    const msg = btn.getAttribute('data-msg');
    if (msg && !isWaiting) { userInput.value = msg; sendMessage(); }
  });
});

// ═══════════════════════════════════════════════════════════
// ORDER HISTORY
// ═══════════════════════════════════════════════════════════

historyBtn.addEventListener('click', async () => {
  if (historyPanel.style.display !== 'none') {
    historyPanel.style.display = 'none'; return;
  }
  historyBody.innerHTML = '<p style="color:var(--text-muted);font-size:12px;padding:4px">Loading...</p>';
  historyPanel.style.display = 'flex';
  try {
    const [ordersResp, bookingsResp] = await Promise.all([
      fetch('/api/orders'), fetch('/api/hotel-bookings')
    ]);
    renderHistoryPanel(await ordersResp.json(), await bookingsResp.json());
  } catch (e) {
    historyBody.innerHTML = '<p style="color:var(--danger);font-size:12px;padding:4px">Failed to load history.</p>';
  }
});

closeHistory.addEventListener('click', () => { historyPanel.style.display = 'none'; });

function renderHistoryPanel(orders, bookings = []) {
  let html = '';
  if (orders && orders.length > 0) {
    html += `<p class="history-section-label">🛍️ Orders</p>`;
    html += orders.map(o => {
      const statusClass = `history-status-${o.status}`;
      const items = o.items.map(i => `${i.product_name} ×${i.quantity}`).join(', ');
      const time = o.created_at.slice(0, 16).replace('T', ' ');
      const type = o.notes && o.notes.includes('Delivery from') ? '🍽️' : '🛍️';
      return `<div class="history-item">
        <div class="history-item-id">${type} ${o.order_id}</div>
        <div class="history-item-meta">
          <span class="${statusClass}">● ${o.status.toUpperCase()}</span><br>
          ${items}<br>₹${o.total_amount} · ${time}
        </div></div>`;
    }).join('');
  }
  if (bookings && bookings.length > 0) {
    html += `<p class="history-section-label">🏨 Hotel Bookings</p>`;
    html += bookings.map(b => {
      return `<div class="history-item">
        <div class="history-item-id">🏨 ${b.booking_id}</div>
        <div class="history-item-meta">
          <span class="history-status-${b.status}">● ${b.status.toUpperCase()}</span><br>
          ${b.hotel_name}<br>${b.check_in} → ${b.check_out}<br>
          ${b.total_nights} night(s) · ${b.guests} guest(s) · ${b.room_type}<br>
          ₹${b.estimated_price}
        </div></div>`;
    }).join('');
  }
  if (!html) html = '<p style="color:var(--text-muted);font-size:13px;padding:4px">No history yet.</p>';
  historyBody.innerHTML = html;
}

// ═══════════════════════════════════════════════════════════
// INPUT EVENTS
// ═══════════════════════════════════════════════════════════

userInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (!isWaiting) sendMessage(); }
});
userInput.addEventListener('input', () => {
  userInput.style.height = 'auto';
  userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
});
sendBtn.addEventListener('click', () => { if (!isWaiting) sendMessage(); });
clearBtn.addEventListener('click', clearChat);
closeCard.addEventListener('click', () => { orderContainer.style.display = 'none'; });
closeMap.addEventListener('click', () => { mapPanel.style.display = 'none'; });
menuBtn.addEventListener('click', () => sidebar.classList.toggle('open'));

// ═══════════════════════════════════════════════════════════
// SEND MESSAGE
// ═══════════════════════════════════════════════════════════

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text) return;

  addUserMessage(text);
  conversationHistory.push({ role: 'user', content: text });
  userInput.value = '';
  userInput.style.height = 'auto';

  maybeShowContextBar(text);

  const typingEl = showTyping();
  setWaiting(true);

  const env = {
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata',
    locale: navigator.language || 'en-IN',
    device: /Mobi|Android/i.test(navigator.userAgent) ? 'mobile' : 'desktop',
    platform: 'web',
  };

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        session_id: SESSION_ID,
        conversation_history: conversationHistory.slice(-12),
        location: userLocation,
        selected_restaurant: selectedRestaurant,
        selected_hotel: selectedHotel,
        environment: env,
      })
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${response.status}`);
    }

    const data = await response.json();
    typingEl.remove();
    contextBar.style.display = 'none';

    if (data.agent_used === 'guardrail') setGuardrailViolated(true);

    logAgentHop(lastAgent || 'user', data.agent_used, 'route');
    lastAgent = data.agent_used;

    addBotMessage(data.reply, data.agent_used, data.context_injected);
    updateStateBar(data.agent_used, data.reply);
    conversationHistory.push({ role: 'assistant', content: data.reply });

    if (data.restaurants && data.restaurants.length > 0) showRestaurantCards(data.restaurants);
    if (data.hotels && data.hotels.length > 0) showHotelCards(data.hotels);
    if (data.map_embed_url) {
      mapIframe.src = data.map_embed_url;
      mapPanel.style.display = 'block';
    }

    // ── Card rendering — order matters, check both, show correct one ──────
    if (data.order) showOrderCard(data.order);
    if (data.hotel_booking) showHotelBookingCard(data.hotel_booking);

    if (data.orders_list || data.hotel_bookings_list) {
      renderHistoryPanel(data.orders_list || [], data.hotel_bookings_list || []);
      historyPanel.style.display = 'flex';
    }

    fetchAndRenderMemory();

  } catch (err) {
    typingEl.remove();
    contextBar.style.display = 'none';
    addBotMessage(`⚠️ Error: **${err.message}**`, 'error');
  } finally {
    setWaiting(false);
  }
}

// ═══════════════════════════════════════════════════════════
// RENDER HELPERS
// ═══════════════════════════════════════════════════════════

function addUserMessage(text) {
  const el = document.createElement('div');
  el.className = 'message user';
  el.innerHTML = `<div class="msg-avatar">👤</div><div class="msg-bubble">${escapeHtml(text)}</div>`;
  chatMessages.appendChild(el);
  scrollToBottom();
}

function addBotMessage(text, agentUsed = '', contextInjected = false) {
  const el = document.createElement('div');
  el.className = 'message bot';
  const badge = agentUsed && agentUsed !== 'greeting' && agentUsed !== 'error'
    ? `<div class="agent-badge">agent: ${agentUsed}</div>` : '';
  const ctxBadge = contextInjected
    ? `<span class="context-badge">⚡ context injected</span>` : '';
  el.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div>
      <div class="msg-bubble">${formatMarkdown(text)}</div>
      <div>${badge}${ctxBadge}</div>
    </div>`;
  chatMessages.appendChild(el);
  scrollToBottom();
}

function showRestaurantCards(restaurants) {
  const wrapper = document.createElement('div');
  wrapper.className = 'message bot';
  const container = document.createElement('div');
  container.className = 'result-cards';

  restaurants.forEach((r, i) => {
    const card = document.createElement('div');
    card.className = 'result-card';
    card.innerHTML = `
      <div class="rc-name">${escapeHtml(r.name)}</div>
      <div class="rc-meta">
        ${r.rating && r.rating !== 'N/A' ? `<span>⭐ ${r.rating}</span>` : ''}
        ${r.cuisine ? `<span>🍽️ ${escapeHtml(r.cuisine)}</span>` : ''}
        ${r.address ? `<span>📍 ${escapeHtml(r.address)}</span>` : ''}
        ${r.distance ? `<span class="rc-badge">${r.distance} · ${r.eta || ''}</span>` : ''}
      </div>
      <div class="rc-actions">
        <button class="rc-btn primary select-restaurant" data-index="${i}">🍽️ Order from here</button>
        ${r.directions_url ? `<a class="rc-btn" href="${r.directions_url}" target="_blank">🗺️ Directions</a>` : ''}
      </div>`;
    container.appendChild(card);
  });

  wrapper.appendChild(container);
  chatMessages.appendChild(wrapper);
  scrollToBottom();

  document.querySelectorAll('.select-restaurant').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const idx = parseInt(e.target.dataset.index);
      selectedRestaurant = restaurants[idx];
      currentSlotState = { restaurant: selectedRestaurant.name };
      document.querySelectorAll('.result-card').forEach(c => c.classList.remove('selected'));
      e.target.closest('.result-card').classList.add('selected');
      addBotMessage(`Great choice! 🍽️ You selected **${selectedRestaurant.name}**.\n\nWhat would you like to order? e.g. "1 Biryani and 2 Pepsi"`, 'food_delivery');
      conversationHistory.push({ role: 'assistant', content: `Restaurant selected: ${selectedRestaurant.name}` });
      updateStateBar('food_delivery', '');
    });
  });
}

function showHotelCards(hotels) {
  const wrapper = document.createElement('div');
  wrapper.className = 'message bot';
  const container = document.createElement('div');
  container.className = 'result-cards';

  hotels.forEach((h, i) => {
    const card = document.createElement('div');
    card.className = 'result-card';
    const metaParts = [];
    if (h.rating && h.rating !== 'N/A') metaParts.push(`⭐ ${h.rating}`);
    if (h.price_level && h.price_level !== 'N/A') metaParts.push(`💰 ${h.price_level}`);
    if (h.type) metaParts.push(`🏨 ${h.type}`);
    if (h.address) metaParts.push(`📍 ${h.address}`);
    if (h.phone) metaParts.push(`📞 ${h.phone}`);
    card.innerHTML = `
      <div class="rc-name">${escapeHtml(h.name)}</div>
      <div class="rc-meta">${metaParts.map(p => `<span>${escapeHtml(p)}</span>`).join('')}</div>
      <div class="rc-actions">
        <button class="rc-btn primary select-hotel" data-index="${i}">🏨 Book a Room</button>
        ${h.directions_url ? `<a class="rc-btn" href="${h.directions_url}" target="_blank">🗺️ Directions</a>` : ''}
        ${h.google_search_url ? `<a class="rc-btn" href="${h.google_search_url}" target="_blank">🔍 Google</a>` : ''}
        ${h.website ? `<a class="rc-btn" href="${h.website}" target="_blank">🌐 Website</a>` : ''}
      </div>`;
    container.appendChild(card);
  });

  wrapper.appendChild(container);
  chatMessages.appendChild(wrapper);
  scrollToBottom();

  document.querySelectorAll('.select-hotel').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const idx = parseInt(e.target.dataset.index);
      selectedHotel = hotels[idx];
      currentSlotState = { hotel: selectedHotel.name };
      document.querySelectorAll('.result-card').forEach(c => c.classList.remove('selected'));
      e.target.closest('.result-card').classList.add('selected');
      addBotMessage(
        `Great! 🏨 You selected **${selectedHotel.name}**.\n\nTo book a room, tell me:\n• Check-in date\n• Check-out date (or number of nights)\n• Number of guests\n• Room type (Standard / Deluxe / Suite)\n\ne.g. "Book a Standard room for 2 nights from tomorrow for 2 guests"`,
        'hotel_booking'
      );
      conversationHistory.push({ role: 'assistant', content: `Hotel selected: ${selectedHotel.name}` });
      updateStateBar('hotel_booking', '');
    });
  });
}

function showOrderCard(order) {
  // Always reset header to food/product order title
  orderContainer.querySelector('.order-card-header span').textContent = '✅ Order Confirmed';

  const items = order.items.map(i =>
    `  ${i.product_name} × ${i.quantity}    ₹${i.total_price.toFixed(2)}`
  ).join('\n');
  const extra = order.restaurant ? `
    <div><strong>Restaurant:</strong> ${order.restaurant}</div>
    <div><strong>Delivery to:</strong> ${order.delivery_address || 'Your location'}</div>
    <div><strong>ETA:</strong> ${order.eta || '30-45 mins'}</div>
    <div><strong>Distance:</strong> ${order.distance || 'N/A'}</div>` : '';
  orderCardBody.innerHTML = `
    <div><strong>Order ID:</strong> ${order.order_id}</div>
    <div><strong>Status:</strong> ${order.status}</div>
    ${extra}
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.07);margin:8px 0">
    <pre style="white-space:pre-wrap;font-size:11px">${items}</pre>
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.07);margin:8px 0">
    <div><strong>Total:</strong> ₹${(order.grand_total || order.total_amount).toFixed(2)}</div>
    <div style="margin-top:5px;font-size:10px;opacity:0.5">${order.created_at.slice(0,16).replace('T',' ')}</div>`;
  orderContainer.style.display = 'block';
  orderContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  stateBar.style.display = 'none';
  currentSlotState = {};
}

function showHotelBookingCard(booking) {
  // Always reset header to hotel booking title first
  orderContainer.querySelector('.order-card-header span').textContent = '🏨 Room Booked';

  orderCardBody.innerHTML = `
    <div><strong>Booking ID:</strong> ${booking.booking_id}</div>
    <div><strong>Hotel:</strong> ${booking.hotel_name}</div>
    ${booking.hotel_address ? `<div><strong>Address:</strong> ${booking.hotel_address}</div>` : ''}
    <div><strong>Status:</strong> ${booking.status}</div>
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.07);margin:8px 0">
    <div><strong>Room Type:</strong> ${booking.room_type}</div>
    <div><strong>Check-in:</strong> ${booking.check_in}</div>
    <div><strong>Check-out:</strong> ${booking.check_out}</div>
    <div><strong>Nights:</strong> ${booking.total_nights}</div>
    <div><strong>Guests:</strong> ${booking.guests}</div>
    <div><strong>Rooms:</strong> ${booking.rooms}</div>
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.07);margin:8px 0">
    <div><strong>Est. Total:</strong> ₹${booking.estimated_price}</div>
    <div style="margin-top:5px;font-size:10px;opacity:0.6;color:#facc15">
      ⚠️ Contact the hotel to confirm actual availability.
    </div>
    <div style="margin-top:4px;font-size:10px;opacity:0.4">${booking.created_at.slice(0,16).replace('T',' ')}</div>`;
  orderContainer.style.display = 'block';
  orderContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  stateBar.style.display = 'none';
  currentSlotState = {};
}

// ═══════════════════════════════════════════════════════════
// UTILS
// ═══════════════════════════════════════════════════════════

function clearChat() {
  chatMessages.innerHTML = '';
  conversationHistory = [];
  selectedRestaurant = null;
  selectedHotel = null;
  lastAgent = null;
  currentSlotState = {};
  orderContainer.style.display = 'none';
  mapPanel.style.display = 'none';
  historyPanel.style.display = 'none';
  stateBar.style.display = 'none';
  agentLog.style.display = 'none';
  agentLogBody.innerHTML = '';
  orderContainer.querySelector('.order-card-header span').textContent = '✅ Order Confirmed';
  addBotMessage("Chat cleared! How can I help you? 😊", "greeting");
  fetchAndRenderMemory();
}

function showTyping() {
  const el = document.createElement('div');
  el.className = 'message bot';
  el.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div class="msg-bubble typing-indicator">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>`;
  chatMessages.appendChild(el);
  scrollToBottom();
  return el;
}

function scrollToBottom() {
  requestAnimationFrame(() => { chatMessages.scrollTop = chatMessages.scrollHeight; });
}

function setWaiting(val) {
  isWaiting = val;
  sendBtn.disabled = val;
  userInput.disabled = val;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function formatMarkdown(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" class="rc-btn" style="display:inline-block;margin:4px 4px 4px 0">$1</a>')
    .replace(/^[•\-] (.+)$/gm, '<li>$1</li>')
    .replace(/\n/g, '<br>');
}


// ═══════════════════════════════════════════════════════════
// LOGOUT + USERNAME DISPLAY
// ═══════════════════════════════════════════════════════════

async function fetchAndShowUsername() {
  try {
    const res = await fetch('/auth/me');
    if (!res.ok) return;
    const data = await res.json();
    if (data.username) {
      document.getElementById('usernameDisplay').textContent = data.username;
      document.getElementById('userChip').style.display = 'flex';
    }
  } catch (e) {}
}

async function handleLogout() {
  const btn = document.getElementById('logoutBtn');
  btn.textContent = '⏻ Logging out...';
  btn.style.pointerEvents = 'none';
  try {
    await fetch('/auth/logout', { method: 'POST' });
  } catch (e) {}
  window.location.href = '/login';
}

document.getElementById('logoutBtn').addEventListener('click', handleLogout);

// ═══════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════

window.addEventListener('DOMContentLoaded', () => {
  detectAndSendEnv();
  startEnvClock();
  fetchAndRenderMemory();
  fetchAndShowUsername();

  addBotMessage(
    "👋 Hey! I'm **OrderBot** — your smart assistant.\n\nI can help you:\n• 🛍️ Browse & order products\n• 🍽️ Find nearby restaurants & order food\n• 🏨 Search & book hotel rooms\n• 📦 Track or cancel orders\n• 🧾 View order history\n\nTip: Click **📍** to share your location!",
    "greeting"
  );
});