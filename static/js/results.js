/* ScamShield AI — renders an analysis result (used on the home page and saved-analysis page). */
(function () {
  'use strict';
  const SS = window.SS;
  const el = SS.el;
  const icon = SS.icon;

  const SEV_RANK = { low: 1, medium: 2, high: 3 };
  const SEV_LABEL = { low: 'Weak signal', medium: 'Moderate', high: 'Strong signal' };
  const URL_SEV = { high: 'high', medium: 'medium', low: 'low' };
  const SCORE_DISCLAIMER = 'This score represents detected warning signals, not proof that the message is fraudulent.';

  const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  /** Locate a phrase in the message, tolerating whitespace and case differences. */
  function findRange(text, phrase) {
    if (!phrase) return null;
    const parts = phrase.trim().split(/\s+/).filter(Boolean).map(escapeRe);
    if (!parts.length) return null;
    const m = new RegExp(parts.join('\\s+'), 'i').exec(text);
    return m ? { start: m.index, end: m.index + m[0].length } : null;
  }

  /** Build non-overlapping highlight ranges from red flags and URLs. */
  function buildRanges(text, flags, urls) {
    const ranges = [];
    flags.forEach((f, i) => {
      const r = findRange(text, f.evidence);
      if (r) ranges.push({ ...r, refs: [{ type: 'flag', i }], sev: f.severity || 'medium' });
    });
    urls.forEach((u, i) => {
      const r = findRange(text, u.url);
      if (r) ranges.push({ ...r, refs: [{ type: 'url', i }], sev: URL_SEV[u.risk] || 'low' });
    });
    ranges.sort((a, b) => a.start - b.start || b.end - a.end);
    const merged = [];
    for (const r of ranges) {
      const last = merged[merged.length - 1];
      if (last && r.start < last.end) {
        last.end = Math.max(last.end, r.end);
        last.refs.push(...r.refs);
        if (SEV_RANK[r.sev] > SEV_RANK[last.sev]) last.sev = r.sev;
      } else merged.push({ ...r, refs: [...r.refs] });
    }
    return merged;
  }

  function gauge(score) {
    const len = Math.PI * 85;
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 200 112');
    svg.setAttribute('aria-hidden', 'true');
    const mk = (cls) => {
      const p = document.createElementNS(ns, 'path');
      p.setAttribute('d', 'M15 100 A85 85 0 0 1 185 100');
      p.setAttribute('fill', 'none');
      p.setAttribute('stroke-width', '16');
      p.setAttribute('stroke-linecap', 'round');
      p.setAttribute('class', cls);
      return p;
    };
    const track = mk('gauge__track');
    const fill = mk('gauge__fill');
    fill.setAttribute('stroke-dasharray', String(len));
    fill.setAttribute('stroke-dashoffset', String(len));
    svg.append(track, fill);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      fill.setAttribute('stroke-dashoffset', String(len * (1 - Math.max(0, Math.min(100, score)) / 100)));
    }));
    return el('div', { class: 'gauge', role: 'img', 'aria-label': `Risk score ${score} out of 100` },
      svg, el('div', { class: 'gauge__value' }, el('b', { text: String(score) }), el('span', { text: 'out of 100' })));
  }

  function cardTitle(iconName, title, small) {
    return el('h3', { class: 'card__title' }, icon(iconName), title, small ? el('small', { text: small }) : null);
  }

  /**
   * Render a result.
   * data: { message, result, source, imageUrl, ocr, language, id }
   * opts: { saved: boolean, onAgain: fn }
   */
  SS.renderResult = function (root, data, opts = {}) {
    const r = data.result;
    const message = data.message || '';
    const flags = r.red_flags || [];
    const urls = r.detected_urls || [];
    const sender = r.sender_analysis || {};
    const risk = SS.riskClass(r.risk_level);
    const lang = data.language || 'en';
    const context = () => ({ message, analysis: r, language: lang });

    root.textContent = '';
    const wrap = el('div', { class: `result ${risk}` });

    // ---------------- verdict ----------------
    const planBox = el('div', { class: 'card', hidden: true });
    const eliBox = el('div', { class: 'card', hidden: true });

    const planBtn = el('button', { class: 'btn btn--primary', type: 'button' }, icon('list'), 'What should I do now?');
    const eliBtn = el('button', { class: 'btn btn--soft', type: 'button' }, icon('smile'), "Explain like I'm 12");
    const famBtn = el('button', { class: 'btn btn--soft', type: 'button' }, icon('user'), 'Send to family');
    const famBox = el('div', { class: 'card', hidden: true });

    famBtn.addEventListener('click', async () => {
      famBtn.disabled = true;
      famBox.hidden = false;
      const title = cardTitle('user', 'A note for your family', 'Edit it, then copy or share');
      famBox.replaceChildren(title, el('p', { class: 'muted', text: 'Writing a short note…' }));
      try {
        const res = await SS.postJSON('/api/family-note', context());
        const area = el('textarea', { class: 'family-note', rows: '5', 'aria-label': 'Message for your family' });
        area.value = res.note;
        const status = el('span', { class: 'muted', 'aria-live': 'polite' });
        const copy = el('button', { class: 'btn btn--primary', type: 'button' }, icon('check'), 'Copy message');
        copy.addEventListener('click', async () => {
          try { await navigator.clipboard.writeText(area.value); status.textContent = 'Copied.'; }
          catch (e) { area.select(); status.textContent = 'Press Ctrl+C to copy.'; }
        });
        const share = el('a', { class: 'btn btn--ghost', target: '_blank', rel: 'noopener' }, icon('send'), 'Share on WhatsApp');
        const syncShare = () => share.setAttribute('href', 'https://wa.me/?text=' + encodeURIComponent(area.value));
        area.addEventListener('input', syncShare);
        syncShare();
        famBox.replaceChildren(title,
          el('p', { class: 'muted', style: { marginBottom: '10px' }, text: 'Forward this to a parent, grandparent or friend who received the message. It contains no links from the original.' }),
          area, el('div', { class: 'verdict__actions' }, copy, share, status));
        famBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } catch (e) {
        famBox.replaceChildren(title, el('p', { class: 'notice', text: e.message }));
      } finally { famBtn.disabled = false; }
    });

    planBtn.addEventListener('click', async () => {
      planBtn.disabled = true;
      planBox.hidden = false;
      planBox.replaceChildren(cardTitle('list', 'Your 3-step action plan'), el('p', { class: 'muted', text: 'Preparing a plan for this message…' }));
      try {
        const res = await SS.postJSON('/api/action-plan', context());
        planBox.replaceChildren(cardTitle('list', 'Your 3-step action plan'),
          el('ol', { class: 'plan' }, res.steps.map((s) => el('li', {}, el('h4', { text: s.title }), el('p', { text: s.detail })))));
        planBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } catch (e) {
        planBox.replaceChildren(cardTitle('list', 'Your 3-step action plan'), el('p', { class: 'notice', text: e.message }));
      } finally { planBtn.disabled = false; }
    });

    eliBtn.addEventListener('click', async () => {
      eliBtn.disabled = true;
      eliBox.hidden = false;
      eliBox.replaceChildren(cardTitle('smile', 'In simple words'), el('p', { class: 'muted', text: 'Simplifying…' }));
      try {
        const res = await SS.postJSON('/api/eli12', context());
        eliBox.replaceChildren(cardTitle('smile', 'In simple words'), el('p', { class: 'eli12', text: res.explanation }));
        eliBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } catch (e) {
        eliBox.replaceChildren(cardTitle('smile', 'In simple words'), el('p', { class: 'notice', text: e.message }));
      } finally { eliBtn.disabled = false; }
    });

    const tags = [
      el('span', { class: 'tag', title: r.engine === 'ai' ? 'Open-weight model, checked by ScamShield validators' : 'Built-in pattern rules' },
        icon(r.engine === 'ai' ? 'sparkles' : 'cpu'), r.engine === 'ai' ? (r.model || 'AI analysis') : 'Rule engine'),
      data.source === 'screenshot' ? el('span', { class: 'tag' }, icon('image'), 'From screenshot') : null,
      r.language && r.language !== 'auto' ? el('span', { class: 'tag' }, icon('globe'), r.language) : null,
    ];

    wrap.append(el('section', { class: 'card verdict', 'aria-labelledby': 'verdict-h' },
      gauge(r.risk_score),
      el('div', {},
        el('div', { class: 'verdict__level' },
          el('h2', { class: 'level-badge', id: 'verdict-h' }, el('span', { class: 'risk-dot' }), r.risk_level), tags),
        r.categories && r.categories.length
          ? el('div', { class: 'cats', 'aria-label': 'Possible categories' }, r.categories.map((c) => el('span', { class: 'cat', text: c })))
          : null,
        el('p', { class: 'verdict__summary', text: r.summary }),
        el('p', { class: 'verdict__note' }, icon('info'), r.confidence_note),
        r.notice ? el('p', { class: 'notice', style: { marginTop: '12px' }, text: r.notice }) : null,
        el('div', { class: 'verdict__actions' }, planBtn, eliBtn, famBtn),
      )));
    wrap.append(planBox, eliBox, famBox);

    // ---------------- evidence + score ----------------
    const detail = el('div', { class: 'evidence__detail is-empty', 'aria-live': 'polite' },
      flags.length ? 'Select a highlighted phrase to see why it was flagged.' : 'Nothing in this message was flagged.');
    const textBox = el('div', { class: 'evidence__text' });
    const ranges = buildRanges(message, flags, urls);
    const marks = [];
    let pos = 0;
    ranges.forEach((rg, idx) => {
      if (rg.start > pos) textBox.append(message.slice(pos, rg.start));
      const mark = el('button', {
        type: 'button', class: `hl sev-${rg.sev}`, 'data-idx': idx,
        'aria-label': `Flagged: ${message.slice(rg.start, rg.end)}. Show why.`,
      }, message.slice(rg.start, rg.end));
      mark.addEventListener('click', () => select(idx));
      marks.push(mark);
      textBox.append(mark);
      pos = rg.end;
    });
    if (pos < message.length) textBox.append(message.slice(pos));

    function refDetail(ref) {
      if (ref.type === 'flag') {
        const f = flags[ref.i];
        return el('div', { class: `evidence__detail sev-${f.severity}` },
          el('h4', {}, f.title, el('span', { class: 'sev', text: SEV_LABEL[f.severity] || 'Signal' })),
          f.evidence ? el('q', { text: f.evidence }) : null,
          el('p', { text: f.explanation }),
          f.evidence_verified === false ? el('p', { class: 'unverified', text: 'This wording was paraphrased by the AI and could not be found word-for-word in the message, so treat it as an interpretation.' }) : null);
      }
      const u = urls[ref.i];
      return el('div', { class: `evidence__detail sev-${URL_SEV[u.risk]}` },
        el('h4', {}, 'Link to verify independently', el('span', { class: 'sev', text: `${u.risk} risk` })),
        el('q', { text: u.defanged }),
        el('p', { text: u.flags.length ? u.flags.join('. ') + '.' : 'No unusual characteristics found in the link text.' }));
    }

    function select(idx, pulse) {
      marks.forEach((m) => m.classList.remove('is-selected', 'is-pulse'));
      const m = marks[idx];
      if (!m) return;
      m.classList.add('is-selected');
      if (pulse) { void m.offsetWidth; m.classList.add('is-pulse'); }
      detail.replaceWith(detailHolder);
      detailHolder.replaceChildren(...ranges[idx].refs.map(refDetail));
    }
    const detailHolder = el('div', { 'aria-live': 'polite' });

    const evidenceCard = el('section', { class: 'card evidence' },
      cardTitle('search', data.source === 'screenshot' ? 'Extracted message' : 'Evidence', flags.length || urls.length ? 'Click a highlight to see why' : ''),
      data.imageUrl ? (() => {
        const shot = el('div', { class: 'shot' });
        const img = el('img', { src: data.imageUrl, alt: 'Your uploaded screenshot (tap to enlarge)' });
        img.addEventListener('click', () => shot.classList.toggle('is-open'));
        shot.append(img, el('p', { text: 'Original screenshot (kept only in your browser). The text below was extracted from it automatically' + (data.ocr && data.ocr.notes ? `. Note: ${data.ocr.notes}` : '.') }));
        return shot;
      })() : null,
      textBox,
      ranges.length ? el('div', { class: 'evidence__legend' },
        el('span', { class: 'sev-high' }, el('i'), 'Strong signal'),
        el('span', { class: 'sev-medium' }, el('i'), 'Moderate'),
        el('span', { class: 'sev-low' }, el('i'), 'Weak signal')) : null,
      detail);

    const breakdown = r.score_breakdown || [];
    const maxPts = Math.max(25, ...breakdown.map((b) => Math.abs(b.points)));
    const scoreCard = el('section', { class: 'card' },
      cardTitle('flag', 'How the score was built', `${r.risk_score}/100`),
      breakdown.length
        ? el('ol', { class: 'breakdown' }, breakdown.map((b, i) => el('li', { class: b.points < 0 ? 'is-negative' : null },
          el('b', { text: b.points < 0 ? `−${Math.abs(b.points)}` : `+${b.points}` }),
          el('span', { class: 'breakdown__name', text: b.signal }),
          el('span', { class: 'breakdown__bar' }, el('span', { style: { width: `${(Math.abs(b.points) / maxPts) * 100}%`, animationDelay: `${i * 70}ms` } })),
          b.evidence ? el('span', { class: 'breakdown__ev', title: b.evidence, text: `“${b.evidence}”` }) : null)))
        : el('p', { class: 'muted', text: 'No warning signals contributed to the score.' }),
      el('div', { class: 'breakdown__total' }, el('span', { text: 'Total' }), el('span', { text: `${r.risk_score} / 100` })),
      el('p', { class: 'breakdown__disclaimer', text: SCORE_DISCLAIMER }));

    wrap.append(el('div', { class: 'grid-2' }, evidenceCard, scoreCard));

    // ---------------- red flags ----------------
    const flagsCard = el('section', { class: 'card' }, cardTitle('alert', 'Red flags detected', `${flags.length} found`));
    if (flags.length) {
      flagsCard.append(el('ul', { class: 'flags' }, flags.map((f, i) => {
        const btn = el('button', { type: 'button', class: `flag sev-${f.severity}` },
          el('h4', {}, f.title, el('span', { class: 'sev', text: SEV_LABEL[f.severity] || 'Signal' })),
          f.evidence ? el('q', { text: f.evidence }) : null,
          el('p', { text: f.explanation }),
          f.evidence_verified === false ? el('span', { class: 'unverified', text: 'AI interpretation, not an exact quote' }) : null);
        btn.addEventListener('click', () => {
          const idx = ranges.findIndex((rg) => rg.refs.some((ref) => ref.type === 'flag' && ref.i === i));
          if (idx >= 0) {
            select(idx, true);
            marks[idx].scrollIntoView({ behavior: 'smooth', block: 'center' });
          } else {
            detail.replaceWith(detailHolder);
            detailHolder.replaceChildren(refDetail({ type: 'flag', i }));
            evidenceCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        });
        return el('li', {}, btn);
      })));
    } else {
      flagsCard.append(el('p', { class: 'muted', text: 'No common scam warning signs were found. That is not a guarantee of safety, so stay alert if the sender later asks for money, codes or personal details.' }));
    }
    if ((r.trust_signals || []).length) {
      flagsCard.append(el('h4', { style: { margin: '18px 0 0', fontSize: '1rem' }, text: 'Signs of a genuine sender' }),
        el('ul', { class: 'trust' }, r.trust_signals.map((t) => el('li', {}, icon('shield-check'),
          el('span', {}, el('strong', { text: t.title + '. ' }), t.explanation)))));
    }
    wrap.append(flagsCard);

    // ---------------- why + actions ----------------
    wrap.append(el('div', { class: 'grid-2 grid-2--even' },
      el('section', { class: 'card' }, cardTitle('bulb', 'Why this matters'), el('p', { class: 'prose', text: r.why_it_matters })),
      el('section', { class: 'card' }, cardTitle('shield-check', 'What you should do'),
        el('ul', { class: 'checklist' }, (r.recommended_actions || []).map((a) => el('li', {}, icon('check'), el('span', { text: a })))))));

    // ---------------- links + sender ----------------
    const side = [];
    if (urls.length) {
      side.push(el('section', { class: 'card' }, cardTitle('link', 'Detected links', `${urls.length}`),
        el('div', { class: 'urls' }, urls.map((u) => el('div', { class: 'url' },
          el('div', { class: 'url__head' },
            el('span', { class: 'url__text', text: u.defanged }),
            el('span', { class: `url__risk r-${u.risk}`, text: `${u.risk[0].toUpperCase()}${u.risk.slice(1)} risk` })),
          el('dl', { class: 'url__facts' },
            fact('Domain', u.domain || u.host || '—'),
            fact('HTTPS', u.uses_https === true ? 'Yes' : u.uses_https === false ? 'No (plain HTTP)' : 'Not shown'),
            fact('URL shortener', u.is_shortener ? 'Yes, destination hidden' : 'No'),
            fact('Resembles', u.resembles_brand ? `${u.resembles_brand} (not official)` : 'No known brand'),
            fact('Subdomains', u.subdomains && u.subdomains.length ? u.subdomains.join(', ') : 'None')),
          u.flags.length ? el('ul', { class: 'url__flags' }, u.flags.map((f) => el('li', { text: f }))) : null))),
        el('p', { class: 'safe-note' }, icon('shield'), 'Checked as text only. ScamShield never opens or visits links. Addresses are shown with [.] so they can\'t be clicked by accident.')));
    }
    if (sender.present) {
      const rows = [];
      const add = (k, v) => { if (v && (!Array.isArray(v) || v.length)) rows.push(el('dt', { text: k }), el('dd', { text: Array.isArray(v) ? v.join(', ') : v })); };
      add('Sender name', sender.sender_name);
      add('Email', (sender.emails || []).map((e) => e.address + (e.free_provider ? ' (free email provider)' : '')));
      add('Phone', (sender.phones || []).map((p) => `${p.number} (${p.format})`));
      add('SMS header', sender.sender_ids);
      add('UPI ID', sender.upi_ids);
      add('Claims to be', sender.claimed_organizations);
      if (sender.auth && (sender.auth.spf || sender.auth.dkim || sender.auth.dmarc)) {
        add('Sender verification', ['spf', 'dkim', 'dmarc'].filter((k) => sender.auth[k]).map((k) => `${k.toUpperCase()} ${sender.auth[k]}`));
      }
      side.push(el('section', { class: 'card' }, cardTitle('user', 'Sender details'),
        el('dl', { class: 'kv' }, rows),
        (sender.observations || []).length
          ? el('ul', { class: 'obs' }, sender.observations.map((o) => el('li', { class: o.level }, icon(o.level === 'warn' ? 'alert' : 'info'), el('span', { text: o.text }))))
          : null,
        el('p', { class: 'safe-note' }, icon('info'), 'Unusual details are reasons to verify, not proof that the sender is fake.')));
    }
    if (side.length === 2) wrap.append(el('div', { class: 'grid-2 grid-2--even' }, side));
    else side.forEach((s) => wrap.append(s));

    // ---------------- chat ----------------
    wrap.append(chatCard(context));

    // ---------------- footer ----------------
    wrap.append(el('div', { class: 'result__foot' },
      el('span', {}, data.id ? 'Saved to your history. ' : '', data.id && !opts.saved ? el('a', { href: `/analysis/${data.id}`, text: 'Open the saved copy' }) : null),
      opts.onAgain ? el('button', { class: 'btn btn--ghost', type: 'button', onclick: opts.onAgain }, icon('search'), opts.againLabel || 'Analyze another message') : null));

    root.append(wrap);
  };

  function fact(label, value) {
    return el('div', {}, el('dt', { text: label }), el('dd', { text: value }));
  }

  function chatCard(context) {
    const history = [];
    const log = el('div', { class: 'chat__log', 'aria-live': 'polite' },
      el('div', { class: 'chat__msg chat__msg--ai', text: 'Ask me anything about this message, such as which part is most worrying or how to check if it is real.' }));
    const input = el('input', { type: 'text', placeholder: 'Ask a question about this message', 'aria-label': 'Your question', maxlength: '500' });
    const send = el('button', { class: 'btn btn--primary', type: 'submit', 'aria-label': 'Send question' }, icon('send'));
    const form = el('form', { class: 'chat__form' }, input, send);

    async function ask(q) {
      q = q.trim();
      if (!q) return;
      log.append(el('div', { class: 'chat__msg chat__msg--user', text: q }));
      const typing = el('div', { class: 'chat__msg chat__msg--ai chat__msg--typing', text: 'Thinking…' });
      log.append(typing);
      log.scrollTop = log.scrollHeight;
      input.value = '';
      send.disabled = true;
      try {
        const res = await SS.postJSON('/api/chat', { ...context(), question: q, history });
        typing.textContent = res.answer;
        typing.classList.remove('chat__msg--typing');
        history.push({ role: 'user', content: q }, { role: 'assistant', content: res.answer });
      } catch (e) {
        typing.textContent = e.message;
      } finally {
        send.disabled = false;
        log.scrollTop = log.scrollHeight;
      }
    }
    form.addEventListener('submit', (e) => { e.preventDefault(); ask(input.value); });

    const suggestions = ['Why is this suspicious?', 'Which part should I be worried about?', 'How can I verify this company?',
      'What information should I never share?', 'I already clicked the link. What now?'];
    return el('section', { class: 'card chat' }, cardTitle('chat', 'Ask ScamShield AI'),
      el('div', { class: 'chat__suggest' }, suggestions.map((s) => el('button', { type: 'button', class: 'chip', text: s, onclick: () => ask(s) }))),
      log, form);
  }
})();
