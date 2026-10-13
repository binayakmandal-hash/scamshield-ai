/* ScamShield AI: renders an analysis result (used on the home page and saved-analysis page).
 *
 * Two views of the same analysis:
 *  - Evidence board (default): the message marked up like a detective's notes. Each risky phrase
 *    is highlighted in turn, a handwritten note explains it in the margin, and the score is circled
 *    by hand with a ledger showing exactly how it was built.
 *  - Simple mode (for parents and grandparents): one big answer, three plain reasons and big buttons.
 */
(function () {
  'use strict';
  const SS = window.SS;
  const el = SS.el;
  const icon = SS.icon;

  const SEV_RANK = { low: 1, medium: 2, high: 3 };
  const SEV_LABEL = { low: 'Weak signal', medium: 'Moderate', high: 'Strong signal' };
  const URL_SEV = { high: 'high', medium: 'medium', low: 'low' };
  const SCORE_DISCLAIMER = 'This score represents detected warning signals, not proof that the message is fraudulent.';
  const HEADLINE = {
    'Very High Risk': 'Very likely a scam',
    'High Risk': 'Likely a scam',
    Suspicious: 'Be careful with this one',
    'Low Risk': 'No scam signs found',
  };
  const svgNS = 'http://www.w3.org/2000/svg';

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

  function svg(viewBox, w, h, ...paths) {
    const s = document.createElementNS(svgNS, 'svg');
    s.setAttribute('viewBox', viewBox);
    s.setAttribute('width', w);
    s.setAttribute('height', h);
    s.setAttribute('aria-hidden', 'true');
    paths.forEach((d) => {
      const p = document.createElementNS(svgNS, 'path');
      p.setAttribute('d', d);
      p.setAttribute('pathLength', '1');
      s.appendChild(p);
    });
    return s;
  }

  /** Count a number up from 0, unless the person prefers reduced motion. */
  function countUp(node, to, delay, ms) {
    if (SS.reducedMotion()) { node.textContent = String(to); return; }
    node.textContent = '0';
    setTimeout(() => {
      const t0 = performance.now();
      const step = (t) => {
        const k = Math.min(1, (t - t0) / ms);
        node.textContent = String(Math.round(to * (1 - Math.pow(1 - k, 3))));
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }, delay);
  }

  /** The score, circled by hand. */
  function ringScore(score, delay) {
    const num = el('b', { class: 'ring__num', text: String(score) });
    countUp(num, score, delay * 1000 + 250, 800);
    return el('div', { class: 'ring', role: 'img', 'aria-label': `Risk score ${score} out of 100`, style: { '--d': `${delay}s` } },
      svg('0 0 150 104', 150, 104, 'M118 20 C140 34 142 66 118 84 C94 102 44 102 22 84 C2 66 6 32 30 18 C52 4 96 6 122 24'),
      num);
  }

  function cardTitle(iconName, title, small) {
    return el('h3', { class: 'card__title' }, icon(iconName), title, small ? el('small', { text: small }) : null);
  }

  /** "Send to family": an editable, link-free warning note to forward. */
  function familyNote(box, btn, context) {
    return async () => {
      btn.disabled = true;
      box.hidden = false;
      const title = cardTitle('user', 'A note for your family', 'Edit it, then copy or share');
      box.replaceChildren(title, el('p', { class: 'muted', text: 'Writing a short note…' }));
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
        box.replaceChildren(title,
          el('p', { class: 'muted', style: { marginBottom: '10px' }, text: 'Forward this to a parent, grandparent or friend who received the message. It contains no links from the original.' }),
          area, el('div', { class: 'verdict__actions' }, copy, share, status));
        box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } catch (e) {
        box.replaceChildren(title, el('p', { class: 'notice', text: e.message }));
      } finally { btn.disabled = false; }
    };
  }

  /** Spam / Block / It's safe buttons, when the message came from the inbox. */
  function inboxActions(opts, big) {
    if (!opts.onAction) return [];
    const defs = [['spam', 'Move to spam', 'btn--danger-solid'], ['block', 'Block sender', 'btn--ghost'], ['safe', "It's safe", 'btn--ghost']];
    return defs.filter(([a]) => !big || a === 'spam').map(([a, label, cls]) => {
      const b = el('button', { class: `btn ${big ? 'btn--xl btn--ink' : cls}`, type: 'button' }, big ? 'Move it to spam' : label);
      b.addEventListener('click', async () => {
        b.disabled = true;
        const ok = await opts.onAction(a);
        if (ok) b.textContent = a === 'spam' ? 'Moved to spam' : a === 'block' ? 'Sender blocked' : 'Marked safe';
        else b.disabled = false;
      });
      return b;
    });
  }

  /**
   * Render a result.
   * data: { message, result, source, imageUrl, ocr, language, id }
   * opts: { saved, onAgain, againLabel, onAction(action) -> Promise<bool>, full }
   */
  SS.renderResult = function (root, data, opts = {}) {
    SS.lastResult = { root, data, opts };
    if (SS.isSimple && SS.isSimple() && !opts.full) return renderSimple(root, data, opts);

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

    // ---------------- evidence board ----------------
    const detail = el('div', { class: 'evidence__detail is-empty', 'aria-live': 'polite' },
      flags.length ? 'Select a highlighted phrase to see why it was flagged.' : 'Nothing in this message was flagged.');
    const textBox = el('div', { class: 'evidence__text' });
    const ranges = buildRanges(message, flags, urls);
    const marks = [];
    let pos = 0;
    const HL_START = 0.5, HL_STEP = 0.42;
    ranges.forEach((rg, idx) => {
      if (rg.start > pos) textBox.append(message.slice(pos, rg.start));
      const mark = el('button', {
        type: 'button', class: `hl sev-${rg.sev}`, 'data-idx': idx,
        style: { '--d': `${HL_START + idx * HL_STEP}s` },
        'aria-label': `Flagged: ${message.slice(rg.start, rg.end)}. Show why.`,
      }, message.slice(rg.start, rg.end));
      mark.addEventListener('click', () => select(idx));
      marks.push(mark);
      textBox.append(mark);
      pos = rg.end;
    });
    if (pos < message.length) textBox.append(message.slice(pos));
    const boardDone = HL_START + Math.max(ranges.length, 1) * HL_STEP;

    // Handwritten margin note for each highlight: the flag's short title, or the link's verdict.
    const noteText = (rg) => {
      const ref = rg.refs[0];
      if (ref.type === 'flag') return (flags[ref.i].title || '').toLowerCase();
      const u = urls[ref.i];
      return u.resembles_brand ? `not really ${u.resembles_brand}` : `${u.risk} risk link`;
    };
    const notes = el('div', { class: 'mnotes', 'aria-hidden': 'true' });
    const noteEls = ranges.map((rg, idx) => {
      const n = el('div', { class: 'mnote', style: { '--d': `${HL_START + idx * HL_STEP + 0.3}s` } },
        svg('0 0 60 22', 52, 19, 'M56 16 C40 6 22 4 6 11', 'M13 6 L5 11 L13 16'),
        el('span', { text: noteText(rg) }));
      notes.append(n);
      return n;
    });
    const paper = el('div', { class: 'paper' }, textBox, notes);

    function layoutNotes() {
      const narrow = paper.clientWidth < 600;
      paper.classList.toggle('paper--narrow', narrow);
      if (narrow) return;
      const base = paper.getBoundingClientRect().top;
      let floor = 0;
      noteEls.forEach((n, i) => {
        const want = marks[i].getBoundingClientRect().top - base - 6;
        const top = Math.max(want, floor);
        n.style.top = `${top}px`;
        floor = top + n.offsetHeight + 10;
      });
      paper.style.minHeight = `${Math.max(floor, textBox.offsetHeight)}px`;
    }
    if (window.ResizeObserver) new ResizeObserver(() => layoutNotes()).observe(paper);

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

    const detailHolder = el('div', { 'aria-live': 'polite' });
    function select(idx, pulse) {
      marks.forEach((m) => m.classList.remove('is-selected', 'is-pulse'));
      const m = marks[idx];
      if (!m) return;
      m.classList.add('is-selected');
      if (pulse) { void m.offsetWidth; m.classList.add('is-pulse'); }
      detail.replaceWith(detailHolder);
      detailHolder.replaceChildren(...ranges[idx].refs.map(refDetail));
    }

    const evidenceCard = el('section', { class: 'card evidence' },
      cardTitle('search', data.source === 'screenshot' ? 'Extracted message' : 'The message, marked up', ranges.length ? 'Tap a highlight to see why' : ''),
      data.imageUrl ? (() => {
        const shot = el('div', { class: 'shot' });
        const img = el('img', { src: data.imageUrl, alt: 'Your uploaded screenshot (tap to enlarge)' });
        img.addEventListener('click', () => shot.classList.toggle('is-open'));
        shot.append(img, el('p', { text: 'Original screenshot (kept only in your browser). The text below was extracted from it automatically' + (data.ocr && data.ocr.notes ? `. Note: ${data.ocr.notes}` : '.') }));
        return shot;
      })() : null,
      paper,
      detail);

    // ---------------- score: circled by hand, with the ledger ----------------
    const breakdown = r.score_breakdown || [];
    const tags = [
      el('span', { class: 'tag', title: r.engine === 'ai' ? 'Open-weight model, checked by ScamShield validators' : 'Built-in pattern rules' },
        icon(r.engine === 'ai' ? 'sparkles' : 'cpu'), r.engine === 'ai' ? (r.model || 'AI analysis') : 'Rule engine'),
      data.source === 'screenshot' ? el('span', { class: 'tag' }, icon('image'), 'From screenshot') : null,
      r.language && r.language !== 'auto' ? el('span', { class: 'tag' }, icon('globe'), r.language) : null,
    ];
    const scoreHead = el('div', { class: 'scorehead' },
      ringScore(r.risk_score, Math.min(boardDone, 2.2)),
      el('div', {},
        el('h2', { class: 'scorehead__title', id: 'verdict-h' }, HEADLINE[r.risk_level] || r.risk_level),
        el('p', { class: 'scorehead__sub' }, `${r.risk_level}. Score out of 100, and every point is backed by something in the message.`)));

    const ledger = el('div', { class: 'ledger' },
      el('h4', { text: `How we got ${r.risk_score}` }),
      breakdown.length
        ? el('ol', {}, breakdown.map((b, i) => el('li', { class: b.points < 0 ? 'is-negative' : null, style: { '--d': `${Math.min(boardDone, 2.2) + 0.5 + i * 0.12}s` } },
          el('span', { class: 'ledger__what' },
            b.evidence ? el('span', { class: 'ledger__q', title: b.evidence, text: `“${b.evidence}”` }) : null,
            el('span', { class: 'ledger__why', text: b.signal })),
          el('b', { class: 'ledger__pts', text: b.points < 0 ? `−${Math.abs(b.points)}` : `+${b.points}` }))))
        : el('p', { class: 'muted', text: 'No warning signals contributed to the score.' }),
      el('div', { class: 'ledger__total' }, el('span', { text: 'Total' }), el('b', { text: String(r.risk_score) })),
      el('p', { class: 'breakdown__disclaimer', text: SCORE_DISCLAIMER }));

    const planBox = el('div', { class: 'card', hidden: true });
    const eliBox = el('div', { class: 'card', hidden: true });
    const famBox = el('div', { class: 'card', hidden: true });
    const planBtn = el('button', { class: 'btn btn--ghost', type: 'button' }, icon('list'), 'What should I do now?');
    const eliBtn = el('button', { class: 'btn btn--ghost', type: 'button' }, icon('smile'), "Explain like I'm 12");
    const famBtn = el('button', { class: 'link-btn link-btn--strong', type: 'button' }, 'Warn my family');
    famBtn.addEventListener('click', familyNote(famBox, famBtn, context));

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

    const scoreCard = el('section', { class: 'card scorecard', 'aria-labelledby': 'verdict-h' },
      scoreHead,
      el('div', { class: 'scorecard__tags' }, tags),
      r.categories && r.categories.length
        ? el('div', { class: 'cats', 'aria-label': 'Possible categories' }, r.categories.map((c) => el('span', { class: 'cat', text: c })))
        : null,
      ledger);

    wrap.append(el('div', { class: 'board' }, evidenceCard, scoreCard));

    // summary + actions under the board
    const actions = inboxActions(opts, false);
    wrap.append(el('section', { class: 'card verdict' },
      el('p', { class: 'verdict__summary', text: r.summary }),
      el('p', { class: 'verdict__note' }, icon('info'), r.confidence_note),
      r.notice ? el('p', { class: 'notice', style: { marginTop: '12px' }, text: r.notice }) : null,
      el('div', { class: 'verdict__actions' }, actions, planBtn, eliBtn, famBtn)));
    wrap.append(planBox, eliBox, famBox);

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
            fact('Domain', u.domain || u.host || 'unknown'),
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
    requestAnimationFrame(layoutNotes);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(layoutNotes);
  };

  // ======================================================================
  // Simple mode
  // ======================================================================
  const T = {
    en: {
      scam: 'This message is a scam.', risky: 'Be careful with this message.', safe: 'No scam signs found.',
      scamSub: "Don't click any link. Don't share any OTP, PIN or card number.",
      riskySub: 'Check with the company on its official number before you do anything.',
      safeSub: 'It still never hurts to check. Never share an OTP or PIN with anyone.',
      why: 'Why we think so', family: 'Ask my family first', clicked: 'I already clicked the link',
      details: 'Show all the details', helpTitle: 'Do these now', helpLine: 'Call 1930, the national cyber-crime helpline, and your bank.',
    },
    hi: {
      scam: 'यह संदेश एक धोखा है।', risky: 'इस संदेश से सावधान रहें।', safe: 'धोखे के कोई संकेत नहीं मिले।',
      scamSub: 'किसी भी लिंक पर क्लिक न करें। कोई OTP, PIN या कार्ड नंबर साझा न करें।',
      riskySub: 'कुछ भी करने से पहले कंपनी के आधिकारिक नंबर पर जाँच करें।',
      safeSub: 'फिर भी सावधान रहें। किसी को भी OTP या PIN न बताएँ।',
      why: 'हमें ऐसा क्यों लगता है', family: 'पहले परिवार से पूछें', clicked: 'मैंने लिंक पर क्लिक कर दिया है',
      details: 'पूरी जानकारी देखें', helpTitle: 'अभी ये करें', helpLine: 'राष्ट्रीय साइबर अपराध हेल्पलाइन 1930 और अपने बैंक को फ़ोन करें।',
    },
    bn: {
      scam: 'এই বার্তাটি একটি প্রতারণা।', risky: 'এই বার্তাটি নিয়ে সাবধান থাকুন।', safe: 'প্রতারণার কোনো লক্ষণ পাওয়া যায়নি।',
      scamSub: 'কোনো লিঙ্কে ক্লিক করবেন না। কোনো OTP, PIN বা কার্ড নম্বর কাউকে দেবেন না।',
      riskySub: 'কিছু করার আগে কোম্পানির অফিসিয়াল নম্বরে যাচাই করুন।',
      safeSub: 'তবুও সাবধান থাকুন। কাউকে OTP বা PIN বলবেন না।',
      why: 'কেন আমরা এমন মনে করছি', family: 'আগে পরিবারকে জিজ্ঞেস করুন', clicked: 'আমি লিঙ্কে ক্লিক করে ফেলেছি',
      details: 'সব বিস্তারিত দেখুন', helpTitle: 'এখনই এগুলো করুন', helpLine: 'জাতীয় সাইবার ক্রাইম হেল্পলাইন 1930 এবং আপনার ব্যাংকে ফোন করুন।',
    },
  };

  function renderSimple(root, data, opts) {
    const r = data.result;
    const lang = T[data.language] ? data.language : 'en';
    const t = T[lang];
    const flags = [...(r.red_flags || [])].sort((a, b) => (SEV_RANK[b.severity] || 0) - (SEV_RANK[a.severity] || 0));
    const level = r.risk_score >= 60 ? 'scam' : r.risk_score >= 30 ? 'risky' : 'safe';
    const context = () => ({ message: data.message || '', analysis: r, language: data.language || 'en' });

    root.textContent = '';
    const band = el('section', { class: `simple-verdict simple-verdict--${level}`, 'aria-labelledby': 'simple-h' },
      el('span', { class: 'simple-verdict__icon' }, icon(level === 'safe' ? 'shield-check' : 'alert')),
      el('div', {},
        el('h2', { id: 'simple-h', text: t[level] }),
        el('p', { text: t[`${level}Sub`] })));

    const reasons = flags.slice(0, 3).map((f, i) => el('article', { class: 'simple-reason', style: { '--d': `${0.5 + i * 0.12}s` } },
      el('span', { class: 'simple-reason__n', text: String(i + 1) }),
      el('h3', { text: f.title }),
      el('p', {}, f.evidence ? [el('b', { text: `“${f.evidence}”` }), ' '] : null, f.explanation)));

    const famBox = el('div', { class: 'card', hidden: true });
    const helpBox = el('div', { class: 'card simple-help', hidden: true });
    const famBtn = el('button', { class: 'btn btn--xl btn--outline', type: 'button' }, t.family);
    famBtn.addEventListener('click', familyNote(famBox, famBtn, context));
    const clickedBtn = el('button', { class: 'btn btn--xl btn--alarm', type: 'button' }, t.clicked);
    clickedBtn.addEventListener('click', async () => {
      clickedBtn.disabled = true;
      helpBox.hidden = false;
      helpBox.replaceChildren(el('h3', { text: t.helpTitle }), el('p', { class: 'simple-help__line', text: t.helpLine }), el('p', { class: 'muted', text: '…' }));
      helpBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      try {
        const res = await SS.postJSON('/api/chat', { ...context(), question: 'I already clicked the link in this message. What should I do right now, step by step?', history: [] });
        helpBox.replaceChildren(el('h3', { text: t.helpTitle }), el('p', { class: 'simple-help__line', text: t.helpLine }), el('p', { class: 'simple-help__answer', text: res.answer }));
      } catch (e) {
        helpBox.replaceChildren(el('h3', { text: t.helpTitle }), el('p', { class: 'simple-help__line', text: t.helpLine }));
      } finally { clickedBtn.disabled = false; }
    });

    const details = el('button', { type: 'button', class: 'link-btn simple-details' }, icon('search'), t.details);
    details.addEventListener('click', () => SS.renderResult(root, data, { ...opts, full: true }));

    root.append(el('div', { class: 'simple' },
      band,
      reasons.length ? el('h3', { class: 'simple__why', text: t.why }) : null,
      reasons.length ? el('div', { class: 'simple-reasons' }, reasons) : null,
      el('div', { class: 'simple-actions' }, inboxActions(opts, true), famBtn, level === 'safe' ? null : clickedBtn),
      famBox, helpBox,
      el('div', { class: 'simple__foot' }, details,
        opts.onAgain ? el('button', { class: 'link-btn', type: 'button', onclick: opts.onAgain }, opts.againLabel || 'Check another message') : null)));
  }

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
