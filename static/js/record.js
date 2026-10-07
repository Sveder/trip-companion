// The 'record' step: film a short clip with the phone camera, then share it or keep it.
// No camera (the TV, a desktop without one, an old browser) -> the "do this on your phone" box.
(function () {
  var box = document.querySelector('[data-recorder]');
  if (!box) return;
  var noCam = document.querySelector('[data-no-camera]');
  var view = box.querySelector('[data-view]');
  var status = box.querySelector('[data-status]');
  var btn = {};
  box.querySelectorAll('[data-act]').forEach(function (b) { btn[b.dataset.act] = b; });
  var MAX_MS = 30000;
  var stream = null, recorder = null, chunks = [], blob = null, timer = null, savedId = null;

  function show(names) {
    Object.keys(btn).forEach(function (k) { btn[k].hidden = names.indexOf(k) < 0; });
  }
  function say(text) { status.textContent = text; }
  function noCamera() { box.hidden = true; noCam.hidden = false; }

  var md = navigator.mediaDevices;
  if (!md || !md.getUserMedia || !window.MediaRecorder) return noCamera();
  var probe = md.enumerateDevices ? md.enumerateDevices() : Promise.resolve([{ kind: 'videoinput' }]);
  probe.then(function (list) {
    if (!list.some(function (d) { return d.kind === 'videoinput'; })) return noCamera();
    box.hidden = false;
    show(['camera']);
  }).catch(noCamera);

  function pickType() {
    var types = ['video/mp4', 'video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'];
    for (var i = 0; i < types.length; i++) if (MediaRecorder.isTypeSupported(types[i])) return types[i];
    return '';
  }

  function live() {
    view.srcObject = stream; view.src = ''; view.muted = true; view.controls = false; view.play();
  }

  btn.camera.addEventListener('click', function () {
    say('Starting the camera…');
    md.getUserMedia({ video: { facingMode: 'user' }, audio: true }).then(function (s) {
      stream = s; live(); say('Ready? Press Start.'); show(['start']);
    }).catch(function () {
      say('The camera did not turn on. Allow the camera, or do this part on a phone.');
      noCam.hidden = false;
    });
  });

  btn.start.addEventListener('click', function () {
    chunks = []; blob = null; savedId = null;
    var type = pickType();
    recorder = type ? new MediaRecorder(stream, { mimeType: type }) : new MediaRecorder(stream);
    recorder.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
    recorder.onstop = done;
    recorder.start();
    say('Recording! Show your chopsticks.');
    show(['stop']);
    timer = setTimeout(function () { if (recorder.state === 'recording') recorder.stop(); }, MAX_MS);
  });

  btn.stop.addEventListener('click', function () { if (recorder && recorder.state === 'recording') recorder.stop(); });

  function done() {
    clearTimeout(timer);
    blob = new Blob(chunks, { type: (recorder.mimeType || 'video/webm').split(';')[0] });
    var url = URL.createObjectURL(blob);
    view.srcObject = null; view.src = url; view.muted = false; view.controls = true;
    btn.download.href = url;
    btn.download.download = 'chopsticks.' + (blob.type === 'video/mp4' ? 'mp4' : 'webm');
    say('Great job! Watch it, then share it.');
    var file = asFile();
    var canShare = navigator.canShare && navigator.canShare({ files: [file] });
    show([canShare ? 'share' : 'download', 'save', 'again']);
  }

  function asFile() {
    return new File([blob], btn.download.download || 'chopsticks.webm', { type: blob.type });
  }

  btn.share.addEventListener('click', function () {
    navigator.share({ files: [asFile()], title: 'Chopsticks!', text: 'Look, I can eat with chopsticks! 🥢' })
      .catch(function () { /* the family closed the share sheet */ });
  });

  btn.again.addEventListener('click', function () { live(); say('Ready? Press Start.'); show(['start']); });

  btn.save.addEventListener('click', function () {
    if (savedId) return;
    var form = new FormData();
    form.append('clip', asFile());
    var token = document.querySelector('input[name=csrfmiddlewaretoken]');
    btn.save.disabled = true;
    say('Saving…');
    fetch(box.dataset.saveUrl, { method: 'POST', body: form, headers: { 'X-CSRFToken': token ? token.value : '' }, credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) { savedId = j.id; say('Saved! You will see it again after the trip.'); btn.save.hidden = true; })
      .catch(function () { say('Saving did not work. Try again, or download it.'); btn.download.hidden = false; })
      .then(function () { btn.save.disabled = false; });
  });
})();
