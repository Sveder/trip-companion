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

  function setupSpots(box) {
    var total = +box.getAttribute('data-total');
    var page = box.closest('[data-page]');
    var label = page.querySelector('[data-spots-count]');
    var seen = {};
    function update() { label.textContent = fmt(T.seen, Object.keys(seen).length, total); }
    box.addEventListener('click', function (e) {
      var b = e.target.closest('[data-spot]');
      if (!b) return;
      var n = b.getAttribute('data-spot');
      var infos = page.querySelectorAll('[data-spot-info]');
      for (var i = 0; i < infos.length; i++) infos[i].hidden = infos[i].getAttribute('data-spot-info') !== n;
      var spots = box.querySelectorAll('[data-spot]');
      for (var j = 0; j < spots.length; j++) spots[j].classList.toggle('on', spots[j] === b);
      b.classList.add('seen');
      var first = !seen[n];
      seen[n] = 1;
      update();
      if (first && Object.keys(seen).length === total) cheer();
    });
    update();
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
      }, 900);
    }
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
