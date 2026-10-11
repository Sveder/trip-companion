// Say a Japanese word out loud: tap (or press OK on) any element with data-say.
// First choice: the pre-made mp3 in data-say-src (works in every browser, also with no Japanese voice).
// Fallback: the browser's own Japanese voice. With neither, the hint stays hidden and nothing plays.
(function () {
  var synth = window.speechSynthesis && window.SpeechSynthesisUtterance ? window.speechSynthesis : null;
  var voice = null;
  var player = null;

  function pick() {
    if (synth) {
      var list = synth.getVoices();
      for (var i = 0; i < list.length; i++) {
        if (/^ja/i.test(list[i].lang)) { voice = list[i]; break; }
      }
    }
    var hints = document.querySelectorAll('[data-say-hint]');
    for (var j = 0; j < hints.length; j++) {
      var card = hints[j].closest ? hints[j].closest('[data-say]') : null;
      var src = card ? card.getAttribute('data-say-src') : '';
      hints[j].hidden = !(src || voice);
    }
  }

  // While a word plays, its element has the class .playing, so its speaker mark pulses (T156).
  var active = null;
  function on(el) { off(); active = el; el.classList.add('playing'); }
  function off() { if (active) active.classList.remove('playing'); active = null; }

  function speak(text, el) {
    if (!synth || !voice || !text) { off(); return; }
    synth.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.voice = voice; u.lang = voice.lang; u.rate = 0.8;
    if (el) { on(el); u.onend = u.onerror = function () { if (active === el) off(); }; }
    synth.speak(u);
  }

  // The header toggle turns every sound off: spoken words, the train game words and the finish chime (T156).
  function soundOn() { try { return localStorage.getItem('tc_sound') !== '0'; } catch (e) { return true; } }
  window.tcSoundOn = soundOn;

  function say(el) {
    hintGone();
    if (!soundOn()) return;
    var text = el.getAttribute('data-say');
    var src = el.getAttribute('data-say-src');
    if (!src) { speak(text, el); return; }
    if (synth) synth.cancel();
    if (player) player.pause();
    var me = player = new Audio(src);
    on(el);
    me.onended = me.onerror = me.onpause = function () { if (player === me) off(); };
    var p = me.play();
    if (p && p.catch) p.catch(function () { speak(text, el); });
  }
  // Other scripts say a word too: the tap-the-dots page says the word of a dot (lesson.js, T156).
  window.tcSay = say;

  function from(e) {
    var el = e.target.closest ? e.target.closest('[data-say]') : null;
    if (el) say(el);
  }

  function showToggle(btn) {
    var on = soundOn();
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    btn.classList.toggle('off', !on);
    btn.querySelector('.sound-word').textContent = btn.getAttribute(on ? 'data-on' : 'data-off');
  }
  var toggle = document.querySelector('.sound-btn');
  if (toggle) {
    showToggle(toggle);
    toggle.addEventListener('click', function () {
      var on = !soundOn();
      try { localStorage.setItem('tc_sound', on ? '1' : '0'); } catch (e) {}
      if (!on) { if (synth) synth.cancel(); if (player) player.pause(); off(); }
      showToggle(toggle);
    });
  }

  // A one-time hint: the first page in this browser with a talking word says 'Tap a Japanese word to hear it'
  // for 6 s, or until the first tap on a word. Position fixed, so the page does not move.
  var hint = document.querySelector('.say-hint'), hintTimer = null;
  function hintGone() {
    if (!hint || hint.hidden) return;
    hint.classList.remove('show');
    clearTimeout(hintTimer);
    setTimeout(function () { hint.hidden = true; }, 300);
  }
  function hintMaybe() {
    if (!hint) return;
    var talks = document.querySelector('.say-word[data-say-src]:not([data-say-src=""]), [data-say][data-say-src]:not([data-say-src=""])');
    if (!talks) return;
    try {
      if (localStorage.getItem('tc_hint_say') === '1') return;
      localStorage.setItem('tc_hint_say', '1');
    } catch (e) { return; }
    var top = document.querySelector('.top');
    hint.style.top = Math.max(8, top ? top.getBoundingClientRect().bottom + 8 : 8) + 'px';
    hint.hidden = false;
    setTimeout(function () { hint.classList.add('show'); }, 20);
    hintTimer = setTimeout(hintGone, 6000);
  }

  document.addEventListener('click', from);
  // A button gets a click from the browser after Enter, so the click path says it; saying it here too would play it twice.
  document.addEventListener('keydown', function (e) {
    if (e.keyCode !== 13) return;
    var el = e.target.closest ? e.target.closest('[data-say]') : null;
    if (el && el.tagName !== 'BUTTON') say(el);
  });
  pick();
  hintMaybe();
  if (synth) {
    if (synth.addEventListener) synth.addEventListener('voiceschanged', pick); else synth.onvoiceschanged = pick;
  }
})();
