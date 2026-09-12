const RULESETS = ['custom', 'easylist', 'easylistchina', 'easyprivacy'];

// Dynamic-rule ids for per-site pauses live in their own range so they can
// never collide with the static rulesets, whose ids start at 1 in each file.
const PAUSE_ID_BASE = 1_000_000;

const statusEl = document.getElementById('status');
const hostEl = document.getElementById('host');
const pauseEl = document.getElementById('pause');
const blockedEl = document.getElementById('blocked');

let currentTab = null;
let currentHost = null;

/** The registrable-ish domain: enough to cover www. and other subdomains. */
function hostOf(url) {
  try {
    const { protocol, hostname } = new URL(url);
    if (protocol !== 'http:' && protocol !== 'https:') return null;
    return hostname.replace(/^www\./, '');
  } catch {
    return null;
  }
}

/** Lowest unused id in the pause range. Hashing the host would be shorter but
    two hosts could collide, and pausing one would silently unpause the other. */
async function nextPauseId() {
  const rules = await chrome.declarativeNetRequest.getDynamicRules();
  const used = new Set(rules.map((r) => r.id));
  let id = PAUSE_ID_BASE;
  while (used.has(id)) id++;
  return id;
}

async function pausedRuleFor(host) {
  const rules = await chrome.declarativeNetRequest.getDynamicRules();
  return rules.find((r) => r.condition?.requestDomains?.includes(host)) || null;
}

async function refreshRulesets() {
  const enabled = await chrome.declarativeNetRequest.getEnabledRulesets();
  for (const id of RULESETS) {
    document.getElementById(id).checked = enabled.includes(id);
  }
  statusEl.textContent = enabled.length
    ? `Blocking with ${enabled.length}/${RULESETS.length} rulesets`
    : 'Paused';
}

async function refreshSite() {
  [currentTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentHost = currentTab ? hostOf(currentTab.url || '') : null;

  if (!currentHost) {
    hostEl.textContent = 'Not a web page';
    pauseEl.disabled = true;
    pauseEl.textContent = 'Pause on this site';
    pauseEl.dataset.paused = 'false';
    blockedEl.innerHTML = '&nbsp;';
    return;
  }

  hostEl.innerHTML = 'Site: <b></b>';
  hostEl.querySelector('b').textContent = currentHost;
  pauseEl.disabled = false;

  const paused = await pausedRuleFor(currentHost);
  pauseEl.dataset.paused = paused ? 'true' : 'false';
  pauseEl.textContent = paused ? 'Resume on this site' : 'Pause on this site';

  await refreshBlockedCount(paused);
}

async function refreshBlockedCount(paused) {
  if (paused) {
    blockedEl.textContent = 'Rules bypassed here';
    return;
  }
  try {
    const { rulesMatchedInfo } = await chrome.declarativeNetRequest.getMatchedRules({
      tabId: currentTab.id,
    });
    const n = rulesMatchedInfo.length;
    blockedEl.textContent =
      n === 0 ? 'No rule matches on this tab yet' : `${n} rule matches on this tab`;
  } catch {
    // getMatchedRules needs the declarativeNetRequestFeedback permission, which
    // Chrome only grants to unpacked extensions. Packed? Just say nothing.
    blockedEl.innerHTML = '&nbsp;';
  }
}

pauseEl.addEventListener('click', async () => {
  if (!currentHost) return;
  pauseEl.disabled = true;

  const existing = await pausedRuleFor(currentHost);
  if (existing) {
    await chrome.declarativeNetRequest.updateDynamicRules({
      removeRuleIds: [existing.id],
    });
  } else {
    await chrome.declarativeNetRequest.updateDynamicRules({
      addRules: [
        {
          id: await nextPauseId(),
          // Above every static rule, including the $important ones at 2.
          priority: 100,
          action: { type: 'allowAllRequests' },
          condition: {
            requestDomains: [currentHost],
            resourceTypes: ['main_frame', 'sub_frame'],
          },
        },
      ],
    });
  }

  await refreshSite();
  if (currentTab) chrome.tabs.reload(currentTab.id);
});

for (const id of RULESETS) {
  document.getElementById(id).addEventListener('change', async (e) => {
    await chrome.declarativeNetRequest.updateEnabledRulesets(
      e.target.checked
        ? { enableRulesetIds: [id] }
        : { disableRulesetIds: [id] }
    );
    refreshRulesets();
  });
}

refreshRulesets();
refreshSite();
