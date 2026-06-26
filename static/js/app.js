/* ── Helpers ── */
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
const show = el => el && el.classList.remove("hidden");
const hide = el => el && el.classList.add("hidden");

function setStatus(el, msg, type = "info") {
  if (!el) return;
  el.textContent = msg;
  el.className = `status-msg ${type}`;
  show(el);
}

function setLoading(btn, loading) {
  const label  = $(".btn-label",  btn);
  const spinner = $(".spinner", btn);
  btn.disabled = loading;
  if (loading) { hide(label); show(spinner); }
  else         { show(label); hide(spinner); }
}

/* ── Upload queue ── */
let uploadQueue = []; // Array of File

function addToQueue(files) {
  for (const f of files) {
    if (!uploadQueue.find(q => q.name === f.name && q.size === f.size)) {
      uploadQueue.push(f);
    }
  }
  renderQueue();
}

function renderQueue() {
  const list = $("#upload-queue");
  if (!uploadQueue.length) { hide(list); return; }
  show(list);
  list.innerHTML = uploadQueue.map((f, i) => `
    <div class="file-chip">
      📷 ${escHtml(f.name)}
      <span class="chip-remove" data-i="${i}" title="Remove">✕</span>
    </div>
  `).join("");

  list.querySelectorAll(".chip-remove").forEach(btn => {
    btn.addEventListener("click", e => {
      uploadQueue.splice(Number(e.target.dataset.i), 1);
      renderQueue();
      updateUploadBtn();
    });
  });
  updateUploadBtn();
}

function updateUploadBtn() {
  const btn = $("#btn-upload");
  const label = $(".btn-label", btn);
  btn.disabled = uploadQueue.length === 0;
  label.textContent = uploadQueue.length
    ? `Upload ${uploadQueue.length} Photo${uploadQueue.length > 1 ? "s" : ""}`
    : "Upload Photos";
}

/* ── Drop zone (multi-photo) ── */
const dropZone   = $("#drop-zone");
const fileInput  = $("#file-input");

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") fileInput.click(); });
fileInput.addEventListener("change", () => { addToQueue([...fileInput.files]); fileInput.value = ""; });

["dragover", "dragenter"].forEach(ev =>
  dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.add("drag-over"); }));
["dragleave", "drop"].forEach(ev =>
  dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.remove("drag-over"); }));
dropZone.addEventListener("drop", e => { addToQueue([...e.dataTransfer.files]); });

/* ── Upload ── */
$("#btn-upload").addEventListener("click", async () => {
  if (!uploadQueue.length) return;
  const btn = $("#btn-upload");
  const status = $("#upload-status");
  setLoading(btn, true);
  setStatus(status, `Uploading ${uploadQueue.length} photos and detecting faces…`, "info");

  const fd = new FormData();
  uploadQueue.forEach(f => fd.append("photos", f));

  try {
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed");

    const n = data.saved.length;
    const errs = data.errors.length;
    let msg = `✅ ${n} photo${n !== 1 ? "s" : ""} uploaded successfully!`;
    if (errs) msg += ` (${errs} skipped)`;
    setStatus(status, msg, "success");
    uploadQueue = [];
    renderQueue();
    loadGallery();
  } catch (err) {
    setStatus(status, `❌ ${err.message}`, "error");
  } finally {
    setLoading(btn, false);
  }
});

/* ── Gallery ── */
async function loadGallery() {
  const gallery = $("#gallery");
  const hint    = $("#gallery-hint");
  gallery.innerHTML = "";
  try {
    const res   = await fetch("/api/photos");
    const photos = await res.json();
    if (!photos.length) {
      show(hint);
      return;
    }
    hide(hint);
    photos.forEach(p => gallery.appendChild(makePhotoCard(p)));
  } catch {
    show(hint);
    hint.textContent = "Could not load photos.";
  }
}

function makePhotoCard(photo, selectable = false) {
  const div = document.createElement("div");
  div.className = "photo-card";
  div.dataset.id = photo.id;
  div.innerHTML = `
    <img src="${photo.thumb_url}" alt="${escHtml(photo.original_name)}" loading="lazy" />
    <div class="photo-name">${escHtml(photo.original_name)}</div>
    <div class="check-badge">✓</div>
  `;
  div.addEventListener("click", () => {
    if (selectable) {
      div.classList.toggle("selected");
    } else {
      openLightbox(photo.url, photo.original_name);
    }
  });
  return div;
}

