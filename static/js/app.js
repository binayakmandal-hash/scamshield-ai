/* ScamShield AI — shared helpers (loaded on every page). */
(function () {
  'use strict';
  const SS = (window.SS = window.SS || {});

  /** Fetch JSON and throw a readable Error when the API reports a problem. */
  SS.api = async function (url, options = {}) {
    let res;
    try {
      res = await fetch(url, options);
    } catch (e) {
      throw new Error('Could not reach the ScamShield server. Check that app.py is still running.');
    }
    let data;
    try { data = await res.json(); } catch (e) { data = { ok: false, error: `Server error (${res.status}).` }; }
    if (!res.ok || data.ok === false) throw new Error(data.error || `Request failed (${res.status}).`);
    return data;
  };

  SS.postJSON = (url, body) =>
    SS.api(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

  /** Tiny DOM builder. Text is always inserted as text (never HTML) to keep message content inert. */
  SS.el = function (tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value === null || value === undefined || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key === 'style' && typeof value === 'object') Object.assign(node.style, value);
      else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? '' : value);
    }
    append(node, children);
    return node;
  };
  function append(node, children) {
    for (const child of children.flat(Infinity)) {
      if (child === null || child === undefined || child === false) continue;
      node.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
    }
  }

  SS.icon = function (name, cls) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'ic' + (cls ? ' ' + cls : ''));
    svg.setAttribute('aria-hidden', 'true');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', '#i-' + name);
    svg.appendChild(use);
    return svg;
  };

  SS.riskClass = (level) =>
    ({ 'Low Risk': 'risk-low', Suspicious: 'risk-susp', 'High Risk': 'risk-high', 'Very High Risk': 'risk-vhigh' }[level] ||
    'risk-low');

  SS.formatDate = function (iso) {
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  };

  SS.store = {
    get(key) { try { return localStorage.getItem(key); } catch (e) { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* storage unavailable */ } },
  };

  // ---- theme toggle -------------------------------------------------------
  const root = document.documentElement;
  const toggle = document.getElementById('theme-toggle');
  function effectiveTheme() {
    if (root.dataset.theme) return root.dataset.theme;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  if (toggle) {
    toggle.addEventListener('click', () => {
      const next = effectiveTheme() === 'dark' ? 'light' : 'dark';
      root.dataset.theme = next;
      SS.store.set('ss-theme', next);
      toggle.setAttribute('aria-label', `Switch to ${next === 'dark' ? 'light' : 'dark'} theme`);
    });
  }

  // ---- mobile menu --------------------------------------------------------
  const menuBtn = document.getElementById('nav-menu');
  const links = document.getElementById('nav-links');
  if (menuBtn && links) {
    menuBtn.addEventListener('click', () => {
      const open = links.classList.toggle('is-open');
      menuBtn.setAttribute('aria-expanded', String(open));
    });
    links.addEventListener('click', (e) => {
      if (e.target.closest('a')) { links.classList.remove('is-open'); menuBtn.setAttribute('aria-expanded', 'false'); }
    });
  }

  // ---- local times --------------------------------------------------------
  document.querySelectorAll('[data-local-time]').forEach((t) => { t.textContent = SS.formatDate(t.getAttribute('datetime')); });
})();
