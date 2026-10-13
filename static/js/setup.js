// Trip setup (feedback T264): one page for the country, the family, the trip length and the modules.
// The - and + buttons change the number boxes. Only the chosen country's modules show. The two group
// switches turn every kids' module (or every grown-ups' module) on or off at once.
(function () {
  var form = document.querySelector("[data-setup]");
  if (!form) return;
  form.querySelectorAll("[data-js-only]").forEach(function (el) { el.hidden = false; });

  function count(id) {
    var input = form.querySelector('[data-stepper="' + id + '"] input');
    return input ? Math.max(0, parseInt(input.value, 10) || 0) : 0;
  }

  form.querySelectorAll("[data-stepper]").forEach(function (box) {
    var input = box.querySelector("input");
    box.querySelectorAll("[data-step]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var before = count(box.dataset.stepper);
        var n = Math.min(12, Math.max(0, before + parseInt(btn.dataset.step, 10)));
        input.value = n;
        // No kids: the kids' modules go off. The first kid: they come back on.
        if (box.dataset.stepper === "kid" && (before === 0) !== (n === 0)) setAudience("child", n > 0);
        if (box.dataset.stepper === "grownup" && (before === 0) !== (n === 0)) setAudience("adult", n > 0);
      });
    });
  });

  function current() { return form.querySelector('[data-modules-for]:not([hidden])'); }

  function setAudience(audience, on) {
    var set = current();
    if (!set) return;
    set.querySelectorAll('[data-audience="' + audience + '"] input').forEach(function (i) { i.checked = on; });
    sync();
  }

  // A group switch is on when every module of its audience is on; it hides when the country has none.
  function sync() {
    var set = current();
    if (!set) return;
    set.querySelectorAll("[data-audience-switch]").forEach(function (sw) {
      var boxes = set.querySelectorAll('[data-audience="' + sw.dataset.audienceSwitch + '"] input');
      sw.hidden = boxes.length === 0;
      sw.querySelector("input").checked = boxes.length > 0 && Array.prototype.every.call(boxes, function (i) { return i.checked; });
    });
  }

  form.querySelectorAll("[data-audience-switch] input").forEach(function (input) {
    input.addEventListener("change", function () { setAudience(input.closest("[data-audience-switch]").dataset.audienceSwitch, input.checked); });
  });
  form.querySelectorAll('.switch-list input').forEach(function (input) { input.addEventListener("change", sync); });

  // Only the chosen country's modules show. A hidden module box is disabled, so it is not sent.
  function showCountry() {
    var picked = form.querySelector('input[name="destination"]:checked');
    form.querySelectorAll("[data-modules-for]").forEach(function (set) {
      var on = picked && set.dataset.modulesFor === picked.value;
      set.hidden = !on;
      set.querySelectorAll('input[name="modules"]').forEach(function (i) { i.disabled = !on; });
    });
    sync();
  }
  form.querySelectorAll('input[name="destination"]').forEach(function (r) { r.addEventListener("change", showCountry); });
  showCountry();

  var firstError = Array.prototype.filter.call(form.querySelectorAll(".errorlist"), function (el) { return el.offsetParent; })[0];
  if (firstError) firstError.scrollIntoView({ block: "center" });
})();
