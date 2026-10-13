/* UPI check: say which way the money moves before anyone scans or approves. */
(function () {
  'use strict';
  const { el, icon } = SS;
  const $ = (id) => document.getElementById(id);

  const SAMPLES = {
    collect: 'Ramesh Kumar has requested ₹2,000 from you on PhonePe. Approve the request to receive your cashback. Expires in 10 minutes.',
    mistake: 'Hello sir, I sent you ₹5,000 by mistake on Google Pay. Please return the money to 9845012345@okaxis, I am a poor man.',
  };
  const UI = {
    en: { you: 'You', leaves: 'leaves your account', arrives: 'arrives in your account', claim: 'Claimed: ', flags: 'Why we say this', steps: 'What to do', unknown: 'Unknown app', personal: 'personal account', merchant: 'registered merchant', paid: 'I already paid', chat: 'Check the whole chat', qr: 'Text inside the QR' },
    hi: { you: 'आप', leaves: 'आपके खाते से जाएगा', arrives: 'आपके खाते में आया', claim: 'दावा: ', flags: 'हम ऐसा क्यों कह रहे हैं', steps: 'क्या करें', unknown: 'अनजान ऐप', personal: 'व्यक्तिगत खाता', merchant: 'पंजीकृत व्यापारी', paid: 'मैं पैसे दे चुका हूँ', chat: 'पूरी चैट जाँचें', qr: 'QR के अंदर का टेक्स्ट' },
    bn: { you: 'আপনি', leaves: 'আপনার অ্যাকাউন্ট থেকে যাবে', arrives: 'আপনার অ্যাকাউন্টে এসেছে', claim: 'দাবি: ', flags: 'কেন এমন বলছি', steps: 'কী করবেন', unknown: 'অচেনা অ্যাপ', personal: 'ব্যক্তিগত অ্যাকাউন্ট', merchant: 'নথিভুক্ত ব্যবসা', paid: 'আমি টাকা দিয়ে ফেলেছি', chat: 'পুরো চ্যাট দেখুন', qr: 'QR-এর ভেতরের লেখা' },
  };

  // ---- image input ---------------------------------------------------------
  let image = null;
  function setImage(file) {
    if (!/^image\/(png|jpe?g|webp)$/.test(file.type)) return SS.showError($('upi-error'), 'Upload a JPG, PNG or WebP image.');
    if (file.size > 8 * 1024 * 1024) return SS.showError($('upi-error'), 'That image is larger than 8 MB.');
    image = file;
    $('upi-img').src = URL.createObjectURL(file);
    $('upi-name').textContent = file.name || 'Pasted image';
    $('upi-preview').hidden = false; $('upi-drop').hidden = true;
    SS.showError($('upi-error'), null);
  }
  SS.fileDrop({ zone: $('upi-drop'), input: $('upi-file'), onFile: setImage, paste: true });
  $('upi-clear').addEventListener('click', () => {
    image = null; $('upi-file').value = ''; $('upi-preview').hidden = true; $('upi-drop').hidden = false;
  });
  document.querySelectorAll('[data-sample]').forEach((b) => b.addEventListener('click', async () => {
    if (b.dataset.sample === 'qr') {
      const blob = await (await fetch('/static/samples/refund-qr.png')).blob();
      setImage(new File([blob], 'refund-qr.png', { type: 'image/png' }));
      $('upi-text').value = '';
    } else {
      $('upi-clear').click();
      $('upi-text').value = SAMPLES[b.dataset.sample];
    }
    $('upi-btn').classList.add('is-ready');
  }));

  // ---- submit --------------------------------------------------------------
  $('upi-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    SS.showError($('upi-error'), null);
    const text = $('upi-text').value.trim();
    if (!image && !text) return SS.showError($('upi-error'), 'Upload a QR code or screenshot, or paste the message first.');
    const fd = new FormData();
    if (image) fd.append('image', image);
    fd.append('text', text);
    fd.append('language', $('upi-lang').value);
    const btn = $('upi-btn');
    btn.disabled = true; btn.querySelector('span').textContent = image ? 'Reading the image…' : 'Checking…';
    try {
      const data = await SS.api('/api/upi-check', { method: 'POST', body: fd });
      render(data.result);
    } catch (err) {
      SS.showError($('upi-error'), err.message);
    } finally {
      btn.disabled = false; btn.querySelector('span').textContent = 'Translate it';
    }
  });

  // ---- rendering -----------------------------------------------------------
  function render(r) {
    const t = UI[r.language] || UI.en;
    const root = $('upi-result');
    const v = r.verdict;
    const card = el('article', { class: `card upi upi--${v}`, lang: r.language },
      el('div', { class: 'upi__band' },
        el('span', { class: 'upi__icon' }, icon(v === 'danger' ? 'alert' : v === 'info' ? 'shield-check' : v === 'none' ? 'search' : 'info')),
        el('h2', { text: r.headline })),
      r.direction ? flow(r, t) : null,
      el('p', { class: 'upi__truth', text: r.truth }),
      r.note_on_qr ? el('p', { class: 'upi__claim' }, el('span', { text: t.claim }), `"${r.note_on_qr}"`) : null,
      r.flags.length ? el('section', { class: 'upi__flags' },
        el('h3', { text: t.flags }),
        el('ul', null, r.flags.map((f, i) => el('li', { class: `upi-flag sev-${f.severity}`, style: { '--d': `${0.6 + i * 0.12}s` } },
          el('strong', { text: f.title }), el('span', { text: f.detail }))))) : null,
      r.steps.length ? el('section', { class: 'upi__steps' },
        el('h3', { text: t.steps }),
        el('ol', null, r.steps.map((s) => el('li', { text: s })))) : null,
      r.qr_text.length ? el('details', { class: 'upi__raw' }, el('summary', { text: t.qr }), r.qr_text.map((q) => el('code', { text: q }))) : null,
      el('footer', { class: 'upi__foot' },
        el('a', { class: 'btn btn--ghost', href: '/chat-check' }, icon('chat'), t.chat),
        v !== 'none' ? el('a', { class: 'btn btn--alarm', href: '/paid' }, icon('alert'), t.paid) : null),
    );
    root.replaceChildren(card);
    root.scrollIntoView({ behavior: SS.reducedMotion() ? 'auto' : 'smooth', block: 'start' });
  }

  function flow(r, t) {
    const incoming = r.direction === 'in';
    const p = r.payee || {};
    const who = el('div', { class: 'party party--them' },
      el('span', { class: 'party__avatar', 'aria-hidden': 'true', text: initials(p.name || p.vpa || '?') }),
      el('div', null,
        el('strong', { text: p.name || p.vpa || 'Unknown' }),
        p.vpa && p.name ? el('code', { text: p.vpa }) : null,
        el('small', { text: [p.app || (p.vpa ? t.unknown : ''), p.is_personal ? t.personal : '', p.merchant ? t.merchant : ''].filter(Boolean).join(' · ') })));
    const me = el('div', { class: 'party party--me' },
      el('span', { class: 'party__avatar', 'aria-hidden': 'true' }, icon('user')), el('strong', { text: t.you }));
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 200 40'); svg.setAttribute('class', 'flow__line'); svg.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS(ns, 'path');
    path.setAttribute('d', 'M4 20 C 60 4, 140 36, 186 20'); path.setAttribute('pathLength', '1');
    const head = document.createElementNS(ns, 'path');
    head.setAttribute('d', 'M176 11 L 190 20 L 176 29'); head.setAttribute('class', 'flow__head'); head.setAttribute('pathLength', '1');
    svg.append(path, head);
    return el('div', { class: `flow ${incoming ? 'flow--in' : 'flow--out'}`, role: 'img',
      'aria-label': incoming ? `${r.amount || ''} ${t.arrives}` : `${r.amount || ''} ${t.leaves}` },
      incoming ? who : me,
      el('div', { class: 'flow__mid' },
        el('span', { class: 'flow__amount', text: r.amount || '₹ ?' }),
        svg,
        el('span', { class: 'flow__label', text: incoming ? t.arrives : t.leaves })),
      incoming ? me : who);
  }

  function initials(s) {
    const parts = String(s).replace(/@.*/, '').split(/[\s._-]+/).filter(Boolean);
    return ((parts[0]?.[0] || '?') + (parts[1]?.[0] || '')).toUpperCase();
  }
})();
