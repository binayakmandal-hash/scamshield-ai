/* Golden hour: a calm, ordered checklist after paying a scammer, plus a complaint drafted from the receipt. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);

  // ---- clock ---------------------------------------------------------------
  const pad = (n) => String(n).padStart(2, '0');
  const toLocalInput = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  let paidAt = new Date(SS.store.get('ss-paid-at') || Date.now());
  if (isNaN(paidAt)) paidAt = new Date();
  $('paid-at').value = toLocalInput(paidAt);
  $('paid-at').max = toLocalInput(new Date());
  $('paid-at').addEventListener('change', () => {
    const d = new Date($('paid-at').value);
    if (!isNaN(d)) { paidAt = d; SS.store.set('ss-paid-at', d.toISOString()); tick(); }
  });

  function tick() {
    const mins = Math.max(0, Math.floor((Date.now() - paidAt) / 60000));
    const h = Math.floor(mins / 60);
    $('clock-time').textContent = h >= 48 ? `${Math.floor(h / 24)} days` : `${h}h ${pad(mins % 60)}m`;
    const golden = mins < 60;
    $('clock').classList.toggle('is-golden', golden);
    $('clock-note').textContent = golden
      ? "You're inside the first hour. Reporting now gives the best chance the money can be held."
      : h < 48 ? "Still report it today. Money is sometimes held even hours or days later."
        : "It's still worth reporting. A complaint also helps catch the gang and protect others.";
  }
  tick();
  setInterval(tick, 15000);

  // ---- checklist (ticks remembered in this browser) ------------------------
  let done = {};
  try { done = JSON.parse(SS.store.get('ss-golden-steps') || '{}'); } catch (e) { done = {}; }
  document.querySelectorAll('#checklist > li').forEach((li) => {
    const box = li.querySelector('input[type=checkbox]');
    box.setAttribute('aria-label', 'Done: ' + li.querySelector('h2').textContent);
    box.checked = !!done[li.dataset.step];
    li.classList.toggle('is-done', box.checked);
    box.addEventListener('change', () => {
      done[li.dataset.step] = box.checked;
      li.classList.toggle('is-done', box.checked);
      SS.store.set('ss-golden-steps', JSON.stringify(done));
    });
  });

  // ---- receipt → fields ----------------------------------------------------
  let receipt = null;
  SS.fileDrop({
    zone: $('receipt-drop'), input: $('receipt-file'), paste: true,
    onFile: (f) => { receipt = f; $('receipt-name').textContent = f.name || 'Pasted screenshot'; },
  });
  $('receipt-sample').addEventListener('click', () => {
    receipt = null;
    $('receipt-name').innerHTML = '<svg class="ic"><use href="#i-upload"/></svg> Payment screenshot, or <u>browse</u>';
    $('receipt-text').value = 'Dear Customer, Rs.25,000.00 debited from A/c XX4521 on 12-10-26 to VPA rbi.verify77@ybl (UPI Ref No 428615937204). Not you? Call 1800 1234 -SBI';
  });

  $('receipt-btn').addEventListener('click', async () => {
    SS.showError($('receipt-error'), null);
    const text = $('receipt-text').value.trim();
    if (!receipt && !text) return SS.showError($('receipt-error'), 'Upload the payment screenshot or paste the bank SMS first. You can also type the details below.');
    const fd = new FormData();
    if (receipt) fd.append('image', receipt);
    fd.append('text', text);
    const btn = $('receipt-btn');
    btn.disabled = true; btn.querySelector('span').textContent = 'Reading…';
    try {
      const data = await SS.api('/api/paid/extract', { method: 'POST', body: fd });
      const form = $('fields');
      for (const [k, v] of Object.entries(data.fields)) {
        if (v && form.elements[k]) {
          form.elements[k].value = v;
          form.elements[k].classList.add('is-filled');
        }
      }
      if (!data.found.length) SS.showError($('receipt-error'), "We couldn't find payment details in that. Please type them in below.");
      draft();
    } catch (err) {
      SS.showError($('receipt-error'), err.message);
    } finally {
      btn.disabled = false; btn.querySelector('span').textContent = 'Read the details';
    }
  });

  // ---- drafts ----------------------------------------------------------------
  function val(name) { return ($('fields').elements[name]?.value || '').trim(); }
  const blank = (v, label) => v || `[${label}]`;

  function draft() {
    const num = Number(val('amount').replace(/[^\d.]/g, ''));
    const amount = val('amount') ? (num ? '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : `₹${val('amount')}`) : '[amount]';
    const when = [val('date'), val('time')].filter(Boolean).join(' at ') || '[date and time]';
    const payee = [val('payee_name'), val('payee_vpa') && `UPI ID ${val('payee_vpa')}`].filter(Boolean).join(', ') || '[UPI ID / account it went to]';
    const refs = [val('utr') && `UTR / UPI reference ${val('utr')}`, val('txn_id') && `transaction ID ${val('txn_id')}`].filter(Boolean).join(', ') || 'UTR [12-digit reference]';
    const via = [val('app') && `using ${val('app')}`, val('bank') && `from my ${val('bank')} account`].filter(Boolean).join(' ');
    const story = val('story') || '[Describe briefly how they contacted you and what they said.]';

    $('draft-text').textContent =
`I am reporting an online financial fraud.

On ${when}, I paid ${amount} ${via ? via + ' ' : ''}to ${payee} (${refs}).

${story}

${val('phone') ? `The fraudster contacted me from: ${val('phone')}.\n\n` : ''}I did not receive anything in return and I believe this was a scam. I request that the amount be put on hold in the beneficiary account and recovered, and that action be taken against the people responsible. I have kept screenshots of the chat, the call log and the payment as evidence.`;

    $('bank-text').textContent =
`Subject: Fraudulent UPI transaction - please block and raise a dispute

Dear Sir/Madam,

I was defrauded and made a payment of ${amount} on ${when} to ${payee} (${refs}).

Please block UPI and net banking on my account immediately, raise a fraud dispute for this transaction, and contact the beneficiary bank to hold the amount. ${val('bank') ? `My bank is ${val('bank')}. ` : ''}I am also reporting this on the national helpline 1930 and at cybercrime.gov.in and will share the acknowledgement number.

Regards,
${blank('', 'Your name')}
${blank('', 'Account number / registered mobile')}`;
  }
  $('fields').addEventListener('input', (e) => { e.target.classList.remove('is-filled'); draft(); });
  draft();

  document.querySelectorAll('[data-copy]').forEach((b) => b.addEventListener('click', () => SS.copy($(b.dataset.copy).textContent, b)));
})();
