'use strict';

// --- DOM Elements ---
const stage = document.getElementById('stage');
const stageWrapper = document.querySelector('.stage-wrapper');
const textBox = document.getElementById('textBox');
const textBoxPlaceholder = textBox ? textBox.querySelector('.textbox-placeholder') : null;
const characterHandle = document.getElementById('characterHandle');
const charPreview = document.getElementById('charPreview');
const overlayContainer = document.getElementById('overlayContainer');
const statusEl = document.getElementById('status');
const layerList = document.getElementById('layerList');
const overlayEditor = document.getElementById('overlayEditor');
const removeOverlayBtn = document.getElementById('removeOverlayBtn');
const presetSelect = document.getElementById('presetSelect');
const loadPresetBtn = document.getElementById('loadPresetBtn');
const savePresetBtn = document.getElementById('savePresetBtn');
const overridePresetBtn = document.getElementById('overridePresetBtn');
const presetStatus = document.getElementById('presetStatus');
const saveDefaultBtn = document.getElementById('saveDefaultBtn');
const characterRoleSelect = document.getElementById('characterRoleSelect');
const characterRoleUploadSelect = document.getElementById('characterRoleUploadSelect');
const characterRoleCustom = document.getElementById('characterRoleCustom');
const characterEmotionSelect = document.getElementById('characterEmotionSelect');
const characterEmotionCustom = document.getElementById('characterEmotionCustom');
const characterUploadInput = document.getElementById('characterUpload');
const componentUploadInput = document.getElementById('componentUpload');
const fontUploadInput = document.getElementById('fontUpload');
const emotionListEl = document.getElementById('emotionList');
const addEmotionBtn = document.getElementById('addEmotionBtn');
const saveEmotionBtn = document.getElementById('saveEmotionBtn');
const resetEmotionBtn = document.getElementById('resetEmotionBtn');
const backgroundGroupSelect = document.getElementById('backgroundGroupSelect');
const characterFitModeSelect = document.getElementById('characterFitModeSelect');
const characterAlignBottomInput = document.getElementById('characterAlignBottomInput');
const backgroundGroupUploadSelect = document.getElementById('backgroundGroupUploadSelect');
const backgroundGroupCustom = document.getElementById('backgroundGroupCustom');
const backgroundUploadInput = document.getElementById('backgroundUpload');
const uploadBackgroundBtn = document.getElementById('uploadBackgroundBtn');

// Inputs
const inputs = {
  bgColor: document.getElementById('backgroundColorInput'),
  bgAsset: document.getElementById('backgroundAssetSelect'),
  charAsset: document.getElementById('characterAssetSelect'),
  charRole: characterRoleSelect,
  textColor: document.getElementById('textColorInput'),
  bodyFont: document.getElementById('bodyFontSelect'),
  // Overlay inputs
  oText: document.getElementById('overlayTextInput'),
  oImage: document.getElementById('overlayImageSelect'),
  oLeft: document.getElementById('overlayLeftInput'),
  oTop: document.getElementById('overlayTopInput'),
  oWidth: document.getElementById('overlayWidthInput'),
  oHeight: document.getElementById('overlayHeightInput'),
  oZ: document.getElementById('overlayZIndexInput'),
  oOpacity: document.getElementById('overlayOpacityInput'),
  oFont: document.getElementById('overlayFontSelect'),
  oSize: document.getElementById('overlayFontSizeInput'),
  oColor: document.getElementById('overlayColorInput'),
  oBold: document.getElementById('overlayBoldInput'),
  oStrokeWidth: document.getElementById('overlayStrokeWidthInput'),
  oStrokeColor: document.getElementById('overlayStrokeColorInput'),
};

// --- State ---
const token = new URLSearchParams(location.search).get('token') || '';
const authHeader = token ? { 'Authorization': `Bearer ${token}` } : {};
const suffix = token ? `?token=${encodeURIComponent(token)}` : '';

