// Count a video play. A YouTube frame is another site, so the page cannot see the play button.
// When the family taps the video, the page loses focus to the frame: that tap is the play.
(function () {
  var frames = document.querySelectorAll("[data-video-play]");
  if (!frames.length || !navigator.sendBeacon) return;
  var sent = {};
  window.addEventListener("blur", function () {
    setTimeout(function () {
      var el = document.activeElement;
      if (!el || el.tagName !== "IFRAME") return;
      var box = el.closest("[data-video-play]");
      if (!box || sent[box.dataset.video]) return;
      sent[box.dataset.video] = true;
      var token = document.querySelector("input[name=csrfmiddlewaretoken]");
      var body = new FormData();
      body.append("video", box.dataset.video || "");
      if (token) body.append("csrfmiddlewaretoken", token.value);
      navigator.sendBeacon(box.dataset.videoPlay, body);
    }, 0);
  });
})();
