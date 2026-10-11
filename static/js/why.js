// T154: the buzzing word 'excited' on the welcome page opens the 'why' dialog.
// The first visit opens it by itself once (localStorage 'tc_why_seen').
(function () {
  var word = document.querySelector('[data-why]'), box = document.getElementById('why');
  if (!word || !box || !box.showModal) return;

  var auto = false;
  function open() {
    if (box.open) return;
    box.showModal();
    var btn = box.querySelector('button');
    if (btn) btn.focus();
  }

  word.addEventListener('click', function () { auto = false; open(); });
  // Focus goes back to the word when the dialog closes (Esc, the button or the backdrop).
  // TV mode, first visit (the dialog opened by itself): the focus goes to the first card, so OK opens it (T169).
  box.addEventListener('close', function () {
    var card = auto && document.documentElement.classList.contains('tv') && document.querySelector('main .card');
    auto = false;
    (card || word).focus();
  });
  // A click on the backdrop lands on the <dialog> itself, outside its content box.
  box.addEventListener('click', function (e) {
    if (e.target !== box) return;
    var r = box.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) box.close();
  });

  var seen = false;
  try { seen = localStorage.getItem('tc_why_seen') === '1'; localStorage.setItem('tc_why_seen', '1'); } catch (e) {}
  if (!seen) setTimeout(function () { auto = true; open(); }, 600);
})();
