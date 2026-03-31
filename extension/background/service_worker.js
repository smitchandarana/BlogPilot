/**
 * BlogPilot Service Worker (MV3)
 *
 * Responsibilities:
 * - Native messaging bridge to Python backend
 * - Message routing between extension contexts (popup, sidepanel, content scripts)
 * - Alarm-based scheduling (feed scan, budget reset)
 * - LLM provider routing
 * - Engine state management (mirrors native host state)
 */

import { NativeBridge } from './native_bridge.js';
import { StorageManager } from './storage.js';
import { AlarmScheduler } from './alarm_scheduler.js';

// ── State ────────────────────────────────────────────────────────────────
const state = {
  engineState: 'STOPPED',   // STOPPED | RUNNING | PAUSED | ERROR
  nativeConnected: false,
  startedAt: null,
  lastActivity: null,
  budgets: {}
};

const bridge = new NativeBridge();
const storage = new StorageManager();
const scheduler = new AlarmScheduler();

// ── Listeners & Ports ────────────────────────────────────────────────────
const connectedPorts = new Set();

// Track connected UI contexts (popup, sidepanel, content scripts)
chrome.runtime.onConnect.addListener((port) => {
  connectedPorts.add(port);
  port.onDisconnect.addListener(() => connectedPorts.delete(port));

  // Send current state immediately to new connection
  port.postMessage({ type: 'STATE_SYNC', payload: state });

  port.onMessage.addListener((msg) => handlePortMessage(port, msg));
});

// One-shot messages from content scripts or popup
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  handleMessage(msg, sender).then(sendResponse);
  return true; // async response
});

// ── Message Handlers ─────────────────────────────────────────────────────

async function handleMessage(msg, sender) {
  switch (msg.type) {
    case 'GET_STATE':
      return { ...state };

    case 'ENGINE_START':
      return await bridgeCommand('engine_start');

    case 'ENGINE_STOP':
      return await bridgeCommand('engine_stop');

    case 'ENGINE_PAUSE':
      return await bridgeCommand('engine_pause');

    case 'ENGINE_RESUME':
      return await bridgeCommand('engine_resume');

    case 'ENGINE_STATUS':
      return await bridgeCommand('engine_status');

    case 'SCAN_NOW':
      return await bridgeCommand('scan_now');

    case 'APPROVE_COMMENT':
      return await bridgeCommand('approve_comment', msg.payload);

    case 'REJECT_COMMENT':
      return await bridgeCommand('reject_comment', msg.payload);

    case 'GET_PENDING_PREVIEWS':
      return await bridgeCommand('pending_previews');

    case 'GET_ANALYTICS':
      return await bridgeCommand('analytics', msg.payload);

    case 'GET_LEADS':
      return await bridgeCommand('leads_list', msg.payload);

    case 'EXPORT_LEADS':
      return await bridgeCommand('leads_export', msg.payload);

    case 'GENERATE_COMMENT':
      return await bridgeCommand('generate_comment', msg.payload);

    case 'GENERATE_POST':
      return await bridgeCommand('generate_post', msg.payload);

    case 'GET_SETTINGS':
      return await bridgeCommand('get_settings');

    case 'UPDATE_SETTINGS':
      return await bridgeCommand('update_settings', msg.payload);

    case 'GET_TOPICS':
      return await bridgeCommand('get_topics');

    case 'UPDATE_TOPICS':
      return await bridgeCommand('update_topics', msg.payload);

    case 'GET_BUDGETS':
      return await bridgeCommand('get_budgets');

    // LLM provider management
    case 'LLM_COMPLETE':
      return await handleLLMComplete(msg.payload);

    case 'SET_LLM_PROVIDER':
      await storage.set('llm_provider', msg.payload);
      return { ok: true };

    case 'GET_LLM_PROVIDER':
      return await storage.get('llm_provider');

    // Content script feeds observed posts
    case 'FEED_POSTS_OBSERVED':
      return await bridgeCommand('feed_posts_observed', msg.payload);

    // Native bridge control
    case 'CONNECT_NATIVE':
      return await connectNative();

    case 'DISCONNECT_NATIVE':
      bridge.disconnect();
      state.nativeConnected = false;
      broadcastState();
      return { ok: true };

    default:
      console.warn('[SW] Unknown message type:', msg.type);
      return { error: 'Unknown message type' };
  }
}

function handlePortMessage(port, msg) {
  // Port messages are handled the same way, just routed back through the port
  handleMessage(msg, null).then((response) => {
    try { port.postMessage({ type: 'RESPONSE', id: msg.id, payload: response }); }
    catch (e) { /* port disconnected */ }
  });
}

// ── Native Bridge ────────────────────────────────────────────────────────

async function connectNative() {
  try {
    bridge.connect();
    state.nativeConnected = true;

    bridge.onMessage((data) => {
      handleNativeMessage(data);
    });

    bridge.onDisconnect(() => {
      console.warn('[SW] Native host disconnected');
      state.nativeConnected = false;
      state.engineState = 'STOPPED';
      broadcastState();
      broadcastToAll({ type: 'NATIVE_DISCONNECTED' });
    });

    // Request initial state
    const status = await bridgeCommand('engine_status');
    if (status && status.state) {
      state.engineState = status.state;
      state.budgets = status.budget_used || {};
    }

    broadcastState();
    return { ok: true, state: state.engineState };
  } catch (e) {
    console.error('[SW] Native connect failed:', e);
    state.nativeConnected = false;
    return { error: e.message };
  }
}

