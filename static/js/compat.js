// Old browsers (the LG TV runs Chrome 87) have no CSS :has(). The CSS keeps :has() for new
// browsers and also styles a class that this script sets: .on on a .pick or .module label
// whose input is checked, .kb-focus while its input has the focus.
(function () {
  var SEL = '.pick, .module';
  function sync() {
    var labels = document.querySelectorAll(SEL);
    for (var i = 0; i < labels.length; i++) {
      var input = labels[i].querySelector('input');
      if (input) labels[i].classList.toggle('on', input.checked);
    }
  }
  function onFocus(e, on) {
    var label = e.target.closest && e.target.closest(SEL);
    if (label && e.target.tagName === 'INPUT') label.classList.toggle('kb-focus', on);
  }
  // A radio that turns off sends no change event, so every change syncs every label.
  document.addEventListener('change', sync);
  document.addEventListener('focusin', function (e) { onFocus(e, true); });
  document.addEventListener('focusout', function (e) { onFocus(e, false); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', sync);
  else sync();
  // The back button can restore checked boxes from the page cache.
  window.addEventListener('pageshow', sync);
})();