function buildQueryUrl(path, extra = {}) {
  const params = new URLSearchParams();
  if(token) params.set('token', token);
  Object.entries(extra || {}).forEach(([key, value]) => {
    if(value !== undefined && value !== null && value !== '') {
      params.set(key, value);
    }
  });
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

const state = {
  layout: {},
  overlays: [],
  components: [],
  fonts: [],
  backgrounds: [],
  background_groups: [],
  characters: [],
  presets: [],
  roles: [],
  emotions: [],
  scale: 1,
  selectedOverlayId: null,
  activeLayerId: 'sys_box',
  dragging: null, // { type, id, startX, startY, initialParams }
  characterRatio: 1.8,
  currentPresetSlug: '',
  currentPresetName: '',
  personas: [],
  personaBindings: [],
};


if(charPreview) {
  charPreview.addEventListener('load', () => {
    if(charPreview.naturalWidth > 0) {
      const ratio = charPreview.naturalHeight / charPreview.naturalWidth;
      if(Number.isFinite(ratio) && ratio > 0) {
        state.characterRatio = ratio;
        renderCanvas();
      }
    }
  });
}

// --- Helpers ---
function setStatus(msg, err = false) {
  statusEl.textContent = msg;
  statusEl.style.color = err ? 'var(--danger)' : 'var(--success)';
  if(!err) setTimeout(() => statusEl.textContent = '', 3000);
}
const escapeHtml = (text = '') => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const formatCharacterLabel = (value) => {
  if(value === '__auto__') return '自动';
  if(value === '__random__') return '随机';
  if(value && value.startsWith('user::')) {
    const parts = value.split('::');
    const role = parts.length > 1 ? (parts[1] || 'custom') : 'custom';
    const emotion = parts.length > 2 ? (parts[2] || '') : '';
    const file = parts.length > 3 ? (parts[3] || '') : (parts[parts.length - 1] || '');
    const emotionPath = emotion ? `${emotion}/` : '';
    return `用户/${role}/${emotionPath}${file || '未知'}`;
  }
  return value || '';
};
const formatBackgroundLabel = (value) => {
  if(value === '__auto__') return '自动（分组随机）';
  if(value === '__random__') return '随机（所有背景）';
  if(value && value.startsWith('builtin::')) {
    return `内置/${value.split('::')[1] || ''}`;
  }
  if(value && value.startsWith('user::')) {
    const parts = value.split('::');
    const group = parts.length > 1 ? parts[1] : 'custom';
    const file = parts.length > 2 ? parts[2] : '';
    return `用户/${group}/${file}`;
  }
  return value || '';
};
function normalizeLegacyBackgroundAsset() {
  const asset = state.layout.background_asset;
  if(asset && !asset.includes('::') && asset !== '__auto__' && asset !== '__random__') {
    const candidate = `builtin::${asset}`;
    if(state.backgrounds.includes(candidate)) {
      state.layout.background_asset = candidate;
    }
  }
}
function renderPresetOptions() {
  if(!presetSelect) return;
  presetSelect.innerHTML = '<option value="">选择一个预设</option>';
  state.presets.forEach(p => {
    const option = document.createElement('option');
    option.value = p.slug;
    const label = p.name || p.slug;
    option.textContent = p.slug === state.currentPresetSlug ? `${label}（当前）` : label;
    presetSelect.appendChild(option);
  });
  presetSelect.value = state.currentPresetSlug || '';
}

function renderPresetStatus() {
  if(!presetStatus) return;
  if(state.currentPresetSlug) {
    const label = state.currentPresetName || state.currentPresetSlug;
    presetStatus.textContent = `当前预设：${label}（已绑定角色组）`;
  } else {
    presetStatus.textContent = '当前预设：未应用（正在编辑默认布局）';
  }
  if(overridePresetBtn) {
    overridePresetBtn.disabled = !state.currentPresetSlug;
  }
}

function setCurrentPreset(preset) {
  state.currentPresetSlug = preset?.slug || '';
  state.currentPresetName = preset?.name || '';
  if(presetSelect) {
    presetSelect.value = state.currentPresetSlug || '';
  }
  renderPresetStatus();
}

function renderPersonaOptions() {
  const select = document.getElementById('personaSelect');
  if(!select) return;
  const options = ['<option value="">选择人格</option>'];
  (state.personas || []).forEach(p => {
    const id = escapeHtml(p.id || '');
    const label = escapeHtml(p.label || p.id || '');
    options.push(`<option value="${id}">${label}</option>`);
  });
  select.innerHTML = options.join('');
}

function renderPersonaPresetOptions() {
  const select = document.getElementById('personaPresetSelect');
  if(!select) return;
  const options = ['<option value="">选择预设</option>'];
  (state.presets || []).forEach(p => {
    const value = escapeHtml(p.name || p.slug || '');
    const label = escapeHtml(p.name || p.slug || '');
    options.push(`<option value="${value}">${label}</option>`);
  });
  select.innerHTML = options.join('');
}

function renderPersonaBindings() {
  const list = document.getElementById('personaBindingList');
  const status = document.getElementById('personaBindingStatus');
  const bindings = state.personaBindings || [];
  if(status) {
    status.textContent = bindings.length ? `已绑定 ${bindings.length} 项` : '暂未绑定任何人格预设';
  }
  if(!list) return;
  if(!bindings.length) {
    list.innerHTML = '<p class="helper-text">在上方选择人格与预设后点击「绑定」。</p>';
    return;
  }
  list.innerHTML = bindings.map(b => {
    const id = escapeHtml(b.persona_id || '');
    const personaLabel = escapeHtml(b.persona_label || b.persona_id || '');
    const presetLabel = escapeHtml(b.preset_name || b.preset_slug || '未命名预设');
    return `<div class="preset-row" data-persona-id="${id}">
      <span style="flex:1;">${personaLabel} → ${presetLabel}</span>
      <button class="btn-ghost" data-unbind="${id}">解绑</button>
    </div>`;
  }).join('');
  list.querySelectorAll('button[data-unbind]').forEach(btn => {
    btn.onclick = async () => {
      const personaId = btn.getAttribute('data-unbind');
      if(!personaId) return;
      if(!window.confirm(`确定解绑「${personaId}」的人格预设？`)) return;
      setStatus('正在解绑...');
      try {
        const res = await fetch(`/api/persona-bindings/delete${suffix}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeader },
          body: JSON.stringify({ persona_id: personaId })
        });
        if(!res.ok) {
          const msg = await res.text();
          throw new Error(msg || '解绑失败');
        }
        const data = await res.json();
        state.personaBindings = data.bindings || [];
        renderPersonaBindings();
        setStatus(data.message || '已解绑');
      } catch(e) {
        setStatus(e.message || '解绑失败', true);
      }
    };
  });
}

async function loadPersonaBindings() {
  try {
    const res = await fetch(`/api/persona-bindings${suffix}`, { headers: authHeader });
    if(!res.ok) throw new Error('加载失败');
    const data = await res.json();
    state.personas = data.personas || state.personas || [];
    state.presets = data.presets || state.presets;
    state.personaBindings = data.bindings || [];
    renderPersonaOptions();
    renderPersonaPresetOptions();
    renderPersonaBindings();
  } catch(e) {
    renderPersonaBindings();
  }
}

const sanitizeEmotionKey = (value = '') => (value || '').toLowerCase().replace(/[^0-9a-z_]/g, '_');
const sanitizeFolderName = (value = '') => (value || '').replace(/[^0-9a-zA-Z_-]/g, '_');

function renderRoleOptions() {
  if(characterRoleSelect) {
    const fragments = [];
    fragments.push('<option value="__auto__">自动匹配（全部角色）</option>');
    state.roles.forEach(role => {
      const label = role.label || role.id;
      fragments.push(`<option value="${escapeHtml(role.id)}">${escapeHtml(label)}</option>`);
    });
    characterRoleSelect.innerHTML = fragments.join('');
    const currentRole = state.layout.character_role || '__auto__';
    characterRoleSelect.value = currentRole;
  }
  if(characterRoleUploadSelect) {
    characterRoleUploadSelect.innerHTML = '<option value="">角色分组</option>';
    state.roles
      .filter(role => role.source !== 'builtin')
      .forEach(role => {
        const option = document.createElement('option');
        option.value = role.id;
        option.textContent = role.label || role.id;
        characterRoleUploadSelect.appendChild(option);
      });
  }
}

function renderBackgroundGroupOptions() {
  if(backgroundGroupSelect) {
    const fragments = ['<option value="__auto__">自动（全部背景）</option>'];
    const hasBuiltin = state.background_groups.some(g => g.id === 'builtin');
    if(hasBuiltin) {
      fragments.push('<option value="builtin">仅内置背景</option>');
    }
    state.background_groups
      .filter(group => group.id && group.id.startsWith('user::'))
      .forEach(group => {
        const slug = group.id.split('::')[1] || 'default';
        const label = `${slug} (${group.count || 0})`;
        fragments.push(`<option value="${escapeHtml(group.id)}">${escapeHtml(label)}</option>`);
      });
    backgroundGroupSelect.innerHTML = fragments.join('');
    backgroundGroupSelect.value = state.layout.background_group || '__auto__';
  }
  if(backgroundGroupUploadSelect) {
    backgroundGroupUploadSelect.innerHTML = '<option value="">选择已有分组</option>';
    state.background_groups
      .filter(group => group.id && group.id.startsWith('user::'))
      .forEach(group => {
        const slug = group.id.split('::')[1] || 'default';
        const option = document.createElement('option');
        option.value = slug;
        option.textContent = slug;
        backgroundGroupUploadSelect.appendChild(option);
      });
    updateBackgroundGroupInputState();
  }
}

async function savePresetLayout(name, successLabel) {
  const trimmed = (name || '').trim();
  if(!trimmed) {
    setStatus('预设名称不能为空', true);
    return;
  }
  state.layout.text_overlays = state.overlays;
  setStatus('正在保存预设...');
  try {
    const res = await fetch(`/api/presets/save${suffix}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeader },
      body: JSON.stringify({ name: trimmed, layout: state.layout })
    });
    if(!res.ok) {
      const msg = await res.text();
      throw new Error(msg || '保存失败');
    }
    const data = await res.json();
    state.layout = data.layout || state.layout;
    if(!state.layout.character_role) state.layout.character_role = '__auto__';
    if(state.layout.character_role !== '__auto__') {
      state.layout.character_asset = '__auto__';
    }
    if(!state.layout.background_asset) state.layout.background_asset = '__auto__';
    if(!state.layout.background_group) state.layout.background_group = '__auto__';
    if(!state.layout.character_fit_mode) state.layout.character_fit_mode = 'fixed_width';
    if(state.layout.character_align_bottom === undefined) state.layout.character_align_bottom = true;
    if(state.layout.character_uniform_height === undefined) state.layout.character_uniform_height = 620;
    if(state.layout.character_top === undefined) state.layout.character_top = 0;
    normalizeLegacyBackgroundAsset();
    state.overlays = normalizeOverlays(state.layout.text_overlays);
    state.presets = data.presets || state.presets;
    setCurrentPreset(data.preset || { name: trimmed, slug: trimmed });
    renderPresetOptions();
    renderRoleOptions();
    renderBackgroundGroupOptions();
    syncInputsToState();
    renderLayerList();
    renderCanvas();
    updatePreviewImages();
    const finalLabel = successLabel || `预设「${data?.preset?.name || trimmed}」保存成功`;
    setStatus(finalLabel);
  } catch(err) {
    setStatus(err.message || '保存失败', true);
  }
}

function normalizeOverlays(raw = []) {
  return (raw || [])
    .map(o => {
      const normalizedType = o.type === 'converted_text' ? 'text' : (o.type || 'text');
      return {
        ...o,
        type: normalizedType,
        stroke_width: Number(o.stroke_width ?? 0) || 0,
        stroke_color: o.stroke_color || '#000000'
      };
    })
    .filter(o => ['text', 'image', 'glass'].includes(o.type));
}

function renderEmotionOptions() {
  if(!characterEmotionSelect) return;
  characterEmotionSelect.innerHTML = '<option value="">情绪 / 差分</option>';
  const list = Array.isArray(state.emotions) ? state.emotions : [];
  list.forEach(item => {
    const value = item.folder || item.key || '';
    if(!value) return;
    const label = item.key ? `${item.key} (${value})` : value;
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    characterEmotionSelect.appendChild(option);
  });
}

function renderEmotionEditor() {
  if(!emotionListEl) return;
  emotionListEl.innerHTML = '';
  if(!Array.isArray(state.emotions) || !state.emotions.length) {
    emotionListEl.innerHTML = '<p class="helper-text">暂无情绪标签，点击下方"新增标签"创建。</p>';
    return;
  }
  state.emotions.forEach((emotion, index) => {
    const row = document.createElement('div');
    row.className = 'emotion-item';

    const grid = document.createElement('div');
    grid.className = 'emotion-row';

    const keyGroup = document.createElement('div');
    keyGroup.className = 'form-group';
    keyGroup.innerHTML = '<label>标签 Key (&key&)</label>';
    const keyInput = document.createElement('input');
    keyInput.type = 'text';
    keyInput.value = emotion.key || '';
    keyInput.addEventListener('input', (e) => {
      const val = sanitizeEmotionKey(e.target.value);
      state.emotions[index].key = val;
      e.target.value = val;
    });
    keyGroup.appendChild(keyInput);

    const labelGroup = document.createElement('div');
    labelGroup.className = 'form-group';
    labelGroup.innerHTML = '<label>展示名称</label>';
    const labelInput = document.createElement('input');
    labelInput.type = 'text';
    labelInput.value = emotion.label || '';
    labelInput.addEventListener('input', (e) => {
      state.emotions[index].label = e.target.value;
    });
    labelGroup.appendChild(labelInput);

    const folderGroup = document.createElement('div');
    folderGroup.className = 'form-group';
    folderGroup.innerHTML = '<label>差分文件夹</label>';
    const folderInput = document.createElement('input');
    folderInput.type = 'text';
    folderInput.value = emotion.folder || '';
    folderInput.addEventListener('input', (e) => {
      const val = sanitizeFolderName(e.target.value);
      state.emotions[index].folder = val;
      e.target.value = val;
    });
    folderGroup.appendChild(folderInput);

    const colorGroup = document.createElement('div');
    colorGroup.className = 'form-group';
    colorGroup.innerHTML = '<label>标签颜色</label>';
    const colorInput = document.createElement('input');
    colorInput.type = 'color';
    const colorVal = /^#[0-9a-fA-F]{6}$/.test(emotion.color || '') ? emotion.color : '#ffffff';
    colorInput.value = colorVal;
    colorInput.addEventListener('input', (e) => {
      state.emotions[index].color = e.target.value;
    });
    colorGroup.appendChild(colorInput);

    grid.appendChild(keyGroup);
    grid.appendChild(labelGroup);
    grid.appendChild(folderGroup);
    grid.appendChild(colorGroup);
    row.appendChild(grid);

    const actions = document.createElement('div');
    actions.className = 'emotion-actions';
    const toggleLabel = document.createElement('label');
    const enableInput = document.createElement('input');
    enableInput.type = 'checkbox';
    enableInput.checked = emotion.enabled !== false;
    enableInput.addEventListener('change', (e) => {
      state.emotions[index].enabled = e.target.checked;
    });
    toggleLabel.appendChild(enableInput);
    toggleLabel.appendChild(document.createTextNode('启用'));
    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn-danger';
    removeBtn.type = 'button';
    removeBtn.textContent = '删除';
    removeBtn.onclick = () => {
      state.emotions.splice(index, 1);
      renderEmotionEditor();
    };
    actions.appendChild(toggleLabel);
    actions.appendChild(removeBtn);
    row.appendChild(actions);

    emotionListEl.appendChild(row);
  });
}

function addEmotionRecord() {
  if(!Array.isArray(state.emotions)) state.emotions = [];
  const seq = (state.emotions.length + 1).toString(36);
  const baseKey = `emo_${seq}`;
  state.emotions.push({
    key: baseKey,
    folder: baseKey,
    label: `情绪${state.emotions.length + 1}`,
    color: '#ffffff',
    enabled: true,
  });
  renderEmotionEditor();
}

async function syncEmotionSets(path, payload = {}, successMsg = '情绪配置已更新') {
  setStatus('正在同步情绪配置...');
  try {
    const res = await fetch(`${path}${suffix}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeader },
      body: JSON.stringify(payload),
    });
    if(!res.ok) {
      const msg = await res.text();
      throw new Error(msg || '保存失败');
    }
    const data = await res.json();
    state.emotions = data.emotion_sets || [];
    renderEmotionOptions();
    renderEmotionEditor();
    setStatus(successMsg);
  } catch(err) {
    setStatus(err.message || '操作失败', true);
  }
}

function updateEmotionInputState() {
  if(!characterEmotionCustom) return;
  const locked = characterEmotionSelect && characterEmotionSelect.value;
  characterEmotionCustom.disabled = !!locked;
  if(locked) {
    characterEmotionCustom.value = '';
    characterEmotionCustom.placeholder = '已选择情绪';
  } else {
    characterEmotionCustom.placeholder = '自定义情绪 (可选)';
  }
}

function updateRoleInputState() {
  if(!characterRoleCustom) return;
  const locked = characterRoleUploadSelect && characterRoleUploadSelect.value;
  characterRoleCustom.disabled = !!locked;
  if(locked) {
    characterRoleCustom.value = '';
    characterRoleCustom.placeholder = '已选择角色';
  } else {
    characterRoleCustom.placeholder = '自定义角色 (仅英文)';
  }
}

function updateBackgroundGroupInputState() {
  if(!backgroundGroupCustom) return;
  const locked = backgroundGroupUploadSelect && backgroundGroupUploadSelect.value;
  backgroundGroupCustom.disabled = !!locked;
  if(locked) {
    backgroundGroupCustom.value = '';
    backgroundGroupCustom.placeholder = '已选择分组';
  } else {
    backgroundGroupCustom.placeholder = '自定义分组 (仅英文)';
  }
}

function resolveSelectedRoleSlug() {
  const selected = characterRoleUploadSelect && characterRoleUploadSelect.value ? characterRoleUploadSelect.value.trim() : '';
  const customEnabled = characterRoleCustom && !characterRoleCustom.disabled;
  const custom = customEnabled ? (characterRoleCustom.value || '').trim() : '';
  return custom || selected || '';
}

function resolveSelectedEmotionSlug() {
  const selected = characterEmotionSelect && characterEmotionSelect.value ? characterEmotionSelect.value.trim() : '';
  const customEnabled = characterEmotionCustom && !characterEmotionCustom.disabled;
  const custom = customEnabled ? (characterEmotionCustom.value || '').trim() : '';
  return custom || selected || '';
}

function resolveSelectedBackgroundGroupSlug() {
  const selected = backgroundGroupUploadSelect && backgroundGroupUploadSelect.value ? backgroundGroupUploadSelect.value.trim() : '';
  const customEnabled = backgroundGroupCustom && !backgroundGroupCustom.disabled;
  const custom = customEnabled ? (backgroundGroupCustom.value || '').trim() : '';
  return custom || selected || 'default';
}

const getUrl = (name, type) => {
  if(!name) return '';
  if(type === 'bg') return `/api/backgrounds/raw/${encodeURIComponent(name)}${suffix}`;
  if(type === 'char') return `/api/characters/raw/${encodeURIComponent(name)}${suffix}`;
  if(type === 'font') return `/api/fonts/raw/${encodeURIComponent(name)}${suffix}`;
  return `/api/components/raw/${encodeURIComponent(name)}${suffix}`;
};

// 动态加载字体
const loadedFonts = new Set();
function loadFont(fontName) {
  if(!fontName || loadedFonts.has(fontName)) return;
  if(!state.fonts.includes(fontName)) return; // 不是自定义字体，使用系统字体

  // 检查是否已经加载
  const fontId = `font-${fontName.replace(/[^a-zA-Z0-9]/g, '-')}`;
  if(document.getElementById(fontId)) return;

  // 创建@font-face
  const style = document.createElement('style');
  style.id = fontId;
  const ext = fontName.split('.').pop().toLowerCase();
  const fontFormat = ext === 'otf' ? 'opentype' : 'truetype';
  style.textContent = `
    @font-face {
      font-family: "${fontName}";
      src: url("${getUrl(fontName, 'font')}") format("${fontFormat}");
    }
  `;
  document.head.appendChild(style);
  loadedFonts.add(fontName);
}

// --- Core Logic ---

async function init() {
  try {
    setStatus('正在加载配置...');
    const res = await fetch(`/api/config${suffix}`, { headers: authHeader });
    if(!res.ok) throw new Error('API Error');
    const data = await res.json();

    state.layout = data.layout || {};
    state.overlays = normalizeOverlays(state.layout.text_overlays);
    state.components = data.components || [];
    state.characters = data.characters || [];  // 立绘列表
    state.fonts = data.fonts || [];
    state.backgrounds = data.backgrounds || [];
    state.background_groups = data.background_groups || [];
    state.presets = data.presets || [];
    state.roles = data.character_roles || [];
    state.emotions = data.emotion_sets || [];
    if(!state.layout.character_role) state.layout.character_role = '__auto__';
    if(state.layout.character_role !== '__auto__') {
      state.layout.character_asset = '__auto__';
    }
    if(!state.layout.background_asset) state.layout.background_asset = '__auto__';
    if(!state.layout.background_group) state.layout.background_group = '__auto__';
    if(!state.layout.character_fit_mode) state.layout.character_fit_mode = 'fixed_width';
    if(state.layout.character_align_bottom === undefined) state.layout.character_align_bottom = true;
    if(state.layout.character_uniform_height === undefined) state.layout.character_uniform_height = 620;
    if(state.layout.character_top === undefined) state.layout.character_top = 0;
    normalizeLegacyBackgroundAsset();

    // Ensure defaults
    if(!state.layout.canvas_width) state.layout.canvas_width = 1280;
    if(!state.layout.canvas_height) state.layout.canvas_height = 720;

    state.currentPresetSlug = '';
    state.currentPresetName = '';
    setCurrentPreset(null);

    populateSelects();
    renderPresetOptions();
    renderRoleOptions();
    renderBackgroundGroupOptions();
    renderEmotionOptions();
    renderEmotionEditor();
    updateRoleInputState();
    updateEmotionInputState();
    updateBackgroundGroupInputState();
    syncInputsToState();
    renderCanvas();
    renderLayerList();
    renderPresetStatus();
    updatePreviewImages();
    setStatus('配置加载成功');
    loadPersonaBindings();
  } catch (e) {
    setStatus('加载失败: ' + e.message, true);
    console.error(e);
  }
}

function populateSelects() {
  const makeOpts = (arr, extra = []) =>
    [...extra, ...arr].map(v => {
      const val = String(v);
      return `<option value="${escapeHtml(val)}">${escapeHtml(val)}</option>`;
    }).join('');

  const bgValues = ['__auto__', '__random__', ...state.backgrounds];
  inputs.bgAsset.innerHTML = bgValues.map(v => {
    if(v === '__auto__') return '<option value="__auto__">自动（使用背景分组）</option>';
    if(v === '__random__') return '<option value="__random__">随机（全部背景）</option>';
    const val = String(v);
    return `<option value="${escapeHtml(val)}">${escapeHtml(formatBackgroundLabel(val))}</option>`;
  }).join('');
  const charValues = ['__auto__', '__random__', ...state.characters];
  inputs.charAsset.innerHTML = charValues.map(v => {
    const val = String(v);
    return `<option value="${escapeHtml(val)}">${escapeHtml(formatCharacterLabel(val))}</option>`;
  }).join('');

  const fontOpts = makeOpts(state.fonts, ['']);
  inputs.bodyFont.innerHTML = fontOpts;
  if(inputs.oFont) inputs.oFont.innerHTML = fontOpts;

  inputs.oImage.innerHTML = makeOpts(state.components, ['']);
}

function syncInputsToState() {
  // Bind basic fields
  document.querySelectorAll('[data-field]').forEach(el => {
    const key = el.dataset.field;
    if(state.layout[key] !== undefined) el.value = state.layout[key];
  });

  inputs.bgColor.value = state.layout.background_color || '#000000';
  inputs.textColor.value = state.layout.text_color || '#ffffff';

  // Selects
  inputs.bgAsset.value = state.layout.background_asset || '__auto__';
  inputs.charAsset.value = state.layout.character_asset || '__auto__';
  inputs.bodyFont.value = state.layout.body_font || '';
  if(backgroundGroupSelect) {
    backgroundGroupSelect.value = state.layout.background_group || '__auto__';
  }
  if(characterFitModeSelect) {
    characterFitModeSelect.value = state.layout.character_fit_mode || 'fixed_width';
  }
  if(characterAlignBottomInput) {
    characterAlignBottomInput.checked = state.layout.character_align_bottom !== false;
  }

  // 只在初始化时更新预览，且只在资源不是auto/random时更新
  const bg = state.layout.background_asset;
  const char = state.layout.character_asset;
  if(bg && bg !== '__auto__' && bg !== '__random__') {
    if(state.backgrounds.includes(bg)) {
      stage.style.backgroundImage = `url(${getUrl(bg, 'bg')})`;
    }
  }
  if(char && char !== '__auto__' && char !== '__random__' && state.characters.includes(char)) {
    const imgEl = document.getElementById('charPreview');
    if(imgEl) imgEl.src = getUrl(char, 'char');
  } else if(state.characters.length > 0) {
    const imgEl = document.getElementById('charPreview');
    if(imgEl && !imgEl.src) imgEl.src = getUrl(state.characters[0], 'char');
  }
}

let previewUpdateTimer = null;
async function updatePreviewImages() {
   // 防抖：避免频繁调用API
   if(previewUpdateTimer) {
     clearTimeout(previewUpdateTimer);
   }
   previewUpdateTimer = setTimeout(async () => {
    const roleParam = state.layout.character_role && state.layout.character_role !== '__auto__'
      ? state.layout.character_role
      : '';
    const bgGroupParam = state.layout.background_group && state.layout.background_group !== '__auto__'
      ? state.layout.background_group
      : '';
    let previewCache = null;
    const ensurePreviewData = async () => {
      if(previewCache) return previewCache;
      try {
        const query = {};
        if(roleParam) query.role = roleParam;
        if(bgGroupParam) query.bg_group = bgGroupParam;
        const res = await fetch(buildQueryUrl('/api/preview-assets', query), { headers: authHeader });
        if(res.ok) {
          previewCache = await res.json();
        }
      } catch(e) { console.warn('Failed to load preview assets', e); }
      return previewCache;
    };
     // Background preview
     const bg = state.layout.background_asset;
     if(bg && bg !== '__auto__' && bg !== '__random__') {
       if(state.backgrounds.includes(bg)) {
         stage.style.backgroundImage = `url(${getUrl(bg, 'bg')})`;
       } else if(state.components.includes(bg)) {
         stage.style.backgroundImage = `url(${getUrl(bg, 'comp')})`;
       }
     } else if(bg === '__auto__' || bg === '__random__') {
       // 调用API获取随机背景预览（只在需要时调用）
      const data = await ensurePreviewData();
      if(data && data.background) {
        stage.style.backgroundImage = `url(${data.background})`;
      }
     }

     // Character preview - 只使用立绘列表
     const char = state.layout.character_asset;
     const imgEl = document.getElementById('charPreview');
     if(char && char !== '__auto__' && char !== '__random__' && state.characters.includes(char)) {
       imgEl.src = getUrl(char, 'char');
     } else if(char === '__auto__' || char === '__random__') {
       // 调用API获取随机立绘预览（只在需要时调用）
      const data = await ensurePreviewData();
      if(data && data.character) {
        imgEl.src = data.character;
      }
     } else if(state.characters.length > 0 && !imgEl.src) {
       // 默认读取第一个立绘
       imgEl.src = getUrl(state.characters[0], 'char');
     }
   }, 300); // 300ms防抖
}

function renderCanvas() {
  const l = state.layout;

  // Stage dimensions
  stage.style.width = l.canvas_width + 'px';
  stage.style.height = l.canvas_height + 'px';
  stage.style.backgroundColor = l.background_color;

  // Scaling to fit
  const container = stageWrapper.getBoundingClientRect();
  const scaleX = (container.width - 40) / l.canvas_width;
  const scaleY = (container.height - 40) / l.canvas_height;
  state.scale = Math.min(scaleX, scaleY, 1);
  stage.style.transform = `scale(${state.scale})`;

  // Main Text Box
  const boxWidth = Math.max(20, Number(l.box_width) || 640);
  const boxHeight = Math.max(20, Number(l.box_height) || 340);
  const boxLeft = Number(l.box_left) || 520;
  const boxTop = Number(l.box_top) || 160;
  const padding = Math.max(0, Number(l.padding) || 20);
  const radius = Math.max(0, Number(l.radius) || 0);

  setPosSize(textBox, boxLeft, boxTop, boxWidth, boxHeight);
  textBox.style.borderRadius = radius + 'px';
  textBox.style.padding = padding + 'px';
  textBox.style.fontSize = (Number(l.font_size) || 24) + 'px';
  textBox.style.lineHeight = l.line_height || 1.5;
  textBox.style.color = l.text_color;
  // 加载并应用字体
  if(l.body_font) {
    loadFont(l.body_font);
    textBox.style.fontFamily = `"${l.body_font}", "PingFang SC", "Microsoft YaHei", sans-serif`;
  } else {
    textBox.style.fontFamily = '"PingFang SC", "Microsoft YaHei", sans-serif';
  }
  const strokeWidth = Math.max(0, Number(l.text_stroke_width) || 0);
  const strokeColor = l.text_stroke_color || '#000000';
  if(strokeWidth > 0) {
    textBox.style.webkitTextStroke = `${strokeWidth}px ${strokeColor}`;
    textBox.style.textShadow = `0 0 ${Math.max(1, strokeWidth)}px ${strokeColor}`;
  } else {
    textBox.style.webkitTextStroke = '0px transparent';
    textBox.style.textShadow = 'none';
  }

  // 更新预览文本内容
  if(textBoxPlaceholder) {
    textBoxPlaceholder.textContent = '这是一段示例文本，用于预览对话框效果。你可以在这里看到文本的显示效果，包括字体、颜色、大小等设置。';
  }
  textBox.style.zIndex = l.textbox_z_index || 200;
  textBox.classList.toggle('selected', state.activeLayerId === 'sys_box');

  // Character
  const canvasW = Number(l.canvas_width) || 1280;
  const canvasH = Number(l.canvas_height) || 720;
  const { width: charWidth, height: charHeight } = getCharacterDimensions();
  // 允许负值坐标，支持立绘一半在屏幕外
  l.character_left = Number(l.character_left) || 0;
  characterHandle.style.left = l.character_left + 'px';
  if(l.character_align_bottom !== false) {
    // 允许负值 bottom，支持立绘一半在屏幕外
    l.character_bottom = Number(l.character_bottom) || 0;
    characterHandle.style.bottom = l.character_bottom + 'px';
    characterHandle.style.top = 'auto';
  } else {
    // 允许负值 top，支持立绘一半在屏幕外
    l.character_top = Number(l.character_top) || 0;
    characterHandle.style.top = l.character_top + 'px';
    characterHandle.style.bottom = 'auto';
  }
  characterHandle.style.width = charWidth + 'px';
  characterHandle.style.height = charHeight + 'px';
  characterHandle.style.zIndex = l.character_z_index || 100;
  characterHandle.classList.toggle('selected', state.activeLayerId === 'sys_char');

  // 名字和角标已移除，用户需要自己添加文本层

  // Overlays
  renderOverlays();
}

function renderOverlays() {
  overlayContainer.innerHTML = '';
  state.overlays.forEach(o => {
    const el = document.createElement('div');
    const classes = ['layer-box'];
    if(state.activeLayerId === o.id) classes.push('selected');
    if(o.type === 'image') classes.push('image-layer');
    el.className = classes.join(' ');
    setPosSize(el, o.left, o.top, o.width, o.height);

    el.style.zIndex = o.z_index || 300;
    el.style.opacity = o.opacity !== undefined ? o.opacity : 1;

    if (o.type === 'image') {
      el.style.backgroundImage = '';
      el.style.backgroundColor = 'transparent';
      el.style.backdropFilter = 'none';
      if(o.image) {
        const img = document.createElement('img');
        img.src = getUrl(o.image, 'comp');
        img.alt = o.image || '';
        el.appendChild(img);
      } else {
        el.innerText = '未选择组件';
      }
    } else if (o.type === 'glass') {
      // 毛玻璃层：显示为半透明毛玻璃效果
      el.innerText = '毛玻璃';
      el.style.backgroundColor = 'rgba(255,255,255,0.1)';
      el.style.backdropFilter = 'blur(10px)';
      el.style.border = '1px solid rgba(255,255,255,0.2)';
      el.style.color = '#e3ecff';
      el.style.fontSize = '12px';
      el.style.display = 'flex';
      el.style.alignItems = 'center';
      el.style.justifyContent = 'center';
    } else {
      el.classList.add('text-layer');
      el.textContent = o.text || 'Text';
      el.style.fontSize = (o.font_size || 24) + 'px';
      el.style.color = o.color || '#ffffff';
      el.style.display = 'block';
      el.style.alignItems = '';
      el.style.justifyContent = '';
      el.style.whiteSpace = 'pre-wrap';
      el.style.wordBreak = 'break-word';
      // 加载并应用字体
      const overlayFont = o.font || '';
      if(overlayFont && state.fonts.includes(overlayFont)) {
        loadFont(overlayFont);
        el.style.fontFamily = `"${overlayFont}", "PingFang SC", "Microsoft YaHei", sans-serif`;
      } else {
        el.style.fontFamily = overlayFont || '"PingFang SC", "Microsoft YaHei", sans-serif';
      }
      el.style.fontWeight = o.bold ? 'bold' : 'normal';
      el.style.lineHeight = '1.25';
      const strokeWidth = Math.max(0, Number(o.stroke_width) || 0);
      const strokeColor = o.stroke_color || '#000000';
      if(strokeWidth > 0) {
        el.style.webkitTextStroke = `${strokeWidth}px ${strokeColor}`;
        el.style.textShadow = `0 0 ${Math.max(1, strokeWidth)}px ${strokeColor}`;
      } else {
        el.style.webkitTextStroke = '0px transparent';
        el.style.textShadow = 'none';
      }
    }

    // Add Resize handle
    const resizer = document.createElement('div');
    resizer.className = 'resize-handle';
    el.appendChild(resizer);

    // Events
    el.onmousedown = (e) => {
      e.stopPropagation();
      state.activeLayerId = o.id;
      selectOverlay(o.id);
      if(e.target === resizer) startDrag('resize-overlay', e, o.id);
      else startDrag('move-overlay', e, o.id);
    };

    overlayContainer.appendChild(el);
  });
}

function renderLayerList() {
  layerList.innerHTML = '';

  // Combine base layers + overlays for the list, sorted by Z-index descending
  const layers = [
    { id: 'sys_char', name: '立绘 (Character)', z: state.layout.character_z_index || 100, icon: '👤' },
    { id: 'sys_box', name: '主文本框', z: state.layout.textbox_z_index || 200, icon: '💬' },
    ...state.overlays.map(o => {
      let name = '';
      let icon = '📝';
      if (o.type === 'image') {
        name = `组件: ${o.image || '未选择'}`;
        icon = '🖼️';
      } else if (o.type === 'glass') {
        name = '毛玻璃';
        icon = '🔲';
      } else {
        name = `文本: ${o.text || '未命名'}`;
        icon = '📝';
      }
      return {
        id: o.id,
        name,
        z: o.z_index || 300,
        icon,
        isOverlay: true
      };
    })
  ].sort((a, b) => b.z - a.z);

  layers.forEach((l, idx) => {
    const div = document.createElement('div');
    const isActive = l.isOverlay ? state.selectedOverlayId === l.id : state.activeLayerId === l.id;
    div.className = `layer-item ${isActive ? 'active' : ''}`;
    div.dataset.layerId = l.id;
    div.dataset.layerIndex = idx;
    div.draggable = true;
    div.innerHTML = `
      <span class="layer-icon">${l.icon}</span>
      <span class="layer-name">${l.name}</span>
      <span class="layer-meta">z:${l.z}</span>
    `;
    div.onclick = () => {
       if(l.isOverlay) {
         selectOverlay(l.id);
       } else {
         state.selectedOverlayId = null;
         state.activeLayerId = l.id;
         overlayEditor.style.display = 'none';
         renderLayerList();
         renderCanvas();
       }
    };

    // 拖动排序功能
    div.ondragstart = (e) => {
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', l.id);
      div.classList.add('dragging');
      div.style.opacity = '0.5';
    };
    div.ondragend = (e) => {
      div.classList.remove('dragging');
      div.style.opacity = '';
      // 拖动结束后重新排序所有图层
      reorderLayers();
    };
    div.ondragover = (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      const dragging = layerList.querySelector('.dragging');
      if(!dragging || dragging === div) return;
      const afterElement = getDragAfterElement(layerList, e.clientY);
      if(afterElement == null) {
        layerList.appendChild(dragging);
      } else {
        layerList.insertBefore(dragging, afterElement);
      }
    };
    div.ondrop = (e) => {
      e.preventDefault();
    };

    layerList.appendChild(div);
  });

  function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.layer-item:not(.dragging)')];
    return draggableElements.reduce((closest, child) => {
      const box = child.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      if(offset < 0 && offset > closest.offset) {
        return { offset: offset, element: child };
      } else {
        return closest;
      }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
  }

  function reorderLayers() {
    // 重新排序所有图层的Z-index
    const allLayers = [...layerList.querySelectorAll('.layer-item')];
    allLayers.forEach((el, idx) => {
      const layerId = el.dataset.layerId;
      // 从下往上，Z-index递增（列表底部 = 最上层）
      const newZ = 100 + (allLayers.length - 1 - idx) * 10;

      if(layerId === 'sys_char') {
        state.layout.character_z_index = newZ;
      } else if(layerId === 'sys_box') {
        state.layout.textbox_z_index = newZ;
      } else if(layerId && layerId.startsWith('ov_')) {
        const overlay = state.overlays.find(o => o.id === layerId);
        if(overlay) {
          overlay.z_index = newZ;
        }
      }
    });
    // 立即更新预览
    renderCanvas();
    renderOverlays();
    renderLayerList();
  }
}

function selectOverlay(id) {
  state.selectedOverlayId = id;
  state.activeLayerId = id;
  const overlay = state.overlays.find(o => o.id === id);

  if(overlay) {
    overlayEditor.style.display = 'block';
    // Populate inputs
    inputs.oText.value = overlay.text || '';
    inputs.oImage.value = overlay.image || '';
    inputs.oLeft.value = overlay.left;
    inputs.oTop.value = overlay.top;
    inputs.oWidth.value = overlay.width;
    inputs.oHeight.value = overlay.height;
    inputs.oZ.value = overlay.z_index || 300;
    inputs.oOpacity.value = overlay.opacity !== undefined ? overlay.opacity : 1;
    inputs.oSize.value = overlay.font_size || 24;
    inputs.oColor.value = overlay.color || '#ffffff';
    if(inputs.oFont) inputs.oFont.value = overlay.font || '';
    if(inputs.oBold) inputs.oBold.checked = overlay.bold !== false;
    if(inputs.oStrokeWidth) inputs.oStrokeWidth.value = overlay.stroke_width || 0;
    if(inputs.oStrokeColor) inputs.oStrokeColor.value = overlay.stroke_color || '#000000';

    const typeControls = document.getElementById('overlayTypeControls');
    const fontControls = document.getElementById('overlayFontControls');
    const typeSelect = document.getElementById('overlayTypeSelect');
    const textFields = document.getElementById('overlayTextFields');
    const imageFields = document.getElementById('overlayImageFields');

    if(typeSelect) {
      typeSelect.value = overlay.type || 'text';
      typeSelect.disabled = false;
    }
    if(typeControls) {
      typeControls.style.display = 'block';
    }
    if(removeOverlayBtn) {
      removeOverlayBtn.disabled = false;
      removeOverlayBtn.title = '';
    }

    // 根据图层类型显示/隐藏相应的配置项
    if(overlay.type === 'image') {
        if(textFields) textFields.style.display = 'none';
        if(imageFields) imageFields.style.display = 'block';
        if(fontControls) fontControls.style.display = 'none';
    } else if(overlay.type === 'glass') {
        if(textFields) textFields.style.display = 'none';
        if(imageFields) imageFields.style.display = 'none';
        if(fontControls) fontControls.style.display = 'none';
    } else {
        if(textFields) textFields.style.display = 'block';
        if(imageFields) imageFields.style.display = 'none';
        if(fontControls) fontControls.style.display = 'flex';
    }

  } else {
    overlayEditor.style.display = 'none';
  }
  renderOverlays();
  renderLayerList();
}

// --- Interaction ---

function setPos(el, x, y) { el.style.left = x + 'px'; el.style.top = y + 'px'; }
function setPosSize(el, x, y, w, h) { setPos(el, x, y); el.style.width = w + 'px'; el.style.height = h + 'px'; }
function getCharacterDimensions() {
  const mode = state.layout.character_fit_mode || 'fixed_width';
  const ratio = state.characterRatio && Number.isFinite(state.characterRatio) && state.characterRatio > 0
    ? state.characterRatio
    : 1.8;
  if(mode === 'uniform_height') {
    const height = Math.max(20, Number(state.layout.character_uniform_height) || 620);
    const width = Math.max(20, Math.round(height / Math.max(ratio, 0.1)));
    return { width, height };
  }
  const width = Math.max(20, Number(state.layout.character_width) || 520);
  const height = Math.max(20, Math.round(width * ratio));
  return { width, height };
}

function updateFromInputs() {
  // 注意：背景和立绘资源不在input事件中更新，只在change事件中更新
  // 这样可以避免操作其他元素时触发预览更新

  // Inputs to State
  document.querySelectorAll('[data-field]').forEach(el => {
    const key = el.dataset.field;
    state.layout[key] = parseFloat(el.value) || el.value;
  });
  if(characterAlignBottomInput) {
    state.layout.character_align_bottom = characterAlignBottomInput.checked;
  }
  if(backgroundGroupSelect) {
    state.layout.background_group = backgroundGroupSelect.value || '__auto__';
  }

  // 关键数值做限制，避免出现非法值
  state.layout.box_width = Math.max(20, Number(state.layout.box_width) || 640);
  state.layout.box_height = Math.max(20, Number(state.layout.box_height) || 340);
  state.layout.box_left = Number(state.layout.box_left) || 520;
  state.layout.box_top = Number(state.layout.box_top) || 160;
  state.layout.padding = Math.max(0, Number(state.layout.padding) || 20);
  state.layout.radius = Math.max(0, Number(state.layout.radius) || 0);
  state.layout.font_size = Math.max(8, Number(state.layout.font_size) || 24);
  state.layout.text_stroke_width = Math.max(0, Number(state.layout.text_stroke_width) || 0);
  state.layout.character_width = Math.max(50, Number(state.layout.character_width) || 520);
  state.layout.character_left = Math.max(0, Number(state.layout.character_left) || 0);
  state.layout.character_bottom = Math.max(0, Number(state.layout.character_bottom) || 0);
  state.layout.character_uniform_height = Math.max(50, Number(state.layout.character_uniform_height) || 620);
  state.layout.character_top = Math.max(0, Number(state.layout.character_top) || 0);

  state.layout.background_color = inputs.bgColor.value;
  // 不在这里更新background_asset和character_asset，它们由change事件处理
  state.layout.text_color = inputs.textColor.value;
  state.layout.body_font = inputs.bodyFont.value;

  renderCanvas();
  // 不在这里调用updatePreviewImages()，避免闪烁
}

// Bind all panel inputs
// 注意：backgroundAssetSelect和characterAssetSelect使用change事件，避免频繁触发
document.querySelectorAll('.panel input, .panel select, .panel textarea').forEach(el => {
  if(el.id.startsWith('overlay')) {
    el.addEventListener('input', updateOverlayFromInput);
  } else if(el.id === 'backgroundAssetSelect' || el.id === 'characterAssetSelect') {
    // 这些select已经在上面单独绑定了change事件，这里跳过
  } else {
    el.addEventListener('input', updateFromInputs);
  }
});

function updateOverlayFromInput() {
   if(!state.selectedOverlayId) return;
   const o = state.overlays.find(x => x.id === state.selectedOverlayId);
   if(!o) return;

   // 处理图层类型变化
   const typeSelect = document.getElementById('overlayTypeSelect');
   if(typeSelect && typeSelect.value !== o.type) {
     o.type = typeSelect.value;
     // 切换显示字段
     const textFields = document.getElementById('overlayTextFields');
     const imageFields = document.getElementById('overlayImageFields');
     const fontControls = document.getElementById('overlayFontControls');

     if(o.type === 'image') {
       if(textFields) textFields.style.display = 'none';
       if(imageFields) imageFields.style.display = 'block';
       if(fontControls) fontControls.style.display = 'none';
    } else if(o.type === 'glass') {
      // 毛玻璃层：只显示位置和大小
      if(textFields) textFields.style.display = 'none';
      if(imageFields) imageFields.style.display = 'none';
      if(fontControls) fontControls.style.display = 'none';
    } else {
       if(textFields) textFields.style.display = 'block';
       if(imageFields) imageFields.style.display = 'none';
       if(fontControls) fontControls.style.display = 'flex';
     }
   }

   o.text = inputs.oText.value;
   o.image = inputs.oImage.value;
   o.left = parseFloat(inputs.oLeft.value);
   o.top = parseFloat(inputs.oTop.value);
   o.width = parseFloat(inputs.oWidth.value);
   o.height = parseFloat(inputs.oHeight.value);
   o.z_index = parseFloat(inputs.oZ.value);
   o.opacity = parseFloat(inputs.oOpacity.value);
   o.font_size = parseFloat(inputs.oSize.value);
   o.color = inputs.oColor.value;
   if(inputs.oFont) o.font = inputs.oFont.value;
   if(inputs.oBold !== undefined) o.bold = inputs.oBold.checked;
   if(inputs.oStrokeWidth) o.stroke_width = Math.max(0, parseFloat(inputs.oStrokeWidth.value) || 0);
   if(inputs.oStrokeColor) o.stroke_color = inputs.oStrokeColor.value || '#000000';

   renderCanvas();
   renderLayerList(); // Update Z display
}

// Drag Logic
function startDrag(type, e, id = null) {
  e.preventDefault();
  const rect = stage.getBoundingClientRect();
  const startX = (e.clientX - rect.left) / state.scale;
  const startY = (e.clientY - rect.top) / state.scale;

  let initialParams = {};

  if(type.includes('box')) {
    initialParams = { x: state.layout.box_left, y: state.layout.box_top, w: state.layout.box_width, h: state.layout.box_height };
  } else if (type.includes('overlay')) {
    const o = state.overlays.find(x => x.id === id);
    initialParams = { x: o.left, y: o.top, w: o.width, h: o.height };
  } else if (type === 'move-char') {
     initialParams = { x: state.layout.character_left || 0, bottom: state.layout.character_bottom || 0 };
  } else if (type === 'resize-char') {
     initialParams = { w: state.layout.character_width || 520 };
  }

  state.dragging = { type, id, startX, startY, initialParams };

  window.addEventListener('mousemove', onDrag);
  window.addEventListener('mouseup', stopDrag);
}

function onDrag(e) {
  if(!state.dragging) return;
  const rect = stage.getBoundingClientRect();
  const curX = (e.clientX - rect.left) / state.scale;
  const curY = (e.clientY - rect.top) / state.scale;
  const dx = curX - state.dragging.startX;
  const dy = curY - state.dragging.startY;
  const p = state.dragging.initialParams;
  const l = state.layout;

  switch(state.dragging.type) {
    case 'move-box':
      l.box_left = p.x + dx; l.box_top = p.y + dy;
      break;
    case 'resize-box':
      l.box_width = Math.max(50, p.w + dx); l.box_height = Math.max(50, p.h + dy);
      break;
    case 'move-char': {
      // 允许负值坐标，支持立绘一半在屏幕外
      l.character_left = p.x + dx;
      const newBottom = p.bottom - dy;
      l.character_bottom = newBottom;
      break;
    }
    case 'resize-char': {
      const canvasW = Number(l.canvas_width) || 1280;
      const maxWidth = Math.max(50, canvasW - (Number(l.character_left) || 0));
      l.character_width = Math.min(Math.max(50, p.w + dx), maxWidth);
      const canvasH = Number(l.canvas_height) || 720;
      const { height: newCharHeight } = getCharacterDimensions();
      const maxBottom = Math.max(0, canvasH - newCharHeight);
      l.character_bottom = Math.min(Math.max(0, Number(l.character_bottom) || 0), maxBottom);
      break;
    }
    case 'move-overlay':
      const mo = state.overlays.find(x => x.id === state.dragging.id);
      if(mo) { mo.left = p.x + dx; mo.top = p.y + dy; selectOverlay(mo.id); }
      break;
    case 'resize-overlay':
      const ro = state.overlays.find(x => x.id === state.dragging.id);
      if(ro) { ro.width = Math.max(20, p.w + dx); ro.height = Math.max(20, p.h + dy); selectOverlay(ro.id); }
      break;
  }

  syncInputsToState();
  renderCanvas();
}

function stopDrag() {
  state.dragging = null;
  window.removeEventListener('mousemove', onDrag);
  window.removeEventListener('mouseup', stopDrag);
}

// --- Element Binding ---
textBox.onmousedown = (e) => {
   state.selectedOverlayId = null;
   state.activeLayerId = 'sys_box';
   overlayEditor.style.display = 'none';
   renderLayerList();
   if(e.target.classList.contains('resize-handle')) startDrag('resize-box', e);
   else startDrag('move-box', e);
};
characterHandle.onmousedown = (e) => {
   state.selectedOverlayId = null;
   state.activeLayerId = 'sys_char';
   overlayEditor.style.display = 'none';
   renderLayerList();
   if(e.target.classList.contains('resize-handle')) startDrag('resize-char', e);
   else startDrag('move-char', e);
};

// --- Buttons ---
document.getElementById('addOverlayBtn').onclick = () => {
  const id = 'ov_' + Date.now();
  state.overlays.push({
    id,
    type: 'text',
    text:'新文本',
    left: 100,
    top: 100,
    width: 200,
    height: 60,
    z_index: 300,
    font_size: 24,
    color: '#ffffff',
    stroke_width: 0,
    stroke_color: '#000000'
  });
  renderLayerList();
  selectOverlay(id);
};

document.getElementById('addGlassBtn').onclick = () => {
  const id = 'ov_' + Date.now();
  // 毛玻璃层：默认位置在主文本框位置，作为独立的毛玻璃效果
  const l = state.layout;
  state.overlays.push({
    id,
    type: 'glass',
    text: '',
    left: l.box_left || 520,
    top: l.box_top || 160,
    width: l.box_width || 640,
    height: l.box_height || 340,
    z_index: 195,  // 在主文本框下方
    opacity: 1,
    glass_strength: 12
  });
  renderLayerList();
  selectOverlay(id);
};

document.getElementById('addImageOverlayBtn').onclick = () => {
  const id = 'ov_' + Date.now();
  state.overlays.push({ id, type: 'image', image: state.components[0] || '', left: 150, top: 150, width: 100, height: 100, z_index: 310 });
  renderLayerList();
  selectOverlay(id);
};

document.getElementById('removeOverlayBtn').onclick = () => {
  state.overlays = state.overlays.filter(o => o.id !== state.selectedOverlayId);
  state.selectedOverlayId = null;
  renderLayerList();
  renderOverlays();
  overlayEditor.style.display = 'none';
};

if(addEmotionBtn) {
  addEmotionBtn.onclick = () => addEmotionRecord();
}
if(saveEmotionBtn) {
  saveEmotionBtn.onclick = async () => {
    await syncEmotionSets('/api/emotions/save', { emotions: state.emotions }, '情绪配置已保存');
  };
}
if(resetEmotionBtn) {
  resetEmotionBtn.onclick = async () => {
    const confirmed = window.confirm('确认恢复默认情绪标签配置？');
    if(!confirmed) return;
    await syncEmotionSets('/api/emotions/reset', {}, '已恢复默认情绪配置');
  };
}

if(saveDefaultBtn) {
  saveDefaultBtn.onclick = async () => {
    state.layout.text_overlays = state.overlays;
    if(state.layout.character_role && state.layout.character_role !== '__auto__') {
      state.layout.character_asset = '__auto__';
      if(inputs.charAsset) inputs.charAsset.value = '__auto__';
    }
    setStatus('正在保存默认布局...');
    try {
      const res = await fetch(`/api/config${suffix}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify({ layout: state.layout })
      });
      if(!res.ok) {
        const msg = await res.text();
        throw new Error(msg || '保存失败');
      }
      await res.json();
      setCurrentPreset(null);
      renderPresetOptions();
      setStatus('默认布局已保存');
    } catch(e) {
      setStatus(e.message || '保存失败', true);
    }
  };
}

