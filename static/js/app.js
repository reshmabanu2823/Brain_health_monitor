document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const filePreviewInfo = document.getElementById('file-preview-info');
  const selectedFilename = document.getElementById('selected-filename');
  const btnAnalyse = document.getElementById('btn-analyse');

  const imgOriginal = document.getElementById('img-original');
  const phOriginal = document.getElementById('ph-original');
  const imgHeatmap = document.getElementById('img-heatmap');
  const phHeatmap = document.getElementById('ph-heatmap');

  const resultLabel = document.getElementById('result-label');
  const resultBadge = document.getElementById('result-badge');

  const statTotal = document.getElementById('stat-total');
  const statTumors = document.getElementById('stat-tumors');
  const statNormal = document.getElementById('stat-normal');

  const historyTbody = document.getElementById('history-tbody');
  const btnRefreshHistory = document.getElementById('btn-refresh-history');

  let selectedFile = null;

  // ── Drag and Drop Events ──────────────────────────────────────────
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

  function handleFile(file) {
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file (.jpg, .png)');
      return;
    }
    selectedFile = file;
    selectedFilename.textContent = file.name;
    filePreviewInfo.style.display = 'block';
    btnAnalyse.disabled = false;

    // Local Preview
    const reader = new FileReader();
    reader.onload = (e) => {
      imgOriginal.src = e.target.result;
      imgOriginal.style.display = 'block';
      phOriginal.style.display = 'none';

      // Reset heatmap & result
      imgHeatmap.style.display = 'none';
      phHeatmap.style.display = 'block';
      resultLabel.textContent = 'READY TO ANALYSE';
      resultLabel.style.color = '#1f6feb';
      resultBadge.style.display = 'none';
      resetProbBars();
    };
    reader.readAsDataURL(file);
  }

  // ── Run Analysis ──────────────────────────────────────────────────
  btnAnalyse.addEventListener('click', async () => {
    if (!selectedFile) return;

    btnAnalyse.disabled = true;
    btnAnalyse.innerHTML = '⏳ ANALYSING MRI SCAN...';
    resultLabel.textContent = 'ANALYSING...';
    resultLabel.style.color = '#1f6feb';

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch('/api/predict', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.detail || 'Analysis failed');
      }

      // Display Heatmap
      if (data.heatmap_b64) {
        imgHeatmap.src = data.heatmap_b64;
        imgHeatmap.style.display = 'block';
        phHeatmap.style.display = 'none';
      }

      // Display Outcome
      const isTumor = data.is_tumor;
      resultLabel.textContent = `${isTumor ? '⚠️ ' : '✓ '}${data.label.toUpperCase()}`;
      resultLabel.style.color = isTumor ? '#f85149' : '#3fb950';

      resultBadge.textContent = isTumor ? 'TUMOR DETECTED' : 'NORMAL';
      resultBadge.className = `result-badge ${isTumor ? 'badge-tumor' : 'badge-normal'}`;
      resultBadge.style.display = 'inline-block';

      // Update Probability Distribution Bars
      const probs = data.probabilities || {};
      updateProbBar('glioma', probs['Glioma'] || 0);
      updateProbBar('meningioma', probs['Meningioma'] || 0);
      updateProbBar('notumor', probs['No Tumor'] || 0);
      updateProbBar('pituitary', probs['Pituitary'] || 0);

      // Refresh Stats and Log Table
      loadStats();
      loadHistory();

    } catch (err) {
      alert(`Error: ${err.message}`);
      resultLabel.textContent = 'ANALYSIS ERROR';
      resultLabel.style.color = '#f85149';
    } finally {
      btnAnalyse.disabled = false;
      btnAnalyse.innerHTML = '▶ RUN AI DIAGNOSIS';
    }
  });

  function updateProbBar(key, val) {
    const bar = document.getElementById(`bar-${key}`);
    const pct = document.getElementById(`pct-${key}`);
    if (bar && pct) {
      bar.style.width = `${val}%`;
      pct.textContent = `${val.toFixed(1)}%`;
    }
  }

  function resetProbBars() {
    ['glioma', 'meningioma', 'notumor', 'pituitary'].forEach(k => updateProbBar(k, 0));
  }

  // ── Load Stats ────────────────────────────────────────────────────
  async function loadStats() {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      statTotal.textContent = data.total_scans || 0;
      statTumors.textContent = data.tumors_detected || 0;
      statNormal.textContent = data.normal_scans || 0;
    } catch (e) {
      console.error('Stats load error:', e);
    }
  }

  // ── Load History ──────────────────────────────────────────────────
  async function loadHistory() {
    try {
      const res = await fetch('/api/scans');
      const data = await res.json();

      if (!data || data.length === 0) {
        historyTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">No diagnostic history logged yet.</td></tr>`;
        return;
      }

      historyTbody.innerHTML = data.map(item => `
        <tr>
          <td>${item.timestamp}</td>
          <td><strong>${item.filename}</strong></td>
          <td>${item.result}</td>
          <td>${item.confidence.toFixed(1)}%</td>
          <td>
            <span class="status-pill ${item.is_tumor ? 'pill-red' : 'pill-green'}">
              ${item.tumor_flag}
            </span>
          </td>
        </tr>
      `).join('');
    } catch (e) {
      console.error('History load error:', e);
    }
  }

  btnRefreshHistory.addEventListener('click', loadHistory);

  // Initial Load
  loadStats();
  loadHistory();
});
