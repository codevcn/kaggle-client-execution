/* =============================================================
   manage.js — Logic cho trang quản lý Local Server
   Cấu trúc:
     1. State (biến toàn cục)
     2. Config & Filters (fetch, render flows/notebooks/filters)
     3. Data Updaters (updateFlowData, updateNested...)
     4. Save & Run API (saveConfig, runAllFlows, stopAllFlows)
     5. Terminal Modal (appendTerminalLine, polling, copyLogs)
     6. GDrive Modal
     7. Shortcuts Modal (ShortcutManager class + register)
     8. Docs Modal (markdown-it integration)
     9. Utilities (showToast, escapeHtml, escapeJs)
   ============================================================= */

// ─────────────────────────────────────────────────────────────
// 1. STATE
// ─────────────────────────────────────────────────────────────

let configData = { flows: [] };
let availableFilters = [];
let pollInterval = null;
let logOffset = 0;

document.addEventListener("DOMContentLoaded", fetchConfig);

// ─────────────────────────────────────────────────────────────
// 2. CONFIG & FILTERS — fetch, render
// ─────────────────────────────────────────────────────────────

async function fetchConfig() {
  try {
    const [configRes, filtersRes, statusRes] = await Promise.all([
      fetch("/api/configs"),
      fetch("/api/available-filters"),
      fetch("/"),
    ]);
    if (!configRes.ok) throw new Error("Không thể tải cấu hình");
    configData = await configRes.json();
    if (filtersRes.ok) availableFilters = await filtersRes.json();

    if (statusRes.ok) {
      const statusData = await statusRes.json();
      if (statusData.cloudflare_url) {
        const urlContainer = document.getElementById("cf-url-container");
        const urlLink = document.getElementById("cf-url-link");
        if (urlContainer && urlLink) {
          urlContainer.style.display = "flex";
          urlLink.href = statusData.cloudflare_url;

          let displayUrl = statusData.cloudflare_url;
          if (displayUrl.length > 35) {
            displayUrl = displayUrl.substring(0, 32) + "...";
          }
          urlLink.textContent = displayUrl;
          urlLink.title = statusData.cloudflare_url;
        }
      }
    }

    document.getElementById("loading-indicator").style.display = "none";
    document.getElementById("config-container").style.display = "block";
    renderFlows();
  } catch (error) {
    showToast(error.message, "error");
    document.getElementById("loading-indicator").innerHTML =
      `<span style="color:var(--danger)">Lỗi: ${error.message}</span>`;
  }
}

function renderFlows() {
  const container = document.getElementById("flow-list");
  container.innerHTML = "";

  configData.flows.forEach((flow, index) => {
    const isFirst = index === 0;
    const isLast = index === configData.flows.length - 1;

    const card = document.createElement("div");
    card.className = "flow-card";
    card.id = `flow-card-${index}`;
    card.innerHTML = `
      <div class="flow-header">
        <h2>Flow #${index + 1}: <span id="title-display-${index}" style="color:var(--text-main); font-weight:500; font-size:1.1rem">${flow.flow_title || "Mới"}</span></h2>
        <div style="display: flex; gap: 0.5rem; align-items: center; margin-left: auto;">
          <button class="btn btn-outline" style="padding: 0.4rem; ${isFirst ? 'opacity: 0.5; cursor: not-allowed;' : ''}" onclick="moveFlow(${index}, -1)" title="Di chuyển lên" ${isFirst ? 'disabled' : ''}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"></polyline></svg>
          </button>
          <button class="btn btn-outline" style="padding: 0.4rem; ${isLast ? 'opacity: 0.5; cursor: not-allowed;' : ''}" onclick="moveFlow(${index}, 1)" title="Di chuyển xuống" ${isLast ? 'disabled' : ''}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </button>
          <button class="btn btn-danger" onclick="removeFlow(${index})">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            Xóa Flow
          </button>
        </div>
      </div>

      <div class="switch-wrapper" style="margin-bottom: 1rem; display: flex; align-items: center; gap: 8px;">
        <label class="switch" style="margin: 0;">
          <input type="checkbox" id="enable-${index}" ${!flow.skip ? "checked" : ""} onchange="updateFlowData(${index}, 'skip', !this.checked)">
          <span class="slider"></span>
        </label>
        <label for="enable-${index}" style="color:var(--text-muted); font-weight:500; cursor:pointer; user-select:none; margin: 0;">Bật flow này (Không skip flow này)</label>
      </div>

      <div id="flow-body-${index}" style="display: ${flow.skip ? 'none' : 'block'};">
        <div class="form-group">
          <label>Flow Title</label>
        <input type="text" class="form-control" value="${escapeHtml(flow.flow_title || "")}" oninput="updateTitleDisplay(${index}, this.value); updateFlowData(${index}, 'flow_title', this.value)">
      </div>

      <div class="form-group">
        <label>Local Data Input Path</label>
        <input type="text" class="form-control" value="${escapeHtml(flow.local_data_input || "")}" oninput="updateFlowData(${index}, 'local_data_input', this.value)">
      </div>

      <div class="grid-2">
        <div>
          <div class="section-title">Google Drive Config</div>
          <div class="form-group">
            <label>Upload Folder URL</label>
            <input type="text" class="form-control" value="${escapeHtml(flow.gdrive?.upload_gdrive_folder_url || "")}" oninput="updateNestedFlowData(${index}, 'gdrive', 'upload_gdrive_folder_url', this.value)">
          </div>
          <div class="form-group">
            <label>Rclone Config Path</label>
            <input type="text" class="form-control" value="${escapeHtml(flow.gdrive?.rclone_config_path || "")}" oninput="updateNestedFlowData(${index}, 'gdrive', 'rclone_config_path', this.value)">
          </div>
        </div>

        <div>
          <div class="section-title" style="justify-content:space-between">
            <span>Kaggle Notebooks</span>
            <button class="btn-icon" style="padding:0.2rem 0.6rem; font-size:0.85rem" onclick="addNotebook(${index})">+ Thêm notebook</button>
          </div>
          <div class="notebook-list" id="notebooks-list-${index}">
            <!-- Rendered in JS -->
          </div>
        </div>
      </div>

      <div>
        <div class="section-title">
          Entrance Filters
          <button class="btn-icon" style="margin-left:auto; padding:0.2rem 0.5rem" onclick="addEntranceFilter(${index})">+</button>
        </div>
        <div class="dynamic-list" id="filters-list-${index}">
          <!-- Rendered in JS -->
        </div>
      </div>
      </div>
    `;
    container.appendChild(card);

    renderEntranceFilters(index);
    renderNotebooks(index);
  });
  
  renderToc();
}

