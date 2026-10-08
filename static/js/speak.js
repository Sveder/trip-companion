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

  function speak(text) {
    if (!synth || !voice || !text) return;
    synth.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.voice = voice; u.lang = voice.lang; u.rate = 0.8;
    synth.speak(u);
  }

  function say(el) {
    var text = el.getAttribute('data-say');
    var src = el.getAttribute('data-say-src');
    if (!src) { speak(text); return; }
    if (synth) synth.cancel();
    if (player) player.pause();
    player = new Audio(src);
    var p = player.play();
    if (p && p.catch) p.catch(function () { speak(text); });
  }

  function from(e) {
    var el = e.target.closest ? e.target.closest('[data-say]') : null;
    if (el) say(el);
  }

  document.addEventListener('click', from);
  // A button gets a click from the browser after Enter, so the click path says it; saying it here too would play it twice.
  document.addEventListener('keydown', function (e) {
    if (e.keyCode !== 13) return;
    var el = e.target.closest ? e.target.closest('[data-say]') : null;
    if (el && el.tagName !== 'BUTTON') say(el);
  });
  pick();
  if (synth) {
    if (synth.addEventListener) synth.addEventListener('voiceschanged', pick); else synth.onvoiceschanged = pick;
  }
})();
