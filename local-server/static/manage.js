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
let availableFlowModules = [];
let pollInterval = null;
let logOffset = 0;
let copiedEditVars = null;

document.addEventListener("DOMContentLoaded", fetchConfig);

// ─────────────────────────────────────────────────────────────
// 2. CONFIG & FILTERS — fetch, render
// ─────────────────────────────────────────────────────────────

async function fetchConfig() {
  try {
    const [configRes, filtersRes, modulesRes, statusRes] = await Promise.all([
      fetch("/api/configs"),
      fetch("/api/available-filters"),
      fetch("/api/available-flow-modules"),
      fetch("/"),
    ]);
    if (!configRes.ok) throw new Error("Không thể tải cấu hình");
    configData = await configRes.json();
    if (filtersRes.ok) availableFilters = await filtersRes.json();
    if (modulesRes.ok) availableFlowModules = await modulesRes.json();

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
    setTimeout(updateActiveFlowIndicator, 100);
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
          <button class="btn btn-outline" style="padding: 0.4rem;" onclick="duplicateFlow(${index})" title="Nhân bản Flow">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
          </button>
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
        <label>Flow Module</label>
        <select class="form-control" onchange="updateFlowData(${index}, 'module', this.value)">
          <option value="">-- Chọn Flow Module --</option>
          ${availableFlowModules.map(m => `<option value="${escapeHtml(m)}" ${flow.module === m ? 'selected' : ''}>${escapeHtml(m)}</option>`).join('')}
        </select>
      </div>

      <div class="form-group">
        <label>Local Data Input Path</label>
        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <input type="text" class="form-control" id="local-data-input-${index}" value="${escapeHtml(flow.local_data_input || "")}" oninput="updateFlowData(${index}, 'local_data_input', this.value)" style="flex: 1;">
          <button class="btn-icon" title="Mở folder trong File Explorer" onclick="openLocalDataFolder(${index})" style="color: #a78bfa; padding: 0.4rem; flex-shrink: 0; border: 1px solid var(--card-border); border-radius: 6px; background: var(--card-bg); cursor: pointer; display: flex; align-items: center; transition: background 0.2s, color 0.2s;" onmouseover="this.style.background='#3b1fa3'; this.style.color='#fff';" onmouseout="this.style.background='var(--card-bg)'; this.style.color='#a78bfa';">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
          </button>
        </div>
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
  updateActiveFlowIndicator();
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
        target.classList.remove("flow-focused");
        void target.offsetWidth;
        target.classList.add("flow-focused");
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

    const isExtractAudio = filter.name === "extract_audio_from_video" || filter.name === "extract_audio_from_video.py";
    const configBtnHtml = isExtractAudio ? `
      <button class="btn-icon" style="color: #60a5fa" onclick="openFilterConfigModal(${flowIndex}, ${filterIndex})" title="Cấu hình Audio Filter">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
      </button>
    ` : "";

    const div = document.createElement("div");
    div.className = "dynamic-item";
    div.innerHTML = `
      <select class="form-control" onchange="updateFilterName(${flowIndex}, ${filterIndex}, this.value)">
        ${optionsHtml}
      </select>
      ${configBtnHtml}
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
  renderEntranceFilters(flowIndex);
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
          <div style="display: flex; gap: 0.3rem;">
            <button class="btn-icon" style="padding:0.15rem 0.5rem; font-size:0.78rem; border: 1px solid var(--border-color); border-radius: 4px;" onclick="copyNbEditVars(${flowIndex}, ${nbIndex})" title="Sao chép toàn bộ biến">Copy</button>
            <button class="btn-icon" style="padding:0.15rem 0.5rem; font-size:0.78rem; border: 1px solid var(--border-color); border-radius: 4px;" onclick="pasteNbEditVars(${flowIndex}, ${nbIndex})" title="Dán các biến đã sao chép">Paste</button>
            <button class="btn-icon" style="padding:0.15rem 0.5rem; font-size:0.78rem" onclick="addNbEditVar(${flowIndex}, ${nbIndex})">+</button>
          </div>
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

function parseEditVarValue(val) {
  // Tự động detect và convert sang đúng kiểu JS:
  // "true"/"false" (case-insensitive) → boolean
  // số nguyên/số thực → number
  // còn lại → giữ nguyên string
  const trimmed = typeof val === "string" ? val.trim() : val;
  if (trimmed.toLowerCase() === "true") return true;
  if (trimmed.toLowerCase() === "false") return false;
  // Thử parse số: chỉ khi string không rỗng và là số thuần túy
  if (trimmed !== "" && !isNaN(trimmed) && trimmed !== " ") {
    const num = Number(trimmed);
    if (!isNaN(num)) return num;
  }
  return val; // giữ nguyên string
}

function updateNbEditVarValue(flowIndex, nbIndex, key, val) {
  getNotebooks(flowIndex)[nbIndex].edit_vars[key] = parseEditVarValue(val);
}

function removeNbEditVar(flowIndex, nbIndex, key) {
  delete getNotebooks(flowIndex)[nbIndex].edit_vars[key];
  renderNotebooks(flowIndex);
}

function copyNbEditVars(flowIndex, nbIndex) {
  const vars = getNotebooks(flowIndex)[nbIndex].edit_vars || {};
  copiedEditVars = JSON.parse(JSON.stringify(vars));
  showToast("Đã sao chép các Edit Variables!", "success");
}

function pasteNbEditVars(flowIndex, nbIndex) {
  if (!copiedEditVars) {
    showToast("Bạn chưa sao chép biến nào!", "warning");
    return;
  }
  if (confirm("Bạn có muốn THAY THẾ TOÀN BỘ các biến hiện tại bằng các biến đã copy không?\\n- OK: Xóa hết cũ, dán đè biến mới\\n- Cancel: Giữ biến cũ, thêm/đè biến mới trùng tên")) {
    getNotebooks(flowIndex)[nbIndex].edit_vars = JSON.parse(JSON.stringify(copiedEditVars));
  } else {
    const currentVars = getNotebooks(flowIndex)[nbIndex].edit_vars || {};
    getNotebooks(flowIndex)[nbIndex].edit_vars = Object.assign(currentVars, JSON.parse(JSON.stringify(copiedEditVars)));
  }
  renderNotebooks(flowIndex);
  showToast("Đã dán các Edit Variables!", "success");
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

function duplicateFlow(index) {
  const clonedFlow = JSON.parse(JSON.stringify(configData.flows[index]));
  clonedFlow.flow_title = clonedFlow.flow_title ? clonedFlow.flow_title + " (Copy)" : "Flow mới (Copy)";
  configData.flows.splice(index + 1, 0, clonedFlow);
  renderFlows();
  showToast("Đã nhân bản Flow thành công!", "success");
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

function updateAllCurrentJobIds() {
  let modifiedCount = 0;
  if (!configData || !configData.flows) return 0;
  
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  
  configData.flows.forEach((flow, fIndex) => {
    // Generate a unique token for this specific flow
    const flowToken = Array.from({length: 8}, () => chars[Math.floor(Math.random() * chars.length)]).join('');
    
    if (flow.kaggle && flow.kaggle.notbooks) {
      flow.kaggle.notbooks.forEach((nb, nIndex) => {
        if (nb.edit_vars && nb.edit_vars.CURRENT_JOB_ID !== undefined) {
          let val = String(nb.edit_vars.CURRENT_JOB_ID);
          if (val.includes("---")) {
            val = val.substring(0, val.lastIndexOf("---"));
          }
          const newVal = val + "---" + flowToken;
          nb.edit_vars.CURRENT_JOB_ID = newVal;
          modifiedCount++;
          
          const nbName = nb.notebook_to_execute || `Notebook ${nIndex + 1} (Flow ${fIndex + 1})`;
          appendTerminalLine(`[SYSTEM] Đã cấp mới token cho CURRENT_JOB_ID [${nbName}]: ${newVal}`, "info");
        }
      });
    }
  });
  
  return modifiedCount;
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
    '<div class="terminal-line info">[SYSTEM] Đang chuẩn bị cấu hình trước khi chạy...</div>';
  if (countSpan) countSpan.textContent = "1 dòng";
  statusBadge.className = "terminal-status status-running";
  statusBadge.textContent = "Lưu cấu hình...";
  stopBtn.style.display = "inline-flex";
  stopBtn.disabled = true;
  closeBtn.disabled = true;
  setRunButtonState(true);
  logOffset = 0;

  const updatedCount = updateAllCurrentJobIds();
  if (updatedCount > 0) {
    // Re-render UI inputs behind the modal to reflect the new JOB IDs
    renderFlows();
  }

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
    setRunButtonState(false);
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
    setRunButtonState(false);
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
      setRunButtonState(false);
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
      setRunButtonState(true);
      startPolling();
    } else {
      stopPolling();
      stopBtn.disabled = true;
      closeBtn.disabled = false;
      setRunButtonState(false);
      applyTerminalFinalStatus(statusBadge, status.returncode);
    }
  } catch (err) {
    appendTerminalLine(`[LỖI API] Không thể tải log: ${err.message}`, "error");
  }
}

function setRunButtonState(isRunning) {
  const runAllBtn = document.getElementById("btn-run-all");
  if (!runAllBtn) return;
  if (isRunning) {
    runAllBtn.innerHTML = `
      <span class="fab-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline>
        </svg>
      </span>
      Đang chạy các Flow...
    `;
    runAllBtn.onclick = reopenLogModal;
    runAllBtn.style.background = "var(--card-bg)";
    runAllBtn.style.color = "var(--warning)";
    runAllBtn.style.border = "1px solid var(--warning)";
    runAllBtn.style.cursor = "pointer";
  } else {
    runAllBtn.innerHTML = `
      <span class="fab-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
      </span>
      Chạy Tất Cả Flow
    `;
    runAllBtn.onclick = runAllFlows;
    runAllBtn.style.background = "";
    runAllBtn.style.color = "";
    runAllBtn.style.border = "";
    runAllBtn.style.cursor = "pointer";
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

async function openLocalDataFolder(flowIndex) {
  const input = document.getElementById(`local-data-input-${flowIndex}`);
  const path = input ? input.value.trim() : "";
  if (!path) {
    showToast("Chưa có đường dẫn trong Local Data Input Path!", "error");
    return;
  }
  await openFolder(path);
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
  if (!configData.available_gdrive_urls) configData.available_gdrive_urls = [];
  const urls = configData.available_gdrive_urls;
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

  urls.forEach((item, index) => {
    const name = item.name || "";
    const url = item.url || "";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>
        <input type="text" class="form-control" style="font-size:0.85rem; padding:0.4rem 0.5rem;" value="${escapeHtml(name)}" onchange="updateGdriveUrl(${index}, 'name', this.value)">
      </td>
      <td>
        <input type="text" class="form-control" style="font-size:0.85rem; padding:0.4rem 0.5rem;" value="${escapeHtml(url)}" onchange="updateGdriveUrl(${index}, 'url', this.value)">
      </td>
      <td>
        <div class="gdrive-actions">
          <button class="btn-icon danger" title="Xóa" onclick="removeGdriveUrl(${index})">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
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

function updateGdriveUrl(index, field, value) {
  configData.available_gdrive_urls[index][field] = value;
  saveConfigSilent().then(ok => {
    if(ok) showToast("Đã lưu GDrive URL thành công", "success");
    else showToast("Lỗi lưu cấu hình", "error");
  });
  renderGdriveTable();
}

function addGdriveUrl() {
  if (!configData.available_gdrive_urls) configData.available_gdrive_urls = [];
  configData.available_gdrive_urls.push({ name: "Tên mới", url: "" });
  saveConfigSilent();
  renderGdriveTable();
}

function removeGdriveUrl(index) {
  if (confirm("Bạn có chắc chắn muốn xóa URL này?")) {
    configData.available_gdrive_urls.splice(index, 1);
    saveConfigSilent().then(ok => {
      if(ok) showToast("Đã xóa GDrive URL", "success");
    });
    renderGdriveTable();
  }
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

  register(combo, action, description, hide = false) {
    this.shortcuts.set(this._normalize(combo), { action, description, hide });
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
    return Array.from(this.shortcuts.entries())
      .filter(([combo, data]) => !data.hide)
      .map(([combo, data]) => ({
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
    closeSettingsModal();
  },
  "Đóng tất cả popup/modal",
);

function toggleSettingsModal() {
  const modal = document.getElementById("settings-modal-backdrop");
  if (modal.style.display === "flex") {
    closeSettingsModal();
  } else {
    openSettingsModal();
  }
}

window.shortcutManager.register("alt+i", () => toggleSettingsModal(), "Mở/Đóng Cài Đặt (Settings)");

function jumpToFlow(direction) {
  const header = document.querySelector("header");
  const headerH = header ? header.offsetHeight : 0;
  const EXTRA_GAP = 16;
  
  const flowCards = document.querySelectorAll('.flow-card');
  if (flowCards.length === 0) return;
  
  let currentFlowIndex = -1;
  for (let i = 0; i < flowCards.length; i++) {
    const rect = flowCards[i].getBoundingClientRect();
    if (rect.top - headerH - EXTRA_GAP - 10 <= 0) {
      currentFlowIndex = i;
    } else {
      break;
    }
  }
  
  if (currentFlowIndex === -1) currentFlowIndex = 0;
  
  let targetIndex = currentFlowIndex + direction;
  
  if (direction === -1) {
    const currentRect = flowCards[currentFlowIndex].getBoundingClientRect();
    if (currentRect.top < headerH + EXTRA_GAP - 100 && currentFlowIndex >= 0) {
      targetIndex = currentFlowIndex;
    } else {
      targetIndex = currentFlowIndex - 1;
    }
  } else {
     targetIndex = currentFlowIndex + 1;
  }
  
  if (targetIndex < 0) targetIndex = 0;
  if (targetIndex >= flowCards.length) targetIndex = flowCards.length - 1;
  
  const target = flowCards[targetIndex];
  if (target) {
    const targetTop = target.getBoundingClientRect().top + window.scrollY - headerH - EXTRA_GAP;
    window.scrollTo({ top: targetTop, behavior: "instant" });
    
    target.classList.remove("flow-focused");
    void target.offsetWidth;
    target.classList.add("flow-focused");
  }
}

window.shortcutManager.register("ctrl+,", () => jumpToFlow(-1), "Nhảy đến Flow trước đó");
window.shortcutManager.register("ctrl+.", () => jumpToFlow(1), "Nhảy đến Flow kế tiếp");

let isTocModeEnabled = false;
let tocModeIndex = -1;

function toggleTocMode() {
  isTocModeEnabled = !isTocModeEnabled;
  const tocContainer = document.getElementById("toc-container");
  if (!tocContainer) return;
  
  if (isTocModeEnabled) {
    tocContainer.classList.add("toc-mode-active");
    tocModeIndex = 0;
    scrollToFlowAbsolute(tocModeIndex);
    showToast("Chế độ duyệt ToC: Bật", "success");
  } else {
    tocContainer.classList.remove("toc-mode-active");
    showToast("Chế độ duyệt ToC: Tắt", "info");
  }
}

function scrollToFlowAbsolute(index) {
  const flowCards = document.querySelectorAll('.flow-card');
  if (index < 0 || index >= flowCards.length) return;
  
  const target = flowCards[index];
  const header = document.querySelector("header");
  const headerH = header ? header.offsetHeight : 0;
  const EXTRA_GAP = 16;
  const targetTop = target.getBoundingClientRect().top + window.scrollY - headerH - EXTRA_GAP;
  window.scrollTo({ top: targetTop, behavior: "instant" });
  
  target.classList.remove("flow-focused");
  void target.offsetWidth;
  target.classList.add("flow-focused");
}

document.addEventListener("keydown", (e) => {
  if (!isTocModeEnabled) return;
  const isInput = e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.isContentEditable;
  if (isInput) return;
  
  if (["ArrowUp", "ArrowLeft"].includes(e.key)) {
    e.preventDefault();
    tocModeIndex = Math.max(0, tocModeIndex - 1);
    scrollToFlowAbsolute(tocModeIndex);
  } else if (["ArrowDown", "ArrowRight"].includes(e.key)) {
    e.preventDefault();
    const maxIndex = (configData.flows?.length || 1) - 1;
    tocModeIndex = Math.min(maxIndex, tocModeIndex + 1);
    scrollToFlowAbsolute(tocModeIndex);
  }
});

window.shortcutManager.register("ctrl+/", () => toggleTocMode(), "Bật/Tắt chế độ duyệt bằng ToC");
window.shortcutManager.register("alt++", () => toggleNotifications(), "Mở/Đóng bảng thông báo");
window.shortcutManager.register("alt+=", () => toggleNotifications(), "Mở/Đóng bảng thông báo", true);

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
      let parts;
      if (s.combo.endsWith("++")) {
        parts = s.combo.substring(0, s.combo.length - 2).split("+");
        parts.push("+");
      } else if (s.combo.endsWith("+=")) {
        parts = s.combo.substring(0, s.combo.length - 2).split("+");
        parts.push("+"); // Display it as + even if it's =
      } else {
        parts = s.combo.split("+");
      }
      const keys = parts
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

// ─────────────────────────────────────────────────────────────
// 10. NOTIFICATIONS
// ─────────────────────────────────────────────────────────────

let notificationPollInterval = null;

async function pollNotifications() {
  try {
    const res = await fetch("/api/notifications");
    if (!res.ok) return;
    const data = await res.json();
    renderNotifications(data.notifications);
  } catch (err) {
    console.error("Lỗi lấy thông báo:", err);
  }
}

function renderNotifications(notifs) {
  const badge = document.getElementById("notification-badge");
  const listEl = document.getElementById("notification-list");
  
  if (!badge || !listEl) return;
  
  let unreadCount = 0;
  listEl.innerHTML = "";
  
  if (!notifs || notifs.length === 0) {
    listEl.innerHTML = '<div style="padding: 15px; color: var(--text-muted); text-align: center; font-size: 0.9rem;">Không có thông báo nào</div>';
    badge.style.display = "none";
    return;
  }
  
  notifs.forEach(n => {
    if (!n.seen) unreadCount++;
    
    const item = document.createElement("div");
    item.style.padding = "12px 15px";
    item.style.borderBottom = "1px solid var(--card-border)";
    item.style.cursor = n.seen ? "default" : "pointer";
    item.style.backgroundColor = n.seen ? "transparent" : "darkgreen";
    item.style.transition = "background 0.2s";
    
    item.innerHTML = `
      <div style="font-size: 0.9rem; color: ${n.seen ? 'var(--text-muted)' : 'black'}; line-height: 1.4;">${escapeHtml(n.message)}</div>
      <div style="font-size: 0.75rem; color: ${n.seen ? 'var(--text-muted)' : 'black'}; margin-top: 5px;">${escapeHtml(n.timestamp)}</div>
    `;
    
    if (!n.seen) {
      item.onclick = async () => {
        await markNotificationAsRead(n.id);
        item.style.backgroundColor = "transparent";
        item.querySelector("div").style.color = "var(--text-muted)";
        item.onclick = null;
        item.style.cursor = "default";
      };
    }
    
    listEl.appendChild(item);
  });
  
  if (unreadCount > 0) {
    badge.textContent = unreadCount;
    badge.style.display = "flex";
  } else {
    badge.style.display = "none";
  }
}

async function markNotificationAsRead(id) {
  try {
    const res = await fetch(`/api/notifications/${id}/read`, { method: "POST" });
    if (res.ok) {
      pollNotifications();
    }
  } catch (err) {
    console.error("Lỗi cập nhật trạng thái thông báo:", err);
  }
}

async function markAllNotificationsAsRead() {
  try {
    const res = await fetch("/api/notifications/read-all", { method: "POST" });
    if (res.ok) {
      pollNotifications();
    }
  } catch (err) {
    console.error("Lỗi cập nhật trạng thái thông báo:", err);
  }
}

function toggleNotifications() {
  const dropdown = document.getElementById("notification-dropdown");
  if (dropdown.style.display === "none") {
    dropdown.style.display = "flex";
    pollNotifications();
  } else {
    dropdown.style.display = "none";
  }
}

// Close dropdown when clicking outside
document.addEventListener("click", (e) => {
  const container = document.getElementById("notification-container-el");
  if (container && !container.contains(e.target)) {
    const dropdown = document.getElementById("notification-dropdown");
    if (dropdown && dropdown.style.display !== "none") {
      dropdown.style.display = "none";
    }
  }
});

// Bắt đầu polling khi load trang
document.addEventListener("DOMContentLoaded", () => {
  pollNotifications();
  notificationPollInterval = setInterval(pollNotifications, 5000);
});

// ─────────────────────────────────────────────────────────────
// 11. FILTER CONFIG MODAL
// ─────────────────────────────────────────────────────────────

function openFilterConfigModal(flowIndex, filterIndex) {
  const filter = configData.flows[flowIndex].entrance_filters[filterIndex];
  document.getElementById("filter-config-title").textContent = filter.name;
  document.getElementById("filter-config-flow-index").value = flowIndex;
  document.getElementById("filter-config-filter-index").value = filterIndex;
  
  document.getElementById("filter-local-path-input").value = filter.input_path || (filter.kwargs && filter.kwargs.input_path) || "";
  document.getElementById("filter-local-path-output").value = filter.output_path || (filter.kwargs && filter.kwargs.output_path) || "";
  
  document.getElementById("filter-config-modal-backdrop").style.display = "flex";
}

function closeFilterConfigModal(event) {
  if (event && event.target !== document.getElementById("filter-config-modal-backdrop")) return;
  document.getElementById("filter-config-modal-backdrop").style.display = "none";
}

function saveFilterConfig() {
  const flowIndex = parseInt(document.getElementById("filter-config-flow-index").value, 10);
  const filterIndex = parseInt(document.getElementById("filter-config-filter-index").value, 10);
  
  const inputPath = document.getElementById("filter-local-path-input").value;
  const outputPath = document.getElementById("filter-local-path-output").value;
  
  if (configData.flows[flowIndex].entrance_filters[filterIndex].kwargs) {
    delete configData.flows[flowIndex].entrance_filters[filterIndex].kwargs;
  }
  
  configData.flows[flowIndex].entrance_filters[filterIndex].input_path = inputPath;
  configData.flows[flowIndex].entrance_filters[filterIndex].output_path = outputPath;
  
  closeFilterConfigModal();
  saveConfig();
}

// ─────────────────────────────────────────────────────────────
// 12. ACTIVE FLOW TRACKING
// ─────────────────────────────────────────────────────────────

function updateActiveFlowIndicator() {
  const header = document.querySelector("header");
  const headerH = header ? header.offsetHeight : 0;
  const EXTRA_GAP = 16;
  const flowCards = document.querySelectorAll('.flow-card');
  if (flowCards.length === 0) return;

  let activeIndex = -1;
  for (let i = 0; i < flowCards.length; i++) {
    const rect = flowCards[i].getBoundingClientRect();
    if (rect.top - headerH - EXTRA_GAP - 150 <= 0) {
      activeIndex = i;
    } else {
      break;
    }
  }
  
  if (activeIndex === -1) activeIndex = 0;

  // Cập nhật trên ToC
  document.querySelectorAll(".toc-item").forEach((el, i) => {
    if (i === activeIndex) {
      el.classList.add("active-toc");
    } else {
      el.classList.remove("active-toc");
    }
  });
}

document.addEventListener("scroll", updateActiveFlowIndicator, { passive: true });

// ─────────────────────────────────────────────────────────────
// 13. SETTINGS MODAL
// ─────────────────────────────────────────────────────────────

function openSettingsModal() {
  document.getElementById("settings-modal-backdrop").style.display = "flex";
  renderSettingsFlows();
}

function closeSettingsModal(event) {
  if (event && event.target !== document.getElementById("settings-modal-backdrop")) return;
  document.getElementById("settings-modal-backdrop").style.display = "none";
}

function switchSettingsTab(tabName, el) {
  const container = document.getElementById("settings-modal-backdrop");
  container.querySelectorAll(".doc-item").forEach(d => d.classList.remove("active"));
  if (el) el.classList.add("active");
  // Curently only 1 tab
}

function renderSettingsFlows() {
  const container = document.getElementById("settings-flow-list");
  if (!container) return;
  container.innerHTML = "";
  
  if (!configData.flows || configData.flows.length === 0) {
    container.innerHTML = '<div style="color:var(--text-muted); font-style:italic;">Không có flow nào.</div>';
    return;
  }
  
  configData.flows.forEach((flow, index) => {
    const card = document.createElement("div");
    card.style.cssText = "display: flex; justify-content: space-between; align-items: center; background: rgba(255, 255, 255, 0.03); padding: 1rem 1.25rem; border-radius: 8px; border: 1px solid var(--card-border); transition: var(--transition);";
    
    card.innerHTML = `
      <div style="display: flex; align-items: center; gap: 1rem;">
        <span style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; font-weight: bold; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: 50%; font-size: 0.9rem;">${index + 1}</span>
        <span style="font-weight: 500; font-size: 1.05rem; color: var(--text-main);">${escapeHtml(flow.flow_title || "Flow mới")}</span>
      </div>
      <div class="switch-wrapper" style="margin: 0; display: flex; align-items: center; gap: 8px;">
        <label class="switch" style="margin: 0;">
          <input type="checkbox" id="settings-enable-${index}" ${!flow.skip ? "checked" : ""} onchange="updateSettingsFlowToggle(${index}, !this.checked)">
          <span class="slider"></span>
        </label>
      </div>
    `;
    container.appendChild(card);
  });
}

function updateSettingsFlowToggle(index, isSkip) {
  updateFlowData(index, 'skip', isSkip);
  const mainSwitch = document.getElementById(`enable-${index}`);
  if (mainSwitch) mainSwitch.checked = !isSkip;
  
  // Lưu cấu hình ngay lập tức để tiện lợi
  saveConfigSilent().then(ok => {
    if (ok) {
      const statusText = !isSkip ? "bật" : "tắt";
      showToast(`Đã lưu trạng thái: ${statusText} Flow #${index + 1}`, "success");
    } else {
      showToast("Lỗi khi lưu cấu hình!", "error");
    }
  });
}
