/* T277: the child safety card. Everything happens in this browser: the photo is read with FileReader, the card is
   drawn on a canvas, and the PDF is written byte by byte below (one JPEG image, used 8 times on one A4 page).
   No field has a name and no request carries the data, so nothing reaches the server. Nothing is saved. */
(function () {
  var root = document.querySelector('[data-safety-card]');
  if (!root) return;
  var form = root.querySelector('[data-sc-form]');
  var canvas = root.querySelector('[data-sc-preview]');
  var ctx = canvas.getContext('2d');
  var status = root.querySelector('[data-sc-status]');
  var download = root.querySelector('[data-sc-download]');
  var clear = root.querySelector('[data-sc-clear]');
  var photoInput = form.querySelector('[data-sc="photo"]');
  var photo = null;
  var lastUrl = null;

  var W = 1011, H = 638;  // 85.6 x 54 mm at 300 dpi
  var FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans JP", "Hiragino Sans", "Yu Gothic", Meiryo, sans-serif';
  var RED = '#d62828', NAVY = '#1d3557', GREY = '#5c6670';

  // T284: the words on the card, per country. Each label is English · the local language. `allergy` is the index
  // of the local word in data-sc-allergy ("English|Japanese|Uzbek"). Uzbek words: Latin script, the official one.
  var TEXT = {
    japan: {
      help: ['I am lost. Please help me.', '迷子です。助けてください。'],
      name: 'Name · 名前', call: 'Please call my family · 家族に電話してください', hotel: 'My hotel · ホテル',
      allergyLabel: 'Allergy · アレルギー', allergy: 1,
      numbers: ['Police 110 · Fire / Ambulance 119', '警察 110 ・ 消防・救急 119']
    },
    uzbekistan: {
      help: ['I am lost. Please help me.', 'Men adashib qoldim. Iltimos, yordam bering.'],
      name: 'Name · Ism', call: "Please call my family · Oilamga qo'ng'iroq qiling", hotel: 'My hotel · Mehmonxona',
      allergyLabel: 'Allergy · Allergiya', allergy: 2,
      numbers: ['Fire 101 · Police 102 · Ambulance 103 · Any emergency 112',
                "Yong'in 101 · Politsiya 102 · Tez yordam 103 · Favqulodda vaziyat 112"]
    }
  };
  var T = TEXT[root.getAttribute('data-country')] || TEXT.japan;

  function val(key) {
    var el = form.querySelector('[data-sc="' + key + '"]');
    return el ? el.value.replace(/\s+/g, ' ').trim() : '';
  }

  function allergies() {
    var out = [];
    form.querySelectorAll('[data-sc-allergy]').forEach(function (box) {
      if (!box.checked) return;
      var p = box.getAttribute('data-sc-allergy').split('|');
      out.push(p[0] + ' ' + (p[T.allergy] || ''));
    });
    if (val('allergy')) out.push(val('allergy'));
    return out.join(', ');
  }

  function font(size, bold) { return (bold ? '700 ' : '400 ') + Math.round(size) + 'px ' + FONT; }

  // One line in a band: the font shrinks until the text fits `width`.
  function fitText(text, size, x, y, width) {
    do { ctx.font = font(size, true); size -= 1; } while (size > 12 && ctx.measureText(text).width > width);
    ctx.fillText(text, x, y);
  }

  // Lines of text that fit `width`, at most `max` lines; the last line ends with … when text is left over.
  function wrap(text, width, max) {
    var words = text.split(' '), lines = [], line = '';
    for (var i = 0; i < words.length; i++) {
      var next = line ? line + ' ' + words[i] : words[i];
      if (ctx.measureText(next).width <= width || !line) { line = next; continue; }
      lines.push(line); line = words[i];
      if (lines.length === max) { line = ''; break; }
    }
    if (line) lines.push(line);
    if (lines.length > max) lines.length = max;
    var used = lines.join(' ').length;
    if (used < text.length && lines.length) {
      var last = lines[lines.length - 1];
      while (last && ctx.measureText(last + '…').width > width) last = last.slice(0, -1);
      lines[lines.length - 1] = last + '…';
    }
    // One very long word: cut it to the width.
    return lines.map(function (l) {
      while (l.length > 1 && ctx.measureText(l).width > width) l = l.slice(0, -2) + '…';
      return l;
    });
  }

  // The text blocks of the right column, top to bottom. Each block: a small label and its value.
  function blocks() {
    var out = [];
    if (val('name')) out.push({label: T.name, value: val('name'), size: 60, lines: 1});
    var phones = [val('phone'), val('phone2')].filter(Boolean);
    // One phone number per line: a number never breaks in the middle.
    if (phones.length) out.push({label: T.call, value: phones, size: phones.length > 1 ? 46 : 54, lines: 1});
    if (val('hotel') || val('address')) {
      out.push({label: T.hotel, value: val('hotel'), size: 38, lines: 1, sub: val('address'), subSize: 28, subLines: 2});
    }
    return out;
  }

  // Draws the right column at `scale`; returns the bottom y. With dry = true it only measures.
  function column(x, y, width, scale, dry) {
    blocks().forEach(function (b) {
      ctx.font = font(24 * scale, true);
      if (!dry) { ctx.fillStyle = GREY; ctx.fillText(b.label, x, y + 24 * scale); }
      y += 32 * scale;
      if (b.value) {
        ctx.font = font(b.size * scale, true);
        [].concat(b.value).forEach(function (v) {
          wrap(v, width, b.lines).forEach(function (l) {
            if (!dry) { ctx.fillStyle = '#111'; ctx.fillText(l, x, y + b.size * scale * .9); }
            y += b.size * scale * 1.15;
          });
        });
      }
      if (b.sub) {
        ctx.font = font(b.subSize * scale, false);
        wrap(b.sub, width, b.subLines).forEach(function (l) {
          if (!dry) { ctx.fillStyle = '#111'; ctx.fillText(l, x, y + b.subSize * scale * .9); }
          y += b.subSize * scale * 1.2;
        });
      }
      y += 14 * scale;
    });
    return y;
  }

  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }

  function draw() {
    ctx.direction = 'ltr';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, W, H);

    // The top band: the words a helper reads first.
    var band = 132;
    ctx.fillStyle = RED;
    ctx.fillRect(0, 0, W, band);
    ctx.fillStyle = '#fff';
    fitText(T.help[0], 50, 36, 58, W - 72);
    fitText(T.help[1], 44, 36, 112, W - 72);

    // The bottom band: the emergency numbers of the country.
    var foot = 76;
    ctx.fillStyle = NAVY;
    ctx.fillRect(0, H - foot, W, foot);
    ctx.fillStyle = '#fff';
    fitText(T.numbers[0], 27, 36, H - foot + 32, W - 72);
    fitText(T.numbers[1], 25, 36, H - foot + 64, W - 72);

    var allergy = allergies();
    var top = band + 24, bottom = H - foot - 16;
    var allergyLines = [];
    if (allergy) {
      ctx.font = font(30, true);
      allergyLines = wrap(T.allergyLabel + ': ' + allergy, W - 72, 2);
      bottom -= allergyLines.length * 36 + 6;
    }

    var x = 36;
    if (photo) {
      var ph = bottom - top, pw = Math.round(ph * .8);
      var r = Math.max(pw / photo.width, ph / photo.height);
      var sw = pw / r, sh = ph / r;
      ctx.save();
      roundRect(36, top, pw, ph, 18);
      ctx.clip();
      ctx.drawImage(photo, (photo.width - sw) / 2, (photo.height - sh) / 2, sw, sh, 36, top, pw, ph);
      ctx.restore();
      x = 36 + pw + 30;
    }
    var width = W - 36 - x;
    var scale = 1;
    while (scale > .5 && column(x, top, width, scale, true) > bottom + 14 * scale) scale -= .05;
    column(x, top, width, scale, false);
    if (!blocks().length && !photo) {
      ctx.fillStyle = GREY;
      ctx.font = font(32, false);
      ctx.fillText('Name · Phone · Hotel', x, top + 60);
    }

    if (allergyLines.length) {
      ctx.fillStyle = RED;
      ctx.font = font(30, true);
      allergyLines.forEach(function (l, i) { ctx.fillText(l, 36, bottom + 30 + i * 36); });
    }

    // A thin edge to cut along.
    ctx.strokeStyle = '#9aa3ab';
    ctx.lineWidth = 3;
    ctx.strokeRect(1.5, 1.5, W - 3, H - 3);
  }

  // ---- The PDF: A4, 8 cards of 85.6 x 54 mm, the same JPEG drawn 8 times. ----
  function bytes(str) {
    var out = new Uint8Array(str.length);
    for (var i = 0; i < str.length; i++) out[i] = str.charCodeAt(i) & 255;
    return out;
  }

  function makePdf(jpeg, w, h) {
    var mm = 72 / 25.4, PW = 595.28, PH = 841.89;
    var cw = 85.6 * mm, ch = 54 * mm, gap = 4 * mm;
    var x0 = (PW - 2 * cw - gap) / 2, y0 = (PH - 4 * ch - 3 * gap) / 2;
    var content = '';
    for (var row = 0; row < 4; row++) {
      for (var col = 0; col < 2; col++) {
        var x = x0 + col * (cw + gap), y = PH - y0 - (row + 1) * ch - row * gap;
        content += 'q ' + cw.toFixed(2) + ' 0 0 ' + ch.toFixed(2) + ' ' + x.toFixed(2) + ' ' + y.toFixed(2) + ' cm /Im0 Do Q\n';
      }
    }
    var parts = [], offsets = [], length = 0;
    function add(part) { if (typeof part === 'string') part = bytes(part); parts.push(part); length += part.length; }
    add('%PDF-1.4\n%\xe2\xe3\xcf\xd3\n');
    var objects = [
      '<< /Type /Catalog /Pages 2 0 R >>',
      '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
      '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ' + PW + ' ' + PH + '] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>',
      null,
      '<< /Length ' + content.length + ' >>\nstream\n' + content + 'endstream'
    ];
    objects.forEach(function (obj, i) {
      offsets.push(length);
      add((i + 1) + ' 0 obj\n');
      if (obj === null) {
        add('<< /Type /XObject /Subtype /Image /Width ' + w + ' /Height ' + h + ' /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ' + jpeg.length + ' >>\nstream\n');
        add(jpeg);
        add('\nendstream');
      } else {
        add(obj);
      }
      add('\nendobj\n');
    });
    var xref = length;
    var table = 'xref\n0 ' + (objects.length + 1) + '\n0000000000 65535 f \n';
    offsets.forEach(function (o) { table += ('0000000000' + o).slice(-10) + ' 00000 n \n'; });
    add(table + 'trailer\n<< /Size ' + (objects.length + 1) + ' /Root 1 0 R >>\nstartxref\n' + xref + '\n%%EOF\n');
    return new Blob(parts, {type: 'application/pdf'});
  }

  function make() {
    status.textContent = root.getAttribute('data-busy');
    download.hidden = true;
    try {
      draw();
      var data = canvas.toDataURL('image/jpeg', .92);
      var jpeg = bytes(atob(data.split(',')[1]));
      if (lastUrl) URL.revokeObjectURL(lastUrl);
      lastUrl = URL.createObjectURL(makePdf(jpeg, W, H));
      download.href = lastUrl;
      download.hidden = false;
      status.textContent = root.getAttribute('data-ready');
      download.focus();
    } catch (e) {
      status.textContent = root.getAttribute('data-failed');
      if (window.Sentry && window.Sentry.captureException) window.Sentry.captureException(e);
    }
  }

  photoInput.addEventListener('change', function () {
    var file = photoInput.files && photoInput.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () {
      var img = new Image();
      img.onload = function () { photo = img; clear.hidden = false; draw(); };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
  clear.addEventListener('click', function () { photo = null; photoInput.value = ''; clear.hidden = true; draw(); });
  form.addEventListener('input', function () { download.hidden = true; status.textContent = ''; draw(); });
  form.addEventListener('change', function () { draw(); });
  form.addEventListener('submit', function (e) { e.preventDefault(); });
  root.querySelector('[data-sc-make]').addEventListener('click', make);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(draw);
  draw();
  window.tcSafetyCard = {draw: draw, makePdf: makePdf, text: T};
})();
