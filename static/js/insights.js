/**
 * CORTIA Insights — Explainable AI Centre Client Controller
 */

let currentMRIScan = null;
let currentEEGSession = null;
let currentViewMode = 'side-by-side';
let currentOpacity = 0.65;

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initViewModeControls();
  initURLParams();
  loadOverview();
  loadHistory();

  document.getElementById('mri-load-latest-btn')?.addEventListener('click', loadLatestMRI);
  document.getElementById('eeg-load-latest-btn')?.addEventListener('click', loadLatestEEG);
  document.getElementById('history-refresh-btn')?.addEventListener('click', () => {
    const filter = document.getElementById('history-filter-select').value;
    loadHistory(filter);
  });
  document.getElementById('history-filter-select')?.addEventListener('change', (e) => {
    loadHistory(e.target.value);
  });

  document.getElementById('mri-ask-ai-btn')?.addEventListener('click', () => {
    if (currentMRIScan && currentMRIScan.scan_id) {
      window.location.href = `/ai?analysis_type=mri&analysis_id=${currentMRIScan.scan_id}`;
    } else {
      window.location.href = '/ai';
    }
  });

  document.getElementById('eeg-ask-ai-btn')?.addEventListener('click', () => {
    if (currentEEGSession && currentEEGSession.session_id) {
      window.location.href = `/ai?analysis_type=eeg&analysis_id=${currentEEGSession.session_id}`;
    } else {
      window.location.href = '/ai';
    }
  });
});

function initTabs() {
  const tabs = document.querySelectorAll('.insights-tab-btn');
  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      tabs.forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      const targetPane = document.getElementById(btn.dataset.tab);
      if (targetPane) {
        targetPane.classList.add('active');
      }

      if (btn.dataset.tab === 'tab-mri' && !currentMRIScan) {
        loadLatestMRI();
      }
      if (btn.dataset.tab === 'tab-eeg' && !currentEEGSession) {
        loadLatestEEG();
      }
    });
  });
}

function initURLParams() {
  const params = new URLSearchParams(window.location.search);
  const type = params.get('type');
  const id = params.get('id');

  if (type === 'mri') {
    document.querySelector('[data-tab=tab-mri]')?.click();
    if (id) {
      loadMRIScan(id);
    } else {
      loadLatestMRI();
    }
  } else if (type === 'eeg') {
    document.querySelector('[data-tab=tab-eeg]')?.click();
    if (id) {
      loadEEGSession(id);
    } else {
      loadLatestEEG();
    }
  }
}

function initViewModeControls() {
  const modeBtns = document.querySelectorAll('.mode-btn');
  const opacityControl = document.getElementById('opacity-control-wrap');
  const opacitySlider = document.getElementById('mri-opacity-slider');
  const opacityLabel = document.getElementById('opacity-val-label');

  modeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      modeBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentViewMode = btn.dataset.mode;
      if (opacityControl) {
        opacityControl.style.display = (currentViewMode === 'overlay') ? 'flex' : 'none';
      }
      renderMRICanvas();
    });
  });

  if (opacitySlider && opacityLabel) {
    opacitySlider.addEventListener('input', (e) => {
      currentOpacity = parseInt(e.target.value, 10) / 100;
      opacityLabel.textContent = `${e.target.value}%`;
      const heatmap = document.querySelector('.overlay-heatmap');
      if (heatmap) {
        heatmap.style.opacity = currentOpacity;
      }
    });
  }
}

async function loadOverview() {
  try {
    const res = await fetch('/api/insights/overview');
    if (!res.ok) return;
    const data = await res.json();

    if (data.mri_status && data.mri_status.test_accuracy) {
      const acc = Math.round(data.mri_status.test_accuracy * 1000) / 10;
      document.getElementById('ov-mri-acc').textContent = `${acc}%`;
    }

    const tbody = document.getElementById('ov-recent-body');
    if (tbody && data.recent_activity && data.recent_activity.length > 0) {
      tbody.innerHTML = '';
      data.recent_activity.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${formatTimestamp(item.timestamp)}</td>
          <td><span class="badge ${item.type === 'mri' ? 'badge-info' : 'badge-neutral'}">${item.type.toUpperCase()}</span></td>
          <td><strong>${item.title}</strong></td>
          <td>${item.status}</td>
          <td>${item.primary_metric}</td>
          <td>
            <button class="btn-pacs-secondary" style="padding:4px 8px;font-size:0.75rem;" onclick="inspectItem('${item.type}', '${item.id}')">Inspect</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    } else if (tbody) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:16px;color:var(--md-text-secondary);">No recent activity logged yet.</td></tr>`;
    }
  } catch (err) {
    console.error('Failed to load overview:', err);
  }
}