function renderToc() {
  const tocContainer = document.getElementById("toc-container");
  const tocList = document.getElementById("toc-list");
  
  if (!configData.flows || configData.flows.length === 0) {
    tocContainer.style.display = "none";
    return;
  }
  
  tocContainer.style.display = "flex";
  tocList.innerHTML = "";
  
  configData.flows.forEach((flow, index) => {
    const title = flow.flow_title || "Flow mới";
    const a = document.createElement("a");
    a.href = `#flow-card-${index}`;
    a.className = "toc-item";
    a.textContent = `${index + 1}. ${title}`;
    a.title = title;
    
    // Add instant scroll listener — offset by sticky header height
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const target = document.getElementById(`flow-card-${index}`);
      if (target) {
        const header = document.querySelector("header");
        const headerH = header ? header.offsetHeight : 0;
        const EXTRA_GAP = 16; // khoảng cách thêm để dễ nhìn
        const targetTop = target.getBoundingClientRect().top + window.scrollY - headerH - EXTRA_GAP;
        window.scrollTo({ top: targetTop, behavior: "instant" });

        // Highlight effect
        target.style.transition = "box-shadow 0.3s";
        target.style.boxShadow = "0 0 20px rgba(59, 130, 246, 0.5)";
        setTimeout(() => target.style.boxShadow = "", 1500);
      }
    });
    
    tocList.appendChild(a);
  });
}

function renderEntranceFilters(flowIndex) {
  const container = document.getElementById(`filters-list-${flowIndex}`);
  container.innerHTML = "";
  const filters = configData.flows[flowIndex].entrance_filters || [];

  if (filters.length === 0) {
    container.innerHTML = `<span style="color:var(--text-muted); font-size:0.9rem; font-style:italic">Chưa có filter nào</span>`;
    return;
  }

  filters.forEach((filter, filterIndex) => {
    let optionsHtml = '<option value="">-- Chọn Filter --</option>';
    availableFilters.forEach((f) => {
      const selected = f === filter.name ? "selected" : "";
      optionsHtml += `<option value="${escapeHtml(f)}" ${selected}>${escapeHtml(f)}</option>`;
    });

    if (filter.name && !availableFilters.includes(filter.name)) {
      optionsHtml += `<option value="${escapeHtml(filter.name)}" selected>${escapeHtml(filter.name)} (Lỗi: Không tồn tại)</option>`;
    }

    const isFirst = filterIndex === 0;
    const isLast = filterIndex === filters.length - 1;

    const div = document.createElement("div");
    div.className = "dynamic-item";
    div.innerHTML = `
      <select class="form-control" onchange="updateFilterName(${flowIndex}, ${filterIndex}, this.value)">
        ${optionsHtml}
      </select>
      <button class="btn-icon btn-up-down--filter" onclick="moveEntranceFilter(${flowIndex}, ${filterIndex}, -1)" title="Di chuyển lên" ${isFirst ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : ""}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"></polyline></svg>
      </button>
      <button class="btn-icon btn-up-down--filter" onclick="moveEntranceFilter(${flowIndex}, ${filterIndex}, 1)" title="Di chuyển xuống" ${isLast ? 'disabled style="opacity: 0.5; cursor: not-allowed;"' : ""}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
      </button>
      <button class="btn-icon danger btn-up-down--filter" onclick="removeEntranceFilter(${flowIndex}, ${filterIndex})" title="Xóa filter">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
      </button>
    `;
    container.appendChild(div);
  });
}

// ─────────────────────────────────────────────────────────────
// 3. DATA UPDATERS
// ─────────────────────────────────────────────────────────────

function updateTitleDisplay(index, val) {
  document.getElementById(`title-display-${index}`).textContent = val || "Mới";
  renderToc();
}

function updateFlowData(index, field, value) {
  configData.flows[index][field] = value;
  if (field === 'skip') {
    const body = document.getElementById(`flow-body-${index}`);
    if (body) {
      body.style.display = value ? 'none' : 'block';
    }
  }
}

