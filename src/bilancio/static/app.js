'use strict';

// ─── State ────────────────────────────────────────────────────────────────────
const S = {
  token:        localStorage.getItem('bilancio_token') || '',
  user:         null,
  view:         'accounts',   // 'accounts' | 'account' | 'rules'
  accounts:     [],
  account:      null,
  transactions: [],
  txFilter:     { needs_review: false, account_id: null },
  rules:        [],
  msg:          null,   // { type: 'success'|'error'|'info', text }
  loading:      false,
  loginTab:     'token', // 'token' | 'setup'
  setupToken:   null,   // plain token shown once after first-time setup
};

// ─── API client ───────────────────────────────────────────────────────────────
async function api(method, path, body = null) {
  const headers = {};
  if (S.token) headers['Authorization'] = `Bearer ${S.token}`;
  if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';

  const res = await fetch(path, {
    method,
    headers,
    body: body ? (body instanceof FormData ? body : JSON.stringify(body)) : null,
  });

  if (res.status === 204) return null;
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: res.statusText }));
    const msg = Array.isArray(data.detail)
      ? data.detail.map(e => e.msg).join('; ')
      : (data.detail || res.statusText);
    throw new Error(msg);
  }
  return res.json();
}

// ─── Utilities ────────────────────────────────────────────────────────────────
function fmtAmount(n) {
  const abs = Math.abs(Number(n)).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return n < 0 ? `−${abs}` : `+${abs}`;
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' });
}

function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function flash(type, text) {
  S.msg = { type, text };
  render();
  setTimeout(() => { S.msg = null; render(); }, 4500);
}

// ─── Render helpers ───────────────────────────────────────────────────────────
function renderMsg() {
  if (!S.msg) return '';
  return `<div class="alert alert-${S.msg.type === 'error' ? 'error' : S.msg.type === 'success' ? 'success' : 'info'}">${esc(S.msg.text)}</div>`;
}

// ─── Login / Setup view ───────────────────────────────────────────────────────
function renderLogin() {
  // After setup: show a dedicated token-reveal screen the user must dismiss.
  if (S.setupToken) {
    return `
<div class="login-wrap">
  <div class="login-card">
    <div class="login-logo">Bilancio</div>
    <div class="login-sub">Account created — save your token</div>
    <div class="alert alert-info" style="margin-bottom:16px">
      This token is shown <strong>once only</strong>. Copy it before continuing.
    </div>
    <div class="form-group">
      <label>Your API token</label>
      <div style="display:flex;gap:6px">
        <input type="text" id="token-reveal" value="${esc(S.setupToken)}" readonly
          style="font-family:var(--font-mono);font-size:12px;flex:1" onclick="this.select()">
        <button class="btn btn-secondary" onclick="copyToken()">Copy</button>
      </div>
    </div>
    <div id="copy-confirm" style="font-size:12px;color:var(--success);min-height:18px;margin-bottom:12px"></div>
    <button class="btn btn-primary" style="width:100%" onclick="continueFromSetup()">
      I've saved my token — continue →
    </button>
  </div>
</div>`;
  }

  const tokenTab = S.loginTab === 'token';
  return `
<div class="login-wrap">
  <div class="login-card">
    <div class="login-logo">Bilancio</div>
    <div class="login-sub">Personal finance tracker</div>
    ${renderMsg()}
    <div class="login-tabs">
      <button class="login-tab ${tokenTab ? 'active' : ''}" onclick="setLoginTab('token')">Sign in</button>
      <button class="login-tab ${!tokenTab ? 'active' : ''}" onclick="setLoginTab('setup')">First-time setup</button>
    </div>
    ${tokenTab ? `
      <div class="form-group">
        <label>API Token</label>
        <input type="password" id="inp-token" placeholder="Paste your token here…" autocomplete="off">
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" style="width:100%" onclick="doLogin()">Sign in</button>
      </div>
    ` : `
      <div class="form-group">
        <label>Email</label>
        <input type="text" id="inp-email" placeholder="you@example.com">
      </div>
      <div class="form-group">
        <label>Display name</label>
        <input type="text" id="inp-name" placeholder="Your name">
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" style="width:100%" onclick="doSetup()">Create account</button>
      </div>
      <p style="font-size:11px;color:var(--text-muted);margin-top:12px">
        Creates the first (and only) user. Only works on a fresh installation.
      </p>
    `}
  </div>
</div>`;
}