async function bridgeCommand(command, payload = {}) {
  if (!state.nativeConnected) {
    // Try auto-connect
    const result = await connectNative();
    if (result.error) return { error: 'Native host not connected. Start BlogPilot backend first.' };
  }

  try {
    const response = await bridge.send({ command, ...payload });

    // Update local state from responses
    if (response && response.state) {
      state.engineState = response.state;
      broadcastState();
    }
    if (response && response.budget_used) {
      state.budgets = response.budget_used;
    }

    return response;
  } catch (e) {
    console.error(`[SW] Bridge command '${command}' failed:`, e);
    return { error: e.message };
  }
}

function handleNativeMessage(data) {
  // Native host pushes events (activity, alerts, budget updates, previews)
  switch (data.event) {
    case 'engine_state':
      state.engineState = data.payload.state;
      broadcastState();
      break;

    case 'activity':
    case 'budget_update':
    case 'alert':
    case 'post_preview':
    case 'lead_added':
    case 'stats_update':
      broadcastToAll({ type: 'EVENT', event: data.event, payload: data.payload });
      break;

    default:
      // Forward unknown events
      broadcastToAll({ type: 'EVENT', event: data.event, payload: data.payload });
  }
}

// ── LLM Provider Routing ─────────────────────────────────────────────────

async function handleLLMComplete(payload) {
  const providerConfig = await storage.get('llm_provider') || { provider: 'native' };

  // Default: route through native host (uses Python AI layer)
  if (providerConfig.provider === 'native') {
    return await bridgeCommand('llm_complete', payload);
  }

  // Direct API call from extension (bypasses native host)
  try {
    const { default: getProvider } = await import(`../providers/${providerConfig.provider}.js`);
    const provider = getProvider(providerConfig);
    return await provider.complete(payload.system, payload.user, payload.options || {});
  } catch (e) {
    console.error(`[SW] LLM provider '${providerConfig.provider}' failed:`, e);
    // Fallback to native host
    return await bridgeCommand('llm_complete', payload);
  }
}

// ── Broadcasting ─────────────────────────────────────────────────────────

function broadcastState() {
  broadcastToAll({ type: 'STATE_SYNC', payload: { ...state } });
}

function broadcastToAll(msg) {
  for (const port of connectedPorts) {
    try { port.postMessage(msg); }
    catch (e) { connectedPorts.delete(port); }
  }
}

// ── Alarms (replaces APScheduler) ────────────────────────────────────────

chrome.alarms.onAlarm.addListener(async (alarm) => {
  console.log(`[SW] Alarm fired: ${alarm.name}`);

  switch (alarm.name) {
    case 'blogpilot_keepalive':
      // Ping native host to keep connection alive
      if (state.nativeConnected) {
        await bridgeCommand('ping');
      }
      break;

    case 'blogpilot_budget_reset':
      await bridgeCommand('budget_reset');
      break;

    case 'blogpilot_status_poll':
      if (state.nativeConnected && state.engineState === 'RUNNING') {
        const status = await bridgeCommand('engine_status');
        if (status) {
          state.budgets = status.budget_used || {};
          broadcastState();
        }
      }
      break;
  }
});

// ── Install / Startup ────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(async (details) => {
  console.log('[SW] BlogPilot installed/updated:', details.reason);

  // Set up alarms
  chrome.alarms.create('blogpilot_keepalive', { periodInMinutes: 0.5 }); // 30s
  chrome.alarms.create('blogpilot_status_poll', { periodInMinutes: 1 });

  // Enable side panel
  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
    await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false });
  }

  // Initialize default storage
  const existing = await storage.get('llm_provider');
  if (!existing) {
    await storage.set('llm_provider', { provider: 'native', model: 'llama-3.3-70b-versatile' });
  }

  // Show welcome notification on fresh install
  if (details.reason === 'install') {
    chrome.notifications.create('welcome', {
      type: 'basic',
      iconUrl: 'icons/icon128.png',
      title: 'BlogPilot Installed',
      message: 'Click the extension icon to get started. Make sure the BlogPilot backend is running.'
    });
  }
});

chrome.runtime.onStartup.addListener(async () => {
  console.log('[SW] BlogPilot startup');
  // Re-create alarms (they persist across restarts, but be safe)
  chrome.alarms.create('blogpilot_keepalive', { periodInMinutes: 0.5 });
  chrome.alarms.create('blogpilot_status_poll', { periodInMinutes: 1 });

  // Try to reconnect to native host
  await connectNative();
});

// ── Side Panel ───────────────────────────────────────────────────────────

// Open side panel when user clicks on LinkedIn tab
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    if (tab.url && tab.url.includes('linkedin.com')) {
      await chrome.sidePanel.setOptions({
        tabId: activeInfo.tabId,
        path: 'sidepanel/index.html',
        enabled: true
      });
    }
  } catch (e) { /* tab access error — ignore */ }
});

console.log('[SW] BlogPilot service worker loaded');
