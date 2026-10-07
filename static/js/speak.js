// Say a Japanese word out loud: tap (or press OK on) any element with data-say.
// Uses the browser's own Japanese voice. With no Japanese voice, the hint stays hidden and nothing plays.
(function () {
  var synth = window.speechSynthesis;
  if (!synth || !window.SpeechSynthesisUtterance) return;
  var voice = null;

  function pick() {
    var list = synth.getVoices();
    for (var i = 0; i < list.length; i++) {
      if (/^ja/i.test(list[i].lang)) { voice = list[i]; break; }
    }
    var hints = document.querySelectorAll('[data-say-hint]');
    for (var j = 0; j < hints.length; j++) hints[j].hidden = !voice;
  }

  function say(text) {
    if (!voice || !text) return;
    synth.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.voice = voice; u.lang = voice.lang; u.rate = 0.8;
    synth.speak(u);
  }

  function from(e) {
    var el = e.target.closest ? e.target.closest('[data-say]') : null;
    if (el) say(el.getAttribute('data-say'));
  }

  document.addEventListener('click', from);
  document.addEventListener('keydown', function (e) { if (e.keyCode === 13) from(e); });
  pick();
  if (synth.addEventListener) synth.addEventListener('voiceschanged', pick); else synth.onvoiceschanged = pick;
})();
