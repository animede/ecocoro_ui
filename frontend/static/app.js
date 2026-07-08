// Vanilla JS SPA controller. No build step, no framework.

const API = "/api";

function $(id) { return document.getElementById(id); }

// ---- Tabs ----
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $("panel-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "gallery") loadGallery();
  });
});

function setStatus(el, message, kind) {
  el.textContent = message || "";
  el.className = "status" + (kind ? " " + kind : "");
}

async function apiJson(path, options) {
  const resp = await fetch(API + path, options);
  let body;
  try {
    body = await resp.json();
  } catch (e) {
    body = null;
  }
  if (!resp.ok) {
    const detail = body && body.detail ? body.detail : `HTTPエラー (${resp.status})`;
    throw new Error(detail);
  }
  return body;
}

function fmtDate(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("ja-JP");
  } catch (e) {
    return iso;
  }
}

function renderResultCards(container, images) {
  container.innerHTML = "";
  images.forEach((img) => {
    const card = document.createElement("div");
    card.className = "result-card";
    card.innerHTML = `
      <img src="${API}/images/${img.id}" alt="生成画像">
      <div class="card-body">
        <div class="card-meta">
          <span class="badge ${img.type}">${img.type}</span>
          <span>${fmtDate(img.created_at)}</span>
        </div>
        <div class="card-prompt">${escapeHtml(img.prompt || "")}</div>
        <div class="card-actions">
          <button class="secondary" data-download="${img.id}">ダウンロード</button>
          <button class="secondary" data-use="i2i" data-use-id="${img.id}">I2Iで使う</button>
          <button class="secondary" data-use="edit" data-use-id="${img.id}">Editで使う</button>
        </div>
      </div>`;
    container.appendChild(card);
  });
  container.querySelectorAll("[data-download]").forEach((btn) => {
    btn.addEventListener("click", () => downloadImage(btn.dataset.download));
  });
  wireUseButtons(container);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function downloadImage(id) {
  const a = document.createElement("a");
  a.href = `${API}/images/${id}/download`;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

// ---- Prompt expand / translate helper ----
async function callExpand(text, mode) {
  const body = await apiJson("/prompt/expand", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, mode }),
  });
  return body.result;
}

async function callTranslate(text, direction) {
  const body = await apiJson("/prompt/translate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, direction }),
  });
  return body.result;
}

function wirePromptTools(prefix, mode, textareaId) {
  const textarea = $(textareaId);

  $(prefix + "-expand").addEventListener("click", async () => {
    const status = $(prefix + "-status");
    if (!textarea.value.trim()) return;
    setStatus(status, "プロンプトを拡張しています...", "loading");
    try {
      const result = await callExpand(textarea.value, mode);
      textarea.value = result;
      setStatus(status, "プロンプトを拡張しました", "ok");
    } catch (e) {
      setStatus(status, e.message, "error");
    }
  });

  $(prefix + "-ja2en").addEventListener("click", async () => {
    const status = $(prefix + "-status");
    if (!textarea.value.trim()) return;
    setStatus(status, "翻訳しています (日→英)...", "loading");
    try {
      textarea.value = await callTranslate(textarea.value, "ja2en");
      setStatus(status, "翻訳しました", "ok");
    } catch (e) {
      setStatus(status, e.message, "error");
    }
  });

  $(prefix + "-en2ja").addEventListener("click", async () => {
    const status = $(prefix + "-status");
    if (!textarea.value.trim()) return;
    setStatus(status, "翻訳しています (英→日)...", "loading");
    try {
      textarea.value = await callTranslate(textarea.value, "en2ja");
      setStatus(status, "翻訳しました", "ok");
    } catch (e) {
      setStatus(status, e.message, "error");
    }
  });
}

wirePromptTools("t2i", "t2i", "t2i-prompt");
wirePromptTools("i2i", "i2i_edit", "i2i-prompt");
wirePromptTools("edit", "i2i_edit", "edit-instruction");

