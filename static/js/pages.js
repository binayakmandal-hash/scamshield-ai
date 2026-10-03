/* ScamShield AI — saved analysis, history and dashboard pages. */
(function () {
  'use strict';
  const SS = window.SS;
  const el = SS.el;
  const icon = SS.icon;
  const page = document.body.dataset.page;

  const LEVELS = ['Low Risk', 'Suspicious', 'High Risk', 'Very High Risk'];

  function emptyState(title, text) {
    return el('div', { class: 'empty' }, icon('shield-check', 'empty__icon'), el('h2', { text: title }), el('p', { class: 'muted', text }),
      el('a', { class: 'btn btn--primary', href: '/#inbox' }, icon('search'), 'Scan my inbox'));
  }

  function errorState(msg) {
    return el('p', { class: 'notice', text: msg });
  }

  // ---------------------------------------------------------------- saved analysis
  if (page === 'analysis') {
    const record = JSON.parse(document.getElementById('saved-analysis').textContent);
    SS.renderResult(document.getElementById('results-root'), {
      id: record.id, message: record.message, result: record.result, source: record.source, language: 'en',
    }, { saved: true });
  }

  // ---------------------------------------------------------------- history
  if (page === 'history') {
    const root = document.getElementById('history-root');
    const clearBtn = document.getElementById('clear-history');
    let confirmTimer = null;

    async function load() {
      try {
        const { items } = await SS.api('/api/history');
        root.textContent = '';
        clearBtn.hidden = !items.length;
        if (!items.length) {
          root.append(emptyState('No analyses yet', 'Messages you check will appear here so you can review them later.'));
          return;
        }
        items.forEach((it) => root.append(row(it)));
      } catch (e) { root.replaceChildren(errorState(e.message)); }
    }

    function row(it) {
      const del = el('button', { class: 'icon-btn', type: 'button', 'aria-label': 'Delete this analysis', title: 'Delete' }, icon('trash'));
      const node = el('article', { class: `h-row ${SS.riskClass(it.risk_level)}` },
        el('div', { class: 'h-row__risk' },
          el('strong', {}, el('span', { class: 'risk-dot' }), it.risk_level),
          el('span', { text: SS.formatDate(it.created_at) })),
        el('div', { class: 'h-row__body' },
          el('p', { class: 'h-row__preview', text: it.preview }),
          el('div', { class: 'h-row__meta' },
            el('span', { class: 'h-row__score', text: `Score ${it.risk_score}/100` }),
            it.source === 'screenshot' ? el('span', { class: 'tag' }, icon('image'), 'Screenshot') : null,
            (it.categories || []).map((c) => el('span', { class: 'cat', text: c })))),
        el('div', { class: 'h-row__actions' },
          el('a', { class: 'btn btn--ghost', href: `/analysis/${it.id}` }, icon('eye'), 'View analysis'), del));
      del.addEventListener('click', async () => {
        try {
          await SS.api(`/api/history/${it.id}`, { method: 'DELETE' });
          node.remove();
          if (!root.querySelector('.h-row')) load();
        } catch (e) { alertInline(e.message); }
      });
      return node;
    }

    function alertInline(msg) { root.prepend(errorState(msg)); }

    clearBtn.addEventListener('click', async () => {
      if (!clearBtn.classList.contains('is-confirming')) {
        clearBtn.classList.add('is-confirming');
        clearBtn.lastChild.textContent = 'Click again to delete everything';
        confirmTimer = setTimeout(() => {
          clearBtn.classList.remove('is-confirming');
          clearBtn.lastChild.textContent = 'Delete all history';
        }, 4000);
        return;
      }
      clearTimeout(confirmTimer);
      clearBtn.classList.remove('is-confirming');
      clearBtn.lastChild.textContent = 'Delete all history';
      try { await SS.api('/api/history', { method: 'DELETE' }); load(); } catch (e) { alertInline(e.message); }
    });

    load();
  }

  // ---------------------------------------------------------------- dashboard
  if (page === 'dashboard') {
    const root = document.getElementById('dashboard-root');
    const learningRoot = el('div', { id: 'learning' });
    loadLearning(learningRoot);
    SS.api('/api/stats').then((s) => {
      root.textContent = '';
      root.after(learningRoot);
      if (!s.total) {
        root.append(emptyState('Nothing to show yet', 'Open an email from your inbox (or the demo inbox) and your summary will appear here.'));
        return;
      }
      const stat = (label, iconName, value, hint, isText) => el('div', { class: 'stat' },
        el('div', { class: 'stat__label' }, icon(iconName), label),
        el('div', { class: 'stat__value' + (isText ? ' stat__value--text' : ''), text: value }),
        hint ? el('div', { class: 'stat__hint', text: hint }) : null);

      root.append(el('div', { class: 'stats' },
        stat('Messages analyzed', 'search', String(s.total)),
        stat('High-risk messages', 'alert', String(s.high_risk), `${Math.round((s.high_risk / s.total) * 100)}% rated high or very high`),
        stat('Most common category', 'flag', s.most_common_category || 'None yet', null, true),
        stat('Safety tips learned', 'bulb', String(s.tips_learned), 'Different warning signs explained to you')));

      const levelCard = el('section', { class: 'card' }, el('h3', { class: 'card__title' }, icon('shield'), 'Risk levels'));
      const stack = el('div', { class: 'stack', role: 'img', 'aria-label': LEVELS.map((l) => `${l}: ${s.levels[l]}`).join(', ') });
      LEVELS.forEach((l) => { if (s.levels[l]) stack.append(el('span', { class: SS.riskClass(l), style: { flex: String(s.levels[l]) }, title: `${l}: ${s.levels[l]}` })); });
      levelCard.append(stack, el('div', { class: 'legend' },
        LEVELS.map((l) => el('span', { class: SS.riskClass(l) }, el('span', { class: 'risk-dot' }), l, el('b', { text: String(s.levels[l]) })))));

      const catCard = el('section', { class: 'card' }, el('h3', { class: 'card__title' }, icon('flag'), 'Categories'));
      const max = Math.max(1, ...s.categories.map((c) => c[1]));
      catCard.append(s.categories.length
        ? el('ul', { class: 'bars' }, s.categories.map(([name, n]) => el('li', {},
          el('span', { text: name }),
          el('span', { class: 'bars__track' }, el('span', { style: { width: `${(n / max) * 100}%` } })),
          el('b', { text: String(n) }))))
        : el('p', { class: 'muted', text: 'No categories detected yet.' }));

      const recentCard = el('section', { class: 'card' }, el('h3', { class: 'card__title' }, icon('history'), 'Recent analyses',
        el('small', {}, el('a', { href: '/history', text: 'View all' }))),
        el('ul', { class: 'recent' }, s.recent.map((it) => el('li', {}, el('a', { href: `/analysis/${it.id}`, class: SS.riskClass(it.risk_level) },
          el('span', { class: 'risk-dot', title: it.risk_level }),
          el('span', { class: 'recent__preview', text: it.preview }),
          el('span', { class: 'recent__score', text: `${it.risk_score}/100` }))))));

      root.append(el('div', { class: 'grid-2 grid-2--even', style: { marginBottom: '20px' } }, levelCard, catCard), recentCard);
    }).catch((e) => root.replaceChildren(errorState(e.message)));
  }

  // ---------------------------------------------------------------- learning panel
  async function loadLearning(holder) {
    let l;
    try { l = await SS.api('/api/learning'); } catch (e) { holder.replaceChildren(errorState(e.message)); return; }
    const fb = l.feedback || { scam: 0, safe: 0 };
    const ds = l.dataset || { scam: 0, safe: 0 };
    const m = l.metrics || {};
    const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);
    const metric = (label, value) => el('div', {}, el('dt', { text: label }), el('dd', { text: value }));

    const retrain = el('button', { class: 'btn btn--soft', type: 'button' }, icon('cpu'), 'Retrain now');
    retrain.addEventListener('click', async () => { retrain.disabled = true; await SS.postJSON('/api/learning/retrain', {}); loadLearning(holder); });
    const reset = el('button', { class: 'btn btn--danger', type: 'button' }, icon('trash'), el('span', { text: 'Forget my feedback' }));
    reset.addEventListener('click', async () => {
      if (!reset.classList.contains('is-confirming')) {
        reset.classList.add('is-confirming');
        reset.lastChild.textContent = 'Click again to forget all feedback';
        setTimeout(() => { reset.classList.remove('is-confirming'); reset.lastChild.textContent = 'Forget my feedback'; }, 4000);
        return;
      }
      await SS.api('/api/learning/feedback', { method: 'DELETE' });
      loadLearning(holder);
    });

    const senders = (l.senders || []).map((r) => {
      const btn = el('button', { class: 'link-btn', type: 'button', text: r.kind === 'blocked' ? 'Unblock' : 'Remove' });
      const li = el('li', {}, el('span', { text: r.sender }),
        el('span', { class: 'tag', text: r.kind === 'blocked' ? 'Blocked' : 'Trusted' }), btn);
      btn.addEventListener('click', async () => {
        try { await SS.api(`/api/learning/sender/${encodeURIComponent(r.sender)}`, { method: 'DELETE' }); li.remove(); }
        catch (e) { holder.prepend(errorState(e.message)); }
      });
      return li;
    });

    holder.replaceChildren(el('section', { class: 'card', style: { marginTop: '20px' } },
      el('h3', { class: 'card__title' }, icon('cpu'), 'What ScamShield has learned', el('small', { text: 'Naive Bayes, retrains after every decision' })),
      el('dl', { class: 'learn-metrics' },
        metric('Training examples', String(l.total_examples || 0)),
        metric('Your decisions', `${fb.scam} scam, ${fb.safe} safe`),
        metric('Accuracy', pct(m.accuracy)),
        metric('Scams caught (recall)', pct(m.recall))),
      el('p', { class: 'muted', style: { fontSize: '.9rem' } },
        `${l.seed} built-in examples` + (ds.scam + ds.safe ? `, ${ds.scam + ds.safe} imported from a dataset` : '') +
        '. Accuracy is measured with 5-fold cross-validation. To train on a large public dataset, run ',
        el('code', { text: 'python train.py your-dataset.csv' }), '.'),
      el('div', { class: 'verdict__actions' }, retrain, reset),
      el('h4', { style: { margin: '20px 0 0', fontSize: '1rem' }, text: 'Trusted and blocked senders' }),
      senders.length ? el('ul', { class: 'senders' }, senders)
        : el('p', { class: 'muted', style: { marginTop: '6px' }, text: 'None yet. Use Safe or Block in your inbox.' })));
  }
})();