function updateNestedFlowData(index, parentField, field, value) {
  if (!configData.flows[index][parentField])
    configData.flows[index][parentField] = {};
  configData.flows[index][parentField][field] = value;
}

// Entrance Filters
function addEntranceFilter(flowIndex) {
  if (!configData.flows[flowIndex].entrance_filters)
    configData.flows[flowIndex].entrance_filters = [];
  configData.flows[flowIndex].entrance_filters.push({ name: "" });
  renderEntranceFilters(flowIndex);
}
function updateFilterName(flowIndex, filterIndex, val) {
  configData.flows[flowIndex].entrance_filters[filterIndex].name = val;
}
function removeEntranceFilter(flowIndex, filterIndex) {
  configData.flows[flowIndex].entrance_filters.splice(filterIndex, 1);
  renderEntranceFilters(flowIndex);
}

function moveEntranceFilter(flowIndex, filterIndex, direction) {
  const filters = configData.flows[flowIndex].entrance_filters;
  const targetIndex = filterIndex + direction;
  if (targetIndex < 0 || targetIndex >= filters.length) return;
  const temp = filters[filterIndex];
  filters[filterIndex] = filters[targetIndex];
  filters[targetIndex] = temp;
  renderEntranceFilters(flowIndex);
}

// Notebooks
function getNotebooks(flowIndex) {
  const kaggle = configData.flows[flowIndex].kaggle;
  if (!kaggle) configData.flows[flowIndex].kaggle = { notbooks: [] };
  if (!configData.flows[flowIndex].kaggle.notbooks)
    configData.flows[flowIndex].kaggle.notbooks = [];
  return configData.flows[flowIndex].kaggle.notbooks;
}

