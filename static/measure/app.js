const API_BASE = "";

// 與後端 config.py CAMERA_PRESETS 對應（實際物理焦距 + 感光元件寬度）
const CAMERA_PRESETS = {
  "iPhone 13":                { focal_mm: 5.7, sensor_width: 7.5 },
  "iPhone 13 Pro":            { focal_mm: 5.8, sensor_width: 7.8 },
  "iPhone 14":                { focal_mm: 5.7, sensor_width: 7.5 },
  "iPhone 14 Pro":            { focal_mm: 6.9, sensor_width: 10.0 },
  "iPhone 15":                { focal_mm: 6.2, sensor_width: 8.2 },
  "iPhone 15 Pro":            { focal_mm: 6.9, sensor_width: 10.0 },
  "iPhone 16":                { focal_mm: 6.2, sensor_width: 8.2 },
  "iPhone 16 Pro":            { focal_mm: 6.9, sensor_width: 10.0 },
  "Samsung Galaxy S24 Ultra": { focal_mm: 6.5, sensor_width: 9.9 },
};

const imageInput = document.querySelector("#imageInput");
const dropZone = document.querySelector("#dropZone");
const previewGrid = document.querySelector("#previewGrid");
const fileCount = document.querySelector("#fileCount");
const analysisForm = document.querySelector("#analysisForm");
const speciesSelect = document.querySelector("#speciesSelect");
const treeAgeSelect = document.querySelector("#treeAgeSelect");
const phoneSelect = document.querySelector("#phoneSelect");
const distanceRange = document.querySelector("#distanceRange");
const distanceInput = document.querySelector("#distanceInput");
const customCameraFields = document.querySelector("#customCameraFields");
const focalInput = document.querySelector("#focalInput");
const sensorWidthInput = document.querySelector("#sensorWidthInput");
const formMessage = document.querySelector("#formMessage");
const analyzeButton = document.querySelector("#analyzeButton");
const progressArea = document.querySelector("#progressArea");
const progressBar = document.querySelector("#progressBar");
const progressText = document.querySelector("#progressText");
const resultsList = document.querySelector("#resultsList");
const successSummary = document.querySelector("#successSummary");
const resetButton = document.querySelector("#resetButton");