// ---- T2I ----
$("t2i-generate").addEventListener("click", async () => {
  const status = $("t2i-status");
  const btn = $("t2i-generate");
  const prompt = $("t2i-prompt").value.trim();
  if (!prompt) { setStatus(status, "プロンプトを入力してください", "error"); return; }

  const payload = {
    prompt,
    negative_prompt: $("t2i-negative").value.trim() || null,
    width: parseInt($("t2i-width").value, 10),
    height: parseInt($("t2i-height").value, 10),
    steps: parseInt($("t2i-steps").value, 10),
    guidance_scale: parseFloat($("t2i-guidance").value),
    seed: $("t2i-seed").value ? parseInt($("t2i-seed").value, 10) : null,
    num_images: parseInt($("t2i-num").value, 10),
  };

  btn.disabled = true;
  setStatus(status, "生成中です。しばらくお待ちください...", "loading");
  try {
    const result = await apiJson("/t2i", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderResultCards($("t2i-results"), result.images);
    setStatus(status, `${result.images.length}枚生成しました`, "ok");
  } catch (e) {
    setStatus(status, e.message, "error");
  } finally {
    btn.disabled = false;
  }
});

// ---- Shared upload/dropzone wiring for i2i and edit ----
function wireDropzone(prefix) {
  const zone = $(prefix + "-dropzone");
  const input = $(prefix + "-file");
  const preview = $(prefix + "-preview");
  let file = null;

  zone.addEventListener("click", () => input.click());
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("dragover"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      setFile(e.dataTransfer.files[0]);
    }
  });
  input.addEventListener("change", () => {
    if (input.files.length) setFile(input.files[0]);
  });

  function setFile(f) {
    file = f;
    preview.src = URL.createObjectURL(f);
    preview.hidden = false;
  }

  return {
    getFile: () => file,
    setFile,
  };
}

const i2iDropzone = wireDropzone("i2i");
const editDropzone = wireDropzone("edit");

function switchTab(tab) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
  document.querySelector(`.tab-btn[data-tab="${tab}"]`).classList.add("active");
  $("panel-" + tab).classList.add("active");
  if (tab === "gallery") loadGallery();
}

// Pull an already-generated image (from a result card or the gallery) into the
// i2i/edit upload slot instead of requiring a download + re-upload round trip.
async function useImageFor(id, target) {
  const resp = await fetch(`${API}/images/${id}`);
  if (!resp.ok) return;
  const blob = await resp.blob();
  const file = new File([blob], `${id}.png`, { type: "image/png" });
  if (target === "i2i") {
    i2iDropzone.setFile(file);
  } else {
    editDropzone.setFile(file);
  }
  switchTab(target);
}

function wireUseButtons(container) {
  container.querySelectorAll("[data-use]").forEach((btn) => {
    btn.addEventListener("click", () => useImageFor(btn.dataset.useId, btn.dataset.use));
  });
}

$("i2i-generate").addEventListener("click", async () => {
  const status = $("i2i-status");
  const btn = $("i2i-generate");
  const file = i2iDropzone.getFile();
  const prompt = $("i2i-prompt").value.trim();
  if (!file) { setStatus(status, "参照画像を選択してください", "error"); return; }
  if (!prompt) { setStatus(status, "プロンプトを入力してください", "error"); return; }

  const fd = new FormData();
  fd.append("image", file);
  fd.append("prompt", prompt);
  if ($("i2i-negative").value.trim()) fd.append("negative_prompt", $("i2i-negative").value.trim());
  if ($("i2i-width").value) fd.append("width", $("i2i-width").value);
  if ($("i2i-height").value) fd.append("height", $("i2i-height").value);
  fd.append("steps", $("i2i-steps").value);
  fd.append("guidance_scale", $("i2i-guidance").value);
  if ($("i2i-seed").value) fd.append("seed", $("i2i-seed").value);
  fd.append("num_images", $("i2i-num").value);

  btn.disabled = true;
  setStatus(status, "生成中です。しばらくお待ちください...", "loading");
  try {
    const result = await apiJson("/i2i", { method: "POST", body: fd });
    renderResultCards($("i2i-results"), result.images);
    setStatus(status, `${result.images.length}枚生成しました`, "ok");
  } catch (e) {
    setStatus(status, e.message, "error");
  } finally {
    btn.disabled = false;
  }
});

