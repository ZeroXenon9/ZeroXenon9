/* ── Helpers ── */
const $  = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
const show = el => el && el.classList.remove("hidden");
const hide = el => el && el.classList.add("hidden");

function setStatus(el, msg, type = "info") {
  if (!el) return;
  el.textContent = msg;
  el.className = `status-msg ${type}`;
  show(el);
}

function escHtml(str) {
  return (str || "").replace(/[&<>"']/g, m =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
}

/* ── Logout ── */
$("#btn-logout").addEventListener("click", async () => {
  await fetch("/auth/logout", { method: "POST" });
  window.location.href = "/login";
});

/* ════════════════════════════════════
   ALBUMS
   ════════════════════════════════════ */
let albums = [];
let activeAlbumId = "";

async function loadAlbums() {
  const res = await fetch("/api/albums");
  albums = await res.json();
  renderAlbumPills();
  populateAlbumSelects();
}

function renderAlbumPills() {
  const bar = $("#album-bar");
  // Remove old dynamic pills (keep "All Photos" and "+ New Album")
  $$(".album-pill.dynamic", bar).forEach(el => el.remove());

  const newBtn = $("#btn-new-album");
  albums.forEach(album => {
    const pill = document.createElement("button");
    pill.className = "album-pill dynamic" + (album.id === activeAlbumId ? " active" : "");
    pill.dataset.albumId = album.id;
    pill.innerHTML = `${escHtml(album.name)} <span class="album-count">(${album.photo_count})</span>
      <span class="album-delete-btn" data-delete-album="${album.id}" title="Delete album">✕</span>`;
    pill.addEventListener("click", e => {
      if (e.target.dataset.deleteAlbum) {
        e.stopPropagation();
        deleteAlbum(album.id, pill);
        return;
      }
      setActiveAlbum(album.id);
    });
    bar.insertBefore(pill, newBtn);
  });

  // Update "All Photos" pill
  const allPill = $(".album-pill[data-album-id='']");
  if (allPill) allPill.classList.toggle("active", activeAlbumId === "");
}

function setActiveAlbum(id) {
  activeAlbumId = id;
  renderAlbumPills();
  loadGallery();
}

function populateAlbumSelects() {
  const sel = $("#upload-album-select");
  sel.innerHTML = `<option value="">— No album —</option>`;
  albums.forEach(a => {
    const opt = document.createElement("option");
    opt.value = a.id;
    opt.textContent = a.name;
    sel.appendChild(opt);
  });
}

// "All Photos" pill
$(".album-pill[data-album-id='']").addEventListener("click", () => setActiveAlbum(""));

// New album button
$("#btn-new-album").addEventListener("click", () => {
  show($("#album-dialog"));
  $("#album-name-input").value = "";
  setTimeout(() => $("#album-name-input").focus(), 50);
});
$("#album-cancel").addEventListener("click", () => hide($("#album-dialog")));
$("#album-confirm").addEventListener("click", createAlbum);
$("#album-name-input").addEventListener("keydown", e => { if (e.key === "Enter") createAlbum(); });

async function createAlbum() {
  const name = $("#album-name-input").value.trim();
  if (!name) return;
  hide($("#album-dialog"));
  const res  = await fetch("/api/albums", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (res.ok) {
    await loadAlbums();
    const created = albums.find(a => a.name === name);
    if (created) setActiveAlbum(created.id);
  }
}

async function deleteAlbum(id) {
  if (!confirm("Delete this album? Photos inside will stay in your library.")) return;
  await fetch(`/api/albums/${id}`, { method: "DELETE" });
  if (activeAlbumId === id) activeAlbumId = "";
  await loadAlbums();
  loadGallery();
}

/* ════════════════════════════════════
   UPLOAD with per-file progress
   ════════════════════════════════════ */
let uploadQueue = [];

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
  if (!uploadQueue.length) { hide(list); updateUploadBtn(); return; }
  show(list);
  list.innerHTML = uploadQueue.map((f, i) => `
    <div class="file-item" id="file-item-${i}">
      <div class="file-item-row">
        <span class="file-item-name" title="${escHtml(f.name)}">📷 ${escHtml(f.name)}</span>
        <span class="file-item-status" id="file-status-${i}"></span>
        <span class="file-item-remove" data-i="${i}" title="Remove">✕</span>
      </div>
      <div class="file-progress hidden" id="file-progress-${i}">
        <div class="file-progress-bar" id="file-bar-${i}"></div>
      </div>
    </div>
  `).join("");

  list.querySelectorAll(".file-item-remove").forEach(btn => {
    btn.addEventListener("click", e => {
      const i = Number(e.currentTarget.dataset.i);
      uploadQueue.splice(i, 1);
      renderQueue();
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

// Drop zone wiring
const dropZone  = $("#drop-zone");
const fileInput = $("#file-input");
dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") fileInput.click(); });
fileInput.addEventListener("change", () => { addToQueue([...fileInput.files]); fileInput.value = ""; });
["dragover","dragenter"].forEach(ev =>
  dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.add("drag-over"); }));
["dragleave","drop"].forEach(ev =>
  dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.remove("drag-over"); }));
dropZone.addEventListener("drop", e => addToQueue([...e.dataTransfer.files]));

// Camera button
const cameraInput = $("#camera-input");
$("#btn-camera").addEventListener("click", () => cameraInput.click());
cameraInput.addEventListener("change", () => { addToQueue([...cameraInput.files]); cameraInput.value = ""; });

// Upload button — one XHR per file for per-file progress
$("#btn-upload").addEventListener("click", async () => {
  if (!uploadQueue.length) return;
  const btn    = $("#btn-upload");
  const status = $("#upload-status");
  const albumId = $("#upload-album-select").value;

  btn.disabled = true;
  $(".btn-label", btn).textContent = "Uploading…";
  hide(status);

  let totalSaved = 0, totalErrors = 0;
  const filesToUpload = [...uploadQueue];

  for (let i = 0; i < filesToUpload.length; i++) {
    const f         = filesToUpload[i];
    const progressEl = $(`#file-progress-${i}`);
    const barEl      = $(`#file-bar-${i}`);
    const statusEl   = $(`#file-status-${i}`);
    show(progressEl);
    if (statusEl) statusEl.textContent = "Uploading…";

    const result = await uploadOneFile(f, albumId, pct => {
      if (barEl) barEl.style.width = pct + "%";
    });

    if (result.ok) {
      totalSaved++;
      if (barEl) { barEl.style.width = "100%"; barEl.classList.add("done"); }
      if (statusEl) statusEl.textContent = `✓ ${result.faces} face${result.faces !== 1 ? "s" : ""}`;
    } else {
      totalErrors++;
      if (statusEl) statusEl.textContent = "❌ Failed";
    }
  }

  const msg = `✅ ${totalSaved} photo${totalSaved !== 1 ? "s" : ""} uploaded.` +
              (totalErrors ? ` (${totalErrors} failed)` : "");
  setStatus(status, msg, totalErrors ? "error" : "success");

  uploadQueue = [];
  setTimeout(() => {
    renderQueue();
    loadGallery();
    loadAlbums();
  }, 800);

  btn.disabled = false;
  $(".btn-label", btn).textContent = "Upload Photos";
});

function uploadOneFile(file, albumId, onProgress) {
  return new Promise(resolve => {
    const fd  = new FormData();
    fd.append("photos", file);
    if (albumId) fd.append("album_id", albumId);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload");

    xhr.upload.onprogress = e => {
      if (e.lengthComputable) onProgress(Math.round(e.loaded / e.total * 80));
    };

    xhr.onload = () => {
      onProgress(100);
      try {
        const data = JSON.parse(xhr.responseText);
        const saved = data.saved?.[0];
        resolve({ ok: !!saved, faces: saved?.faces_found ?? 0 });
      } catch {
        resolve({ ok: false, faces: 0 });
      }
    };
    xhr.onerror = () => resolve({ ok: false, faces: 0 });
    xhr.send(fd);
  });
}

/* ════════════════════════════════════
   GALLERY
   ════════════════════════════════════ */
async function loadGallery() {
  const gallery = $("#gallery");
  const hint    = $("#gallery-hint");
  gallery.innerHTML = "";

  const url = activeAlbumId ? `/api/photos?album_id=${activeAlbumId}` : "/api/photos";
  try {
    const res    = await fetch(url);
    if (res.status === 401) { window.location.href = "/login"; return; }
    const photos = await res.json();
    if (!photos.length) { show(hint); return; }
    hide(hint);
    photos.forEach(p => gallery.appendChild(makePhotoCard(p)));
  } catch {
    show(hint);
    hint.textContent = "Could not load photos.";
  }
}

function makePhotoCard(photo, showConfidence = false) {
  const div = document.createElement("div");
  div.className = "photo-card";
  div.dataset.id = photo.id;
  div.innerHTML = `
    <img src="${photo.thumb_url}" alt="${escHtml(photo.original_name)}" loading="lazy" />
    <div class="photo-name">${escHtml(photo.original_name)}</div>
    ${showConfidence && photo.confidence != null
      ? `<div class="confidence-badge">${photo.confidence}%</div>` : ""}
  `;
  div.addEventListener("click", () => openLightbox(photo.url, photo.original_name));
  return div;
}

$("#btn-refresh").addEventListener("click", () => { loadGallery(); loadAlbums(); });

/* ════════════════════════════════════
   LIGHTBOX
   ════════════════════════════════════ */
function openLightbox(url, caption) {
  $("#lb-img").src  = url;
  $("#lb-caption").textContent = caption;
  show($("#lightbox"));
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

// Swipe to close lightbox on mobile
let touchStartX = 0, touchStartY = 0;
$("#lightbox").addEventListener("touchstart", e => {
  touchStartX = e.touches[0].clientX;
  touchStartY = e.touches[0].clientY;
}, { passive: true });
$("#lightbox").addEventListener("touchend", e => {
  const dx = Math.abs(e.changedTouches[0].clientX - touchStartX);
  const dy = Math.abs(e.changedTouches[0].clientY - touchStartY);
  if (dx > 60 || dy > 60) closeLightbox();
}, { passive: true });

/* ════════════════════════════════════
   REFERENCE PHOTOS (multi)
   ════════════════════════════════════ */
let refFiles = [];

const refDropZone = $("#ref-drop-zone");
const refInput    = $("#ref-input");

refDropZone.addEventListener("click", () => refInput.click());
refDropZone.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") refInput.click(); });
["dragover","dragenter"].forEach(ev =>
  refDropZone.addEventListener(ev, e => { e.preventDefault(); refDropZone.classList.add("drag-over"); }));
["dragleave","drop"].forEach(ev =>
  refDropZone.addEventListener(ev, e => { e.preventDefault(); refDropZone.classList.remove("drag-over"); }));
refDropZone.addEventListener("drop", e => addRefFiles([...e.dataTransfer.files]));
refInput.addEventListener("change", () => { addRefFiles([...refInput.files]); refInput.value = ""; });

$("#btn-add-ref").addEventListener("click", e => { e.stopPropagation(); refInput.click(); });

function addRefFiles(files) {
  for (const f of files) {
    if (!refFiles.find(r => r.name === f.name && r.size === f.size)) {
      refFiles.push(f);
    }
  }
  renderRefPreviews();
  $("#btn-find").disabled = refFiles.length === 0;
}

function removeRefFile(i) {
  refFiles.splice(i, 1);
  renderRefPreviews();
  $("#btn-find").disabled = refFiles.length === 0;
}

function renderRefPreviews() {
  const container = $("#ref-previews");
  const placeholder = $("#ref-placeholder");

  if (!refFiles.length) {
    container.innerHTML = "";
    show(placeholder);
    return;
  }
  hide(placeholder);

  // Revoke old object URLs
  container.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "ref-previews-grid";
  refFiles.forEach((f, i) => {
    const url = URL.createObjectURL(f);
    const wrap = document.createElement("div");
    wrap.className = "ref-preview-thumb";
    wrap.innerHTML = `<img src="${url}" alt="${escHtml(f.name)}" />
      <span class="ref-preview-remove" data-i="${i}" title="Remove">✕</span>`;
    wrap.querySelector(".ref-preview-remove").addEventListener("click", e => {
      e.stopPropagation();
      URL.revokeObjectURL(url);
      removeRefFile(Number(e.currentTarget.dataset.i));
    });
    grid.appendChild(wrap);
  });
  container.appendChild(grid);
}

/* ════════════════════════════════════
   SENSITIVITY SLIDER
   ════════════════════════════════════ */
const toleranceMap = { 1: 0.5, 2: 0.6, 3: 0.7 };
const toleranceLabel = { 1: "Strict", 2: "Medium", 3: "Loose" };
const slider = $("#tolerance-slider");
slider.addEventListener("input", () => {
  $("#tol-val").textContent = toleranceLabel[slider.value];
});

/* ════════════════════════════════════
   FIND PERSON
   ════════════════════════════════════ */
let matchIds = [];

$("#btn-find").addEventListener("click", async () => {
  if (!refFiles.length) return;
  const btn    = $("#btn-find");
  const status = $("#find-status");
  const rGal   = $("#results-gallery");
  const rHdr   = $("#results-header");
  matchIds = [];
  rGal.innerHTML = "";
  hide(rHdr);

  const label = $(".btn-label", btn);
  const spin  = $(".spinner",   btn);
  btn.disabled = true;
  hide(label); show(spin);
  setStatus(status, "Scanning your photo library…", "info");

  const fd = new FormData();
  refFiles.forEach(f => fd.append("reference", f));
  fd.append("tolerance", toleranceMap[slider.value] || 0.6);

  try {
    const res  = await fetch("/api/find-person", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Search failed");

    const { matches, total } = data;
    matchIds = matches.map(m => m.id);

    if (total === 0) {
      setStatus(status, "No photos found with this person. Try more reference photos or adjust sensitivity.", "info");
    } else {
      hide(status);
      show(rHdr);
      $("#results-count").textContent = `Found ${total} photo${total !== 1 ? "s" : ""} with this person`;
      matches.forEach(p => rGal.appendChild(makePhotoCard(p, true)));
    }
  } catch (err) {
    setStatus(status, `❌ ${err.message}`, "error");
  } finally {
    btn.disabled = refFiles.length === 0;
    show(label); hide(spin);
  }
});

/* ════════════════════════════════════
   DELETE ALL MATCHES
   ════════════════════════════════════ */
$("#btn-delete-all").addEventListener("click", async () => {
  if (!matchIds.length) return;
  const n = matchIds.length;
  if (!confirm(`Permanently delete ${n} photo${n > 1 ? "s" : ""}? This cannot be undone.`)) return;

  const btn    = $("#btn-delete-all");
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
    loadAlbums();
  } catch (err) {
    setStatus(status, `❌ ${err.message}`, "error");
    btn.disabled = false;
    btn.textContent = "🗑️ Delete All";
  }
});

/* ════════════════════════════════════
   BOOT
   ════════════════════════════════════ */
loadAlbums();
loadGallery();