function renderNotebooks(flowIndex) {
  const container = document.getElementById(`notebooks-list-${flowIndex}`);
  if (!container) return;
  container.innerHTML = "";
  const notebooks = getNotebooks(flowIndex);

  if (notebooks.length === 0) {
    container.innerHTML = `<span style="color:var(--text-muted); font-size:0.9rem; font-style:italic">Chưa có notebook nào</span>`;
    return;
  }

  notebooks.forEach((nb, nbIndex) => {
    const isActive = nb.to_execute === true;
    const card = document.createElement("div");
    card.className = `notebook-card${isActive ? " active" : ""}`;
    card.id = `nb-card-${flowIndex}-${nbIndex}`;

    const editVars = nb.edit_vars || {};
    const editVarKeys = Object.keys(editVars);
    let editVarRowsHtml = editVarKeys
      .map(
        (key) => `
        <div class="dynamic-item" style="margin-bottom:0.4rem">
          <input type="text" class="form-control" style="flex:0.8; font-size:0.82rem; padding:0.4rem 0.6rem" value="${escapeHtml(key)}" placeholder="Key"
            onchange="updateNbEditVarKey(${flowIndex}, ${nbIndex}, '${escapeJs(key)}', this.value)">
          <input type="text" class="form-control" style="flex:1.2; font-size:0.82rem; padding:0.4rem 0.6rem" value="${escapeHtml(String(editVars[key]))}" placeholder="Value"
            oninput="updateNbEditVarValue(${flowIndex}, ${nbIndex}, '${escapeJs(key)}', this.value)">
          <button class="btn-icon danger" onclick="removeNbEditVar(${flowIndex}, ${nbIndex}, '${escapeJs(key)}')" title="Xóa biến">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>
      `,
      )
      .join("");

    if (editVarKeys.length === 0) {
      editVarRowsHtml = `<span style="color:var(--text-muted); font-size:0.8rem; font-style:italic">Chưa có biến</span>`;
    }

    card.innerHTML = `
      <div class="notebook-card-header">
        <label class="notebook-radio-label">
          <input type="radio" name="nb-active-${flowIndex}" ${isActive ? "checked" : ""}
            onchange="setActiveNotebook(${flowIndex}, ${nbIndex})">
          Notebook #${nbIndex + 1}
        </label>
        ${isActive ? '<span class="active-badge">▶ SẼ CHẠY</span>' : ""}
        <button class="btn-icon danger" onclick="removeNotebook(${flowIndex}, ${nbIndex})" title="Xóa notebook" style="margin-left:auto">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
        </button>
      </div>

      <div class="form-group" style="margin-bottom:0.6rem">
        <label style="font-size:0.82rem">notebook_to_execute</label>
        <input type="text" class="form-control" style="font-size:0.88rem" value="${escapeHtml(nb.notebook_to_execute || "")}"
          oninput="updateNbField(${flowIndex}, ${nbIndex}, 'notebook_to_execute', this.value)" placeholder="username/notebook-slug">
      </div>

      <div class="form-group" style="margin-bottom:0.75rem">
        <label style="font-size:0.82rem">credentials_path (.env)</label>
        <input type="text" class="form-control" style="font-size:0.88rem" value="${escapeHtml(nb.credentials_path || "")}"
          oninput="updateNbField(${flowIndex}, ${nbIndex}, 'credentials_path', this.value)" placeholder="/path/to/.env">
      </div>

      <div class="form-group" style="margin-bottom:0.75rem; background: var(--bg-card); padding: 0.5rem; border-radius: 4px; border: 1px solid var(--border-color);">
        <label style="font-size:0.82rem; margin-bottom:0.3rem">Kaggle Edit Link</label>
        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <input type="text" class="form-control" style="font-size:0.85rem; flex: 1;" 
            id="edit-link-${flowIndex}-${nbIndex}"
            value="${escapeHtml(nb.notebook_link_to_edit || (nb.notebook_to_execute ? 'https://www.kaggle.com/code/' + nb.notebook_to_execute + '/edit' : ''))}"
            oninput="updateNbField(${flowIndex}, ${nbIndex}, 'notebook_link_to_edit', this.value)"
            placeholder="https://www.kaggle.com/code/...">
            
          <a href="${escapeHtml(nb.notebook_link_to_edit || (nb.notebook_to_execute ? 'https://www.kaggle.com/code/' + nb.notebook_to_execute + '/edit' : ''))}" 
             target="_blank" rel="noopener noreferrer" 
             class="btn-icon" title="Mở link trong tab mới" 
             style="color: #60a5fa; padding: 0.3rem; display: flex; align-items: center;">
             <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
          </a>
          <button class="btn-icon" title="Sao chép URL" onclick="copyNotebookUrl(document.getElementById('edit-link-${flowIndex}-${nbIndex}').value, this)" style="color:#94a3b8; padding: 0.3rem;">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          </button>
        </div>
      </div>

      <div class="notebook-edit-vars">
        <div class="notebook-edit-vars-title">
          <span>Edit Variables</span>
          <button class="btn-icon" style="padding:0.15rem 0.5rem; font-size:0.78rem" onclick="addNbEditVar(${flowIndex}, ${nbIndex})">+</button>
        </div>
        <div id="nb-edit-vars-${flowIndex}-${nbIndex}" class="dynamic-list">
          ${editVarRowsHtml}
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

function setActiveNotebook(flowIndex, activeNbIndex) {
  getNotebooks(flowIndex).forEach((nb, i) => {
    nb.to_execute = i === activeNbIndex;
  });
  renderNotebooks(flowIndex);
}

function addNotebook(flowIndex) {
  const notebooks = getNotebooks(flowIndex);
  notebooks.push({
    notebook_to_execute: "",
    edit_vars: {},
    credentials_path: "",
    to_execute: notebooks.length === 0,
  });
  renderNotebooks(flowIndex);
}

function removeNotebook(flowIndex, nbIndex) {
  const notebooks = getNotebooks(flowIndex);
  const wasActive = notebooks[nbIndex].to_execute === true;
  notebooks.splice(nbIndex, 1);
  if (wasActive && notebooks.length > 0) notebooks[0].to_execute = true;
  renderNotebooks(flowIndex);
}

function updateNbField(flowIndex, nbIndex, field, value) {
  getNotebooks(flowIndex)[nbIndex][field] = value;
}

function addNbEditVar(flowIndex, nbIndex) {
  const nb = getNotebooks(flowIndex)[nbIndex];
  if (!nb.edit_vars) nb.edit_vars = {};
  let newKey = "NEW_VAR";
  let counter = 1;
  while (nb.edit_vars.hasOwnProperty(newKey)) newKey = `NEW_VAR_${counter++}`;
  nb.edit_vars[newKey] = "";
  renderNotebooks(flowIndex);
}

function updateNbEditVarKey(flowIndex, nbIndex, oldKey, newKey) {
  if (oldKey === newKey) return;
  const vars = getNotebooks(flowIndex)[nbIndex].edit_vars;
  if (vars.hasOwnProperty(newKey)) {
    showToast("Key này đã tồn tại!", "error");
    renderNotebooks(flowIndex);
    return;
  }
  vars[newKey] = vars[oldKey];
  delete vars[oldKey];
  renderNotebooks(flowIndex);
}

function updateNbEditVarValue(flowIndex, nbIndex, key, val) {
  getNotebooks(flowIndex)[nbIndex].edit_vars[key] = val;
}

function removeNbEditVar(flowIndex, nbIndex, key) {
  delete getNotebooks(flowIndex)[nbIndex].edit_vars[key];
  renderNotebooks(flowIndex);
}

function copyNotebookUrl(url, btn) {
  navigator.clipboard.writeText(url).then(() => {
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
    btn.style.color = "#10b981";
    setTimeout(() => {
      btn.innerHTML = originalHTML;
      btn.style.color = "#94a3b8";
    }, 2000);
  }).catch(() => showToast("Không thể copy link!", "error"));
}

// Flows array
function addFlow() {
  configData.flows.push({
    skip: false,
    flow_title: "Flow mới",
    entrance_filters: [],
    local_data_input: "",
    gdrive: { upload_gdrive_folder_url: "", rclone_config_path: "" },
    kaggle: {
      notbooks: [
        {
          notebook_to_execute: "",
          edit_vars: {},
          credentials_path: "",
          to_execute: true,
        },
      ],
    },
  });
  renderFlows();
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

function removeFlow(index) {
  if (confirm("Bạn có chắc chắn muốn xóa Flow này?")) {
    configData.flows.splice(index, 1);
    renderFlows();
  }
}

function moveFlow(index, direction) {
  const targetIndex = index + direction;
  if (targetIndex < 0 || targetIndex >= configData.flows.length) return;
  const temp = configData.flows[index];
  configData.flows[index] = configData.flows[targetIndex];
  configData.flows[targetIndex] = temp;
  renderFlows();
}

// ─────────────────────────────────────────────────────────────
// 4. SAVE & RUN API
// ─────────────────────────────────────────────────────────────

async function saveConfigSilent() {
  try {
    const response = await fetch("/api/configs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(configData),
    });
    return response.ok;
  } catch (e) {
    return false;
  }
}

async function saveConfig() {
  try {
    const response = await fetch("/api/configs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(configData),
    });
    const result = await response.json();
    if (response.ok) showToast("Đã lưu cấu hình thành công!");
    else showToast(result.detail || "Lỗi khi lưu", "error");
  } catch (e) {
    showToast("Lỗi mạng: " + e.message, "error");
  }
}

async function runAllFlows() {
  const backdrop = document.getElementById("terminal-modal-backdrop");
  const termBody = document.getElementById("terminal-body");
  const stopBtn = document.getElementById("btn-stop-flow");
  const closeBtn = document.getElementById("btn-close-terminal");
  const statusBadge = document.getElementById("terminal-status-badge");
  const runAllBtn = document.getElementById("btn-run-all");
  const countSpan = document.getElementById("terminal-line-count");

  backdrop.style.display = "flex";
  termBody.innerHTML =
    '<div class="terminal-line info">[SYSTEM] Đang lưu cấu hình trước khi chạy...</div>';
  if (countSpan) countSpan.textContent = "1 dòng";
  statusBadge.className = "terminal-status status-running";
  statusBadge.textContent = "Lưu cấu hình...";
  stopBtn.style.display = "inline-flex";
  stopBtn.disabled = true;
  closeBtn.disabled = true;
  runAllBtn.disabled = true;
  logOffset = 0;

  const saveOk = await saveConfigSilent();
  if (!saveOk) {
    statusBadge.className = "terminal-status status-failed";
    statusBadge.textContent = "Lưu thất bại";
    appendTerminalLine(
      "[LỖI HỆ THỐNG] Không thể lưu cấu hình — hủy chạy flow.",
      "error",
    );
    stopBtn.disabled = true;
    closeBtn.disabled = false;
    runAllBtn.disabled = false;
    return;
  }

  appendTerminalLine("[✓] Đã lưu cấu hình thành công.", "success");
  statusBadge.textContent = "Đang khởi chạy...";
  stopBtn.disabled = false;

  try {
    const response = await fetch("/api/run-flows", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const result = await response.json();
    if (!response.ok)
      throw new Error(result.detail || "Không thể khởi động chạy flow");
    appendTerminalLine(
      "[SYSTEM] Khởi chạy thành công. Bắt đầu nhận logs...",
      "success",
    );
    startPolling();
  } catch (err) {
    statusBadge.className = "terminal-status status-failed";
    statusBadge.textContent = "Lỗi khởi động";
    appendTerminalLine(`[LỖI HỆ THỐNG] ${err.message}`, "error");
    stopBtn.disabled = true;
    closeBtn.disabled = false;
    runAllBtn.disabled = false;
  }
}

// ─────────────────────────────────────────────────────────────
// 5. TERMINAL MODAL — polling, append, copy
// ─────────────────────────────────────────────────────────────

function startPolling() {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(pollFlowStatus, 1000);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

function classifyLogLine(line) {
  if (
    line.includes("❌") ||
    line.includes(" LỖI ") ||
    line.includes(" ERROR ") ||
    line.includes("❌ [RCLONE] Lỗi")
  )
    return "error";
  if (
    line.includes("✅") ||
    line.includes(" thành công") ||
    line.includes(" hoàn tất")
  )
    return "success";
  if (
    line.includes("⚠️") ||
    line.includes(" CẢNH BÁO ") ||
    line.includes(" WARNING ")
  )
    return "warning";
  return "info";
}

async function pollFlowStatus() {
  const stopBtn = document.getElementById("btn-stop-flow");
  const closeBtn = document.getElementById("btn-close-terminal");
  const statusBadge = document.getElementById("terminal-status-badge");
  const runAllBtn = document.getElementById("btn-run-all");

  try {
    const response = await fetch(`/api/flow-status?offset=${logOffset}`);
    if (!response.ok) throw new Error("Mất kết nối với API");
    const status = await response.json();

    if (status.logs && status.logs.length > 0) {
      status.logs.forEach((line) =>
        appendTerminalLine(line, classifyLogLine(line)),
      );
      logOffset += status.logs.length;
    }

    if (status.is_running) {
      statusBadge.className = "terminal-status status-running";
      statusBadge.textContent = "Đang chạy";
    } else {
      stopPolling();
      stopBtn.disabled = true;
      closeBtn.disabled = false;
      runAllBtn.disabled = false;
      applyTerminalFinalStatus(statusBadge, status.returncode);
    }
  } catch (err) {
    appendTerminalLine(`[LỖI THĂM DÒ] ${err.message}`, "error");
  }
}

function applyTerminalFinalStatus(badge, returncode) {
  if (returncode === 0) {
    badge.className = "terminal-status status-success";
    badge.textContent = "Hoàn thành";
    appendTerminalLine(
      "[SYSTEM] Tiến trình đã chạy hoàn tất thành công (exit code 0).",
      "success",
    );
  } else if (
    returncode === -15 ||
    returncode === -9 ||
    returncode === 3221225786
  ) {
    badge.className = "terminal-status status-stopped";
    badge.textContent = "Đã dừng";
    appendTerminalLine(
      "[SYSTEM] Tiến trình đã bị dừng cưỡng bức bởi người dùng.",
      "warning",
    );
  } else {
    badge.className = "terminal-status status-failed";
    badge.textContent = `Lỗi (code ${returncode})`;
    appendTerminalLine(
      `[SYSTEM] Tiến trình thất bại với mã lỗi ${returncode}.`,
      "error",
    );
  }
}

async function stopAllFlows() {
  const stopBtn = document.getElementById("btn-stop-flow");
  stopBtn.disabled = true;
  appendTerminalLine("[SYSTEM] Đang gửi yêu cầu ngắt tiến trình...", "warning");
  try {
    const response = await fetch("/api/stop-flows", { method: "POST" });
    const result = await response.json();
    if (response.ok)
      appendTerminalLine("[SYSTEM] Lệnh dừng đã được gửi.", "success");
    else throw new Error(result.detail || "Không thể gửi lệnh dừng");
  } catch (err) {
    appendTerminalLine(
      `[LỖI HỆ THỐNG] Không thể dừng: ${err.message}`,
      "error",
    );
    stopBtn.disabled = false;
  }
}

function closeTerminalModal(event) {
  if (
    event &&
    event.target !== document.getElementById("terminal-modal-backdrop")
  )
    return;
  document.getElementById("terminal-modal-backdrop").style.display = "none";
  stopPolling();
}

function appendTerminalLine(text, type = "info") {
  const termBody = document.getElementById("terminal-body");
  const lineDiv = document.createElement("div");
  lineDiv.className = `terminal-line ${type}`;
  lineDiv.textContent = text;
  termBody.appendChild(lineDiv);

  const countSpan = document.getElementById("terminal-line-count");
  if (countSpan) countSpan.textContent = termBody.childElementCount + " dòng";
  termBody.scrollTop = termBody.scrollHeight;
}

function copyLogs(btn) {
  const termBody = document.getElementById("terminal-body");
  const lines = Array.from(termBody.querySelectorAll(".terminal-line"))
    .map((div) => div.textContent)
    .join("\n");
  navigator.clipboard
    .writeText(lines)
    .then(() => {
      const originalHTML = btn.innerHTML;
      btn.innerHTML =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 4px;"><polyline points="20 6 9 17 4 12"></polyline></svg>Đã copy!';
      btn.style.color = "#10b981";
      setTimeout(() => {
        btn.innerHTML = originalHTML;
        btn.style.color = "";
      }, 2000);
    })
    .catch(() => showToast("Không thể copy log!", "error"));
}

async function reopenLogModal() {
  const backdrop = document.getElementById("terminal-modal-backdrop");
  const termBody = document.getElementById("terminal-body");
  const stopBtn = document.getElementById("btn-stop-flow");
  const closeBtn = document.getElementById("btn-close-terminal");
  const statusBadge = document.getElementById("terminal-status-badge");
  const runAllBtn = document.getElementById("btn-run-all");
  const countSpan = document.getElementById("terminal-line-count");

  backdrop.style.display = "flex";
  termBody.innerHTML = "";
  logOffset = 0;
  if (countSpan) countSpan.textContent = "0 dòng";

  try {
    const response = await fetch("/api/flow-status?offset=0");
    if (!response.ok) throw new Error("Mất kết nối với API");
    const status = await response.json();

    if (status.logs && status.logs.length > 0) {
      status.logs.forEach((line) =>
        appendTerminalLine(line, classifyLogLine(line)),
      );
      logOffset = status.logs.length;
    }

    if (status.is_running) {
      statusBadge.className = "terminal-status status-running";
      statusBadge.textContent = "Đang chạy";
      stopBtn.disabled = false;
      closeBtn.disabled = true;
      runAllBtn.disabled = true;
      startPolling();
    } else {
      stopPolling();
      stopBtn.disabled = true;
      closeBtn.disabled = false;
      runAllBtn.disabled = false;
      applyTerminalFinalStatus(statusBadge, status.returncode);
    }
  } catch (err) {
    appendTerminalLine(`[LỖI API] Không thể tải log: ${err.message}`, "error");
  }
}

// ─────────────────────────────────────────────────────────────
// 6. FOLDERS MODAL
// ─────────────────────────────────────────────────────────────

async function openFoldersModal() {
  document.getElementById("folders-modal-backdrop").style.display = "flex";
  await renderFoldersModal();
}

function closeFoldersModal(event) {
  if (event && event.target !== document.getElementById("folders-modal-backdrop")) return;
  document.getElementById("folders-modal-backdrop").style.display = "none";
}

async function renderFoldersModal() {
  const container = document.getElementById("folders-list-container");
  container.innerHTML = `<p style="color:var(--text-muted); text-align:center; font-style:italic;">Đang tải...</p>`;

  try {
    const res = await fetch("/api/downloaded-folders");
    const data = await res.json();
    const folders = data.folders || [];

    if (folders.length === 0) {
      container.innerHTML = `
        <div style="text-align:center; padding: 2rem;">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="1.5" style="margin-bottom:1rem"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
          <p style="color:var(--text-muted); font-style:italic;">Chưa có folder nào được tải về trong phiên này.</p>
          <p style="color:#6a798e; font-size:0.82rem; margin-top:0.5rem;">Danh sách tự động reset khi server khởi động lại.</p>
        </div>`;
      return;
    }

    container.innerHTML = "";
    folders.forEach((folder) => {
      const card = document.createElement("div");
      card.className = "folder-card";
      card.title = "Nhấn để mở folder trong File Explorer";
      card.innerHTML = `
        <div class="folder-card-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
          </svg>
        </div>
        <div class="folder-card-info">
          <div class="folder-card-name">${escapeHtml(folder.name)}</div>
          <div class="folder-card-path">${escapeHtml(folder.path)}</div>
          <div class="folder-card-meta">Tải lúc: ${escapeHtml(folder.created_at)} &nbsp;|&nbsp; <a href="${escapeHtml(folder.source_url)}" target="_blank" rel="noopener" style="color:#60a5fa; text-decoration:none;" onclick="event.stopPropagation()">Nguồn GDrive ↗</a></div>
        </div>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#475569" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
      `;
      card.addEventListener("click", () => openFolder(folder.path));
      container.appendChild(card);
    });
  } catch (e) {
    container.innerHTML = `<p style="color:var(--danger); text-align:center;">Lỗi tải danh sách: ${e.message}</p>`;
  }
}

async function openFolder(path) {
  try {
    const res = await fetch("/api/open-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    const data = await res.json();
    if (res.ok) showToast("Đã mở folder trong File Explorer!", "success");
    else showToast(data.detail || "Không thể mở folder!", "error");
  } catch (e) {
    showToast("Lỗi: " + e.message, "error");
  }
}

// ─────────────────────────────────────────────────────────────
// 7. GDRIVE MODAL
// ─────────────────────────────────────────────────────────────

function openGdriveModal() {
  renderGdriveTable();
  document.getElementById("gdrive-modal-backdrop").style.display = "flex";
}

function closeGdriveModal(event) {
  if (
    event &&
    event.target !== document.getElementById("gdrive-modal-backdrop")
  )
    return;
  document.getElementById("gdrive-modal-backdrop").style.display = "none";
}

function renderGdriveTable() {
  const urls = configData.available_gdrive_urls || [];
  const tbody = document.getElementById("gdrive-table-body");
  const emptyMsg = document.getElementById("gdrive-empty");
  const table = document.getElementById("gdrive-table");
  tbody.innerHTML = "";

  if (urls.length === 0) {
    table.style.display = "none";
    emptyMsg.style.display = "block";
    return;
  }

  table.style.display = "table";
  emptyMsg.style.display = "none";

  urls.forEach((item) => {
    const name = item.name || "";
    const url = item.url || "";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span class="gdrive-name-badge">${escapeHtml(name)}</span></td>
      <td class="gdrive-url-cell">
        <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" title="Mở trong tab mới">${escapeHtml(url)}</a>
      </td>
      <td>
        <div class="gdrive-actions">
          <button class="btn-icon" title="Sao chép URL" onclick="copyGdriveUrl('${escapeJs(url)}', this)" style="color:#94a3b8">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          </button>
          <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="btn-icon" title="Mở GDrive" style="color:#60a5fa; display:flex; align-items:center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
          </a>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function copyGdriveUrl(url, btn) {
  navigator.clipboard
    .writeText(url)
    .then(() => {
      const original = btn.innerHTML;
      btn.innerHTML =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
      btn.style.color = "#10b981";
      setTimeout(() => {
        btn.innerHTML = original;
        btn.style.color = "#94a3b8";
      }, 1500);
    })
    .catch(() => showToast("Không thể sao chép!", "error"));
}

// ─────────────────────────────────────────────────────────────
// 7. SHORTCUTS MODAL — ShortcutManager class
// ─────────────────────────────────────────────────────────────

class ShortcutManager {
  constructor() {
    this.shortcuts = new Map();
    this._initListener();
  }

  register(combo, action, description) {
    this.shortcuts.set(this._normalize(combo), { action, description });
  }

  _normalize(combo) {
    return combo.toLowerCase().replace(/\s+/g, "");
  }

  _comboFromEvent(e) {
    const keys = [];
    if (e.ctrlKey) keys.push("ctrl");
    if (e.altKey) keys.push("alt");
    if (e.shiftKey) keys.push("shift");
    if (e.metaKey) keys.push("meta");
    let key = e.key.toLowerCase();
    if (["control", "shift", "alt", "meta"].includes(key)) return null;
    if (key === "\\") key = "\\";
    keys.push(key);
    return keys.join("+");
  }

  _initListener() {
    document.addEventListener("keydown", (e) => {
      const isInput =
        e.target.tagName === "INPUT" ||
        e.target.tagName === "TEXTAREA" ||
        e.target.isContentEditable;
      const combo = this._comboFromEvent(e);
      if (!combo) return;
      const shortcut = this.shortcuts.get(combo);
      if (shortcut) {
        e.preventDefault();
        if (isInput && combo.length === 1) return;
        shortcut.action(e);
      }
    });
  }

  getAllShortcuts() {
    return Array.from(this.shortcuts.entries()).map(([combo, data]) => ({
      combo,
      description: data.description,
    }));
  }
}

window.shortcutManager = new ShortcutManager();

window.shortcutManager.register("ctrl+s", () => saveConfig(), "Lưu cấu hình");
window.shortcutManager.register(
  "ctrl+\\",
  () => runAllFlows(),
  "Chạy tất cả Flow",
);
window.shortcutManager.register(
  "ctrl+q",
  () => {
    closeTerminalModal();
    closeGdriveModal();
    closeShortcutsModal();
    closeDocsModal();
  },
  "Đóng tất cả popup/modal",
);

function openShortcutsModal() {
  document.getElementById("shortcuts-modal-backdrop").style.display = "flex";
  renderShortcuts();
}

function closeShortcutsModal(event) {
  if (
    event &&
    event.target !== document.getElementById("shortcuts-modal-backdrop")
  )
    return;
  document.getElementById("shortcuts-modal-backdrop").style.display = "none";
}

function renderShortcuts() {
  const container = document.getElementById("shortcuts-list-container");
  const shortcuts = window.shortcutManager.getAllShortcuts();

  if (shortcuts.length === 0) {
    container.innerHTML =
      '<p style="color:var(--text-muted);text-align:center">Chưa có phím tắt nào được cấu hình.</p>';
    return;
  }

  container.innerHTML = shortcuts
    .map((s) => {
      const keys = s.combo
        .split("+")
        .map((k) => `<kbd>${k}</kbd>`)
        .join(" + ");
      return `
      <div class="shortcut-item">
        <span style="color:var(--text-main); font-weight: 500;">${escapeHtml(s.description)}</span>
        <span>${keys}</span>
      </div>
    `;
    })
    .join("");
}

// ─────────────────────────────────────────────────────────────
// 8. DOCS MODAL — markdown-it integration
// ─────────────────────────────────────────────────────────────

let mdRenderer = null;
let isCdnLoaded = false;

function initMarkdownIt() {
  if (window.markdownit && !mdRenderer) {
    isCdnLoaded = true;
    mdRenderer = window.markdownit({
      html: false,
      linkify: true,
      typographer: true,
      breaks: true,
    });
    document.getElementById("cdn-error-msg").style.display = "none";
  } else if (!window.markdownit) {
    isCdnLoaded = false;
    document.getElementById("cdn-error-msg").style.display = "block";
  }
}

async function openDocsModal() {
  document.getElementById("docs-modal-backdrop").style.display = "flex";
  initMarkdownIt();
  try {
    const res = await fetch("/api/docs");
    const docs = await res.json();
    const listEl = document.getElementById("docs-list");
    listEl.innerHTML = "";

    if (docs.length === 0) {
      listEl.innerHTML =
        '<div style="padding:1rem;color:var(--text-muted);font-size:0.9rem">Không có tài liệu nào.</div>';
    } else {
      docs.forEach((doc) => {
        const div = document.createElement("div");
        div.className = "doc-item";
        div.textContent = doc;
        div.onclick = () => loadDocContent(doc, div);
        listEl.appendChild(div);
      });
    }
  } catch (err) {
    showToast("Lỗi tải danh sách tài liệu", "error");
  }
}

function closeDocsModal(event) {
  if (event && event.target !== document.getElementById("docs-modal-backdrop"))
    return;
  document.getElementById("docs-modal-backdrop").style.display = "none";
}

async function loadDocContent(filename, el) {
  document
    .querySelectorAll(".doc-item")
    .forEach((d) => d.classList.remove("active"));
  if (el) el.classList.add("active");

  const previewEl = document.getElementById("docs-preview");
  previewEl.innerHTML =
    '<div style="text-align:center;padding:2rem;color:var(--text-muted)">Đang tải nội dung...</div>';

  try {
    const res = await fetch(`/api/docs/${encodeURIComponent(filename)}`);
    if (!res.ok) throw new Error("Lỗi tải file");
    const data = await res.json();

    initMarkdownIt();
    if (isCdnLoaded) {
      let rawHtml = mdRenderer.render(data.content);
      if (window.DOMPurify) rawHtml = DOMPurify.sanitize(rawHtml);
      previewEl.innerHTML = rawHtml;
    } else {
      previewEl.innerHTML =
        '<pre style="white-space:pre-wrap;font-family:monospace">' +
        escapeHtml(data.content) +
        "</pre>";
    }
  } catch (err) {
    previewEl.innerHTML =
      '<div style="color:var(--danger)">' + escapeHtml(err.message) + "</div>";
    showToast("Lỗi tải nội dung file", "error");
  }
}

// ─────────────────────────────────────────────────────────────
// 9. UTILITIES
// ─────────────────────────────────────────────────────────────

function showToast(msg, type = "success") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  const icon =
    type === "success"
      ? `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`
      : `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
  toast.innerHTML = `${icon} <span>${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => toast.classList.add("show"), 10);
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 400);
  }, 3000);
}

function escapeHtml(unsafe) {
  if (typeof unsafe !== "string") return unsafe;
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeJs(unsafe) {
  if (typeof unsafe !== "string") return unsafe;
  return unsafe.replace(/'/g, "\\'").replace(/"/g, '\\"');
}
