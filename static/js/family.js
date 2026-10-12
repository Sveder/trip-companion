// Trip setup (feedback T53): put the family on the plane. Drag a person into the plane, or tap them;
// tap a person in the plane to take them off. The number boxes stay the form fields, so the server sees counts.
(function () {
  var box = document.querySelector("[data-family-pick]");
  if (!box) return;
  var plane = box.querySelector("[data-plane]");
  var seats = box.querySelector("[data-seats]");
  var empty = box.querySelector("[data-empty]");
  var count = box.querySelector("[data-count]");
  var groups = Array.prototype.slice.call(box.querySelectorAll("[data-group]"));
  var MAX = 12;
  box.classList.add("js");
  box.querySelectorAll("[data-js-only]").forEach(function (el) { el.hidden = false; });

  function input(g) { return g.querySelector("input"); }
  function value(g) { return Math.max(0, parseInt(input(g).value, 10) || 0); }
  function total() { return groups.reduce(function (s, g) { return s + value(g); }, 0); }

  function draw() {
    seats.innerHTML = "";
    groups.forEach(function (g) {
      for (var i = 0; i < value(g); i++) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "seat";
        b.textContent = g.dataset.emoji;
        b.setAttribute("aria-label", window.T.takeOff.replace("{who}", g.dataset.label));
        b.addEventListener("click", function () { change(g, -1); });
        seats.appendChild(b);
      }
    });
    groups.forEach(function (g) {
      var badge = g.querySelector(".person-n");
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "person-n";
        badge.setAttribute("aria-hidden", "true");
        g.querySelector("[data-person]").appendChild(badge);
      }
      badge.textContent = value(g) || "";
      badge.hidden = !value(g);
    });
    var n = total();
    empty.hidden = n > 0;
    count.textContent = n ? window.T.onPlane.replace("{n}", n) : "";
  }

  function change(g, by) {
    var next = value(g) + by;
    if (next < 0 || (by > 0 && total() >= MAX)) return;
    input(g).value = next;
    draw();
    if (total() > 0) { var pe = box.querySelector("[data-plane-error]"); if (pe) pe.hidden = true; }
    if (by > 0) {
      plane.classList.remove("bump");
      void plane.offsetWidth;
      plane.classList.add("bump");
    }
  }

  groups.forEach(function (g) {
    var person = g.querySelector("[data-person]");
    input(g).addEventListener("input", draw);
    // Pointer events work for a mouse and a finger. A short press with no movement is a tap.
    person.addEventListener("pointerdown", function (e) {
      if (e.button) return;
      e.preventDefault();
      var startX = e.clientX, startY = e.clientY, ghost = null;
      function move(ev) {
        if (!ghost && Math.abs(ev.clientX - startX) + Math.abs(ev.clientY - startY) < 8) return;
        if (!ghost) {
          ghost = document.createElement("div");
          ghost.className = "person-ghost";
          ghost.textContent = g.dataset.emoji;
          document.body.appendChild(ghost);
        }
        ghost.style.left = ev.clientX + "px";
        ghost.style.top = ev.clientY + "px";
        plane.classList.toggle("over", over(ev));
      }
      function over(ev) {
        var r = plane.getBoundingClientRect();
        return ev.clientX >= r.left && ev.clientX <= r.right && ev.clientY >= r.top && ev.clientY <= r.bottom;
      }
      function up(ev) {
        document.removeEventListener("pointermove", move);
        document.removeEventListener("pointerup", up);
        document.removeEventListener("pointercancel", up);
        plane.classList.remove("over");
        if (!ghost) { if (ev.type === "pointerup") change(g, 1); return; }
        ghost.remove();
        if (ev.type === "pointerup" && over(ev)) change(g, 1);
      }
      document.addEventListener("pointermove", move);
      document.addEventListener("pointerup", up);
      document.addEventListener("pointercancel", up);
    });
    // Keyboard and TV remote: Enter on the person adds one (a click with no pointer).
    person.addEventListener("click", function (e) { if (e.detail === 0) change(g, 1); });
  });
  draw();

  // T166: a pick of a country moves on to the family step. On the TV (or a keyboard) the focus goes to the
  // first person, so the next OK adds someone. Later than tv.js, which puts the focus back on the card it clicked.
  var tv = document.documentElement.classList.contains("tv");
  function toFamily(keys) {
    box.scrollIntoView({ block: "start", behavior: "smooth" });
    var first = box.querySelector("[data-person]");
    if (first && (tv || keys)) first.focus({ preventScroll: true });
  }
  var pending = null;
  document.querySelectorAll(".countries-pick label.pick").forEach(function (label) {
    // A click on a label also clicks its radio: two click events, one move.
    label.addEventListener("click", function (e) {
      var keys = e.detail === 0;
      if (pending) return;
      pending = setTimeout(function () { pending = null; toFamily(keys); }, 50);
    });
  });
  var nextStep = document.querySelector("[data-next-step]");
  if (nextStep) nextStep.addEventListener("click", function (e) { e.preventDefault(); toFamily(e.detail === 0); });

  // T207: an empty plane. Show the message by the plane at once (no round trip), or after the server sent it
  // back; scroll it into view and shake the plane, so the family sees why nothing moved on.
  var planeError = box.querySelector("[data-plane-error]");
  function showError() {
    planeError.hidden = false;
    planeError.scrollIntoView({ block: "center" });
    plane.classList.remove("shake");
    void plane.offsetWidth;
    plane.classList.add("shake");
  }
  var form = box.closest("form");
  if (form && planeError) form.addEventListener("submit", function (e) {
    if (total() > 0) return;
    e.preventDefault();
    showError();
  });
  if (planeError && !planeError.hidden) showError();
  else {
    var firstError = Array.prototype.filter.call(document.querySelectorAll("form .errorlist"), function (el) { return el.offsetParent; })[0];
    if (firstError) firstError.scrollIntoView({ block: "center" });
  }
  groups.forEach(function (g) { input(g).addEventListener("input", function () { if (total() > 0 && planeError) planeError.hidden = true; }); });
})();
