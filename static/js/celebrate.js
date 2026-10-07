// The finish celebration: confetti and a short happy tune.
// A page asks for it with <body data-celebrate>; a button with [data-celebrate-again] plays it again.
// The theme sets the confetti colours (--confetti-1..5). Reduced motion: no confetti, the tune only.
(function () {
  var NOTES = [523.25, 659.25, 783.99, 1046.5]; // C5 E5 G5 C6

  function tune() {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    try {
      var ctx = new AC();
      if (ctx.state === 'suspended' && ctx.resume) ctx.resume();
      NOTES.forEach(function (f, i) {
        var t = ctx.currentTime + i * 0.13;
        var o = ctx.createOscillator(), g = ctx.createGain();
        o.type = 'triangle'; o.frequency.value = f;
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(0.25, t + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, t + (i === NOTES.length - 1 ? 0.7 : 0.25));
        o.connect(g); g.connect(ctx.destination);
        o.start(t); o.stop(t + 0.8);
      });
    } catch (e) { /* no sound is fine */ }
  }

  function colours() {
    var s = getComputedStyle(document.documentElement), out = [];
    for (var i = 1; i <= 5; i++) { var c = s.getPropertyValue('--confetti-' + i).trim(); if (c) out.push(c); }
    return out.length ? out : ['#e8453c', '#ffc93c', '#2f9e8f', '#5b5bd6', '#ff8fb1'];
  }

  function confetti() {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var cv = document.createElement('canvas');
    cv.className = 'confetti';
    cv.setAttribute('aria-hidden', 'true');
    document.body.appendChild(cv);
    var w = cv.width = window.innerWidth, h = cv.height = window.innerHeight;
    var g = cv.getContext('2d'), cols = colours(), bits = [];
    for (var i = 0; i < 140; i++) {
      bits.push({ x: w / 2 + (Math.random() - .5) * w * .3, y: h * .35, vx: (Math.random() - .5) * 16,
        vy: -Math.random() * 16 - 6, r: Math.random() * 6.28, vr: (Math.random() - .5) * .4,
        s: 8 + Math.random() * 8, c: cols[i % cols.length] });
    }
    var start = Date.now();
    (function frame() {
      var age = Date.now() - start;
      g.clearRect(0, 0, w, h);
      bits.forEach(function (b) {
        b.vy += 0.45; b.vx *= 0.99; b.x += b.vx; b.y += b.vy; b.r += b.vr;
        g.save(); g.translate(b.x, b.y); g.rotate(b.r); g.fillStyle = b.c;
        g.fillRect(-b.s / 2, -b.s / 4, b.s, b.s / 2); g.restore();
      });
      if (age < 3200) requestAnimationFrame(frame); else cv.parentNode.removeChild(cv);
    })();
  }

  function celebrate() { confetti(); tune(); }
  window.celebrate = celebrate;

  document.addEventListener('DOMContentLoaded', function () {
    if (document.body.hasAttribute('data-celebrate')) celebrate();
    var again = document.querySelectorAll('[data-celebrate-again]');
    for (var i = 0; i < again.length; i++) again[i].addEventListener('click', celebrate);
  });
})();