// ─── Accounts view ────────────────────────────────────────────────────────────
function renderAccounts() {
  const cards = S.accounts.length ? S.accounts.map(a => `
    <div class="account-card" onclick="openAccount(${a.id})">
      <div style="display:flex;align-items:center">
        <div>
          <div class="account-name">${esc(a.name)}</div>
          <div class="account-bank">${esc(a.bank)}</div>
        </div>
        <div class="account-currency" style="margin-left:auto">
          <span class="badge badge-gray">${esc(a.currency)}</span>
        </div>
      </div>
    </div>`).join('') : `<div class="empty"><strong>No accounts yet</strong>Add your first bank account below.</div>`;

  return `
<div class="page-header">
  <h1>Accounts</h1>
</div>
${renderMsg()}
<div class="account-grid">${cards}</div>
<div class="card" style="margin-top:24px">
  <div class="card-header"><h2>Add account</h2></div>
  <div class="card-body">
    <div class="form-row">
      <div class="form-group">
        <label>Account name</label>
        <input type="text" id="acc-name" placeholder="e.g. Conto Corrente">
      </div>
      <div class="form-group">
        <label>Bank</label>
        <input type="text" id="acc-bank" placeholder="e.g. Mediobanca Premier">
      </div>
      <div class="form-group" style="max-width:100px">
        <label>Currency</label>
        <input type="text" id="acc-currency" value="EUR">
      </div>
    </div>
    <div class="form-actions">
      <button class="btn btn-primary" onclick="createAccount()">Add account</button>
    </div>
  </div>
</div>`;
}

// ─── Account detail view ──────────────────────────────────────────────────────
function renderAccountDetail() {
  const a = S.account;
  if (!a) return '<div class="loading">Loading…</div>';

  const needsReview = S.transactions.filter(t => !t.category).length;
  const rows = S.transactions.map(t => {
    const cls = t.amount < 0 ? 'amount-neg' : 'amount-pos';
    const catHtml = `<span class="cat-display ${t.category ? '' : 'empty'}"
      onclick="startEditCat(${t.id}, this)"
      title="Click to set category">${esc(t.category || 'uncategorised')}</span>`;
    return `<tr>
      <td>${fmtDate(t.value_date)}</td>
      <td style="max-width:280px">
        <div style="font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
          title="${esc(t.description_raw)}">${esc(t.merchant_clean || t.description_raw)}</div>
        ${t.transaction_type ? `<div style="font-size:11px;color:var(--text-muted)">${esc(t.transaction_type)}</div>` : ''}
      </td>
      <td class="${cls}" style="text-align:right;white-space:nowrap">${fmtAmount(t.amount)} ${esc(t.currency)}</td>
      <td id="cat-cell-${t.id}">${catHtml}</td>
      <td>
        <label class="toggle" title="${t.is_transfer ? 'Unmark transfer' : 'Mark as transfer'}">
          <span class="toggle-track ${t.is_transfer ? 'on' : ''}" onclick="toggleTransfer(${t.id}, ${t.is_transfer})"></span>
        </label>
      </td>
    </tr>`;
  }).join('');

  const tableHtml = S.transactions.length ? `
    <div class="table-wrap">
      <table>
        <thead><tr><th>Date</th><th>Description</th><th style="text-align:right">Amount</th><th>Category</th><th title="Transfer">↔</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>` : `<div class="empty"><strong>No transactions</strong>Import a bank file to populate this account.</div>`;

  return `
<a href="#" class="back-link" onclick="showAccounts();return false">← Accounts</a>
<div class="page-header">
  <h1>${esc(a.name)}</h1>
  <div style="margin-left:8px"><span class="badge badge-gray">${esc(a.bank)}</span></div>
  <div class="page-actions">
    <button class="btn btn-secondary btn-sm" onclick="loadTransactions()">↻ Refresh</button>
  </div>
</div>
${renderMsg()}
<div class="card" style="margin-bottom:20px">
  <div class="card-header">
    <h2>Import bank file</h2>
  </div>
  <div class="card-body">
    <div class="form-group">
      <label>XLSX export from ${esc(a.bank)}</label>
      <input type="file" id="import-file" accept=".xlsx">
    </div>
    <div class="form-actions">
      <button class="btn btn-primary" onclick="importFile(${a.id})">Upload &amp; import</button>
    </div>
    <div id="import-result"></div>
  </div>
</div>
<div class="card">
  <div class="card-header">
    <h2>Transactions</h2>
    ${needsReview > 0 ? `<span class="badge badge-warn">${needsReview} uncategorised</span>` : ''}
    <div style="margin-left:auto">
      <div class="filter-bar" style="margin:0;padding:0">
        <label>
          <input type="checkbox" id="chk-review" ${S.txFilter.needs_review ? 'checked' : ''}
            onchange="setTxFilter()">
          Uncategorised only
        </label>
      </div>
    </div>
  </div>
  ${tableHtml}
</div>`;
}

