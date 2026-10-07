// TV mode: the remote's arrow keys move focus between cards, OK opens the card.
// Runs only when the page is in TV mode (<html class="tv">).
(function () {
  var root = document.documentElement;
  if (!root.classList.contains('tv')) return;

  var BACK = { 461: 1, 27: 1, 8: 1 }; // webOS Back, Escape, Backspace
  var DIRS = { 37: 'left', 38: 'up', 39: 'right', 40: 'down' };
  var SELECTOR = 'a[href], button, input:not([type=hidden]):not([type=checkbox]), select, textarea, .card';

  function targets() {
    var all = document.querySelectorAll(SELECTOR), out = [];
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      if (el.closest('.sv2')) continue;
      // A control inside a card belongs to the card: the card takes the focus.
      if (!el.classList.contains('card') && el.closest('.card')) continue;
      var r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      out.push(el);
    }
    return out;
  }

  function prepare() {
    var cards = document.querySelectorAll('.card');
    for (var i = 0; i < cards.length; i++) {
      if (!cards[i].hasAttribute('tabindex')) cards[i].setAttribute('tabindex', '0');
    }
  }

  function centre(r) { return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }

  // Pick the nearest target in the pressed direction; sideways distance costs more.
  function next(from, dir) {
    var a = from.getBoundingClientRect(), ca = centre(a), best = null, bestScore = Infinity;
    var list = targets();
    for (var i = 0; i < list.length; i++) {
      var el = list[i];
      if (el === from) continue;
      var b = el.getBoundingClientRect(), cb = centre(b), main, side;
      if (dir === 'right') { if (b.left < a.right - 4 && cb.x <= ca.x + 4) continue; main = cb.x - ca.x; side = Math.abs(cb.y - ca.y); }
      if (dir === 'left') { if (b.right > a.left + 4 && cb.x >= ca.x - 4) continue; main = ca.x - cb.x; side = Math.abs(cb.y - ca.y); }
      if (dir === 'down') { if (b.top < a.bottom - 4 && cb.y <= ca.y + 4) continue; main = cb.y - ca.y; side = Math.abs(cb.x - ca.x); }
      if (dir === 'up') { if (b.bottom > a.top + 4 && cb.y >= ca.y - 4) continue; main = ca.y - cb.y; side = Math.abs(cb.x - ca.x); }
      if (main <= 0) continue;
      var score = main + side * 3;
      if (score < bestScore) { bestScore = score; best = el; }
    }
    return best;
  }

  function focus(el) {
    el.focus();
    if (el.scrollIntoView) el.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' });
  }

  function first() {
    var main = document.querySelector('main');
    var pick = main && (main.querySelector('.card') || main.querySelector('.btn, a[href], button, input'));
    if (pick) focus(pick);
  }

  var opened = null, shade = null;
  function open(card) {
    shade = document.createElement('div');
    shade.className = 'shade';
    shade.addEventListener('click', close);
    document.body.appendChild(shade);
    card.classList.add('open');
    opened = card;
  }
  function close() {
    if (!opened) return false;
    opened.classList.remove('open');
    if (shade) shade.parentNode.removeChild(shade);
    var card = opened;
    opened = shade = null;
    card.focus();
    return true;
  }

  // OK on a card: follow its link, flip its switch, or show it big.
  function activate(card) {
    if (card.tagName === 'A') { card.click(); return; }
    if (card.tagName === 'LABEL') { card.click(); card.focus(); return; }
    var inner = card.querySelector('a[href], button');
    if (inner) { inner.click(); return; }
    if (opened === card) close(); else open(card);
  }

  document.addEventListener('keydown', function (e) {
    var key = e.keyCode, el = document.activeElement;
    if (BACK[key]) {
      if (opened) { close(); e.preventDefault(); return; }
      if (key === 8 && el && /INPUT|TEXTAREA/.test(el.tagName)) return;
      return;
    }
    var dir = DIRS[key];
    if (dir) {
      if (opened) { e.preventDefault(); return; }
      var typing = el && /INPUT|TEXTAREA/.test(el.tagName) && el.type !== 'checkbox';
      if (typing && (dir === 'left' || dir === 'right')) return;
      e.preventDefault();
      if (!el || el === document.body) { first(); return; }
      var to = next(el, dir);
      if (to) focus(to);
      else window.scrollBy({ top: dir === 'down' ? 300 : dir === 'up' ? -300 : 0, behavior: 'smooth' });
      return;
    }
    if (key === 13 && el && el.classList && el.classList.contains('card')) {
      e.preventDefault();
      activate(el);
    }
  });

  prepare();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', first); else first();
})();