async function loadLatestMRI() {
  const stage = document.getElementById('mri-canvas-stage');
  if (stage) stage.innerHTML = `<div style="color:#DADCE0;">Loading latest MRI scan...</div>`;
  try {
    const res = await fetch('/api/insights/mri/latest');
    if (!res.ok) {
      stage.innerHTML = `<div style="color:#DADCE0;text-align:center;padding:24px;">No scan found in audit log.<br><a href="/" class="btn-pacs-primary" style="margin-top:12px;display:inline-block;">Analyze Scan in Workspace</a></div>`;
      return;
    }
    const data = await res.json();
    currentMRIScan = data;
    renderMRIScanDetails(data);
  } catch (err) {
    console.error('Failed to load latest MRI:', err);
  }
}

async function loadMRIScan(scanId) {
  try {
    const res = await fetch(`/api/insights/mri/${scanId}`);
    if (!res.ok) return;
    const data = await res.json();
    currentMRIScan = data;
    renderMRIScanDetails(data);
  } catch (err) {
    console.error(`Failed to load MRI scan ${scanId}:`, err);
  }
}

function renderMRIScanDetails(scan) {
  document.getElementById('mri-scan-badge').textContent = `Scan #${scan.scan_id}`;
  document.getElementById('mri-pred-label').textContent = scan.predicted_label;
  document.getElementById('mri-pred-conf').textContent = `${scan.confidence.toFixed(1)}%`;
  document.getElementById('mri-area-pct').textContent = `${scan.metrics.tumor_area_pct.toFixed(1)}%`;
  document.getElementById('mri-peak-sal').textContent = scan.metrics.peak_saliency.toFixed(4);

  // Probabilities
  const probsBox = document.getElementById('mri-probs-container');
  if (probsBox && scan.probabilities) {
    probsBox.innerHTML = '';
    Object.entries(scan.probabilities).forEach(([cls, pct]) => {
      const isTop = (cls === scan.predicted_label || cls.toLowerCase().includes(scan.predicted_label.toLowerCase()));
      const row = document.createElement('div');
      row.style.display = 'flex';
      row.style.alignItems = 'center';
      row.style.justifyContent = 'space-between';
      row.style.fontSize = '0.8125rem';
      row.innerHTML = `
        <span style="${isTop ? 'font-weight:600;color:var(--md-text-primary);' : 'color:var(--md-text-secondary);'}">${cls}:</span>
        <div style="display:flex;align-items:center;gap:8px;width:55%;">
          <div style="flex:1;background:#E8EAED;height:6px;border-radius:3px;overflow:hidden;">
            <div style="width:${pct}%;background:${isTop ? 'var(--md-blue-primary)' : '#9AA0A6'};height:100%;"></div>
          </div>
          <span style="font-family:monospace;width:40px;text-align:right;">${pct.toFixed(1)}%</span>
        </div>
      `;
      probsBox.appendChild(row);
    });
  }

  renderMRICanvas();
}

function renderMRICanvas() {
  const stage = document.getElementById('mri-canvas-stage');
  if (!stage || !currentMRIScan) return;

  // Placeholder images if base64 not directly returned in audit row
  const imgUrl = currentMRIScan.original_b64 || `/static/samples/glioma.jpg`;
  const heatmapUrl = currentMRIScan.heatmap_b64 || `/static/samples/glioma.jpg`;

  if (currentViewMode === 'side-by-side') {
    stage.innerHTML = `
      <div class="side-by-side-wrap">
        <div class="compare-viewport">
          <span class="viewport-label">Original MRI Scan</span>
          <img src="${imgUrl}" alt="Original MRI" class="compare-img">
        </div>
        <div class="compare-viewport">
          <span class="viewport-label">Grad-CAM Saliency Overlay</span>
          <img src="${heatmapUrl}" alt="Grad-CAM" class="compare-img" style="filter:contrast(1.1);">
        </div>
      </div>
    `;
  } else if (currentViewMode === 'overlay') {
    stage.innerHTML = `
      <div class="overlay-stage">
        <img src="${imgUrl}" alt="Original MRI" class="overlay-img">
        <img src="${heatmapUrl}" alt="Grad-CAM Heatmap" class="overlay-heatmap" style="opacity:${currentOpacity};filter:hue-rotate(30deg) saturate(1.8);">
      </div>
    `;
  } else if (currentViewMode === 'original') {
    stage.innerHTML = `
      <div class="compare-viewport" style="padding:16px;">
        <span class="viewport-label">Original MRI Scan (Unprocessed Input)</span>
        <img src="${imgUrl}" alt="Original MRI" class="compare-img" style="max-height:400px;">
      </div>
    `;
  } else if (currentViewMode === 'heatmap') {
    stage.innerHTML = `
      <div class="compare-viewport" style="padding:16px;">
        <span class="viewport-label">Grad-CAM Convolutional Saliency Map</span>
        <img src="${heatmapUrl}" alt="Grad-CAM Map" class="compare-img" style="max-height:400px;">
      </div>
    `;
  }
}

async function loadLatestEEG() {
  const tbody = document.getElementById('eeg-features-body');
  if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;">Loading latest EEG session...</td></tr>`;
  try {
    const res = await fetch('/api/insights/eeg/latest');
    if (!res.ok) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--md-text-secondary);">No EEG session found.<br><a href="/eeg" class="btn-pacs-primary" style="margin-top:12px;display:inline-block;">Record in EEG Workspace</a></td></tr>`;
      return;
    }
    const data = await res.json();
    currentEEGSession = data;
    renderEEGSessionDetails(data);
  } catch (err) {
    console.error('Failed to load latest EEG session:', err);
  }
}

