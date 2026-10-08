// TV mode: the remote's arrow keys move focus between cards, OK opens the card.
// Runs only when the page is in TV mode (<html class="tv">).
(function () {
  var root = document.documentElement;
  if (!root.classList.contains('tv')) return;

  var BACK = { 461: 1, 27: 1, 8: 1 }; // webOS Back, Escape, Backspace
  var DIRS = { 37: 'left', 38: 'up', 39: 'right', 40: 'down' };
  var SELECTOR = 'a[href], button, input:not([type=hidden]):not([type=checkbox]), select, textarea, .card, .spot';

  // In a lesson the arrows stay inside the lesson (its dots, cards, Back and Next) and the "We did it!" form.
  // Only UP with nothing above inside the lesson may leave it, to reach the header (T104).
  function inLesson(el) { return !!(el && el.closest && (el.closest('[data-lesson]') || el.closest('.done-form'))); }

  function targets(scope) {
    var all = document.querySelectorAll(SELECTOR), out = [];
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      if (scope && !inLesson(el)) continue;
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
  function next(from, dir, free) {
    var scoped = !free && inLesson(from);
    var a = from.getBoundingClientRect(), ca = centre(a), best = null, bestScore = Infinity;
    var list = targets(scoped);
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
    if (!best && scoped && dir === 'up') return next(from, dir, true);
    return best;
  }

  function focus(el) {
    el.focus();
    if (el.scrollIntoView) el.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' });
  }

  function first() {
    var main = document.querySelector('main');
    var pick = document.querySelector('[data-lesson]') ? targets(true)[0] : null;
    pick = pick || (main && (main.querySelector('.card') || main.querySelector('.btn, a[href], button, input')));
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

  // The LG remote: OK can arrive as a mouse click at the pointer, and a key can
  // arrive as keyup only. So: listen early (window, capture), accept keyup when no
  // keydown came, and treat a stray click after a key press as OK on the last card.
  var last = null, lastKey = 0, lastPointer = 0, down = {}, px = -1, py = -1;

  function keyOf(e) {
    var k = e.keyCode || e.which;
    if (!k && e.key) k = { ArrowLeft: 37, ArrowUp: 38, ArrowRight: 39, ArrowDown: 40, Enter: 13, Escape: 27 }[e.key] || 0;
    return k;
  }

  function current() {
    var el = document.activeElement;
    if ((!el || el === document.body || el === root) && last && document.contains(last)) { focus(last); el = last; }
    return el;
  }

  function handle(e, key) {
    var el = document.activeElement;
    if (BACK[key]) {
      if (opened) { close(); e.preventDefault(); return; }
      return;
    }
    var dir = DIRS[key];
    if (dir) {
      if (opened) { e.preventDefault(); return; }
      var typing = el && /INPUT|TEXTAREA/.test(el.tagName) && el.type !== 'checkbox';
      if (typing && (dir === 'left' || dir === 'right')) return;
      e.preventDefault();
      el = current();
      if (!el || el === document.body || el === root) { first(); return; }
      var to = next(el, dir);
      if (to) focus(to);
      else window.scrollBy({ top: dir === 'down' ? 300 : dir === 'up' ? -300 : 0, behavior: 'smooth' });
      return;
    }
    if (key === 13) {
      var lost = !el || el === document.body || el === root;
      el = current();
      if (el && el.classList && el.classList.contains('card')) { e.preventDefault(); activate(el); }
      else if ((lost || e.type === 'keyup') && el && el.click && el !== document.body) { e.preventDefault(); el.click(); }
    }
  }

  window.addEventListener('keydown', function (e) {
    var key = keyOf(e);
    lastKey = Date.now();
    debug('keydown ' + key + ' ' + (e.key || ''));
    down[key] = 1;
    if (e.repeat && !DIRS[key]) return;
    if (BACK[key] && key === 8) { var a = document.activeElement; if (a && /INPUT|TEXTAREA/.test(a.tagName)) return; }
    handle(e, key);
  }, true);

  window.addEventListener('keyup', function (e) {
    var key = keyOf(e);
    debug('keyup ' + key + (down[key] ? '' : ' (no keydown)'));
    if (!down[key]) { lastKey = Date.now(); handle(e, key); }
    down[key] = 0;
  }, true);

  document.addEventListener('focusin', function (e) {
    var el = e.target;
    if (el && el.matches && el.matches(SELECTOR) && !el.closest('.sv2')) last = el;
    debug('focus ' + describe(el));
  });

  // Only a pointer that really moved counts as the magic remote in use.
  document.addEventListener('mousemove', function (e) {
    if (Math.abs(e.clientX - px) + Math.abs(e.clientY - py) > 2) lastPointer = Date.now();
    px = e.clientX; py = e.clientY;
  });

  function onTarget(t) { return t && t.closest && (t.closest(SELECTOR) || t.closest('.shade') || t.closest('.sv2')); }

  // A press on empty page must not take the focus away from the card.
  document.addEventListener('mousedown', function (e) {
    if (!onTarget(e.target)) e.preventDefault();
  }, true);

  document.addEventListener('click', function (e) {
    debug('click ' + describe(e.target) + ' at ' + e.clientX + ',' + e.clientY);
    if (opened || onTarget(e.target)) return;
    if (last && document.contains(last) && lastKey >= lastPointer) {
      e.preventDefault();
      focus(last);
      if (last.classList.contains('card')) activate(last); else if (last.click) last.click();
    }
  }, true);

  // webOS: when the pointer hides, put the focus back on a card.
  document.addEventListener('cursorStateChange', function (e) {
    var visible = e.detail && e.detail.visibility;
    debug('cursor ' + (visible ? 'shown' : 'hidden'));
    if (!visible) { if (!current() || document.activeElement === document.body) first(); }
  });

  // ?tvdebug=1 shows the last remote events on screen, for a test on the real TV.
  var log = null;
  function describe(el) {
    if (!el || !el.tagName) return String(el);
    var t = (el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 24);
    return el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : '') + (t ? ' "' + t + '"' : '');
  }
  function debug(line) {
    if (!log) return;
    var row = document.createElement('div');
    row.textContent = new Date().toISOString().slice(14, 23) + ' ' + line;
    log.insertBefore(row, log.firstChild);
    while (log.childNodes.length > 10) log.removeChild(log.lastChild);
  }
  try {
    if (/[?&]tvdebug=1/.test(location.search)) sessionStorage.setItem('tvdebug', '1');
    if (/[?&]tvdebug=0/.test(location.search)) sessionStorage.removeItem('tvdebug');
    if (sessionStorage.getItem('tvdebug')) {
      log = document.createElement('div');
      log.className = 'tv-debug';
      document.body.appendChild(log);
      debug('tv debug on, ' + window.innerWidth + 'x' + window.innerHeight + ' ' + navigator.userAgent.slice(0, 60));
    }
  } catch (err) { /* no sessionStorage: no debug box */ }

  prepare();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', first); else first();
})();