$("edit-generate").addEventListener("click", async () => {
  const status = $("edit-status");
  const btn = $("edit-generate");
  const file = editDropzone.getFile();
  const instruction = $("edit-instruction").value.trim();
  if (!file) { setStatus(status, "編集対象の画像を選択してください", "error"); return; }
  if (!instruction) { setStatus(status, "編集指示を入力してください", "error"); return; }

  const fd = new FormData();
  fd.append("image", file);
  fd.append("instruction", instruction);
  if ($("edit-negative").value.trim()) fd.append("negative_prompt", $("edit-negative").value.trim());
  if ($("edit-width").value) fd.append("width", $("edit-width").value);
  if ($("edit-height").value) fd.append("height", $("edit-height").value);
  fd.append("steps", $("edit-steps").value);
  fd.append("guidance_scale", $("edit-guidance").value);
  if ($("edit-seed").value) fd.append("seed", $("edit-seed").value);
  fd.append("num_images", $("edit-num").value);

  btn.disabled = true;
  setStatus(status, "生成中です。しばらくお待ちください...", "loading");
  try {
    const result = await apiJson("/edit", { method: "POST", body: fd });
    renderResultCards($("edit-results"), result.images);
    setStatus(status, `${result.images.length}枚生成しました`, "ok");
  } catch (e) {
    setStatus(status, e.message, "error");
  } finally {
    btn.disabled = false;
  }
});

// ---- Gallery ----
async function loadGallery() {
  const status = $("gallery-status");
  const grid = $("gallery-grid");
  setStatus(status, "読み込み中...", "loading");
  try {
    const images = await apiJson("/images");
    grid.innerHTML = "";
    if (images.length === 0) {
      setStatus(status, "生成済みの画像はまだありません", "");
      return;
    }
    images.forEach((img) => {
      const card = document.createElement("div");
      card.className = "gallery-card";
      card.innerHTML = `
        <img src="${API}/images/${img.id}" alt="生成画像">
        <div class="card-body">
          <div class="card-meta">
            <span class="badge ${img.type}">${img.type}</span>
            <span>${fmtDate(img.created_at)}</span>
          </div>
          <div class="card-prompt">${escapeHtml(img.prompt || "")}</div>
          <div class="card-actions">
            <button class="secondary" data-download="${img.id}">ダウンロード</button>
            <button class="secondary" data-use="i2i" data-use-id="${img.id}">I2Iで使う</button>
            <button class="secondary" data-use="edit" data-use-id="${img.id}">Editで使う</button>
            <button class="danger" data-delete="${img.id}">削除</button>
          </div>
        </div>`;
      grid.appendChild(card);
    });
    grid.querySelectorAll("[data-download]").forEach((btn) => {
      btn.addEventListener("click", () => downloadImage(btn.dataset.download));
    });
    grid.querySelectorAll("[data-delete]").forEach((btn) => {
      btn.addEventListener("click", () => deleteImage(btn.dataset.delete));
    });
    wireUseButtons(grid);
    setStatus(status, `${images.length}件`, "ok");
  } catch (e) {
    setStatus(status, e.message, "error");
  }
}

async function deleteImage(id) {
  if (!confirm("この画像を削除しますか？この操作は取り消せません。")) return;
  const status = $("gallery-status");
  try {
    await apiJson(`/images/${id}`, { method: "DELETE" });
    loadGallery();
  } catch (e) {
    setStatus(status, e.message, "error");
  }
}

$("gallery-refresh").addEventListener("click", loadGallery);
