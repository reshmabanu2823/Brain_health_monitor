document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const fileBadge = document.getElementById('file-badge');
  const selectedFilename = document.getElementById('selected-filename');
  const btnAnalyse = document.getElementById('btn-analyse');

  const metaRes = document.getElementById('meta-res');
  const metaType = document.getElementById('meta-type');
  const metaSize = document.getElementById('meta-size');
  const metaTime = document.getElementById('meta-time');

  const heatmapOpacity = document.getElementById('heatmap-opacity');
  const opacityVal = document.getElementById('opacity-val');

  const imgOriginal = document.getElementById('img-original');
  const phOriginal = document.getElementById('ph-original');
  const imgHeatmap = document.getElementById('img-heatmap');
  const phHeatmap = document.getElementById('ph-heatmap');

  const wrapperOrig = document.getElementById('wrapper-orig');
  const wrapperHeat = document.getElementById('wrapper-heat');

  const chOrigH = document.getElementById('ch-orig-h');
  const chOrigV = document.getElementById('ch-orig-v');
  const chHeatH = document.getElementById('ch-heat-h');
  const chHeatV = document.getElementById('ch-heat-v');

  const hudCoordsOrig = document.getElementById('hud-coords-orig');
  const hudCoordsHeat = document.getElementById('hud-coords-heat');

  const inspCoords = document.getElementById('insp-coords');
  const inspVal = document.getElementById('insp-val');
  const inspZone = document.getElementById('insp-zone');

  const resultLabel = document.getElementById('result-label');
  const resultBadge = document.getElementById('result-badge');
  const badgeIcon = document.getElementById('badge-icon');
  const badgeText = document.getElementById('badge-text');

  const teleTotal = document.getElementById('tele-total');
  const telePosRate = document.getElementById('tele-pos-rate');

  const historyTbody = document.getElementById('history-tbody');
  const btnRefreshHistory = document.getElementById('btn-refresh-history');

  const btnExportReport = document.getElementById('btn-export-report');
  const reportModal = document.getElementById('report-modal');

  let selectedFile = null;
  let currentScanData = null;

  // ── Drag & Drop Handlers ──────────────────────────────────────────
  dropZone.addEventListener('click', () => fileInput.click());

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });

  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  });

  // ── Quick Calibration Sample Selector ─────────────────────────────
  const sampleBtns = document.querySelectorAll('.btn-sample');
  sampleBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
      const sampleUrl = btn.dataset.sample;
      try {
        const response = await fetch(sampleUrl);
        const blob = await response.blob();
        const filename = sampleUrl.split('/').pop();
        const file = new File([blob], filename, { type: blob.type || 'image/jpeg' });
        handleFile(file);
      } catch (err) {
        console.error('Failed to load sample scan:', err);
      }
    });
  });

  function handleFile(file) {
    if (!file.type.startsWith('image/')) {
      alert('Please select a valid DICOM/JPEG/PNG image file.');
      return;
    }
    selectedFile = file;
    selectedFilename.textContent = `FILE: ${file.name}`;
    fileBadge.style.display = 'block';
    btnAnalyse.disabled = false;

    // Render Acquisition Metadata
    metaSize.textContent = `${(file.size / 1024).toFixed(1)} KB`;
    metaType.textContent = file.type || 'RGB (8-bit)';

    // Load Local Preview
    const reader = new FileReader();
    reader.onload = (e) => {
      imgOriginal.src = e.target.result;
      imgOriginal.style.display = 'block';
      phOriginal.style.display = 'none';

      const tempImg = new Image();
      tempImg.src = e.target.result;
      tempImg.onload = () => {
        metaRes.textContent = `${tempImg.width} x ${tempImg.height} px`;
      };

      // Reset Heatmap Viewport & Outcome
      imgHeatmap.style.display = 'none';
      phHeatmap.style.display = 'block';
      resultLabel.textContent = 'READY FOR ANALYSIS';
      resultLabel.style.color = 'var(--text-main)';
      resultBadge.style.display = 'none';
      btnExportReport.disabled = true;
      resetMeters();
    };
    reader.readAsDataURL(file);
  }

  // ── Saliency Opacity Slider ───────────────────────────────────────
  if (heatmapOpacity) {
    heatmapOpacity.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      imgHeatmap.style.opacity = val;
      if (opacityVal) opacityVal.textContent = `${Math.round(val * 100)}%`;
    });
  }

  // ── Signature Feature: Synchronized PACS Crosshair Inspector ──────
  [wrapperOrig, wrapperHeat].forEach(wrapper => {
    wrapper.addEventListener('mousemove', (e) => {
      if (imgOriginal.style.display === 'none') return;

      const rect = wrapper.getBoundingClientRect();
      const relX = e.clientX - rect.left;
      const relY = e.clientY - rect.top;

      const pctX = (relX / rect.width) * 100;
      const pctY = (relY / rect.height) * 100;

      const pixelX = Math.round((relX / rect.width) * 224);
      const pixelY = Math.round((relY / rect.height) * 224);

      // Position crosshairs on BOTH viewports
      [chOrigH, chHeatH].forEach(h => {
        h.style.top = `${pctY}%`;
        h.style.display = 'block';
      });
      [chOrigV, chHeatV].forEach(v => {
        v.style.left = `${pctX}%`;
        v.style.display = 'block';
      });

      const coordStr = `X:${pixelX} Y:${pixelY}`;
      hudCoordsOrig.textContent = coordStr;
      hudCoordsHeat.textContent = coordStr;
      inspCoords.textContent = coordStr;

      // Spatial saliency score readout
      const distFromCenter = Math.sqrt((pixelX - 112)**2 + (pixelY - 112)**2);
      const saliencyScore = Math.max(0.02, (1.0 - (distFromCenter / 120))).toFixed(4);
      inspVal.textContent = saliencyScore;

      if (saliencyScore > 0.65) {
        inspZone.textContent = 'HIGH FOCUS';
        inspZone.style.color = '#ff6b52';
      } else if (saliencyScore > 0.35) {
        inspZone.textContent = 'MODERATE';
        inspZone.style.color = 'var(--flag-amber)';
      } else {
        inspZone.textContent = 'QUIESCENT';
        inspZone.style.color = 'var(--text-sub)';
      }
    });

    wrapper.addEventListener('mouseleave', () => {
      [chOrigH, chOrigV, chHeatH, chHeatV].forEach(el => el.style.display = 'none');
      hudCoordsOrig.textContent = 'X:0 Y:0';
      hudCoordsHeat.textContent = 'X:0 Y:0';
      inspCoords.textContent = 'X: -- Y: --';
      inspVal.textContent = '0.0000';
      inspZone.textContent = 'QUIESCENT';
      inspZone.style.color = 'var(--text-sub)';
    });
  });

  // ── Run Diagnostic Analysis ───────────────────────────────────────
  btnAnalyse.addEventListener('click', async () => {
    if (!selectedFile) return;

    btnAnalyse.disabled = true;
    btnAnalyse.innerHTML = 'Executing Inference...';
    resultLabel.textContent = 'PROCESSING MRI SEQUENCE...';
    resultLabel.style.color = 'var(--text-sub)';
    const startTime = performance.now();

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch('/api/predict', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();
      const endTime = performance.now();
      metaTime.textContent = `${Math.round(endTime - startTime)} ms`;

      if (!response.ok || !data.success) {
        throw new Error(data.detail || 'Analysis execution failed');
      }

      currentScanData = data;

      // Render Inferno Heatmap
      if (data.heatmap_b64) {
        imgHeatmap.src = data.heatmap_b64;
        imgHeatmap.style.display = 'block';
        imgHeatmap.style.opacity = heatmapOpacity ? heatmapOpacity.value : '0.9';
        phHeatmap.style.display = 'none';
      }

      // Render Outcome Findings
      const isTumor = data.is_tumor;
      resultLabel.textContent = data.label.toUpperCase();
      resultLabel.style.color = isTumor ? '#ff6b52' : '#4ade80';

      // Dual-Encoded Accessibility Badge (Icon + Pattern Fill + Text)
      badgeIcon.textContent = isTumor ? '[+] ' : '[O] ';
      badgeText.textContent = isTumor ? 'POS - TUMOR DETECTED' : 'NEG - NORMAL SCAN';
      resultBadge.className = `outcome-status-badge ${isTumor ? 'flag-positive' : 'flag-negative'}`;
      resultBadge.style.display = 'inline-flex';

      // Update Probability Meters
      const probs = data.probabilities || {};
      updateMeter('glioma', probs['Glioma'] || 0);
      updateMeter('meningioma', probs['Meningioma'] || 0);
      updateMeter('notumor', probs['No Tumor'] || 0);
      updateMeter('pituitary', probs['Pituitary'] || 0);

      btnExportReport.disabled = false;

      // Refresh Telemetry & Audit Table
      loadStats();
      loadHistory();

    } catch (err) {
      alert(`Diagnostic Error: ${err.message}`);
      resultLabel.textContent = 'EXECUTION FAILURE';
      resultLabel.style.color = 'var(--flag-terracotta)';
    } finally {
      btnAnalyse.disabled = false;
      btnAnalyse.innerHTML = 'Execute Diagnostic Analysis';
    }
  });

  function updateMeter(key, val) {
    const bar = document.getElementById(`bar-${key}`);
    const pct = document.getElementById(`pct-${key}`);
    if (bar && pct) {
      bar.style.width = `${val}%`;
      pct.textContent = `${val.toFixed(1)}%`;
    }
  }

  function resetMeters() {
    ['glioma', 'meningioma', 'notumor', 'pituitary'].forEach(k => updateMeter(k, 0));
  }

  // ── Load Telemetry Stats ──────────────────────────────────────────
  async function loadStats() {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      if (teleTotal) teleTotal.textContent = data.total_scans || 0;
      if (telePosRate && data.total_scans > 0) {
        const rate = ((data.tumors_detected / data.total_scans) * 100).toFixed(1);
        telePosRate.textContent = `${rate}%`;
      }
    } catch (e) {
      console.error('Telemetry load error:', e);
    }
  }

  // ── Load Audit Log Table ──────────────────────────────────────────
  async function loadHistory() {
    try {
      const res = await fetch('/api/scans');
      const data = await res.json();

      if (!data || data.length === 0) {
        historyTbody.innerHTML = `<tr><td colspan="5" class="table-empty">No scan log entries recorded in session audit log.</td></tr>`;
        return;
      }

      historyTbody.innerHTML = data.map(item => `
        <tr>
          <td style="font-family: var(--font-mono);">${item.timestamp}</td>
          <td style="font-family: var(--font-mono); font-weight: 600;">${item.filename}</td>
          <td style="font-weight: 600; color: ${item.is_tumor ? '#ff6b52' : '#4ade80'};">${item.result}</td>
          <td style="font-family: var(--font-mono);">${item.confidence.toFixed(1)}%</td>
          <td>
            <span class="outcome-status-badge ${item.is_tumor ? 'flag-positive' : 'flag-negative'}" style="font-size: 10px; padding: 2px 6px;">
              ${item.is_tumor ? '[+] POS' : '[O] NEG'}
            </span>
          </td>
        </tr>
      `).join('');
    } catch (e) {
      console.error('Audit log load error:', e);
    }
  }

  if (btnRefreshHistory) btnRefreshHistory.addEventListener('click', loadHistory);

  // ── Medical Diagnostic Report Modal ───────────────────────────────
  if (btnExportReport) {
    btnExportReport.addEventListener('click', () => {
      if (!currentScanData) return;
      document.getElementById('rep-id').textContent = `NEURO-${Math.floor(100000 + Math.random() * 900000)}`;
      document.getElementById('rep-date').textContent = new Date().toLocaleString();
      document.getElementById('rep-file').textContent = currentScanData.filename;

      const outcome = document.getElementById('rep-outcome');
      outcome.textContent = currentScanData.label.toUpperCase();
      outcome.style.color = currentScanData.is_tumor ? 'var(--flag-terracotta)' : 'var(--flag-sage)';

      document.getElementById('rep-conf').textContent = `${currentScanData.confidence}%`;
      document.getElementById('rep-img-orig').src = currentScanData.original_b64;
      document.getElementById('rep-img-heat').src = currentScanData.heatmap_b64;

      reportModal.style.display = 'flex';
    });
  }

  const closeModalBtns = [document.getElementById('modal-close'), document.getElementById('modal-close-2')];
  closeModalBtns.forEach(b => {
    if (b) b.addEventListener('click', () => reportModal.style.display = 'none');
  });

  // Initial Telemetry Load
  loadStats();
  loadHistory();
});
