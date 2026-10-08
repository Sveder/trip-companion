// 'While we are there': picking a photo sends it at once. A big phone photo is made smaller
// (1600 px, JPEG) in the browser first, so it uploads fast on mobile data. A browser that cannot
// read the photo (for example HEIC on Chrome) sends the original file instead.
(function () {
  const MAX = 1600;

  async function shrink(file) {
    if (!window.createImageBitmap || file.type === "image/gif") return file;
    try {
      const img = await createImageBitmap(file, { imageOrientation: "from-image" });
      const scale = Math.min(1, MAX / Math.max(img.width, img.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((ok) => canvas.toBlob(ok, "image/jpeg", 0.85));
      return blob && blob.size < file.size ? blob : file;
    } catch (e) {
      return file;
    }
  }

  document.querySelectorAll(".there-add input[type=file]").forEach((input) => {
    input.addEventListener("change", async () => {
      const file = input.files && input.files[0];
      if (!file) return;
      const form = input.closest("form");
      form.querySelector(".there-busy").hidden = false;
      form.querySelector("label").style.display = "none";
      const data = new FormData(form);
      const small = await shrink(file);
      data.set("photo", small, small === file ? file.name : "photo.jpg");
      try {
        // A good save answers with a redirect. "manual" keeps it unread, so the "Great find!"
        // note is still there for the reload.
        const r = await fetch(form.action, { method: "POST", body: data, credentials: "same-origin", redirect: "manual" });
        if (r.type !== "opaqueredirect" && !r.ok) throw new Error(r.status);
        window.location.hash = form.closest(".there-thing").id;
        window.location.reload();
      } catch (e) {
        form.submit();
      }
    });
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });
})();