if(savePresetBtn) {
  savePresetBtn.onclick = async () => {
    const presetName = window.prompt('请输入新的预设名称', state.currentPresetName || '');
    if(presetName === null) {
      setStatus('已取消保存');
      return;
    }
    await savePresetLayout(presetName, undefined);
  };
}

const bindPersonaPresetBtn = document.getElementById('bindPersonaPresetBtn');
if(bindPersonaPresetBtn) {
  bindPersonaPresetBtn.onclick = async () => {
    const personaSelect = document.getElementById('personaSelect');
    const personaPresetSelect = document.getElementById('personaPresetSelect');
    const personaId = personaSelect ? personaSelect.value.trim() : '';
    const presetName = personaPresetSelect ? personaPresetSelect.value.trim() : '';
    if(!personaId) { setStatus('请先选择人格', true); return; }
    if(!presetName) { setStatus('请先选择预设', true); return; }
    setStatus('正在绑定...');
    try {
      const res = await fetch(`/api/persona-bindings/save${suffix}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify({ persona_id: personaId, preset_name: presetName })
      });
      if(!res.ok) {
        const msg = await res.text();
        throw new Error(msg || '绑定失败');
      }
      const data = await res.json();
      state.personaBindings = data.bindings || [];
      renderPersonaBindings();
      setStatus(data.message || '已绑定');
    } catch(e) {
      setStatus(e.message || '绑定失败', true);
    }
  };
}

if(overridePresetBtn) {
  overridePresetBtn.onclick = async () => {
    if(!state.currentPresetSlug) {
      setStatus('请先应用要覆盖的预设', true);
      return;
    }
    await savePresetLayout(state.currentPresetName || state.currentPresetSlug, '当前预设已更新');
  };
}
if(loadPresetBtn) {
  loadPresetBtn.onclick = async () => {
    const slug = presetSelect ? presetSelect.value : '';
    if(!slug) {
      setStatus('请先选择预设', true);
      return;
    }
    try {
      const res = await fetch(`/api/presets/load${suffix}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify({ name: slug })
      });
      if(!res.ok) {
        const msg = await res.text();
        throw new Error(msg || '加载失败');
      }
      const data = await res.json();
      state.layout = data.layout || state.layout;
      if(!state.layout.character_role) state.layout.character_role = '__auto__';
      if(state.layout.character_role !== '__auto__') {
        state.layout.character_asset = '__auto__';
      }
      if(!state.layout.background_asset) state.layout.background_asset = '__auto__';
      if(!state.layout.background_group) state.layout.background_group = '__auto__';
      if(!state.layout.character_fit_mode) state.layout.character_fit_mode = 'fixed_width';
      if(state.layout.character_align_bottom === undefined) state.layout.character_align_bottom = true;
      if(state.layout.character_uniform_height === undefined) state.layout.character_uniform_height = 620;
      if(state.layout.character_top === undefined) state.layout.character_top = 0;
      normalizeLegacyBackgroundAsset();
      state.overlays = normalizeOverlays(state.layout.text_overlays);
      state.presets = data.presets || state.presets;
      setCurrentPreset(data.preset || { name: data?.preset?.name || slug, slug });
      renderPresetOptions();
      renderRoleOptions();
      renderBackgroundGroupOptions();
      syncInputsToState();
      renderLayerList();
      renderCanvas();
      updatePreviewImages();
      setStatus(`已切换到预设：${data?.preset?.name || slug}`);
    } catch(err) {
      setStatus(err.message || '加载预设失败', true);
    }
  };
}

