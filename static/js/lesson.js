// A lesson: one page per screen, with Back and Next. Without JavaScript every page shows, one under the other.
// Page games: tap the dots on a picture (spots), turn cards over (flip), tap the right picture (pick),
// catch a plate on the sushi train (train), and put each word on its picture (match). The "We did it!" button shows on the last page.
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
      var from = at;
      at = Math.max(0, Math.min(pages.length - 1, n));
      for (var i = 0; i < pages.length; i++) {
        pages[i].hidden = i !== at;
        pages[i].classList.remove('enter');
        if (dots[i]) dots[i].className = 'dot' + (i === at ? ' on' : i < at ? ' seen' : '');
      }
      // The new page slides in like a book page: from the reading side on Next, from the other side on Back (T199).
      if (at !== from) {
        pages[at].setAttribute('data-dir', at > from ? 'next' : 'back');
        void pages[at].offsetWidth;
        pages[at].classList.add('enter');
      }
      count.textContent = pages[at].getAttribute('data-label');
      pages[at].dispatchEvent(new CustomEvent('lpage-show'));
      // Pages 2-N carry lazy pictures (T227). The open page and the next one load theirs now, so a picture is
      // ready when Next slides its page in.
      [pages[at], pages[at + 1]].forEach(function (pg) {
        if (pg) pg.querySelectorAll('img[loading="lazy"]').forEach(function (im) { im.loading = 'eager'; });
      });
      prev.style.visibility = at === 0 ? 'hidden' : '';
      next.hidden = at === pages.length - 1;
      if (done) done.hidden = at !== pages.length - 1;
      if (scroll) toTop();
    }
    // After Next or Back the new page starts at its top: the lesson title sits just under the header, or under a
    // fixed or sticky header when one covers the page top (T108). A title already near the top does not move.
    var title = document.querySelector('h1.with-guide') || root;
    function toTop() {
      var cover = 0, head = document.querySelector('header');
      if (head) {
        var pos = getComputedStyle(head).position;
        if (pos === 'fixed' || pos === 'sticky') cover = head.getBoundingClientRect().bottom;
      }
      var top = title.getBoundingClientRect().top;
      if (top >= cover && top < window.innerHeight / 3) return;
      var y = top + window.pageYOffset - cover - 8;
      var smooth = !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
      window.scrollTo({ top: Math.max(0, y), behavior: smooth ? 'smooth' : 'auto' });
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
      if (Math.abs(dx) < 70 || (e.target.closest && (e.target.closest('.belt') || e.target.closest('[data-match]')))) return;
      var fwd = document.documentElement.dir === 'rtl' ? dx > 0 : dx < 0;
      show(at + (fwd ? 1 : -1), true);
    });
    root.addEventListener('animationend', function (e) {
      if (e.target.classList && e.target.classList.contains('lpage')) e.target.classList.remove('enter');
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
        // A number sits half its width plus 3 px outside the picture (T116). No 20 px cap: a 42 px TV number at 20 px
        // covered the picture edge by 1-4 px (T172).
        var off = s.b.offsetWidth / 2 + 3, bx = k === 'l' ? -off : w + off;
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
    // A name in the start list taps its number (T135).
    page.addEventListener('click', function (e) {
      var nm = e.target.closest('[data-spot-name]');
      if (nm) box.querySelector('.lspot[data-spot="' + nm.getAttribute('data-spot-name') + '"]').click();
    });
    var start = page.querySelector('[data-spot-start]');
    box.addEventListener('click', function (e) {
      var b = e.target.closest('[data-spot]');
      if (!b) return;
      var n = b.getAttribute('data-spot');
      if (start) start.classList.remove('show');
      var infos = page.querySelectorAll('[data-spot-info]');
      var word = null;
      for (var i = 0; i < infos.length; i++) {
        var shown = infos[i].getAttribute('data-spot-info') === n;
        infos[i].classList.toggle('show', shown);
        if (shown) word = infos[i].querySelector('[data-say]');
      }
      // A dot with a Japanese word says it, the same as a tap on the word (T156). No word, no sound.
      if (word && window.tcSay) window.tcSay(word);
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
    // Endless mode after the last round (T157): ask a random plate, count the catches, keep the best.
    var endless = game.querySelector('[data-endless]');
    var more = game.querySelector('[data-train-more]');
    var againBox = game.querySelector('[data-train-again]');
    var scoreEl = game.querySelector('[data-train-score]');
    var key = game.getAttribute('data-best-key');
    var want = null, streak = 0, playing = false;
    function show() {
      for (var i = 0; i < rounds.length; i++) rounds[i].hidden = playing || i !== at;
      if (endless) endless.hidden = !playing;
    }
    function best() {
      try { return parseInt(localStorage.getItem(key), 10) || 0; } catch (e) { return 0; }
    }
    function saveBest(n) {
      try { if (n > best()) localStorage.setItem(key, String(n)); } catch (e) { /* private mode: no best kept */ }
    }
    // Plates on the belt, once each (the belt holds two passes of the same plates).
    function plates() {
      var all = game.querySelectorAll('[data-plate]:not([aria-hidden])'), out = [];
      for (var i = 0; i < all.length; i++) out.push(all[i]);
      return out;
    }
    function ask() {
      var list = plates().filter(function (p) { return p.getAttribute('data-plate') !== want; });
      var pick = list[Math.floor(Math.random() * list.length)];
      want = pick.getAttribute('data-plate');
      var name = pick.querySelector('img').getAttribute('alt').toLowerCase();
      game.querySelector('[data-endless-ask]').textContent = T.catchIt.replace('{name}', name);
    }
    function score() {
      scoreEl.hidden = false;
      scoreEl.textContent = T.score.replace('{n}', streak);
    }
    function keepGoing() {
      playing = true; streak = 0; want = null;
      more.hidden = true; againBox.hidden = true;
      game.classList.remove('won');
      msg.textContent = '';
      ask(); score(); show();
      var first = plates()[0];
      if (first && document.documentElement.classList.contains('tv')) first.focus();
    }
    function endStreak() {
      saveBest(streak);
      game.classList.add('won');
      scoreEl.hidden = true;
      msg.textContent = T.streakEnd.replace('{n}', streak).replace('{best}', best());
      againBox.hidden = false;
      var b = againBox.querySelector('button');
      if (document.documentElement.classList.contains('tv')) b.focus();
    }
    function right(btn) {
      busy = true;
      btn.classList.add('right');
      msg.textContent = T.right;
      if (playing) { streak++; score(); }
      setTimeout(function () {
        btn.classList.remove('right');
        busy = false;
        if (playing) {
          msg.textContent = ''; ask();
          faster();
          return;
        }
        if (at === rounds.length - 1) {
          msg.textContent = T.allRounds;
          game.classList.add('won');
          if (more) {
            more.hidden = false;
            var bestNow = best();
            if (bestNow) msg.textContent += ' ' + T.best.replace('{best}', bestNow);
          }
          cheer();
          return;
        }
        at++; msg.textContent = ''; show();
        if (train) faster();
      }, 900);
    }
    // The sushi train: every round we finish makes the belt about 7% faster than the round before (T103).
    // playbackRate keeps the plates where they are; a new animation-duration would make them jump.
    // Endless mode keeps speeding up, up to 2.5 times the base speed, so a long streak stays catchable.
    var rate = 1;
    function faster() {
      rate = Math.min(rate * 1.07, 2.5);
      var track = game.querySelector('.belt-track');
      var anim = track.getAnimations ? track.getAnimations()[0] : null;
      if (anim) anim.playbackRate = rate;
      else track.style.animationDuration = (21 / rate) + 's';
    }
    // A hidden page stops its animation, and the browser starts a new one at speed 1 when the page shows again.
    if (train) game.closest('[data-page]').addEventListener('lpage-show', function () {
      var anim = game.querySelector('.belt-track').getAnimations;
      if (rate !== 1 && anim) { rate /= 1.07; faster(); }
    });
    function wrong(btn) {
      btn.classList.remove('wrong'); void btn.offsetWidth; btn.classList.add('wrong');
      if (playing) { endStreak(); return; }
      msg.textContent = T.wrong;
    }
    game.addEventListener('click', function (e) {
      if (e.target.closest('[data-keep-going]') || e.target.closest('[data-again]')) { keepGoing(); return; }
      if (busy || game.classList.contains('won')) return;
      if (train) {
        var plate = e.target.closest('[data-plate]');
        if (!plate) return;
        var answer = playing ? want : rounds[at].getAttribute('data-answer');
        (plate.getAttribute('data-plate') === answer ? right : wrong)(plate);
        return;
      }
      var c = e.target.closest('[data-choice]');
      if (!c || !rounds[at].contains(c)) return;
      (c.hasAttribute('data-right') ? right : wrong)(c);
    });
    show();
  }

  // Put the word where it belongs (T162). Three ways in: drag a plate onto a picture (pointer events, so mouse and
  // touch both work), tap a plate and then a picture, or the TV remote, where OK is the tap. A right drop fills the
  // slot under the picture and says the word; a wrong one shakes the plate back. Nothing moves the page around:
  // a lifted plate only moves by transform, and a placed plate keeps its room in the row (T116 rule).
  function setupMatch(game) {
    var rounds = game.querySelectorAll('[data-match-round]');
    var msg = game.querySelector('[data-game-msg]');
    var nextBox = game.querySelector('[data-match-next]'), againBox = game.querySelector('[data-match-again]');
    var tv = document.documentElement.classList.contains('tv');
    var at = 0, picked = null, drag = null, skipClick = false;
    function round() { return rounds[at]; }
    function shuffle(r) {
      var row = r.querySelector('.match-plates'), list = Array.prototype.slice.call(row.children);
      for (var i = list.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1)), t = list[i]; list[i] = list[j]; list[j] = t;
      }
      // Never start with every plate under its own picture.
      var same = list.every(function (p, k) { return r.querySelectorAll('[data-target]')[k].getAttribute('data-target') === p.getAttribute('data-match-plate'); });
      if (same && list.length > 1) list.push(list.shift());
      list.forEach(function (p) { row.appendChild(p); });
    }
    function lift(plate) {
      if (picked) picked.setAttribute('aria-pressed', 'false');
      picked = plate;
      if (plate) plate.setAttribute('aria-pressed', 'true');
    }
    function tryPut(plate, target) {
      var ok = plate.getAttribute('data-match-plate') === target.getAttribute('data-target');
      lift(null);
      if (!ok) {
        plate.classList.remove('wrong'); target.classList.remove('bad');
        void plate.offsetWidth;
        plate.classList.add('wrong'); target.classList.add('bad');
        setTimeout(function () { plate.classList.remove('wrong'); target.classList.remove('bad'); }, 600);
        msg.textContent = T.wrong;
        return;
      }
      var slot = target.querySelector('[data-slot]');
      slot.innerHTML = plate.innerHTML;
      target.classList.add('right');
      target.disabled = true;
      plate.classList.add('placed');
      plate.disabled = true;
      plate.setAttribute('aria-hidden', 'true');
      if (window.tcSay) window.tcSay(plate);
      msg.textContent = T.right;
      var left = round().querySelectorAll('[data-match-plate]:not(.placed)');
      if (left.length) {
        if (tv) left[0].focus();
        return;
      }
      var total = round().querySelectorAll('[data-match-plate]').length;
      msg.textContent = T.placedAll.replace('{n}', total);
      cheer();
      var box = at < rounds.length - 1 ? nextBox : againBox;
      box.hidden = false;
      if (tv) box.querySelector('button').focus();
    }
    function reset(r) {
      r.querySelectorAll('[data-match-plate]').forEach(function (p) {
        p.classList.remove('placed', 'wrong'); p.disabled = false; p.removeAttribute('aria-hidden');
        p.setAttribute('aria-pressed', 'false'); p.style.transform = '';
      });
      r.querySelectorAll('[data-target]').forEach(function (t) {
        t.classList.remove('right', 'bad'); t.disabled = false; t.querySelector('[data-slot]').innerHTML = '';
      });
      shuffle(r);
    }
    function go(n) {
      at = n; lift(null);
      for (var i = 0; i < rounds.length; i++) rounds[i].hidden = i !== at;
      nextBox.hidden = true; againBox.hidden = true; msg.textContent = '';
      reset(round());
      if (tv) { var first = round().querySelector('[data-match-plate]'); if (first) first.focus(); }
    }
    game.addEventListener('click', function (e) {
      if (e.target.closest('[data-next-round]')) { go(at + 1); return; }
      if (e.target.closest('[data-match-replay]')) { go(0); return; }
      if (skipClick) { skipClick = false; return; }
      var plate = e.target.closest('[data-match-plate]');
      if (plate && round().contains(plate)) {
        if (plate.classList.contains('placed')) return;
        lift(picked === plate ? null : plate);
        return;
      }
      var target = e.target.closest('[data-target]');
      if (!target || !round().contains(target) || target.classList.contains('right')) return;
      if (!picked) { msg.textContent = T.pickWord; return; }
      tryPut(picked, target);
    });
    // Drag: the plate follows the finger by transform only, and drops on the picture under the pointer.
    game.addEventListener('pointerdown', function (e) {
      var plate = e.target.closest('[data-match-plate]');
      if (!plate || plate.classList.contains('placed') || (e.pointerType === 'mouse' && e.button !== 0)) return;
      drag = { plate: plate, id: e.pointerId, x: e.clientX, y: e.clientY, moved: false };
      try { plate.setPointerCapture(e.pointerId); } catch (err) { /* old browser: the plate still gets the moves */ }
    });
    game.addEventListener('pointermove', function (e) {
      if (!drag || e.pointerId !== drag.id) return;
      var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (!drag.moved && dx * dx + dy * dy < 64) return;
      if (!drag.moved) { drag.moved = true; lift(drag.plate); drag.plate.classList.add('dragging'); }
      drag.plate.style.transform = 'translate(' + dx + 'px,' + dy + 'px)';
      e.preventDefault();
    });
    function endDrag(e, cancel) {
      if (!drag || e.pointerId !== drag.id) return;
      var d = drag; drag = null;
      if (!d.moved) return;
      skipClick = true;
      setTimeout(function () { skipClick = false; }, 0);
      d.plate.classList.remove('dragging');
      d.plate.style.visibility = 'hidden';
      var under = cancel ? null : document.elementFromPoint(e.clientX, e.clientY);
      d.plate.style.visibility = '';
      d.plate.style.transform = '';
      var target = under && under.closest ? under.closest('[data-target]') : null;
      if (target && round().contains(target) && !target.classList.contains('right')) tryPut(d.plate, target);
      else lift(null);
    }
    game.addEventListener('pointerup', function (e) { endDrag(e, false); });
    game.addEventListener('pointercancel', function (e) { endDrag(e, true); });
    rounds.forEach(shuffle);
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-spots]').forEach(setupSpots);
    document.querySelectorAll('[data-game]').forEach(setupGame);
    document.querySelectorAll('[data-match]').forEach(setupMatch);
    document.querySelectorAll('[data-flip]').forEach(function (b) {
      b.addEventListener('click', function () {
        var on = b.getAttribute('aria-pressed') !== 'true';
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    });
    document.querySelectorAll('[data-lesson]').forEach(setupLesson);
  });
})();
