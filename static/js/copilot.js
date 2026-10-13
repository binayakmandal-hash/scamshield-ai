/* Call copilot: live warnings while a suspicious call is on speaker. Runs entirely in the browser. */
(function () {
  'use strict';
  const { el, icon } = SS;
  const $ = (id) => document.getElementById(id);

  const TACTICS = JSON.parse($('tactics-data').textContent).map((t) => ({
    ...t, regex: t.patterns.map((p) => new RegExp(p, 'iu')),
  }));
  const SPEECH = { en: 'en-IN', hi: 'hi-IN', bn: 'bn-IN' };
  const LEVELS = {
    listening: 'No warning signs heard yet.',
    caution: 'One thing to watch. Keep listening.',
    warning: 'Warning: this is how scam calls sound.',
    scam: 'This call matches a scam. Hang up.',
  };
  const PRACTICE = [
    'Hello, am I speaking with Mr. Sen? This is Inspector Rathore from Mumbai Crime Branch.',
    'A FedEx parcel in your name has been seized with drugs and five fake passports.',
    'Your Aadhaar is linked to a money laundering case. An arrest warrant has been issued.',
    'This is a confidential investigation. Do not tell anyone, not even your family.',
    'Stay on the video call. If you disconnect, local police will come to arrest you.',
    'To prove you are innocent, transfer your savings to the RBI verification account immediately.',
    'It will be refunded after verification, within two hours.',
  ];

  const lang = () => $('call-lang').value;
  let lines = [];        // finished lines of transcript
  let interim = '';      // words still being recognised
  let seen = new Map();  // tactic id -> {tactic, quote}
  let rec = null;
  let listening = false;
  let practiceTimer = null;

  // ---- transcript + matching ----------------------------------------------
  function addLine(text) {
    text = text.trim();
    if (!text) return;
    lines.push(text);
    drawTranscript();
    check(text);
  }

  function drawTranscript() {
    const box = $('transcript');
    const items = lines.slice(-8).map((l) => el('p', { class: 'transcript__line', text: l }));
    if (interim) items.push(el('p', { class: 'transcript__line is-interim', text: interim }));
    box.replaceChildren(...(items.length ? items : [el('p', { class: 'transcript__empty', text: 'What the caller says will appear here.' })]));
    box.scrollTop = box.scrollHeight;
  }

  function check(text) {
    for (const t of TACTICS) {
      if (seen.has(t.id)) continue;
      const m = t.regex.map((r) => text.match(r)).find(Boolean);
      if (m) {
        seen.set(t.id, { tactic: t, quote: text });
        showAlert(t, text, m[0]);
      }
    }
    updateLevel();
  }

  function showAlert(t, line, hit) {
    const L = lang();
    const i = line.toLowerCase().indexOf(hit.toLowerCase());
    const quote = i >= 0 ? [line.slice(0, i), el('mark', { class: 'hl', text: line.slice(i, i + hit.length) }), line.slice(i + hit.length)] : line;
    const item = el('li', { class: `alert alert--${t.severity}` },
      el('span', { class: 'alert__icon' }, icon(t.severity === 'low' ? 'clock' : 'alert')),
      el('div', null,
        el('h3', { text: t.title[L] || t.title.en }),
        el('p', { class: 'alert__say' }, t.say[L] || t.say.en),
        el('blockquote', { class: 'alert__quote' }, '“', quote, '”')));
    $('alert-list').prepend(item);
    if (navigator.vibrate && t.severity === 'high') navigator.vibrate([120, 60, 120]);
  }

  function level() {
    const high = [...seen.values()].filter((s) => s.tactic.severity === 'high').length;
    if (high >= 2) return 'scam';
    if (high === 1 || seen.size >= 2) return 'warning';
    return seen.size ? 'caution' : 'listening';
  }

  function updateLevel() {
    const lv = level();
    $('meter').dataset.level = lv;
    $('meter-text').textContent = LEVELS[lv];
    const wasHidden = $('hangup').hidden;
    $('hangup').hidden = lv !== 'scam';
    if (lv === 'scam' && wasHidden) $('hangup').scrollIntoView({ behavior: SS.reducedMotion() ? 'auto' : 'smooth', block: 'nearest' });
  }

  function reset() {
    stopPractice();
    lines = []; interim = ''; seen = new Map();
    $('alert-list').replaceChildren();
    drawTranscript(); updateLevel();
  }

  // ---- microphone ----------------------------------------------------------
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    $('mic-btn').disabled = true;
    $('mic-hint').textContent = "This browser can't listen. Use Chrome or Edge, or type what the caller says below.";
  }

  function setListening(on) {
    listening = on;
    $('callpad').dataset.state = on ? 'listening' : 'idle';
    $('mic-btn').setAttribute('aria-pressed', String(on));
    $('mic-label').textContent = on ? 'Stop' : 'Listen';
    $('call-status-text').textContent = on ? 'Listening…' : 'Not listening';
  }

  function start() {
    stopPractice();
    rec = new Recognition();
    rec.lang = SPEECH[lang()] || 'en-IN';
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (e) => {
      interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const text = e.results[i][0].transcript;
        if (e.results[i].isFinal) addLine(text);
        else interim += text;
      }
      drawTranscript();
      if (interim) check(interim);
    };
    rec.onerror = (e) => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        $('mic-hint').textContent = 'Microphone access was blocked. Allow it in the address bar, or type what the caller says.';
        setListening(false);
      } else if (e.error === 'network') {
        $('mic-hint').textContent = "The browser's speech service couldn't be reached. Check your internet, or type instead.";
        setListening(false);
      }
    };
    rec.onend = () => { if (listening) { try { rec.start(); } catch (err) { setListening(false); } } };
    try { rec.start(); setListening(true); $('mic-hint').textContent = 'Put the call on speaker and hold the phone near this device.'; }
    catch (err) { setListening(false); }
  }

  function stop() {
    listening = false;
    if (rec) { rec.onend = null; try { rec.stop(); } catch (err) { /* already stopped */ } }
    setListening(false);
  }

  $('mic-btn').addEventListener('click', () => (listening ? stop() : start()));
  $('call-lang').addEventListener('change', () => { if (listening) { stop(); start(); } });

  // ---- typing fallback -----------------------------------------------------
  $('type-form').addEventListener('submit', (e) => {
    e.preventDefault();
    addLine($('type-input').value);
    $('type-input').value = '';
  });

  // ---- practice call -------------------------------------------------------
  function stopPractice() {
    if (practiceTimer) clearTimeout(practiceTimer);
    practiceTimer = null;
    $('callpad').classList.remove('is-practice');
  }
  $('practice-btn').addEventListener('click', () => {
    if (listening) stop();
    reset();
    $('call-lang').value = 'en';
    $('callpad').classList.add('is-practice');
    $('call-status-text').textContent = 'Practice call';
    let i = 0;
    const next = () => {
      if (i >= PRACTICE.length) { stopPractice(); $('call-status-text').textContent = 'Practice finished'; return; }
      const line = PRACTICE[i++];
      let shown = 0;
      const type = () => {
        shown = Math.min(line.length, shown + 3);
        interim = line.slice(0, shown);
        drawTranscript();
        if (shown < line.length) practiceTimer = setTimeout(type, SS.reducedMotion() ? 0 : 28);
        else { interim = ''; addLine(line); practiceTimer = setTimeout(next, SS.reducedMotion() ? 0 : 900); }
      };
      type();
    };
    next();
  });
  $('reset-btn').addEventListener('click', reset);

  // ---- family contact (stored only in this browser) -----------------------
  function loadFamily() {
    let fam = null;
    try { fam = JSON.parse(SS.store.get('ss-family') || 'null'); } catch (e) { fam = null; }
    const link = $('family-call');
    if (fam && fam.phone) {
      link.href = 'tel:' + fam.phone.replace(/[^\d+]/g, '');
      link.querySelector('span').textContent = `Call ${fam.name || 'my family'}`;
      link.hidden = false;
      $('family-summary').textContent = `${fam.name || 'Family'}: ${fam.phone}`;
      $('family-name').value = fam.name || ''; $('family-phone').value = fam.phone;
    }
  }
  $('family-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const phone = $('family-phone').value.trim();
    if (!/^[+\d][\d\s-]{6,}$/.test(phone)) { $('family-phone').focus(); return; }
    SS.store.set('ss-family', JSON.stringify({ name: $('family-name').value.trim(), phone }));
    loadFamily();
    $('family').open = false;
  });
  loadFamily();

  // Exposed for tests and the demo flow.
  SS.copilot = { addLine, reset, level };
})();
