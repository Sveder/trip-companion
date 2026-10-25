// T310: the 'Watch the 2-minute tour' button on the welcome page opens the demo video in a dialog.
// The YouTube iframe is made only after the tap, and removed when the dialog closes, so the video stops.
// Close: the x button, Esc (or Back on the TV remote, tv.js), or a tap outside the video.
(function () {
  var btn = document.querySelector('[data-tour]'), box = document.getElementById('tour');
  if (!btn || !box || !box.showModal) return;
  var frame = box.querySelector('.tour-frame');

  function open() {
    if (box.open) return;
    var f = document.createElement('iframe');
    f.src = 'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(btn.getAttribute('data-tour')) +
      '?autoplay=1&rel=0&playsinline=1';
    f.title = btn.textContent.trim();
    f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    f.allowFullscreen = true;
    f.referrerPolicy = 'strict-origin-when-cross-origin';
    frame.appendChild(f);
    box.showModal();
    box.querySelector('[data-tour-close]').focus();
  }

  btn.addEventListener('click', open);
  box.querySelector('[data-tour-close]').addEventListener('click', function () { box.close(); });
  box.addEventListener('close', function () {
    frame.innerHTML = '';
    btn.focus();
  });
  // A click on the backdrop lands on the <dialog> itself, outside its content box.
  box.addEventListener('click', function (e) {
    if (e.target !== box) return;
    var r = box.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) box.close();
  });
})();