function openLightbox(url, caption) {
  const lb = $("#lightbox");
  $("#lb-img").src = url;
  $("#lb-caption").textContent = caption;
  show(lb);
  document.body.style.overflow = "hidden";
}

function closeLightbox() {
  hide($("#lightbox"));
  document.body.style.overflow = "";
  $("#lb-img").src = "";
}

$("#lb-close").addEventListener("click", closeLightbox);
$("#lightbox").addEventListener("click", e => { if (e.target === e.currentTarget) closeLightbox(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeLightbox(); });

$("#btn-refresh").addEventListener("click", loadGallery);

/* ── Reference photo (find person) ── */
const refDropZone = $("#ref-drop-zone");
const refInput    = $("#ref-input");
let   refFile     = null;

refDropZone.addEventListener("click", () => refInput.click());
refDropZone.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") refInput.click(); });

["dragover", "dragenter"].forEach(ev =>
  refDropZone.addEventListener(ev, e => { e.preventDefault(); refDropZone.classList.add("drag-over"); }));
["dragleave", "drop"].forEach(ev =>
  refDropZone.addEventListener(ev, e => { e.preventDefault(); refDropZone.classList.remove("drag-over"); }));
refDropZone.addEventListener("drop", e => { setRefFile(e.dataTransfer.files[0]); });

refInput.addEventListener("change", () => {
  if (refInput.files[0]) setRefFile(refInput.files[0]);
  refInput.value = "";
});

function setRefFile(file) {
  if (!file) return;
  refFile = file;
  const wrap = $("#ref-preview-wrap");
  const reader = new FileReader();
  reader.onload = e => {
    wrap.innerHTML = `
      <img src="${e.target.result}" alt="Reference photo" />
      <div style="font-size:.75rem;color:var(--text-muted);text-align:center">${escHtml(file.name)}</div>
    `;
  };
  reader.readAsDataURL(file);
  $("#btn-find").disabled = false;
}

/* ── Find person ── */
let matchIds = [];

$("#btn-find").addEventListener("click", async () => {
  if (!refFile) return;
  const btn = $("#btn-find");
  const status = $("#find-status");
  const resultsGallery = $("#results-gallery");
  const resultsHeader  = $("#results-header");
  matchIds = [];

  setLoading(btn, true);
  setStatus(status, "Scanning your photo library…", "info");
  hide(resultsHeader);
  resultsGallery.innerHTML = "";

  const fd = new FormData();
  fd.append("reference", refFile);

  try {
    const res  = await fetch("/api/find-person", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Search failed");

    const { matches, total } = data;
    matchIds = matches.map(m => m.id);

    if (total === 0) {
      setStatus(status, "No photos found with this person. Try a clearer, front-facing photo.", "info");
    } else {
      hide(status);
      show(resultsHeader);
      $("#results-count").textContent = `Found ${total} photo${total !== 1 ? "s" : ""} with this person`;
      matches.forEach(p => resultsGallery.appendChild(makePhotoCard(p, false)));
    }
  } catch (err) {
    setStatus(status, `❌ ${err.message}`, "error");
  } finally {
    setLoading(btn, false);
  }
});

/* ── Delete all matches ── */
$("#btn-delete-all").addEventListener("click", async () => {
  if (!matchIds.length) return;
  const n = matchIds.length;
  if (!confirm(`Delete all ${n} matching photo${n > 1 ? "s" : ""}? This cannot be undone.`)) return;

  const btn  = $("#btn-delete-all");
  const status = $("#find-status");
  btn.disabled = true;
  btn.textContent = "Deleting…";

  try {
    const res  = await fetch("/api/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: matchIds }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Delete failed");

    setStatus(status, `🗑️ Deleted ${data.count} photo${data.count !== 1 ? "s" : ""} successfully.`, "success");
    hide($("#results-header"));
    $("#results-gallery").innerHTML = "";
    matchIds = [];
    loadGallery();
  } catch (err) {
    setStatus(status, `❌ ${err.message}`, "error");
    btn.disabled = false;
    btn.textContent = "🗑️ Delete All Matches";
  }
});

/* ── Escape HTML ── */
function escHtml(str) {
  return (str || "").replace(/[&<>"']/g, m =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
}

/* ── Boot ── */
loadGallery();