async function loadEEGSession(sessionId) {
  try {
    const res = await fetch(`/api/insights/eeg/${sessionId}`);
    if (!res.ok) return;
    const data = await res.json();
    currentEEGSession = data;
    renderEEGSessionDetails(data);
  } catch (err) {
    console.error(`Failed to load EEG session ${sessionId}:`, err);
  }
}

function renderEEGSessionDetails(sess) {
  document.getElementById('eeg-session-badge').textContent = `Session: ${sess.session_id.substring(0, 8)}...`;
  const srcBadge = document.getElementById('eeg-source-badge');
  srcBadge.textContent = `Source: ${sess.source.toUpperCase()}`;
  if (sess.source === 'simulated') {
    srcBadge.style.background = '#FEF7E0';
    srcBadge.style.color = '#B06000';
  } else {
    srcBadge.style.background = '#E6F4EA';
    srcBadge.style.color = '#137333';
  }

  const qBadge = document.getElementById('eeg-quality-badge');
  const qState = sess.quality_summary ? sess.quality_summary.quality_state : 'Unknown';
  qBadge.textContent = `Quality: ${qState}`;
  if (qState === 'Acceptable') {
    qBadge.className = 'badge badge-success';
  } else if (qState === 'Needs review') {
    qBadge.className = 'badge badge-warning';
  } else {
    qBadge.className = 'badge badge-danger';
  }

  // Quality issues banner
  const banner = document.getElementById('eeg-reasons-banner');
  const list = document.getElementById('eeg-reasons-list');
  const issues = sess.quality_summary ? sess.quality_summary.observed_issues : [];
  if (issues && issues.length > 0) {
    banner.style.display = 'block';
    list.innerHTML = '';
    issues.forEach(iss => {
      const chip = document.createElement('span');
      chip.className = 'badge badge-warning';
      chip.textContent = iss;
      list.appendChild(chip);
    });
  } else {
    banner.style.display = 'none';
  }

  // Features Table
  const tbody = document.getElementById('eeg-features-body');
  if (tbody) {
    tbody.innerHTML = '';
    const feats = sess.feature_summary || {};
    if (Object.keys(feats).length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--md-text-secondary);">No valid windows extracted for feature calculation (Quality marked Insufficient).</td></tr>`;
      return;
    }

    Object.entries(feats).forEach(([name, data]) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${formatFeatureName(name)}</strong></td>
        <td>${data.band_definition || '—'}</td>
        <td style="font-family:monospace;font-weight:600;color:var(--md-blue-primary);">${data.mean.toFixed(4)}</td>
        <td style="font-family:monospace;">${data.min.toFixed(3)} / ${data.max.toFixed(3)}</td>
        <td style="font-family:monospace;">&plusmn;${data.std.toFixed(4)}</td>
        <td><span class="feature-unit-chip">${data.unit || 'unit'}</span></td>
      `;
      tbody.appendChild(tr);
    });
  }
}

async function loadHistory(filter = 'all') {
  const tbody = document.getElementById('history-table-body');
  if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;">Loading records...</td></tr>`;
  try {
    const res = await fetch(`/api/insights/history?limit=40&type=${filter}`);
    if (!res.ok) return;
    const history = await res.json();
    if (tbody) {
      tbody.innerHTML = '';
      if (history.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--md-text-secondary);">No historical records found for filter '${filter}'.</td></tr>`;
        return;
      }
      history.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${formatTimestamp(item.timestamp)}</td>
          <td><span class="badge ${item.type === 'mri' ? 'badge-info' : 'badge-neutral'}">${item.type.toUpperCase()}</span></td>
          <td><strong>${item.title}</strong></td>
          <td>${item.source}</td>
          <td>${item.primary_metric}</td>
          <td>
            <div style="display:flex;gap:6px;">
              <button class="btn-pacs-secondary" style="padding:4px 8px;font-size:0.75rem;" onclick="inspectItem('${item.type}', '${item.id}')">Inspect</button>
              <button class="btn-pacs-primary" style="padding:4px 8px;font-size:0.75rem;" onclick="askAIAboutItem('${item.type}', '${item.id}')">Ask AI</button>
            </div>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {
    console.error('Failed to load history:', err);
  }
}

function inspectItem(type, id) {
  if (type === 'mri') {
    document.querySelector('[data-tab=tab-mri]').click();
    loadMRIScan(id);
  } else if (type === 'eeg') {
    document.querySelector('[data-tab=tab-eeg]').click();
    loadEEGSession(id);
  }
}

function askAIAboutItem(type, id) {
  window.location.href = `/ai?analysis_type=${type}&analysis_id=${id}`;
}

function formatTimestamp(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  } catch {
    return isoStr;
  }
}

function formatFeatureName(key) {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, l => l.toUpperCase());
}