const uploadComponentBtn = document.getElementById('uploadComponentBtn');
const uploadFontBtn = document.getElementById('uploadFontBtn');
const uploadCharacterBtn = document.getElementById('uploadCharacterBtn');

if(uploadComponentBtn) {
  uploadComponentBtn.onclick = () => uploadFile('component', componentUploadInput);
}
if(uploadFontBtn) {
  uploadFontBtn.onclick = () => uploadFile('font', fontUploadInput);
}
if(uploadCharacterBtn) {
  uploadCharacterBtn.onclick = () => {
    const emotion = resolveSelectedEmotionSlug();
    const role = resolveSelectedRoleSlug();
    const extra = {};
    if(emotion) extra.emotion = emotion;
    if(role) extra.role = role;
    uploadFile('character', characterUploadInput, extra);
  };
}

if(characterEmotionSelect) {
  characterEmotionSelect.addEventListener('change', updateEmotionInputState);
}
if(characterRoleUploadSelect) {
  characterRoleUploadSelect.addEventListener('change', updateRoleInputState);
}
if(characterRoleSelect) {
  characterRoleSelect.addEventListener('change', () => {
    const selectedRole = characterRoleSelect.value || '__auto__';
    state.layout.character_role = selectedRole;
    if(selectedRole !== '__auto__') {
      state.layout.character_asset = '__auto__';
      if(inputs.charAsset) inputs.charAsset.value = '__auto__';
    }
    updateFromInputs();
    updatePreviewImages();
  });
}
if(characterFitModeSelect) {
  characterFitModeSelect.addEventListener('change', () => {
    updateFromInputs();
    renderCanvas();
  });
}
if(backgroundGroupSelect) {
  backgroundGroupSelect.addEventListener('change', () => {
    state.layout.background_group = backgroundGroupSelect.value || '__auto__';
    updateFromInputs();
    updatePreviewImages();
  });
}
if(backgroundGroupUploadSelect) {
  backgroundGroupUploadSelect.addEventListener('change', updateBackgroundGroupInputState);
}
if(characterAlignBottomInput) {
  characterAlignBottomInput.addEventListener('change', () => {
    state.layout.character_align_bottom = characterAlignBottomInput.checked;
    updateFromInputs();
    renderCanvas();
  });
}
if(uploadBackgroundBtn) {
  uploadBackgroundBtn.onclick = () => {
    const groupSlug = resolveSelectedBackgroundGroupSlug();
    uploadFile('background', backgroundUploadInput, { background_group: groupSlug });
  };
}