// ─── Rules view ───────────────────────────────────────────────────────────────
function renderRules() {
  const rows = S.rules.map(r => `
    <tr>
      <td class="td-mono">${esc(r.pattern)}</td>
      <td><span class="badge badge-gray">${esc(r.pattern_type)}</span></td>
      <td>${esc(r.category)}${r.subcategory ? ` <span style="color:var(--text-muted)">/ ${esc(r.subcategory)}</span>` : ''}</td>
      <td style="text-align:center">${r.priority}</td>
      <td>
        <span class="toggle-track ${r.enabled ? 'on' : ''}" style="cursor:pointer"
          onclick="toggleRule(${r.id}, ${r.enabled})"></span>
      </td>
      <td>
        <button class="btn btn-danger btn-sm btn-icon" onclick="deleteRule(${r.id})" title="Delete">✕</button>
      </td>
    </tr>`).join('');

  const tableHtml = S.rules.length ? `
    <div class="table-wrap">
      <table>
        <thead><tr><th>Pattern</th><th>Type</th><th>Category</th><th style="text-align:center">Priority</th><th>Enabled</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>` : `<div class="empty"><strong>No rules yet</strong>Add rules to auto-categorise transactions on import.</div>`;

  return `
<div class="page-header">
  <h1>Categorisation rules</h1>
  <div class="page-actions">
    <button class="btn btn-secondary btn-sm" onclick="exportRules()">Export YAML</button>
  </div>
</div>
${renderMsg()}
<div class="card" style="margin-bottom:20px">
  <div class="card-header"><h2>Add rule</h2></div>
  <div class="card-body">
    <div class="form-row">
      <div class="form-group" style="flex:2">
        <label>Pattern</label>
        <input type="text" id="r-pattern" placeholder="e.g. ESSELUNGA">
      </div>
      <div class="form-group">
        <label>Type</label>
        <select id="r-type">
          <option value="contains">contains</option>
          <option value="starts_with">starts_with</option>
          <option value="exact">exact</option>
          <option value="regex">regex</option>
        </select>
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label>Category</label>
        <input type="text" id="r-category" placeholder="e.g. Groceries">
      </div>
      <div class="form-group">
        <label>Subcategory (optional)</label>
        <input type="text" id="r-subcategory" placeholder="e.g. Supermarket">
      </div>
      <div class="form-group" style="max-width:90px">
        <label>Priority</label>
        <input type="number" id="r-priority" value="0">
      </div>
    </div>
    <div class="form-actions">
      <button class="btn btn-primary" onclick="createRule()">Add rule</button>
    </div>
  </div>
</div>
<div class="card">${tableHtml}</div>`;
}

// ─── Layout ───────────────────────────────────────────────────────────────────
function renderApp() {
  const navAccActive = S.view === 'accounts' || S.view === 'account';
  return `
<header class="header">
  <div class="header-brand">Bilancio <span>beta</span></div>
  <nav class="header-nav">
    <a href="#" onclick="showAccounts();return false" class="${navAccActive ? 'active' : ''}">Accounts</a>
    <a href="#" onclick="showRules();return false" class="${S.view === 'rules' ? 'active' : ''}">Rules</a>
  </nav>
  <div class="header-user">
    <span>${esc(S.user?.email || '')}</span>
    <button class="btn btn-ghost" onclick="logout()">Sign out</button>
  </div>
</header>
<main class="main">
  ${S.view === 'accounts'  ? renderAccounts()      : ''}
  ${S.view === 'account'   ? renderAccountDetail() : ''}
  ${S.view === 'rules'     ? renderRules()         : ''}
</main>`;
}

