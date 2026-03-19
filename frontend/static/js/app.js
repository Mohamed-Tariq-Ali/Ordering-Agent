// ─── State ────────────────────────────────────────────────
const SESSION_ID = 'sess_' + Math.random().toString(36).slice(2, 10);
let conversationHistory = [];
let isWaiting = false;
let userLocation = null;
let selectedRestaurant = null;

// ─── DOM refs ─────────────────────────────────────────────
const chatMessages    = document.getElementById('chatMessages');
const userInput       = document.getElementById('userInput');
const sendBtn         = document.getElementById('sendBtn');
const clearBtn        = document.getElementById('clearBtn');
const menuBtn         = document.getElementById('menuBtn');
const orderContainer  = document.getElementById('orderCardContainer');
const orderCardBody   = document.getElementById('orderCardBody');
const closeCard       = document.getElementById('closeCard');
const sidebar         = document.getElementById('sidebar');
const getLocationBtn  = document.getElementById('getLocationBtn');
const locIconBtn      = document.getElementById('locIconBtn');
const locationDisplay = document.getElementById('locationDisplay');
const mapPanel        = document.getElementById('mapPanel');
const mapIframe       = document.getElementById('mapIframe');
const closeMap        = document.getElementById('closeMap');
const historyBtn      = document.getElementById('historyBtn');
const historyPanel    = document.getElementById('historyPanel');
const historyBody     = document.getElementById('historyBody');
const closeHistory    = document.getElementById('closeHistory');

// ─── Init ─────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  addBotMessage(
    "👋 Hey! I'm **OrderBot** — your smart assistant.\n\nI can help you:\n• 🛍️ Browse & order products\n• 🍽️ Find nearby restaurants & order food\n• 🏨 Search hotels near you\n• 📦 Track or cancel orders\n• 🧾 View order history\n\nTip: Click **📍** to share your location!",
    "greeting"
  );
});

// ─── Location ─────────────────────────────────────────────
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
        addBotMessage(`📍 Location captured! You can now search restaurants and hotels nearby!`, "location_agent");
      }
    },
    (err) => {
      getLocationBtn.disabled = false;
      getLocationBtn.textContent = "Share My Location";
      locIconBtn.textContent = "📍";
      const msgs = {
        1: "Location access denied. Please allow location in browser settings.",
        2: "Location unavailable. Make sure GPS is on.",
        3: "Location timed out. Please try again."
      };
      addBotMessage(`⚠️ ${msgs[err.code] || "Couldn't get location."}`, "error");
    },
    { timeout: 10000, enableHighAccuracy: true }
  );
}

getLocationBtn.addEventListener('click', requestLocation);
locIconBtn.addEventListener('click', requestLocation);

// ─── Quick buttons (only ones with data-msg) ──────────────
document.querySelectorAll('.quick-btn[data-msg]').forEach(btn => {
  btn.addEventListener('click', () => {
    const msg = btn.getAttribute('data-msg');
    if (msg && !isWaiting) { userInput.value = msg; sendMessage(); }
  });
});

// ─── Order History ────────────────────────────────────────
historyBtn.addEventListener('click', async () => {
  if (historyPanel.style.display !== 'none') {
    historyPanel.style.display = 'none';
    return;
  }
  historyBody.innerHTML = '<p style="color:var(--text-muted);font-size:12px;padding:4px">Loading...</p>';
  historyPanel.style.display = 'flex';
  try {
    const resp = await fetch('/api/orders');
    const orders = await resp.json();
    renderHistoryPanel(orders);
  } catch (e) {
    historyBody.innerHTML = '<p style="color:var(--danger);font-size:12px;padding:4px">Failed to load orders.</p>';
  }
});

closeHistory.addEventListener('click', () => {
  historyPanel.style.display = 'none';
});

function renderHistoryPanel(orders) {
  if (!orders || orders.length === 0) {
    historyBody.innerHTML = '<p style="color:var(--text-muted);font-size:13px;padding:4px">No orders placed yet.</p>';
    return;
  }
  historyBody.innerHTML = orders.map(o => {
    const statusClass = `history-status-${o.status}`;
    const items = o.items.map(i => `${i.product_name} ×${i.quantity}`).join(', ');
    const time = o.created_at.slice(0, 16).replace('T', ' ');
    return `
      <div class="history-item">
        <div class="history-item-id">${o.order_id}</div>
        <div class="history-item-meta">
          <span class="${statusClass}">● ${o.status.toUpperCase()}</span><br>
          ${items}<br>
          ₹${o.total_amount} · ${time}
        </div>
      </div>`;
  }).join('');
}

