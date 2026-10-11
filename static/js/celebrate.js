// The finish celebration (our 4-year-old's choice, feedback T83): a star explosion and a bell-like chime.
// A page asks for it with <body data-celebrate>; a button with [data-celebrate-again] plays it again.
// The theme sets the star colours (--star-1..5). Reduced motion: no stars, the chime only.
// Easter egg: in about one party out of six, our 4-year-old's penguin waddles across the bottom of the screen.
// ?penguin=1 in the address always sends it (for screenshots).
(function () {
  // A rising run on the Japanese yo scale, then a soft chord under it.
  var RUN = [587.33, 659.25, 783.99, 880.0, 1174.66, 1318.51]; // D5 E5 G5 A5 D6 E6
  var CHORD = [293.66, 440.0, 587.33]; // D4 A4 D5

  function bell(ctx, out, f, t, len, vol) {
    // A sine and a quiet overtone with a fast attack and a long fade sound like a small bell.
    [[1, vol], [2.76, vol * 0.25]].forEach(function (p) {
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.type = 'sine'; o.frequency.value = f * p[0];
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(p[1], t + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, t + len);
      o.connect(g); g.connect(out);
      o.start(t); o.stop(t + len + 0.05);
    });
  }

  function chime() {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    if (window.tcSoundOn && !window.tcSoundOn()) return; // the header toggle says sound off (T156)
    try {
      var ctx = new AC();
      if (ctx.state === 'suspended' && ctx.resume) ctx.resume();
      var out = ctx.createGain();
      out.gain.value = 0.9;
      out.connect(ctx.destination);
      var t0 = ctx.currentTime + 0.02;
      RUN.forEach(function (f, i) { bell(ctx, out, f, t0 + i * 0.09, 0.9, 0.16); });
      var tc = t0 + RUN.length * 0.09 + 0.05;
      CHORD.forEach(function (f) { bell(ctx, out, f, tc, 1.8, 0.09); });
      bell(ctx, out, 1760.0, tc + 0.12, 1.4, 0.06); // A6 sparkle on top
    } catch (e) { /* no sound is fine */ }
  }

  function colours() {
    var s = getComputedStyle(document.documentElement), out = [];
    for (var i = 1; i <= 5; i++) { var c = s.getPropertyValue('--star-' + i).trim(); if (c) out.push(c); }
    return out.length ? out : ['#ffc93c', '#ffb703', '#bc002d', '#12806f', '#ffe28a'];
  }

  function star(g, s) {
    g.beginPath();
    for (var i = 0; i < 10; i++) {
      var r = i % 2 ? s * 0.45 : s, a = Math.PI / 5 * i - Math.PI / 2;
      g.lineTo(Math.cos(a) * r, Math.sin(a) * r);
    }
    g.closePath(); g.fill();
  }

  function reduced() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function stars() {
    if (reduced()) return;
    var cv = document.createElement('canvas');
    cv.className = 'stars';
    cv.setAttribute('aria-hidden', 'true');
    document.body.appendChild(cv);
    var w = cv.width = window.innerWidth, h = cv.height = window.innerHeight;
    var g = cv.getContext('2d'), cols = colours(), bits = [], cx = w / 2, cy = h * 0.38;
    // Two waves: a fast ring of big stars, then a slower cloud of small ones.
    for (var i = 0; i < 110; i++) {
      var big = i < 36, a = big ? (Math.PI * 2 / 36) * i : Math.random() * Math.PI * 2;
      var v = big ? 11 + Math.random() * 3 : 3 + Math.random() * 9;
      bits.push({ x: cx, y: cy, vx: Math.cos(a) * v, vy: Math.sin(a) * v, r: Math.random() * 6.28,
        vr: (Math.random() - .5) * .3, s: big ? 11 + Math.random() * 5 : 5 + Math.random() * 7,
        c: cols[i % cols.length], delay: big ? 0 : 120 + Math.random() * 200 });
    }
    var start = Date.now(), LIFE = 2400;
    (function frame() {
      var age = Date.now() - start;
      g.clearRect(0, 0, w, h);
      if (age < 260) { // a soft flash at the centre
        g.globalAlpha = 1 - age / 260; g.fillStyle = cols[4] || cols[0];
        g.beginPath(); g.arc(cx, cy, 30 + age / 2, 0, Math.PI * 2); g.fill();
      }
      bits.forEach(function (b) {
        if (age < b.delay) return;
        b.vx *= 0.965; b.vy = b.vy * 0.965 + 0.12; b.x += b.vx; b.y += b.vy; b.r += b.vr;
        g.globalAlpha = Math.max(0, 1 - (age - b.delay) / (LIFE - b.delay));
        g.save(); g.translate(b.x, b.y); g.rotate(b.r); g.fillStyle = b.c; star(g, b.s); g.restore();
      });
      g.globalAlpha = 1;
      if (age < LIFE) requestAnimationFrame(frame); else cv.parentNode.removeChild(cv);
    })();
  }

  function penguin(always) {
    var tpl = document.getElementById('penguin-egg');
    if (!tpl || reduced() || document.querySelector('.penguin')) return;
    if (!always && Math.random() >= 1 / 6) return;
    var p = tpl.content.firstElementChild.cloneNode(true);
    document.body.appendChild(p);
    var rtl = document.documentElement.dir === 'rtl', w = window.innerWidth + 90, start = Date.now(), LIFE = 4200;
    (function frame() {
      var k = (Date.now() - start) / LIFE, x = -80 + w * k;
      var tilt = Math.sin(k * Math.PI * 14) * 9;
      p.style.transform = 'translateX(' + (rtl ? w - 80 - x : x) + 'px) rotate(' + tilt + 'deg)' + (rtl ? ' scaleX(-1)' : '');
      if (k < 1) requestAnimationFrame(frame); else p.parentNode.removeChild(p);
    })();
  }

  function celebrate() {
    stars(); chime();
    penguin(/[?&]penguin=1\b/.test(location.search));
  }
  window.celebrate = celebrate;

  document.addEventListener('DOMContentLoaded', function () {
    if (document.body.hasAttribute('data-celebrate')) celebrate();
    var again = document.querySelectorAll('[data-celebrate-again]');
    for (var i = 0; i < again.length; i++) again[i].addEventListener('click', celebrate);
  });
})();