// ─── Root render ──────────────────────────────────────────────────────────────
function render() {
  document.getElementById('app').innerHTML = S.token && S.user ? renderApp() : renderLogin();
}

// ─── Auth actions ─────────────────────────────────────────────────────────────
function setLoginTab(tab) { S.loginTab = tab; S.msg = null; render(); }

function copyToken() {
  const el = document.getElementById('token-reveal');
  if (!el) return;
  el.select();
  navigator.clipboard.writeText(el.value).then(() => {
    const confirm = document.getElementById('copy-confirm');
    if (confirm) confirm.textContent = '✓ Copied to clipboard';
  });
}

async function doLogin() {
  const t = document.getElementById('inp-token')?.value.trim();
  if (!t) return;
  S.token = t;
  try {
    S.user = await api('GET', '/me');
    localStorage.setItem('bilancio_token', t);
    await loadAccounts();
    render();
  } catch {
    S.token = '';
    flash('error', 'Invalid token. Check it and try again.');
  }
}

async function doSetup() {
  const email = document.getElementById('inp-email')?.value.trim();
  const name  = document.getElementById('inp-name')?.value.trim();
  if (!email || !name) { flash('error', 'Email and display name are required.'); return; }
  try {
    const data = await api('POST', '/setup', { email, display_name: name });
    // Store token in state but don't transition to app yet — show the
    // token reveal screen first so the user has time to copy it.
    S.setupToken = data.token;
    render();
  } catch(e) {
    flash('error', e.message);
  }
}

async function continueFromSetup() {
  S.token = S.setupToken;
  S.setupToken = null;
  localStorage.setItem('bilancio_token', S.token);
  try {
    S.user = await api('GET', '/me');
    await loadAccounts();
    render();
  } catch(e) {
    S.token = '';
    localStorage.removeItem('bilancio_token');
    flash('error', e.message);
  }
}

function logout() {
  S.token = ''; S.user = null; S.accounts = []; S.transactions = []; S.rules = [];
  localStorage.removeItem('bilancio_token');
  render();
}

// ─── Navigation ───────────────────────────────────────────────────────────────
async function showAccounts() {
  S.view = 'accounts'; S.account = null;
  await loadAccounts();
}

async function showRules() {
  S.view = 'rules';
  await loadRules();
}

async function openAccount(id) {
  S.account = S.accounts.find(a => a.id === id) || null;
  S.view = 'account';
  S.txFilter.account_id = id;
  await loadTransactions();
}

// ─── Account actions ──────────────────────────────────────────────────────────
async function loadAccounts() {
  try { S.accounts = await api('GET', '/accounts'); render(); } catch(e) { flash('error', e.message); }
}

async function createAccount() {
  const name     = document.getElementById('acc-name')?.value.trim();
  const bank     = document.getElementById('acc-bank')?.value.trim();
  const currency = (document.getElementById('acc-currency')?.value.trim() || 'EUR').toUpperCase();
  if (!name || !bank) { flash('error', 'Name and bank are required.'); return; }
  try {
    await api('POST', '/accounts', { name, bank, currency });
    await loadAccounts();
    flash('success', `Account "${name}" created.`);
  } catch(e) { flash('error', e.message); }
}

// ─── Import action ────────────────────────────────────────────────────────────
async function importFile(accountId) {
  const input = document.getElementById('import-file');
  if (!input?.files?.length) { flash('error', 'Select a file first.'); return; }
  const form = new FormData();
  form.append('file', input.files[0]);
  try {
    const result = await api('POST', `/accounts/${accountId}/import`, form);
    document.getElementById('import-result').innerHTML = `
      <div class="import-result">
        <div><strong>${result.added}</strong><span>Added</span></div>
        <div><strong>${result.skipped}</strong><span>Skipped (dup)</span></div>
        <div><strong>${result.needs_review}</strong><span>Needs review</span></div>
      </div>`;
    input.value = '';
    await loadTransactions();
  } catch(e) { flash('error', e.message); }
}

// ─── Transaction actions ──────────────────────────────────────────────────────
async function loadTransactions() {
  if (!S.txFilter.account_id) return;
  const params = new URLSearchParams({ account_id: S.txFilter.account_id, limit: 500 });
  if (S.txFilter.needs_review) params.set('needs_review', 'true');
  try { S.transactions = await api('GET', `/transactions?${params}`); render(); }
  catch(e) { flash('error', e.message); }
}