// 预览生成功能
document.getElementById('previewBtn').onclick = async () => {
  setStatus('生成预览中...');
  try {
    const res = await fetch(`/api/preview/generate${suffix}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeader },
      body: JSON.stringify({
        text: '这是一段示例文本，用于预览对话框效果。你可以在这里看到文本的显示效果，包括字体、颜色、大小等设置。',
        emotion: 'happy'
      }),
    });
    if(!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);

    // 创建预览窗口
    const previewWindow = window.open('', '_blank');
    previewWindow.document.write(`
      <html>
        <head><title>预览</title><style>body{margin:0;display:flex;justify-content:center;align-items:center;min-height:100vh;background:#000;}</style></head>
        <body><img src="${url}" style="max-width:100%;max-height:100vh;" /></body>
      </html>
    `);
    setStatus('预览生成成功');
  } catch(err) {
    setStatus('预览生成失败: ' + err.message, true);
  }
};

// 图层类型选择器change事件
const overlayTypeSelect = document.getElementById('overlayTypeSelect');
if(overlayTypeSelect) {
  overlayTypeSelect.addEventListener('change', () => {
    updateOverlayFromInput();
  });
}

// 当character_asset或background_asset改变时更新预览
// 注意：updateFromInputs()已经处理了input事件，这里只处理change事件（下拉选择）
let lastBgAsset = state.layout.background_asset;
let lastCharAsset = state.layout.character_asset;
inputs.charAsset.addEventListener('change', () => {
  const newValue = inputs.charAsset.value;
  if(newValue !== lastCharAsset) {
    lastCharAsset = newValue;
    state.layout.character_asset = newValue;
    updatePreviewImages();
  }
});
inputs.bgAsset.addEventListener('change', () => {
  const newValue = inputs.bgAsset.value;
  if(newValue !== lastBgAsset) {
    lastBgAsset = newValue;
    state.layout.background_asset = newValue;
    updatePreviewImages();
  }
});

async function uploadFile(type, input, extra = {}) {
  if(!input || !input.files || !input.files.length) {
    setStatus('请先选择要上传的文件', true);
    return;
  }
  const files = Array.from(input.files);
  for(let idx = 0; idx < files.length; idx++) {
    const file = files[idx];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('filename', file.name);
    formData.append('kind', type);
    Object.entries(extra || {}).forEach(([key, value]) => {
      if(value !== undefined && value !== null && value !== '') {
        formData.append(key, value);
      }
    });
    setStatus(`正在上传 ${file.name} (${idx + 1}/${files.length})...`);
    try {
      const res = await fetch(`/api/components/upload${suffix}`, {
        method: 'POST',
        headers: { ...authHeader },
        body: formData
      });
      if(!res.ok) {
        const msg = await res.text();
        throw new Error(msg || '上传失败');
      }
      const data = await res.json();
      if(Array.isArray(data.components)) state.components = data.components;
      if(Array.isArray(data.fonts)) state.fonts = data.fonts;
      if(Array.isArray(data.characters)) state.characters = data.characters;
      if(Array.isArray(data.backgrounds)) state.backgrounds = data.backgrounds;
      if(Array.isArray(data.background_groups)) state.background_groups = data.background_groups;
      if(Array.isArray(data.character_roles)) state.roles = data.character_roles;
      populateSelects();
      renderRoleOptions();
      renderBackgroundGroupOptions();
    } catch(err) {
      console.error(err);
      setStatus(`上传失败：${err?.message || err}`, true);
      input.value = '';
      return;
    }
  }
  setStatus('上传完成');
  input.value = '';
  updatePreviewImages();
}

// Init
window.addEventListener('resize', renderCanvas);
init();