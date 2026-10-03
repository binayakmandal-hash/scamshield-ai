/* ScamShield AI — home page: Gmail / demo inbox, actions with undo, screenshot check. */
(function () {
  'use strict';
  const SS = window.SS;
  const el = SS.el;
  const icon = SS.icon;
  const $ = (id) => document.getElementById(id);

  const app = $('inbox-app');
  const errorBox = $('form-error');
  const list = $('mail-list');
  const langSelect = $('lang-select');
  const resultsSection = $('results');
  const resultsRoot = $('results-root');

  const state = {
    mode: 'gmail',
    gmail: { configured: app.dataset.gmailConfigured === 'yes', connected: app.dataset.gmailConnected === 'yes', email: null },
    items: [],
    openId: null,
  };

  const ACTIONS = {
    spam: { label: 'Spam', icon: 'shield', done: 'Moved to Spam', learned: 'ScamShield learned this is a scam.' },
    block: { label: 'Block', icon: 'x', done: 'Sender blocked and email moved to Spam', learned: 'Future emails from this sender will skip your inbox.' },
    trash: { label: 'Delete', icon: 'trash', done: 'Moved to Trash (recoverable for 30 days)', learned: 'ScamShield learned this is a scam.' },
    safe: { label: 'Safe', icon: 'check', done: 'Marked as safe', learned: 'ScamShield will trust this sender from now on.' },
  };
  const SHORT_LEVEL = { 'Low Risk': 'Low', Suspicious: 'Suspicious', 'High Risk': 'High', 'Very High Risk': 'Very high' };

  // ---------------------------------------------------------------- helpers
  function showError(msg) { errorBox.textContent = msg; errorBox.hidden = false; }
  function hideError() { errorBox.hidden = true; }
  const api = (path) => `/api/mail/${state.mode}${path}`;

  function timeAgo(ts) {
    if (!ts) return '';
    const s = Date.now() / 1000 - ts;
    if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min ago`;
    if (s < 86400) return `${Math.round(s / 3600)} h ago`;
    return new Date(ts * 1000).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
  }

  // ---------------------------------------------------------------- modes
  document.querySelectorAll('#inbox-app .tab').forEach((tab) => tab.addEventListener('click', () => setMode(tab.dataset.mode)));
  document.querySelectorAll('[data-switch]').forEach((b) => b.addEventListener('click', () => {
    setMode(b.dataset.switch);
    $('inbox').scrollIntoView({ behavior: 'smooth' });
  }));

  function setMode(mode) {
    state.mode = mode;
    hideError();
    document.querySelectorAll('#inbox-app .tab').forEach((t) => {
      const on = t.dataset.mode === mode;
      t.classList.toggle('is-active', on);
      t.setAttribute('aria-selected', String(on));
      t.tabIndex = on ? 0 : -1;
    });
    const gmailReady = state.gmail.connected;
    $('gmail-setup').hidden = !(mode === 'gmail' && !gmailReady);
    $('inbox-panel').hidden = !(mode === 'demo' || (mode === 'gmail' && gmailReady));
    $('screenshot-panel').hidden = mode !== 'screenshot';
    $('disconnect-btn').hidden = mode !== 'gmail';
    $('account-label').textContent = mode === 'demo' ? 'Demo inbox (sample emails, nothing real is changed)'
      : (state.gmail.email || 'Gmail connected');
    if (mode === 'gmail' && !gmailReady) renderSetup();
    if (mode !== 'screenshot' && !$('inbox-panel').hidden) {
      list.replaceChildren();
      $('inbox-summary').hidden = true;
      scan();
    }
  }

  function renderSetup() {
    const title = $('connect-title');
    const text = $('connect-text');
    const btn = $('connect-btn');
    if (!state.gmail.configured) {
      title.textContent = 'Gmail needs a one-time setup';
      text.replaceChildren(
        'Add your Google OAuth client file as ', el('code', { text: 'client_secret.json' }),
        ' in the project folder, then restart the app. The README has step-by-step instructions (about 10 minutes). Meanwhile, the demo inbox shows every feature.');
      btn.hidden = true;
    } else {
      btn.hidden = false;
    }
  }

  // ---------------------------------------------------------------- Gmail status
  async function loadGmailStatus() {
    try {
      const s = await SS.api('/api/gmail/status');
      Object.assign(state.gmail, { configured: s.configured, connected: s.connected, email: s.email });
      if (s.error) showError(s.error);
    } catch (e) { /* keep server-rendered state */ }
  }

  $('disconnect-btn').addEventListener('click', async () => {
    await SS.postJSON('/api/gmail/disconnect', {});
    state.gmail.connected = false;
    state.gmail.email = null;
    setMode('gmail');
  });

  // ---------------------------------------------------------------- scanning
  $('scan-btn').addEventListener('click', () => scan());

  async function scan() {
    hideError();
    const btn = $('scan-btn');
    btn.disabled = true;
    btn.lastChild.textContent = 'Scanning…';
    list.replaceChildren(el('li', { class: 'mails__loading', text: state.mode === 'gmail' ? 'Fetching and checking your latest emails…' : 'Checking the demo inbox…' }));
    try {
      const reset = state.mode === 'demo' && !state.demoStarted;  // fresh demo inbox on each page load
      state.demoStarted = state.demoStarted || state.mode === 'demo';
      const res = await SS.postJSON(api('/scan'), { limit: Number($('scan-limit').value), reset });
      state.items = res.items;
      renderList();
      renderLearning(res.learning);
    } catch (e) {
      list.replaceChildren();
      showError(e.message);
      if (/connect/i.test(e.message)) { state.gmail.connected = false; setMode('gmail'); }
    } finally {
      btn.disabled = false;
      btn.lastChild.textContent = 'Scan inbox';
    }
  }

  function renderList() {
    list.replaceChildren();
    if (!state.items.length) {
      list.append(el('li', { class: 'mails__empty', text: 'Your inbox is empty. Nothing to check right now.' }));
      $('inbox-summary').hidden = true;
      return;
    }
    state.items.forEach((it) => list.append(row(it)));
    renderSummary();
  }

  function risky() {
    return state.items.filter((it) => !it._done && (it.risk_level === 'High Risk' || it.risk_level === 'Very High Risk'));
  }

  function renderSummary() {
    const r = risky();
    const total = state.items.length;
    $('inbox-summary').hidden = false;
    $('summary-text').textContent = r.length
      ? `Checked ${total} emails. ${r.length} ${r.length === 1 ? 'looks' : 'look'} risky.`
      : `Checked ${total} emails. Nothing looks high-risk right now.`;
    const bulk = $('bulk-btn');
    bulk.hidden = !r.length;
    bulk.classList.remove('is-confirming');
    bulk.lastChild.textContent = `Move ${r.length} risky ${r.length === 1 ? 'email' : 'emails'} to Spam`;
  }

  function row(it) {
    const node = el('li', { class: `mail ${SS.riskClass(it.risk_level)}`, 'data-id': it.id });
    const main = el('button', { type: 'button', class: 'mail__main', 'aria-label': `Open analysis of email from ${it.from_name}: ${it.subject}` },
      el('span', { class: 'mail__score' }, el('b', { text: String(it.risk_score) }), el('small', { text: SHORT_LEVEL[it.risk_level] || it.risk_level })),
      el('span', { class: 'mail__body' },
        el('span', { class: 'mail__top' },
          el('span', { class: 'mail__from', text: it.from_name || it.from_email }),
          el('span', { class: 'mail__addr', text: it.from_email }),
          el('span', { class: 'mail__date', text: timeAgo(it.timestamp) })),
        el('span', { class: 'mail__subject' }, it.subject, ' ', el('span', { text: '— ' + (it.snippet || '') })),
        it.flags.length || it.sender_rule
          ? el('span', { class: 'mail__flags' },
            it.sender_rule === 'trusted' ? el('span', { class: 'flag-chip', text: 'Trusted sender' }) : null,
            it.flags.map((f) => el('span', { class: `flag-chip ${it.risk_score >= 50 ? 'sev-high' : 'sev-medium'}`, text: f })))
          : null));
    main.addEventListener('click', () => openMail(it, node));

    const actions = el('div', { class: 'mail__actions' },
      ['spam', 'block', 'trash', 'safe'].map((a) => {
        const b = el('button', {
          type: 'button', class: `act ${a === 'safe' ? 'act--ok' : a === 'spam' ? '' : 'act--danger'}`,
          title: ACTIONS[a].done, 'aria-label': `${ACTIONS[a].label}: ${it.subject}`,
        }, icon(ACTIONS[a].icon), el('span', { text: ACTIONS[a].label }));
        b.addEventListener('click', () => act(it, node, a));
        return b;
      }));
    node.append(main, actions);
    return node;
  }

  // ---------------------------------------------------------------- actions + undo
  async function act(it, node, action, silent) {
    node.querySelectorAll('.act').forEach((b) => (b.disabled = true));
    try {
      const res = await SS.postJSON(api(`/${encodeURIComponent(it.id)}/action`), { action });
      it._done = action;
      markDone(it, node, action);
      renderLearning(res.learning);
      if (!silent) renderSummary();
      return true;
    } catch (e) {
      showError(e.message);
      node.querySelectorAll('.act').forEach((b) => (b.disabled = false));
      return false;
    }
  }

  function markDone(it, node, action) {
    node.classList.add('is-done');
    node.querySelector('.mail__status')?.remove();
    const undo = el('button', { type: 'button', class: 'link-btn', text: 'Undo' });
    undo.addEventListener('click', async () => {
      undo.disabled = true;
      try {
        const res = await SS.postJSON(api(`/${encodeURIComponent(it.id)}/action`), { action, undo: true });
        it._done = null;
        node.classList.remove('is-done');
        node.querySelector('.mail__status')?.remove();
        node.querySelectorAll('.act').forEach((b) => (b.disabled = false));
        renderLearning(res.learning);
        renderSummary();
      } catch (e) { showError(e.message); undo.disabled = false; }
    });
    node.append(el('div', { class: 'mail__status', role: 'status' }, icon('check'),
      el('span', {}, el('strong', { text: ACTIONS[action].done + '. ' }), ACTIONS[action].learned), undo));
  }

  $('bulk-btn').addEventListener('click', async () => {
    const bulk = $('bulk-btn');
    const targets = risky();
    if (!targets.length) return;
    if (!bulk.classList.contains('is-confirming')) {
      bulk.classList.add('is-confirming');
      bulk.lastChild.textContent = `Click again to move ${targets.length} to Spam`;
      setTimeout(() => renderSummary(), 4000);
      return;
    }
    bulk.disabled = true;
    for (const it of targets) {
      const node = list.querySelector(`[data-id="${CSS.escape(it.id)}"]`);
      if (node) await act(it, node, 'spam', true);
    }
    bulk.disabled = false;
    renderSummary();
  });

  // ---------------------------------------------------------------- learning strip
  function renderLearning(l) {
    if (!l) return;
    const fb = l.feedback || { scam: 0, safe: 0 };
    const decisions = fb.scam + fb.safe;
    const acc = l.metrics && l.metrics.accuracy != null ? ` Cross-validated accuracy ${Math.round(l.metrics.accuracy * 100)}%.` : '';
    $('learning-text').textContent = `Learning model trained on ${l.total_examples} examples, including ${decisions} of your decisions.${acc}`;
    $('learning-strip').hidden = false;
  }

  // ---------------------------------------------------------------- open one email
  async function openMail(it, node) {
    list.querySelectorAll('.mail').forEach((m) => m.classList.remove('is-open'));
    node.classList.add('is-open');
    state.openId = it.id;
    resultsSection.hidden = false;
    resultsRoot.replaceChildren(el('div', { class: 'card' }, el('p', { class: 'muted', text: `Analysing “${it.subject}” in detail…` })));
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    try {
      const data = await SS.api(api(`/${encodeURIComponent(it.id)}?lang=${langSelect.value}`));
      if (state.openId !== it.id) return;
      SS.renderResult(resultsRoot, data, {
        onAgain: () => { node.scrollIntoView({ behavior: 'smooth', block: 'center' }); node.querySelector('.mail__main').focus({ preventScroll: true }); },
        againLabel: 'Back to inbox',
      });
    } catch (e) {
      resultsRoot.replaceChildren(el('p', { class: 'notice', text: e.message }));
    }
  }

  // ---------------------------------------------------------------- screenshot
  const MAX_BYTES = 8 * 1024 * 1024;
  const TYPES = ['image/png', 'image/jpeg', 'image/webp'];
  let imageFile = null;
  let imageUrl = null;
  const dropzone = $('dropzone');
  ['dragenter', 'dragover'].forEach((ev) => dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add('is-over'); }));
  ['dragleave', 'drop'].forEach((ev) => dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove('is-over'); }));
  dropzone.addEventListener('drop', (e) => { if (e.dataTransfer.files[0]) setImage(e.dataTransfer.files[0]); });
  $('image-input').addEventListener('change', (e) => { if (e.target.files[0]) setImage(e.target.files[0]); });
  document.addEventListener('paste', (e) => {
    const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith('image/'));
    if (item) { setMode('screenshot'); setImage(item.getAsFile()); }
  });
  $('remove-image').addEventListener('click', () => {
    imageFile = null; $('image-input').value = ''; $('image-preview').hidden = true; dropzone.hidden = false;
  });

  function setImage(file) {
    hideError();
    if (!TYPES.includes(file.type)) return showError('Upload a JPG, PNG or WebP screenshot.');
    if (file.size > MAX_BYTES) return showError('That file is larger than 8 MB. Try a smaller screenshot.');
    imageFile = file;
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    imageUrl = URL.createObjectURL(file);
    $('preview-img').src = imageUrl;
    $('preview-name').textContent = file.name || 'Pasted screenshot';
    $('preview-size').textContent = `${(file.size / 1024).toFixed(0)} KB`;
    $('image-preview').hidden = false;
    dropzone.hidden = true;
  }

  $('analyze-btn').addEventListener('click', async () => {
    hideError();
    if (!imageFile) return showError('Choose a screenshot first.');
    const btn = $('analyze-btn');
    const fd = new FormData();
    fd.append('image', imageFile);
    fd.append('language', langSelect.value);
    btn.disabled = true;
    btn.lastChild.textContent = 'Reading screenshot…';
    try {
      const data = await SS.api('/api/analyze', { method: 'POST', body: fd });
      data.imageUrl = imageUrl;
      resultsSection.hidden = false;
      SS.renderResult(resultsRoot, data, { onAgain: () => $('inbox').scrollIntoView({ behavior: 'smooth' }), againLabel: 'Check another screenshot' });
      resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
      showError(e.message);
    } finally {
      btn.disabled = false;
      btn.lastChild.textContent = 'Analyze screenshot';
    }
  });

  // ---------------------------------------------------------------- start
  (async function start() {
    const params = new URLSearchParams(location.search);
    const g = params.get('gmail');
    if (g) {
      history.replaceState(null, '', location.pathname + '#inbox');
      const messages = {
        denied: 'Gmail access was not granted, so nothing was connected.',
        failed: 'Google sign-in failed. Check the client ID, secret and redirect URI in the README, then try again.',
        bad_state: 'The sign-in link expired. Click Connect Gmail again.',
        not_configured: 'Gmail is not set up yet. Add client_secret.json (see README), then restart the app.',
      };
      state.pendingError = messages[g] || null;
    }
    await loadGmailStatus();
    setMode(state.gmail.connected || !state.gmail.configured ? (state.gmail.connected ? 'gmail' : 'demo') : 'gmail');
    if (state.pendingError) showError(state.pendingError);  // after setMode, which clears old errors
    if (g) $('inbox').scrollIntoView();
  })();
})();
