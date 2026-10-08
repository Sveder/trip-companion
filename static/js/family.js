// Trip setup (feedback T53): put the family on the plane. Drag a person into the plane, or tap them;
// tap a person in the plane to take them off. The number boxes stay the form fields, so the server sees counts.
(function () {
  var box = document.querySelector("[data-family]");
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
})();