async function setTxFilter() {
  S.txFilter.needs_review = document.getElementById('chk-review')?.checked || false;
  await loadTransactions();
}

function startEditCat(txId, _el) {
  const cell = document.getElementById(`cat-cell-${txId}`);
  const cur  = S.transactions.find(t => t.id === txId);
  cell.innerHTML = `
    <div class="inline-edit">
      <input type="text" id="cat-inp-${txId}" value="${esc(cur?.category || '')}" placeholder="category" onkeydown="catKeydown(event,${txId})">
      <button class="btn btn-primary btn-sm" onclick="saveCat(${txId})">✓</button>
      <button class="btn btn-ghost btn-sm" onclick="cancelCat(${txId})">✕</button>
    </div>`;
  document.getElementById(`cat-inp-${txId}`)?.focus();
}

function catKeydown(e, txId) {
  if (e.key === 'Enter') saveCat(txId);
  if (e.key === 'Escape') cancelCat(txId);
}

async function saveCat(txId) {
  const val = document.getElementById(`cat-inp-${txId}`)?.value.trim() || null;
  try {
    const updated = await api('PATCH', `/transactions/${txId}`, { category: val || null });
    const idx = S.transactions.findIndex(t => t.id === txId);
    if (idx >= 0) S.transactions[idx] = updated;
    render();
  } catch(e) { flash('error', e.message); }
}

function cancelCat(txId) {
  const cur = S.transactions.find(t => t.id === txId);
  const cell = document.getElementById(`cat-cell-${txId}`);
  if (!cell || !cur) return;
  cell.innerHTML = `<span class="cat-display ${cur.category ? '' : 'empty'}"
    onclick="startEditCat(${txId}, this)">${esc(cur.category || 'uncategorised')}</span>`;
}

async function toggleTransfer(txId, current) {
  try {
    const updated = await api('PATCH', `/transactions/${txId}`, { is_transfer: !current });
    const idx = S.transactions.findIndex(t => t.id === txId);
    if (idx >= 0) S.transactions[idx] = updated;
    render();
  } catch(e) { flash('error', e.message); }
}

// ─── Rule actions ─────────────────────────────────────────────────────────────
async function loadRules() {
  try { S.rules = await api('GET', '/rules'); render(); } catch(e) { flash('error', e.message); }
}

async function createRule() {
  const pattern    = document.getElementById('r-pattern')?.value.trim();
  const type       = document.getElementById('r-type')?.value;
  const category   = document.getElementById('r-category')?.value.trim();
  const sub        = document.getElementById('r-subcategory')?.value.trim() || null;
  const priority   = parseInt(document.getElementById('r-priority')?.value || '0', 10);
  if (!pattern || !category) { flash('error', 'Pattern and category are required.'); return; }
  try {
    await api('POST', '/rules', { pattern, pattern_type: type, category, subcategory: sub, priority });
    await loadRules();
    flash('success', 'Rule added.');
    ['r-pattern','r-category','r-subcategory'].forEach(id => { const el = document.getElementById(id); if(el) el.value=''; });
    document.getElementById('r-priority').value = '0';
  } catch(e) { flash('error', e.message); }
}

async function toggleRule(ruleId, current) {
  try {
    await api('PATCH', `/rules/${ruleId}`, { enabled: !current });
    await loadRules();
  } catch(e) { flash('error', e.message); }
}

async function deleteRule(ruleId) {
  if (!confirm('Delete this rule?')) return;
  try {
    await api('DELETE', `/rules/${ruleId}`);
    await loadRules();
  } catch(e) { flash('error', e.message); }
}

async function exportRules() {
  const res = await fetch('/rules/export', { headers: { Authorization: `Bearer ${S.token}` } });
  if (!res.ok) { flash('error', 'Export failed.'); return; }
  const text = await res.text();
  const blob = new Blob([text], { type: 'text/yaml' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'bilancio-rules.yaml'; a.click();
  URL.revokeObjectURL(url);
}

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  if (S.token) {
    try {
      S.user = await api('GET', '/me');
      await loadAccounts();
    } catch {
      S.token = '';
      localStorage.removeItem('bilancio_token');
    }
  }
  render();
});
