/* Chat check: match a conversation against known scam scripts. */
(function () {
  'use strict';
  const { el, icon } = SS;
  const $ = (id) => document.getElementById(id);

  const SAMPLES = {
    task: `12/10/26, 9:14 pm - Priya HR: Hello! We are hiring for part-time work from home. Earn Rs 3000 daily by liking YouTube videos.
12/10/26, 9:15 pm - Me: ok, how does it work?
12/10/26, 9:21 pm - Priya HR: First 3 tasks completed! We have sent you Rs 150, check your bank account
12/10/26, 9:22 pm - Me: yes received, thanks
12/10/26, 9:30 pm - Priya HR: Now join our Telegram group for prepaid tasks, the receptionist will guide you t.me/earn_daily_task
12/10/26, 9:41 pm - Mentor Rahul: For the next level, deposit Rs 1000 to unlock the task. You will get 30% commission back.`,
    arrest: `[11/10/26, 10:02:11 AM] Officer Sharma: This is Mumbai Cyber Crime. A FedEx parcel in your name was seized with drugs.
[11/10/26, 10:03:40 AM] Officer Sharma: Your Aadhaar is linked to a money laundering case. An FIR is registered.
[11/10/26, 10:05:02 AM] Officer Sharma: Stay on the Skype video call. Don't tell anyone, this is a national secret.
[11/10/26, 10:06:15 AM] Me: I haven't done anything, please help`,
    olx: `Ravi: Hi, I'm interested in your sofa on OLX. I'm an army officer, being transferred, so I'll buy without seeing it
Me: ok, the price is 12000
Ravi: Done. I'm sending a QR code, scan this QR to receive the money`,
    family: `Mom: Are you coming home for dinner?
Me: Yes, by 8
Mom: Bring milk and bread on the way
Me: ok`,
  };

  // ---- input tabs ----------------------------------------------------------
  let chatFile = null;
  let panel = 'paste';
  document.querySelectorAll('#chat-form .tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      panel = tab.dataset.panel;
      document.querySelectorAll('#chat-form .tab').forEach((t) => {
        const on = t === tab;
        t.classList.toggle('is-active', on); t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1;
      });
      document.querySelectorAll('#chat-form .tool__panel').forEach((p) => { p.hidden = p.dataset.panel !== panel; });
    });
  });
  document.querySelectorAll('[data-sample]').forEach((b) => b.addEventListener('click', () => {
    $('chat-text').value = SAMPLES[b.dataset.sample];
    $('chat-btn').classList.add('is-ready');
  }));
  SS.fileDrop({
    zone: $('chat-drop'), input: $('chat-file'), accept: /text|zip/,
    onFile: (file) => { chatFile = file; $('chat-file-name').textContent = file.name; },
  });

  // ---- submit --------------------------------------------------------------
  $('chat-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    SS.showError($('chat-error'), null);
    const btn = $('chat-btn');
    let request;
    if (panel === 'file') {
      if (!chatFile) return SS.showError($('chat-error'), 'Choose the exported chat file first.');
      const fd = new FormData(); fd.append('chat', chatFile);
      request = SS.api('/api/chat-check', { method: 'POST', body: fd });
    } else {
      const text = $('chat-text').value.trim();
      if (!text) return SS.showError($('chat-error'), 'Paste the conversation first, or try one of the examples.');
      request = SS.postJSON('/api/chat-check', { text });
    }
    btn.disabled = true; btn.querySelector('span').textContent = 'Reading the chat…';
    try {
      const data = await request;
      render(data.result);
    } catch (err) {
      SS.showError($('chat-error'), err.message);
    } finally {
      btn.disabled = false; btn.querySelector('span').textContent = 'Check the chat';
    }
  });

  // ---- rendering -----------------------------------------------------------
  let last = null;
  function render(r, forceFull) {
    last = r;
    const root = $('chat-result');
    root.replaceChildren(!r.matched ? noMatch(r) : (SS.isSimple() && !forceFull ? simple(r) : full(r)));
    root.scrollIntoView({ behavior: SS.reducedMotion() ? 'auto' : 'smooth', block: 'start' });
  }
  // Re-render when Simple mode is switched.
  document.getElementById('simple-toggle')?.addEventListener('click', () => { if (last) setTimeout(() => render(last), 0); });

  function noMatch(r) {
    return el('article', { class: 'card track track--none' },
      el('p', { class: 'track__kicker' }, icon('info'), `Checked ${r.messages || 0} message${r.messages === 1 ? '' : 's'}`),
      el('h2', { text: 'No known scam script found' }),
      el('p', { class: 'track__summary', text: r.reason }),
      r.near?.length ? el('p', { class: 'muted' }, 'A little like: ', r.near.map((n) => n.name).join(', '), '. Keep an eye out for the next steps of those.') : null,
      tools(),
    );
  }

  function full(r) {
    const steps = el('ol', { class: 'steps' });
    r.steps.forEach((s, i) => {
      const li = el('li', { class: `step step--${s.status}`, style: { '--d': `${0.15 + i * 0.18}s` } },
        el('span', { class: 'step__n', 'aria-hidden': 'true' }, s.status === 'seen' ? icon('check') : String(s.n)),
        el('div', { class: 'step__body' },
          el('h3', { class: 'step__title' }, s.title, s.status === 'skipped' ? el('small', { text: 'not seen yet' }) : null),
          el('p', { class: 'step__what', text: s.what_happens }),
          s.evidence.length ? el('div', { class: 'step__quotes' }, s.evidence.map((q) =>
            el('blockquote', { class: 'step__quote' }, q.who ? el('b', { text: q.who + ': ' }) : null, el('mark', { class: 'hl', style: { '--d': `${0.5 + i * 0.18}s` }, text: q.quote })))) : null,
          s.status === 'now' ? el('span', { class: 'step__here' }, svgArrow(), 'you are here') : null,
          s.status === 'next' ? el('p', { class: 'step__next' }, el('strong', { text: 'Next, ' }), r.next_move) : null,
        ));
      steps.appendChild(li);
    });
    const engine = r.engine === 'rules' ? 'Rule-based match, every step quoted' : r.engine === 'rules+ai' ? 'Rules, confirmed by the AI model' : 'Found by the AI model, quotes checked';
    return el('article', { class: 'card track' },
      el('header', { class: 'track__head' },
        el('p', { class: 'track__kicker' }, icon('alert'), 'This chat follows a known scam script'),
        el('h2', { text: r.script.name }),
        el('div', { class: 'track__meter', role: 'img', 'aria-label': `Step ${r.current_step} of ${r.total_steps}` },
          el('span', { class: 'track__count' }, el('b', { text: r.current_step }), ` of ${r.total_steps} steps`),
          el('span', { class: 'track__bar' }, el('i', { style: { width: `${(r.current_step / r.total_steps) * 100}%` } }))),
        el('p', { class: 'track__summary', text: r.script.summary }),
        el('div', { class: 'track__tags' },
          el('span', { class: 'tag', text: `${r.confidence === 'high' ? 'Strong' : 'Partial'} match` }),
          el('span', { class: 'tag', text: engine }),
          el('span', { class: 'tag', text: `${r.messages} messages read` })),
        r.ai_note ? el('p', { class: 'track__ai' }, icon('sparkles'), r.ai_note) : null,
      ),
      steps,
      el('footer', { class: 'track__advice' },
        el('div', null, el('h3', { text: r.at_end ? 'This is the last step' : 'Stop here' }), el('p', { text: r.script.advice })),
        r.also_possible?.length ? el('p', { class: 'muted small' }, 'Could also be: ', r.also_possible.map((a) => a.name).join(', ')) : null,
        tools()),
      r.notice ? el('p', { class: 'notice', text: r.notice }) : null,
    );
  }

  function simple(r) {
    return el('article', { class: 'simple' },
      el('div', { class: 'simple-verdict simple-verdict--scam' },
        el('span', { class: 'simple-verdict__icon' }, icon('alert')),
        el('div', null,
          el('h2', { text: `This chat looks like a "${r.script.name}"` }),
          el('p', { text: `They have done ${r.current_step} of its ${r.total_steps} steps.` }))),
      el('div', { class: 'simple__why' },
        el('h3', { text: r.at_end ? 'This is the last step' : 'What they will ask for next' }),
        el('p', { class: 'simple-next', text: r.next_move }),
        el('h3', { text: 'What to do' }),
        el('p', { class: 'simple-next', text: r.script.advice })),
      el('div', { class: 'simple-actions' },
        el('a', { class: 'btn btn--xl btn--alarm', href: '/paid' }, icon('alert'), 'I already paid them'),
        el('button', { class: 'btn btn--xl btn--outline', type: 'button', onclick: () => render(last, true) }, 'Show all the steps')),
    );
  }

  function tools() {
    return el('div', { class: 'track__tools' },
      el('a', { class: 'btn btn--ghost', href: '/upi-check' }, icon('scan'), 'Check a QR or payment request'),
      el('a', { class: 'btn btn--alarm', href: '/paid' }, icon('alert'), 'I already paid'));
  }

  function svgArrow() {
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 60 30'); svg.setAttribute('class', 'step__arrow'); svg.setAttribute('aria-hidden', 'true');
    const p = document.createElementNS(ns, 'path');
    p.setAttribute('d', 'M58 6 C 40 2, 18 6, 6 22 M6 22 L 7 12 M6 22 L 15 19'); p.setAttribute('pathLength', '1');
    svg.appendChild(p);
    return svg;
  }
})();
