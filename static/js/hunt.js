// Street View hunt: count the finds; when every thing is found, celebrate and go on.
// A checkbox is not a TV focus target, so in TV mode OK on a label (made focusable here) ticks it.
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    var form = document.querySelector('[data-hunt]');
    if (!form) return;
    var boxes = form.querySelectorAll('input[name=found]');
    var count = form.querySelector('[data-count]');
    var wasDone = boxes.length && form.querySelectorAll('input[name=found]:checked').length === boxes.length;
    var sent = false;

    function update() {
      var n = form.querySelectorAll('input[name=found]:checked').length;
      var T = window.T || {};
      count.textContent = (T.found || '{n} of {total} found').replace('{n}', n).replace('{total}', boxes.length);
      if (n === boxes.length && !wasDone && !sent) {
        sent = true;
        count.textContent = T.allFound || 'You found them all! 🎉';
        if (window.celebrate) window.celebrate();
        setTimeout(function () { form.submit(); }, 2600);
      }
    }

    var labels = form.querySelectorAll('.spot');
    for (var i = 0; i < labels.length; i++) {
      labels[i].setAttribute('tabindex', '0');
      labels[i].addEventListener('keydown', function (e) {
        if (e.keyCode === 13 || e.keyCode === 32) {
          e.preventDefault();
          var box = this.querySelector('input');
          box.checked = !box.checked;
          update();
        }
      });
    }
    for (var j = 0; j < boxes.length; j++) boxes[j].addEventListener('change', update);
    update();
  });
})();
