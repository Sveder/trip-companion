// Street View hunt: count the finds; when every thing is found, celebrate and go on.
// A checkbox is not a TV focus target, so in TV mode OK on a label (made focusable here) ticks it.
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    var form = document.querySelector('[data-hunt]');
    if (!form) return;
    var boxes = form.querySelectorAll('input[name=found]');
    var count = form.querySelector('[data-count]');
    var btn = form.querySelector('.hunt-skip');
    var label = btn && btn.querySelector('[data-label]');
    var wasDone = boxes.length && form.querySelectorAll('input[name=found]:checked').length === boxes.length;
    var sent = false;

    function update() {
      var n = form.querySelectorAll('input[name=found]:checked').length;
      var T = window.T || {};
      count.textContent = (T.found || '{n} of {total} found').replace('{n}', n).replace('{total}', boxes.length);
      // T274: the one button says "Skip" while things are missing and "Next" when all are found.
      if (label) {
        var all = n === boxes.length;
        label.textContent = all ? btn.getAttribute('data-next') : btn.getAttribute('data-skip');
        btn.className = btn.className.replace(/ ?\balt\b/g, '') + (all ? '' : ' alt');
      }
      if (n === boxes.length && !wasDone && !sent) {
        sent = true;
        count.textContent = T.allFound || 'You found them all! 🎉';
        if (window.celebrate) window.celebrate();
        setTimeout(function () { form.submit(); }, 2600);
      }
    }

    // T273: a found thing folds to its title. A tap on a found row opens or folds it;
    // a tap on its round tick un-finds it.
    function mark(label) {
      var box = label.querySelector('input');
      label.className = label.className.replace(/ ?\b(done|open)\b/g, '') + (box.checked ? ' done' : '');
    }

    var labels = form.querySelectorAll('.spot');
    for (var i = 0; i < labels.length; i++) {
      labels[i].setAttribute('tabindex', '0');
      labels[i].addEventListener('click', function (e) {
        var box = this.querySelector('input');
        if (e.target === box || !box.checked) return;
        var t = e.target;
        while (t && t !== this) { if (t.className === 'spot-tick') return; t = t.parentNode; }
        e.preventDefault();
        if (/\bopen\b/.test(this.className)) this.className = this.className.replace(/ ?\bopen\b/, '');
        else this.className += ' open';
      });
      labels[i].addEventListener('keydown', function (e) {
        if (e.keyCode === 13 || e.keyCode === 32) {
          e.preventDefault();
          var box = this.querySelector('input');
          // OK on the TV: find it; OK again opens it; OK on an open one un-finds it.
          if (box.checked && !/\bopen\b/.test(this.className)) { this.className += ' open'; return; }
          box.checked = !box.checked;
          mark(this);
          update();
        }
      });
    }
    for (var j = 0; j < boxes.length; j++) boxes[j].addEventListener('change', function () { mark(this.parentNode); update(); });
    update();
  });
})();
