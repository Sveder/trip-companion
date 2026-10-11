/* T144: the browser keeps a copy of the family (trip, course, done marks, practice) in localStorage.
   A page with a family saves a fresh copy. A page with no family, or with a new empty one (the cookies are gone),
   sends the copy back to /state/restore/ and reloads, so the family gets the same course again. */
(function () {
  var KEY = 'tc_state', TRIED = 'tc_restore_tried';
  // T155: 'New course' drops the saved copy, so the old family cannot come back from localStorage.
  document.addEventListener('submit', function (e) {
    if (!e.target.hasAttribute || !e.target.hasAttribute('data-clear-state')) return;
    try { localStorage.removeItem(KEY); localStorage.removeItem(KEY + '_at'); } catch (err) { /* ignore */ }
  }, true);
  var body = document.body;
  if (!body || !window.fetch || !window.localStorage) return;

  function store(key, value) { try { localStorage.setItem(key, value); } catch (e) { /* private mode or full */ } }

  var saved;
  try { saved = localStorage.getItem(KEY); } catch (e) { return; }

  function restore() {
    if (!saved) return;
    // One try per tab: a browser that blocks cookies must not reload for ever.
    try { if (sessionStorage.getItem(TRIED)) return; sessionStorage.setItem(TRIED, '1'); } catch (e) { return; }
    var token = document.querySelector('input[name=csrfmiddlewaretoken]');
    if (!token) return;
    fetch('/state/restore/', {
      method: 'POST', credentials: 'same-origin', body: saved,
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token.value }
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (res) { if (res && res.ok) location.reload(); })
      .catch(function () { /* the page still works */ });
  }

  if (body.getAttribute('data-family') !== '1') { restore(); return; }
  fetch('/state.json', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (state) {
      if (!state) return;
      // A new empty family (the cookies were cleared, then a family page opened): bring the old one back.
      if (!state.trip) { restore(); return; }
      store(KEY, JSON.stringify(state));
      store(KEY + '_at', new Date().toISOString());
      try { sessionStorage.removeItem(TRIED); } catch (e) { /* ignore */ }
    })
    .catch(function () { /* offline: keep the old copy */ });
})();
