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

  // ROI Lesion Quantitative Metrics
  const metricTumorArea = document.getElementById('metric-tumor-area');
  const metricPeakSal = document.getElementById('metric-peak-sal');
  const metricBbox = document.getElementById('metric-bbox');
  const metricCenter = document.getElementById('metric-center');

  // Viewport adjustments
  const heatmapOpacity = document.getElementById('heatmap-opacity');
  const opacityVal = document.getElementById('opacity-val');
  const imgContrast = document.getElementById('img-contrast');
  const contrastVal = document.getElementById('contrast-val');
  const imgBrightness = document.getElementById('img-brightness');
  const brightnessVal = document.getElementById('brightness-val');

  const btnZoomIn = document.getElementById('btn-zoom-in');
  const btnZoomOut = document.getElementById('btn-zoom-out');
  const btnZoomReset = document.getElementById('btn-zoom-reset');

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
  const btnClearHistory = document.getElementById('btn-clear-history');

  const btnExportReport = document.getElementById('btn-export-report');
  const reportModal = document.getElementById('report-modal');
  const btnDownloadPdf = document.getElementById('btn-download-pdf');

  let selectedFile = null;
  let currentScanData = null;
  let currentZoom = 1.0;

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

  function isDicomFile(file) {
    const name = file.name.toLowerCase();
    return name.endsWith('.dcm') || name.endsWith('.dicom') || file.type === 'application/dicom';
  }

  function handleFile(file) {
    const isDcm = isDicomFile(file);
    if (!file.type.startsWith('image/') && !isDcm) {
      alert('Please select a valid DICOM (.dcm) or JPEG/PNG/WebP image file.');
      return;
    }

    selectedFile = file;
    selectedFilename.textContent = `FILE: ${file.name}`;
    fileBadge.style.display = 'flex';
    btnAnalyse.disabled = false;

    // Reveal MRI Viewer & Inference Activation Map workspace
    const workspaceGrid = document.querySelector('.workspace-grid');
    if (workspaceGrid) workspaceGrid.classList.add('has-scan');
    const dashboardContainer = document.querySelector('.dashboard-container');
    if (dashboardContainer) dashboardContainer.classList.add('has-scan');

    const viewportsCard = document.querySelector('.viewports-card');
    if (viewportsCard) viewportsCard.style.display = 'flex';
    const detailsGrid = document.querySelector('.details-grid');
    if (detailsGrid) detailsGrid.style.display = 'grid';
    const crosshairCard = document.querySelector('.crosshair-wide-card');
    if (crosshairCard) crosshairCard.style.display = 'block';

    // Render Acquisition Metadata
    metaSize.textContent = `${(file.size / 1024).toFixed(1)} KB`;
    metaType.textContent = isDcm ? 'DICOM (Medical Pixel Stream)' : (file.type || 'RGB (8-bit)');

    // Reset Zoom and Filters
    resetViewportFilters();

    if (isDcm) {
      // For DICOM files, show an indicator preview until server renders the windowed RGB
      phOriginal.textContent = `DICOM file loaded (${file.name}). Run model analysis to decode image.`;
      phOriginal.style.display = 'block';
      imgOriginal.style.display = 'none';
      metaRes.textContent = 'DICOM Matrix';
    } else {
      // Standard image preview
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
      };
      reader.readAsDataURL(file);
    }

    // Reset Heatmap Viewport & Outcome
    imgHeatmap.style.display = 'none';
    phHeatmap.style.display = 'block';
    resultLabel.textContent = 'READY FOR ANALYSIS';
    resultLabel.style.color = 'var(--text-main)';
    resultBadge.style.display = 'none';
    btnExportReport.disabled = true;
    resetMeters();
    resetRoiMetrics();
  }

  // ── Viewport Filters (Contrast & Brightness & Opacity & Zoom) ─────
  function applyImageFilters() {
    const contrast = imgContrast ? imgContrast.value : 100;
    const brightness = imgBrightness ? imgBrightness.value : 100;
    const filterStr = `contrast(${contrast}%) brightness(${brightness}%)`;
    if (imgOriginal) imgOriginal.style.filter = filterStr;
    if (imgHeatmap) imgHeatmap.style.filter = filterStr;
  }

  function applyZoom() {
    const scaleStr = `scale(${currentZoom})`;
    if (imgOriginal) imgOriginal.style.transform = scaleStr;
    if (imgHeatmap) imgHeatmap.style.transform = scaleStr;
  }

  function resetViewportFilters() {
    currentZoom = 1.0;
    applyZoom();
    if (imgContrast) { imgContrast.value = 100; contrastVal.textContent = '100%'; }
    if (imgBrightness) { imgBrightness.value = 100; brightnessVal.textContent = '100%'; }
    applyImageFilters();
  }

  if (heatmapOpacity) {
    heatmapOpacity.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      imgHeatmap.style.opacity = val;
      if (opacityVal) opacityVal.textContent = `${Math.round(val * 100)}%`;
    });
  }

  if (imgContrast) {
    imgContrast.addEventListener('input', (e) => {
      contrastVal.textContent = `${e.target.value}%`;
      applyImageFilters();
    });
  }

  if (imgBrightness) {
    imgBrightness.addEventListener('input', (e) => {
      brightnessVal.textContent = `${e.target.value}%`;
      applyImageFilters();
    });
  }

  if (btnZoomIn) {
    btnZoomIn.addEventListener('click', () => {
      currentZoom = Math.min(3.0, currentZoom + 0.25);
      applyZoom();
    });
  }

  if (btnZoomOut) {
    btnZoomOut.addEventListener('click', () => {
      currentZoom = Math.max(0.5, currentZoom - 0.25);
      applyZoom();
    });
  }

  if (btnZoomReset) {
    btnZoomReset.addEventListener('click', () => {
      currentZoom = 1.0;
      applyZoom();
    });
  }


  // ── View Mode Tabs (Dual Sync, MRI Only, Grad-CAM) ────────────────
  const viewTabs = document.querySelectorAll('#pacs-view-tabs .view-tab');
  const canvasViewport = document.getElementById('canvas-viewport');
  const frameOrig = document.getElementById('frame-orig');
  const frameHeat = document.getElementById('frame-heat');
  if (viewTabs && canvasViewport && frameOrig && frameHeat) {
    viewTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        viewTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const viewMode = tab.dataset.view;
        if (viewMode === 'mri') {
          canvasViewport.style.gridTemplateColumns = '1fr';
          frameOrig.style.display = 'flex';
          frameHeat.style.display = 'none';
        } else if (viewMode === 'heat') {
          canvasViewport.style.gridTemplateColumns = '1fr';
          frameOrig.style.display = 'none';
          frameHeat.style.display = 'flex';
        } else {
          canvasViewport.style.gridTemplateColumns = '1fr 1fr';
          frameOrig.style.display = 'flex';
          frameHeat.style.display = 'flex';
        }
      });
    });
  }

  // ── Synchronized PACS Crosshair Inspector ─────────────────────────
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
        inspZone.style.color = 'var(--cortia-red)';
      } else if (saliencyScore > 0.35) {
        inspZone.textContent = 'MODERATE';
        inspZone.style.color = 'var(--status-amber)';
      } else {
        inspZone.textContent = 'QUIESCENT';
        inspZone.style.color = 'var(--warm-mid)';
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
      const aiBtn = document.getElementById('ask-cortia-ai-btn');
      if (aiBtn && data.scan_id) {
        aiBtn.href = `/ai?analysis_type=mri&analysis_id=${data.scan_id}`;
      }
      if (window.renderPatientMRICompanion && data.patient_companion) {
        window.renderPatientMRICompanion(data.patient_companion);
      }

      // Render Original Scan (especially useful if file was DICOM)
      if (data.original_b64) {
        imgOriginal.src = data.original_b64;
        imgOriginal.style.display = 'block';
        phOriginal.style.display = 'none';
      }

      // Render Inferno Heatmap
      if (data.heatmap_b64) {
        imgHeatmap.src = data.heatmap_b64;
        imgHeatmap.style.display = 'block';
        imgHeatmap.style.opacity = heatmapOpacity ? heatmapOpacity.value : '0.9';
        phHeatmap.style.display = 'none';
      } else {
        imgHeatmap.removeAttribute('src');
        imgHeatmap.style.display = 'none';
        phHeatmap.style.display = '';
        phHeatmap.textContent = (data.explanation && data.explanation.reason) || 'Explanation unavailable for this scan';
      }

      // Render Outcome Findings
      const isTumor = data.is_tumor;
      resultLabel.textContent = data.label.toUpperCase();
      resultLabel.style.color = isTumor ? '#ff6b52' : '#4ade80';

      // Dual-Encoded Accessibility Badge (Icon + Pattern Fill + Text)
      badgeIcon.textContent = isTumor ? '[+] ' : '[O] ';
      badgeText.textContent = isTumor ? 'MODEL: TUMOR CLASS' : 'MODEL: NO TUMOR CLASS';
      resultBadge.className = `outcome-status-badge ${isTumor ? 'flag-positive' : 'flag-negative'}`;
      resultBadge.style.display = 'inline-flex';

      // Update Probability Meters
      const probs = data.probabilities || {};
      updateMeter('glioma', probs['Glioma'] || 0);
      updateMeter('meningioma', probs['Meningioma'] || 0);
      updateMeter('notumor', probs['No Tumor'] || 0);
      updateMeter('pituitary', probs['Pituitary'] || 0);

      // Update Quantitative ROI Lesion Metrics
      const metrics = data.tumor_metrics || {};
      if (metricTumorArea) metricTumorArea.textContent = isTumor ? `${metrics.tumor_area_pct || 0}%` : '0.0% (No Mass)';
      if (metricPeakSal) metricPeakSal.textContent = `${metrics.peak_saliency || 0.0}`;
      if (metricBbox) {
        const b = metrics.bbox;
        metricBbox.textContent = b ? `X:${b.x} Y:${b.y} (${b.w}x${b.h})` : (isTumor ? 'Diffuse ROI' : 'None');
      }
      if (metricCenter) {
        const c = metrics.center;
        metricCenter.textContent = c ? `X:${c.x} Y:${c.y}` : 'N/A';
      }

      btnExportReport.disabled = false;

      // Refresh Telemetry & Audit Table
      loadStats();
      loadHistory();

    } catch (err) {
      alert(`Analysis error: ${err.message}`);
      resultLabel.textContent = 'EXECUTION FAILURE';
      resultLabel.style.color = 'var(--flag-terracotta)';
    } finally {
      btnAnalyse.disabled = false;
      btnAnalyse.innerHTML = 'Run Model Analysis';
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

  function resetRoiMetrics() {
    if (metricTumorArea) metricTumorArea.textContent = '--';
    if (metricPeakSal) metricPeakSal.textContent = '--';
    if (metricBbox) metricBbox.textContent = '--';
    if (metricCenter) metricCenter.textContent = '--';
  }

  // ── Load Telemetry Stats ──────────────────────────────────────────
  async function loadStats() {
    try {
      const res = await fetch('/api/stats');
      if (!res.ok) throw new Error('Statistics unavailable');
      const data = await res.json();
      const teleAcc = document.getElementById('tele-accuracy');
      if (teleAcc) teleAcc.textContent = data.model_accuracy || 'Not evaluated';
      if (teleTotal) teleTotal.textContent = data.total_scans || 0;
      if (telePosRate) telePosRate.textContent = '—';
      if (telePosRate && data.total_scans > 0) {
        const rate = ((data.tumors_detected / data.total_scans) * 100).toFixed(1);
        telePosRate.textContent = `${rate}%`;
      }
    } catch (e) {
      if (teleTotal) teleTotal.textContent = 'Unavailable';
      if (telePosRate) telePosRate.textContent = '—';
      const teleAccErr = document.getElementById('tele-accuracy');
      if (teleAccErr) teleAccErr.textContent = 'Unavailable';
      console.error('Telemetry load error:', e);
    }
  }

  const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  // ── Load Audit Log Table ──────────────────────────────────────────
  async function loadHistory() {
    if (!historyTbody) return;
    try {
      const res = await fetch('/api/scans');
      const data = await res.json();

      if (!data || data.length === 0) {
        historyTbody.innerHTML = `<tr><td colspan="5" class="table-empty">No scan log entries recorded in session audit log.</td></tr>`;
        return;
      }

      historyTbody.innerHTML = data.map(item => {
        const findingLower = (item.result || '').toLowerCase();
        const findingClass = findingLower.includes('glioma') ? 'finding-glioma' :
                             findingLower.includes('pituitary') ? 'finding-pituitary' :
                             (findingLower.includes('notumor') || findingLower.includes('no tumor') || findingLower.includes('normal')) ? 'finding-normal' :
                             'finding-glioma';
        const badgeClass = item.is_tumor ? 'flag-pos' : 'flag-neg';
        const badgeText = item.is_tumor ? '[+] POS' : '[O] NEG';
        return `
        <tr>
          <td class="ts">${escapeHtml(item.timestamp)}</td>
          <td class="filename">${escapeHtml(item.filename)}</td>
          <td class="${findingClass}">${escapeHtml(item.result)}</td>
          <td class="ts">${item.confidence.toFixed(1)}%</td>
          <td>
            <span class="${badgeClass}">${badgeText}</span>
          </td>
        </tr>
        `;
      }).join('');
    } catch (e) {
      console.error('Audit log load error:', e);
    }
  }

  if (btnRefreshHistory) btnRefreshHistory.addEventListener('click', loadHistory);

  if (btnClearHistory) {
    btnClearHistory.addEventListener('click', async () => {
      if (!confirm('Are you sure you want to clear the scan audit log?')) return;
      try {
        const response = await fetch('/api/scans/clear', { method: 'POST' });
        if (!response.ok) throw new Error('History could not be cleared');
        loadHistory();
        loadStats();
      } catch (err) {
        console.error('Failed to clear log:', err);
      }
    });
  }

  // ── Research report modal and PDF download ──────
  if (btnExportReport) {
    btnExportReport.addEventListener('click', () => {
      if (!currentScanData) return;
      document.getElementById('rep-id').textContent = currentScanData.patient_id || 'ANON';
      document.getElementById('rep-date').textContent = new Date().toLocaleString();
      document.getElementById('rep-file').textContent = currentScanData.filename;

      const outcome = document.getElementById('rep-outcome');
      outcome.textContent = currentScanData.label.toUpperCase();
      outcome.style.color = currentScanData.is_tumor ? 'var(--flag-terracotta)' : 'var(--flag-sage)';

      document.getElementById('rep-conf').textContent = `${currentScanData.confidence}%`;
      document.getElementById('rep-img-orig').src = currentScanData.original_b64;
      const repHeat = document.getElementById('rep-img-heat');
      if (currentScanData.heatmap_b64) {
        repHeat.src = currentScanData.heatmap_b64;
        repHeat.style.display = '';
      } else {
        repHeat.removeAttribute('src');
        repHeat.style.display = 'none';
      }

      reportModal.style.display = 'flex';
    });
  }

  if (btnDownloadPdf) {
    btnDownloadPdf.addEventListener('click', async () => {
      if (!currentScanData) return;
      btnDownloadPdf.disabled = true;
      btnDownloadPdf.innerHTML = 'Generating PDF...';

      try {
        const payload = {
          patient_id: currentScanData.patient_id || 'ANON',
          patient_name: currentScanData.patient_name || 'Anonymous / De-identified',
          filename: currentScanData.filename,
          label: currentScanData.label,
          confidence: currentScanData.confidence,
          probabilities: currentScanData.probabilities,
          tumor_metrics: currentScanData.tumor_metrics || {},
          original_b64: currentScanData.original_b64,
          heatmap_b64: currentScanData.heatmap_b64,
          notes: 'Automated diagnostic report generated via Brain Health Monitor PACS Workstation.'
        };

        const res = await fetch('/api/report/pdf', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error('PDF generation failed on server');

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `BHM_Radiology_Report_${currentScanData.filename.replace(/\.[^/.]+$/, '')}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
      } catch (err) {
        alert(`Failed to download PDF report: ${err.message}`);
      } finally {
        btnDownloadPdf.disabled = false;
        btnDownloadPdf.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          Download Research PDF Report
        `;
      }
    });
  }

  const closeModalBtns = [document.getElementById('modal-close'), document.getElementById('modal-close-2')];
  closeModalBtns.forEach(b => {
    if (b) b.addEventListener('click', () => reportModal.style.display = 'none');
  });



  // ── Clear / Reset Uploaded Scan ───────────────────────────────────
  const btnClearScan = document.getElementById('btn-clear-scan');
  if (btnClearScan) {
    btnClearScan.addEventListener('click', (e) => {
      e.stopPropagation();
      clearSelectedScan();
    });
  }

  function clearSelectedScan() {
    selectedFile = null;
    if (fileInput) fileInput.value = '';
    if (selectedFilename) selectedFilename.textContent = 'FILE: -';
    if (fileBadge) fileBadge.style.display = 'none';
    if (btnAnalyse) {
      btnAnalyse.disabled = true;
      btnAnalyse.innerHTML = 'Run Model Analysis';
    }
    if (btnExportReport) btnExportReport.disabled = true;
    if (imgOriginal) {
      imgOriginal.removeAttribute('src');
      imgOriginal.style.display = 'none';
    }
    if (imgHeatmap) {
      imgHeatmap.removeAttribute('src');
      imgHeatmap.style.display = 'none';
    }
    if (phOriginal) phOriginal.style.display = 'block';
    if (phHeatmap) phHeatmap.style.display = 'block';
    if (resultLabel) {
      resultLabel.textContent = 'AWAITING ANALYSIS';
      resultLabel.style.color = 'var(--text-sub)';
    }
    if (resultBadge) resultBadge.style.display = 'none';

    const workspaceGrid = document.querySelector('.workspace-grid');
    if (workspaceGrid) workspaceGrid.classList.remove('has-scan');
    const dashboardContainer = document.querySelector('.dashboard-container');
    if (dashboardContainer) dashboardContainer.classList.remove('has-scan');

    const viewportsCard = document.querySelector('.viewports-card');
    if (viewportsCard) viewportsCard.style.display = 'none';
    const detailsGrid = document.querySelector('.details-grid');
    if (detailsGrid) detailsGrid.style.display = 'none';
    const crosshairCard = document.querySelector('.crosshair-wide-card');
    if (crosshairCard) crosshairCard.style.display = 'none';

    resetMeters();
    resetRoiMetrics();
  }

  // Initial Telemetry Load
  loadStats();
  loadHistory();
});

fetch('/api/health').then(r => r.json()).then(data => {document.getElementById('engine-status').textContent = data.model_loaded ? 'MRI ENGINE LOADED' : 'MRI ENGINE UNAVAILABLE';}).catch(() => {document.getElementById('engine-status').textContent = 'BACKEND UNAVAILABLE';});
