// A lesson: one page per screen, with Back and Next. Without JavaScript every page shows, one under the other.
// Page games: tap the dots on a picture (spots), turn cards over (flip), tap the right picture (pick),
// and catch a plate on the sushi train (train). The "We did it!" button shows on the last page.
(function () {
  var T = window.T || {};
  function fmt(s, n, total) { return (s || '').replace('{n}', n).replace('{total}', total); }
  function cheer(small) {
    if (small) return;
    if (window.celebrate) window.celebrate();
  }

  function setupLesson(root) {
    var pages = root.querySelectorAll('[data-page]');
    var dots = root.querySelectorAll('.lesson-dots .dot');
    var count = root.querySelector('[data-count]');
    var nav = root.querySelector('[data-lesson-nav]');
    var prev = nav.querySelector('[data-prev]'), next = nav.querySelector('[data-next]');
    var done = document.querySelector('.done-form');
    var at = 0;
    root.classList.add('paged');
    nav.hidden = false;
    function show(n, scroll) {
      at = Math.max(0, Math.min(pages.length - 1, n));
      for (var i = 0; i < pages.length; i++) {
        pages[i].hidden = i !== at;
        if (dots[i]) dots[i].className = 'dot' + (i === at ? ' on' : i < at ? ' seen' : '');
      }
      count.textContent = pages[at].getAttribute('data-label');
      pages[at].dispatchEvent(new CustomEvent('lpage-show'));
      prev.style.visibility = at === 0 ? 'hidden' : '';
      next.hidden = at === pages.length - 1;
      if (done) done.hidden = at !== pages.length - 1;
      if (scroll) root.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }
    prev.addEventListener('click', function () { show(at - 1, true); });
    next.addEventListener('click', function () { show(at + 1, true); });
    document.addEventListener('keydown', function (e) {
      var rtl = document.documentElement.dir === 'rtl';
      if (e.target.closest && e.target.closest('input, textarea')) return;
      // On the TV the arrow keys move the focus ring (tv.js marks them handled); OK on Next turns the page (T104).
      if (e.defaultPrevented || document.documentElement.classList.contains('tv')) return;
      if (e.key === 'ArrowRight') show(at + (rtl ? -1 : 1), false);
      if (e.key === 'ArrowLeft') show(at + (rtl ? 1 : -1), false);
    });
    // A swipe on a phone turns the page too.
    var x0 = null;
    root.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
    root.addEventListener('touchend', function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0; x0 = null;
      if (Math.abs(dx) < 70 || (e.target.closest && e.target.closest('.belt'))) return;
      var fwd = document.documentElement.dir === 'rtl' ? dx > 0 : dx < 0;
      show(at + (fwd ? 1 : -1), true);
    });
    show(0, false);
  }

  // The numbers go to the side of the picture nearest their thing, in the same order from top to bottom,
  // and a line leads from each number to a small ring on the thing. So no number covers what it names (T103).
  var SVG = 'http://www.w3.org/2000/svg';
  function placeSpots(box) {
    var img = box.querySelector('.lpic'), svg = box.querySelector('.lspot-lines');
    var w = img.offsetWidth, h = img.offsetHeight;
    if (!w || !h) return;
    box.classList.add('edge');
    w = img.offsetWidth; h = img.offsetHeight;
    var btns = box.querySelectorAll('.lspot'), sides = { l: [], r: [] };
    for (var i = 0; i < btns.length; i++) {
      var x = +btns[i].getAttribute('data-x'), y = +btns[i].getAttribute('data-y');
      sides[x < 50 ? 'l' : 'r'].push({ b: btns[i], x: x * w / 100, y: y * h / 100, side: x < 50 ? 'l' : 'r' });
    }
    // A side with more numbers than fit beside the picture gives the one nearest the middle to the other side.
    var GAP = Math.max(37, btns.length ? btns[0].offsetHeight + 2 : 0), fits = Math.floor((h + 24) / GAP) || 1;
    function mid(a, b) { return Math.abs(a.x - w / 2) - Math.abs(b.x - w / 2); }
    ['l', 'r'].forEach(function (k) {
      var other = k === 'l' ? 'r' : 'l';
      while (sides[k].length > fits && sides[other].length < fits) {
        var s = sides[k].sort(mid).shift();
        s.side = other; sides[other].push(s);
      }
    });
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    ['l', 'r'].forEach(function (k) {
      var list = sides[k].sort(function (a, b) { return a.y - b.y; });
      if (!list.length) return;
      var span = (list.length - 1) * GAP, j;
      if (span > h) {
        // Still too many: spread them evenly, a little above and below the picture.
        for (j = 0; j < list.length; j++) list[j].at = h / 2 - span / 2 + j * GAP;
      } else {
        for (j = 0; j < list.length; j++) list[j].at = Math.max(list[j].y, j ? list[j - 1].at + GAP : 0);
        for (j = list.length - 1; j >= 0; j--) list[j].at = Math.min(list[j].at, j === list.length - 1 ? h : list[j + 1].at - GAP);
      }
      list.forEach(function (s) {
        var bx = k === 'l' ? -20 : w + 20;
        // The line stops at the edge of the ring, so the ring stays empty and the thing shows through it.
        var sx = k === 'l' ? -4 : w + 4, dx = s.x - sx, dy = s.y - s.at, len = Math.sqrt(dx * dx + dy * dy) || 1;
        var ex = s.x - dx * 9 / len, ey = s.y - dy * 9 / len;
        s.b.style.left = bx + 'px';
        s.b.style.top = s.at + 'px';
        ['under', 'over'].forEach(function (c) {
          var line = document.createElementNS(SVG, 'line');
          line.setAttribute('x1', sx); line.setAttribute('y1', s.at);
          line.setAttribute('x2', ex); line.setAttribute('y2', ey);
          line.setAttribute('class', c + (s.b.classList.contains('seen') ? ' seen' : ''));
          line.setAttribute('data-line', s.b.getAttribute('data-spot'));
          svg.appendChild(line);
        });
      });
    });
  }

  function setupSpots(box) {
    var total = +box.getAttribute('data-total');
    var page = box.closest('[data-page]');
    var label = page.querySelector('[data-spots-count]');
    var seen = {};
    function update() { label.textContent = fmt(T.seen, Object.keys(seen).length, total); }
    function place() { placeSpots(box); }
    box.querySelector('.lpic').addEventListener('load', place);
    window.addEventListener('resize', place);
    page.addEventListener('lpage-show', place);
    box.addEventListener('click', function (e) {
      var b = e.target.closest('[data-spot]');
      if (!b) return;
      var n = b.getAttribute('data-spot');
      var infos = page.querySelectorAll('[data-spot-info]');
      for (var i = 0; i < infos.length; i++) infos[i].classList.toggle('show', infos[i].getAttribute('data-spot-info') === n);
      var marks = box.querySelectorAll('[data-spot], [data-line]');
      for (var j = 0; j < marks.length; j++) {
        var mine = (marks[j].getAttribute('data-spot') || marks[j].getAttribute('data-line')) === n;
        if (marks[j].hasAttribute('data-spot')) marks[j].classList.toggle('on', mine);
        if (mine) marks[j].classList.add('seen');
      }
      var first = !seen[n];
      seen[n] = 1;
      update();
      if (first && Object.keys(seen).length === total) cheer();
    });
    update();
    place();
  }

  function setupGame(game) {
    var rounds = game.querySelectorAll('[data-round]');
    var msg = game.querySelector('[data-game-msg]');
    var train = game.hasAttribute('data-train');
    var at = 0, busy = false;
    function show() {
      for (var i = 0; i < rounds.length; i++) rounds[i].hidden = i !== at;
    }
    function right(btn) {
      busy = true;
      btn.classList.add('right');
      msg.textContent = T.right;
      setTimeout(function () {
        btn.classList.remove('right');
        busy = false;
        if (at === rounds.length - 1) {
          msg.textContent = T.allRounds;
          game.classList.add('won');
          cheer();
          return;
        }
        at++; msg.textContent = ''; show();
        if (train) faster();
      }, 900);
    }
    // The sushi train: every round we finish makes the belt about 7% faster than the round before (T103).
    // playbackRate keeps the plates where they are; a new animation-duration would make them jump.
    var rate = 1;
    function faster() {
      rate *= 1.07;
      var track = game.querySelector('.belt-track');
      var anim = track.getAnimations ? track.getAnimations()[0] : null;
      if (anim) anim.playbackRate = rate;
      else track.style.animationDuration = (30 / rate) + 's';
    }
    // A hidden page stops its animation, and the browser starts a new one at speed 1 when the page shows again.
    if (train) game.closest('[data-page]').addEventListener('lpage-show', function () {
      var anim = game.querySelector('.belt-track').getAnimations;
      if (rate !== 1 && anim) { rate /= 1.07; faster(); }
    });
    function wrong(btn) {
      btn.classList.remove('wrong'); void btn.offsetWidth; btn.classList.add('wrong');
      msg.textContent = T.wrong;
    }
    game.addEventListener('click', function (e) {
      if (busy || game.classList.contains('won')) return;
      if (train) {
        var plate = e.target.closest('[data-plate]');
        if (!plate) return;
        (plate.getAttribute('data-plate') === rounds[at].getAttribute('data-answer') ? right : wrong)(plate);
        return;
      }
      var c = e.target.closest('[data-choice]');
      if (!c || !rounds[at].contains(c)) return;
      (c.hasAttribute('data-right') ? right : wrong)(c);
    });
    show();
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-spots]').forEach(setupSpots);
    document.querySelectorAll('[data-game]').forEach(setupGame);
    document.querySelectorAll('[data-flip]').forEach(function (b) {
      b.addEventListener('click', function () {
        var on = b.getAttribute('aria-pressed') !== 'true';
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    });
    document.querySelectorAll('[data-lesson]').forEach(setupLesson);
  });
})();