let selectedImages = [];

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function createId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  return `image-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatDistance(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(1) : "2.0";
}

function setMessage(message, isError = false) {
  formMessage.textContent = message;
  formMessage.classList.toggle("has-error", isError);
}

function updateDistance(value) {
  const clamped = Math.min(7, Math.max(1, Number(value) || 2));
  const stepped = Math.round(clamped * 2) / 2;
  distanceRange.value = stepped;
  distanceInput.value = formatDistance(stepped);
}

function updateCustomCameraFields() {
  const isOther = phoneSelect.value === "其他";
  customCameraFields.classList.toggle("is-hidden", !isOther);
  focalInput.required = isOther;
  sensorWidthInput.required = isOther;
}

function addImages(fileList) {
  const imageFiles = Array.from(fileList).filter((file) => file.type.startsWith("image/"));

  imageFiles.forEach((file) => {
    selectedImages.push({
      id: createId(),
      file,
      url: URL.createObjectURL(file),
    });
  });

  renderPreviews();
  setMessage(imageFiles.length ? "" : "請選擇圖片檔案。", !imageFiles.length);
}

function removeImage(id) {
  const target = selectedImages.find((image) => image.id === id);
  if (target) {
    URL.revokeObjectURL(target.url);
  }
  selectedImages = selectedImages.filter((image) => image.id !== id);
  renderPreviews();
}

function renderPreviews() {
  fileCount.textContent = `${selectedImages.length} 張`;

  if (!selectedImages.length) {
    previewGrid.innerHTML = '<div class="empty-state">尚未選擇圖片</div>';
    return;
  }

  previewGrid.innerHTML = selectedImages
    .map(
      (image) => `
        <div class="preview-item">
          <img src="${image.url}" alt="${escapeHtml(image.file.name)}" />
          <button class="remove-image" type="button" data-remove-id="${image.id}" aria-label="移除 ${escapeHtml(image.file.name)}">×</button>
        </div>
      `,
    )
    .join("");
}

function validateForm() {
  if (!selectedImages.length) {
    return "請先上傳至少一張照片。";
  }

  if (!speciesSelect.value) {
    return "請選擇樹種。";
  }

  if (!phoneSelect.value) {
    return "請選擇手機型號。";
  }

  if (phoneSelect.value === "其他") {
    if (!focalInput.value || Number(focalInput.value) <= 0) {
      return "選擇其他手機時，請輸入焦距。";
    }

    if (!sensorWidthInput.value || Number(sensorWidthInput.value) <= 0) {
      return "選擇其他手機時，請輸入感光元件寬度。";
    }
  }

  return "";
}

function populateTreeAgeOptions() {
  if (!treeAgeSelect) return;
  for (let i = 1; i <= 150; i++) {
    const opt = document.createElement("option");
    opt.value = i;
    opt.textContent = `${i} 年`;
    treeAgeSelect.appendChild(opt);
  }
}

// 從後端載入樹種清單，以 species.id 作為 <option> 的 value
async function loadSpecies() {
  try {
    const response = await fetch(`${API_BASE}/api/species`);
    if (!response.ok) throw new Error();
    const species = await response.json();

    speciesSelect.innerHTML = '<option value="">請選擇樹種</option>';
    species.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.name;
      speciesSelect.appendChild(opt);
    });
  } catch {
    speciesSelect.innerHTML = '<option value="">（樹種載入失敗，請確認後端已啟動）</option>';
  }
}

// 組合後端所需的參數
function buildPayload() {
  let focalMm, sensorWidth;

  if (phoneSelect.value === "其他") {
    focalMm = Number(focalInput.value);
    sensorWidth = Number(sensorWidthInput.value);
  } else {
    const preset = CAMERA_PRESETS[phoneSelect.value];
    focalMm = preset.focal_mm;
    sensorWidth = preset.sensor_width;
  }

  return {
    speciesId: speciesSelect.value,
    phoneModel: phoneSelect.value,
    distanceMeters: Number(distanceInput.value),
    focalMm,
    sensorWidth,
    treeAge: treeAgeSelect ? treeAgeSelect.value : "",
  };
}

// 逐張送出圖片至後端 POST /api/measure
async function analyzeImages(payload) {
  const results = [];
  const total = selectedImages.length;

  for (let i = 0; i < total; i++) {
    const image = selectedImages[i];
    updateProgress(i, total);

    const formData = new FormData();
    formData.append("image",        image.file);
    formData.append("focal_mm",     String(payload.focalMm));
    formData.append("sensor_width", String(payload.sensorWidth));
    formData.append("distance_m",   String(payload.distanceMeters));
    formData.append("species_id",   payload.speciesId);
    formData.append("tree_age",     String(payload.treeAge));

    try {
      const response = await fetch(`${API_BASE}/api/measure`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();

      if (!response.ok) {
        results.push({
          id: image.id,
          fileName: image.file.name,
          sourceUrl: image.url,
          success: false,
          status: "failed",
          reason: data.error || "分析失敗，請再試一次",
        });
      } else {
        results.push({
          id: image.id,
          fileName: image.file.name,
          sourceUrl: image.url,
          annotatedImage: data.annotated_image,
          success: true,
          species: data.species_name,
          distanceMeters: payload.distanceMeters,
          dbhCm: data.diameter_cm,
          carbonKgCo2: data.co2_kg,
          annualCarbonKgCo2: data.annual_co2_kg,
          treeAge: data.tree_age,
          confidence: data.confidence,
          method: data.method,
          status: data.status,
          warnings: data.warnings || [],
        });
      }
    } catch {
      results.push({
        id: image.id,
        fileName: image.file.name,
        sourceUrl: image.url,
        success: false,
        status: "failed",
        reason: "無法連接伺服器，請確認系統是否正常啟動",
      });
    }
  }

  return results;
}

function startProgress() {
  progressArea.classList.remove("is-hidden");
  progressBar.style.width = "0%";
  progressText.textContent = "分析中...";
}

function updateProgress(current, total) {
  progressBar.style.width = `${Math.round((current / total) * 90)}%`;
  if (total > 1) {
    progressText.textContent = `分析中... ${current} / ${total}`;
  }
}

function finishProgress() {
  progressBar.style.width = "100%";
  progressText.textContent = "分析完成";
}

function renderResults(results) {
  const successCount = results.filter((result) => result.success).length;
  successSummary.textContent = `成功辨識：${successCount} / ${results.length} 張`;

  if (!results.length) {
    resultsList.innerHTML = '<div class="result-empty">上方完成設定並開始分析後，結果會顯示在這裡。</div>';
    return;
  }

  resultsList.innerHTML = results
    .map((result, index) => (result.success ? renderSuccessCard(result, index) : renderFailedCard(result, index)))
    .join("");
}

function renderSuccessCard(result, index) {
  const imageSrc = result.annotatedImage || result.sourceUrl;
  const warningsHtml = result.warnings.length
    ? `<div class="detail-item"><span>警告</span><strong class="warning-text">${escapeHtml(result.warnings.join("；"))}</strong></div>`
    : "";

  return `
    <article class="result-card">
      <div class="result-image">
        <img src="${imageSrc}" alt="${escapeHtml(result.fileName)} 分析結果" />
      </div>
      <div class="result-details">
        <h3>結果 ${index + 1}</h3>
        <div class="detail-grid">
          <div class="detail-item carbon-highlight">
            <div class="carbon-copy">
              <span>總固碳量</span>
              <strong class="carbon-unit">kg CO₂</strong>
            </div>
            <strong class="carbon-value">${result.carbonKgCo2}</strong>
          </div>
          <div class="detail-item carbon-highlight">
            <div class="carbon-copy">
              <span>本年度固碳量</span>
              <strong class="carbon-unit">kg CO₂</strong>
            </div>
            <strong class="carbon-value carbon-value-annual">${result.annualCarbonKgCo2}</strong>
          </div>
          <div class="detail-item species-highlight">
            <span>樹種</span>
            <strong>${escapeHtml(result.species)}</strong>
          </div>
          <div class="detail-item">
            <span>DBH 樹徑</span>
            <strong>${result.dbhCm} cm</strong>
          </div>
          <div class="detail-item">
            <span>拍攝距離</span>
            <strong>${formatDistance(result.distanceMeters)} 公尺</strong>
          </div>
          <div class="detail-item">
            <span>信心值</span>
            <strong>${result.confidence}</strong>
          </div>
          ${warningsHtml}
        </div>
      </div>
    </article>
  `;
}

function renderFailedCard(result, index) {
  return `
    <article class="result-card failed-card">
      <div class="result-image">
        <img src="${result.sourceUrl}" alt="${escapeHtml(result.fileName)} 辨識失敗" />
      </div>
      <div class="result-details">
        <h3>結果 ${index + 1}</h3>
        <p class="failed-note">${escapeHtml(result.reason)}</p>
        <div class="detail-grid">
          <div class="detail-item">
            <span>狀態</span>
            <strong>辨識失敗</strong>
          </div>
          <div class="detail-item">
            <span>檔案</span>
            <strong>${escapeHtml(result.fileName)}</strong>
          </div>
        </div>
      </div>
    </article>
  `;
}

imageInput.addEventListener("change", (event) => {
  addImages(event.target.files);
  imageInput.value = "";
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("is-dragging");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("is-dragging");
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("is-dragging");
  addImages(event.dataTransfer.files);
});

previewGrid.addEventListener("click", (event) => {
  const removeButton = event.target.closest("[data-remove-id]");
  if (removeButton) {
    removeImage(removeButton.dataset.removeId);
  }
});

phoneSelect.addEventListener("change", updateCustomCameraFields);
distanceRange.addEventListener("input", (event) => updateDistance(event.target.value));
distanceInput.addEventListener("change", (event) => updateDistance(event.target.value));

analysisForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const error = validateForm();
  if (error) {
    setMessage(error, true);
    return;
  }

  setMessage("");
  const payload = buildPayload();
  analyzeButton.disabled = true;
  analyzeButton.textContent = "分析中...";
  startProgress();

  try {
    const results = await analyzeImages(payload);
    finishProgress();
    renderResults(results);
    resetButton.classList.remove("is-hidden");
  } catch {
    setMessage("無法連接伺服器，請確認系統是否正常啟動。", true);
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.textContent = "開始分析";
  }
});

function resetAll() {
  selectedImages.forEach((img) => URL.revokeObjectURL(img.url));
  selectedImages = [];
  renderPreviews();
  resultsList.innerHTML = '<div class="result-empty">上方完成設定並開始分析後，結果會顯示在這裡。</div>';
  successSummary.textContent = "成功辨識：0 / 0 張";
  progressArea.classList.add("is-hidden");
  progressBar.style.width = "0%";
  resetButton.classList.add("is-hidden");
  setMessage("");
}

resetButton.addEventListener("click", resetAll);

loadSpecies();
populateTreeAgeOptions();
updateDistance(2);
updateCustomCameraFields();