// ─── Input events ─────────────────────────────────────────
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

// ─── Send message ─────────────────────────────────────────
async function sendMessage() {
  const text = userInput.value.trim();
  if (!text) return;

  addUserMessage(text);
  conversationHistory.push({ role: 'user', content: text });
  userInput.value = '';
  userInput.style.height = 'auto';

  const typingEl = showTyping();
  setWaiting(true);

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        session_id: SESSION_ID,
        conversation_history: conversationHistory.slice(-12),
        location: userLocation,
        selected_restaurant: selectedRestaurant
      })
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${response.status}`);
    }

    const data = await response.json();
    typingEl.remove();

    addBotMessage(data.reply, data.agent_used);
    conversationHistory.push({ role: 'assistant', content: data.reply });

    if (data.restaurants && data.restaurants.length > 0) showRestaurantCards(data.restaurants);
    if (data.hotels && data.hotels.length > 0) showHotelCards(data.hotels);
    if (data.map_embed_url) {
      mapIframe.src = data.map_embed_url;
      mapPanel.style.display = 'block';
    }
    if (data.order) showOrderCard(data.order);
    if (data.orders_list) {
      renderHistoryPanel(data.orders_list);
      historyPanel.style.display = 'flex';
    }

  } catch (err) {
    typingEl.remove();
    addBotMessage(`⚠️ Error: **${err.message}**`, 'error');
  } finally {
    setWaiting(false);
  }
}

// ─── Render helpers ───────────────────────────────────────
function addUserMessage(text) {
  const el = document.createElement('div');
  el.className = 'message user';
  el.innerHTML = `<div class="msg-avatar">👤</div><div class="msg-bubble">${escapeHtml(text)}</div>`;
  chatMessages.appendChild(el);
  scrollToBottom();
}

function addBotMessage(text, agentUsed = '') {
  const el = document.createElement('div');
  el.className = 'message bot';
  const badge = agentUsed && agentUsed !== 'greeting' && agentUsed !== 'error'
    ? `<div class="agent-badge">agent: ${agentUsed}</div>` : '';
  el.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div>
      <div class="msg-bubble">${formatMarkdown(text)}</div>
      ${badge}
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
      document.querySelectorAll('.result-card').forEach(c => c.classList.remove('selected'));
      e.target.closest('.result-card').classList.add('selected');
      addBotMessage(`Great choice! 🍽️ You selected **${selectedRestaurant.name}**.\n\nWhat would you like to order? e.g. "1 Biryani and 2 Pepsi"`, 'food_order');
      conversationHistory.push({ role: 'assistant', content: `Restaurant selected: ${selectedRestaurant.name}` });
    });
  });
}

function showHotelCards(hotels) {
  const wrapper = document.createElement('div');
  wrapper.className = 'message bot';
  const container = document.createElement('div');
  container.className = 'result-cards';

  hotels.forEach((h) => {
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
        ${h.directions_url ? `<a class="rc-btn" href="${h.directions_url}" target="_blank">🗺️ Directions</a>` : ''}
        ${h.google_search_url ? `<a class="rc-btn primary" href="${h.google_search_url}" target="_blank">🔍 Google</a>` : ''}
        ${h.website ? `<a class="rc-btn" href="${h.website}" target="_blank">🌐 Website</a>` : ''}
      </div>`;
    container.appendChild(card);
  });

  wrapper.appendChild(container);
  chatMessages.appendChild(wrapper);
  scrollToBottom();
}

function showOrderCard(order) {
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
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:8px 0">
    <pre style="white-space:pre-wrap;font-size:12px">${items}</pre>
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:8px 0">
    <div><strong>Total:</strong> ₹${(order.grand_total || order.total_amount).toFixed(2)}</div>
    <div style="margin-top:6px;font-size:11px;opacity:0.5">${order.created_at.slice(0,16).replace('T',' ')}</div>`;
  orderContainer.style.display = 'block';
  orderContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function clearChat() {
  chatMessages.innerHTML = '';
  conversationHistory = [];
  selectedRestaurant = null;
  orderContainer.style.display = 'none';
  mapPanel.style.display = 'none';
  historyPanel.style.display = 'none';
  addBotMessage("Chat cleared! How can I help you? 😊", "greeting");
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
    .replace(/^[•\-] (.+)$/gm, '<li>$1</li>')
    .replace(/\n/g, '<br>');
}