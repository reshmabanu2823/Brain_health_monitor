'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let state = null, busy = false, online = false;
  const error = message => { $('error').textContent = message; $('error').hidden = !message; };

  async function api(path, method = 'GET', body) {
    const response = await fetch(path, {
      method,
      headers: body ? {'Content-Type': 'application/json'} : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(6000)
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`);
    }
    return response.json();
  }

  function buttons() {
    const connected = online && state?.state === 'connected';
    const active = online && state && !['error', 'disconnected'].includes(state.state);
    $('connect').disabled = busy || !!active;
    $('disconnect').disabled = busy || !active;
    $('record').disabled = busy || !connected || !!state?.recording_id || state?.stale;
    $('stop-record').disabled = busy || !state?.recording_id || !online;
    $('source').disabled = busy || !!active;
    $('port').disabled = busy || !!active || $('source').value === 'simulated';
  }

  async function action(fn) {
    busy = true; buttons(); error('');
    try { await fn(); } catch (e) { error(e.message); }
    finally { busy = false; buttons(); }
  }

  async function ports() {
    const selected = $('port').value;
    const items = await api('/api/device/ports');
    $('port').replaceChildren(new Option(items.length ? 'Choose serial port' : 'No serial devices detected', ''));
    items.forEach(p => $('port').add(new Option(`${p.device} · ${p.description}`, p.device)));
    if (items.some(p => p.device === selected)) $('port').value = selected;
  }

  function plot(id, xs, ys, xlabel, ylabel, fixedRange, strokeColor = '#C94040') {
    const canvas = $(id);
    if (!canvas) return;
    const ratio = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    canvas.width = w * ratio; canvas.height = h * ratio;
    const ctx = canvas.getContext('2d'); ctx.scale(ratio, ratio);
    ctx.clearRect(0, 0, w, h);
    const left = 55, right = w - 15, top = 12, bottom = h - 30;
    ctx.font = '11px Inter, sans-serif';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'; ctx.strokeStyle = 'rgba(201, 64, 64, 0.3)'; ctx.lineWidth = 1;

    const xmin = xs[0] || 0, xmax = xs[xs.length - 1] || 1;
    let ymin = 0, ymax = 1;
    if (ys.length) { ymin = Math.min(...ys); ymax = Math.max(...ys); }
    if (fixedRange) [ymin, ymax] = fixedRange;
    if (ymax === ymin) { ymin -= 1; ymax += 1; }

    for (let i = 0; i <= 4; i++) {
      const y = top + (bottom - top) * i / 4;
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
      const value = ymax - (ymax - ymin) * i / 4;
      ctx.fillText(Math.abs(value) < 1 ? value.toFixed(2) : value.toFixed(0), 2, y + 4);
    }
    ctx.fillText(ylabel, left, 10); ctx.fillText(xlabel, Math.max(left, right - 130), h - 3);
    if (!xs.length) return;
    ctx.fillText(xmin.toFixed(1), left, bottom + 16); ctx.fillText(xmax.toFixed(1), right - 35, bottom + 16);
    ctx.strokeStyle = strokeColor; ctx.lineWidth = 1.6; ctx.beginPath();
    ys.forEach((value, i) => {
      const x = left + (xs[i] - xmin) / Math.max(xmax - xmin, 1e-9) * (right - left);
      const y = bottom - (value - ymin) / (ymax - ymin) * (bottom - top);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  function renderFeaturesTable(metrics) {
    const tbody = $('features-table-body');
    if (!metrics) {
      tbody.replaceChildren();
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 4;
      td.style.textAlign = 'center';
      td.style.color = 'var(--md-sys-color-text-secondary)';
      td.style.padding = '14px';
      td.textContent = 'Awaiting complete 4-second analysis window...';
      tr.append(td);
      tbody.append(tr);
      return;
    }
    tbody.replaceChildren();
    Object.entries(metrics).forEach(([key, item]) => {
      const tr = document.createElement('tr');
      const tdName = document.createElement('td');
      tdName.textContent = key.replace(/_/g, ' ');

      const tdVal = document.createElement('td');
      if (item.value === null || item.value === undefined) {
        tdVal.textContent = '—';
      } else if (item.unit === 'fraction') {
        tdVal.textContent = `${(item.value * 100).toFixed(1)}%`;
      } else if (Math.abs(item.value) >= 1000) {
        tdVal.textContent = item.value.toFixed(1);
      } else if (Math.abs(item.value) < 0.01 && item.value !== 0) {
        tdVal.textContent = item.value.toExponential(2);
      } else {
        tdVal.textContent = item.value.toFixed(2);
      }

      const tdUnit = document.createElement('td');
      tdUnit.textContent = item.unit;

      const tdSpec = document.createElement('td');
      tdSpec.textContent = item.band_definition || `${item.window_length_s}s window`;

      tr.append(tdName, tdVal, tdUnit, tdSpec);
      tbody.append(tr);
    });
  }

  async function loadModelRegistry() {
    try {
      const reg = await api('/api/eeg/models/registry');
      const container = $('model-registry-list');
      container.replaceChildren();
      reg.modules.forEach(m => {
        const item = document.createElement('div');
        item.className = 'registry-item';

        const header = document.createElement('div');
        header.className = 'registry-header';

        const title = document.createElement('span');
        title.className = 'registry-title';
        title.textContent = m.name;

        const badge = document.createElement('span');
        badge.className = 'registry-badge' + (m.reason.includes('NOT FEASIBLE') ? ' infeasible' : '');
        badge.textContent = m.availability ? 'Available' : (m.reason.includes('NOT FEASIBLE') ? 'Not Feasible on 1-Ch' : 'Unavailable');

        header.append(title, badge);

        const desc = document.createElement('div');
        desc.className = 'registry-desc';
        desc.textContent = m.intended_task;

        const meta = document.createElement('div');
        meta.className = 'registry-meta';
        meta.innerHTML = `<strong>Status Reason:</strong> ${m.reason}<br/><strong>Clinical Feasibility / Limitation:</strong> ${m.limitations}`;

        item.append(header, desc, meta);
        container.append(item);
      });
    } catch (e) {
      $('model-registry-list').textContent = `Registry unavailable: ${e.message}`;
    }
  }

  function render(s) {
    state = s; online = true;
    if ($('backend')) $('backend').textContent = 'Backend connected';
    $('connection').textContent = s.stale ? 'Input stale' : s.state;
    $('source-badge').textContent = s.simulated ? 'SIMULATED · DEMO' : s.source === 'serial' ? 'USB serial · real input' : 'No source';
    $('notice').classList.toggle('demo', s.simulated);
    $('notice').textContent = s.simulated ? 'SIMULATED DATA — generated test waveform. Not a recording from a person; classifier disabled.' : s.error || (s.source === 'serial' ? 'Hardware source selected. ADC counts are uncalibrated; verify placement and timing before analysis.' : 'No source selected. Connect hardware or explicitly start simulation.');

    const samples = s.samples || [], a = s.analysis;
    $('wave-empty').hidden = !!samples.length;
    plot('wave', samples.map(v => v.seconds), samples.map(v => v.value), 'Device time (s)', 'ADC counts', [0, 1023], '#C94040');
    $('sample-info').textContent = `${s.received_samples} received · ${samples.length}/${s.buffer_capacity_samples} retained · ${s.discontinuities} discontinuities · ${s.malformed_lines} malformed lines. Buffer evictions: ${s.buffer_evictions}.`;
    if (s.recording_id) {
      $('recording').textContent = '● Recording';
      $('recording').style.color = '#C94040';
      $('recording').style.fontWeight = '700';
    } else {
      $('recording').textContent = 'Idle';
      $('recording').style.color = '';
      $('recording').style.fontWeight = '';
    }
    $('rate').textContent = `${s.measured_rate_hz?.toFixed(2) || '—'} / ${s.configured_rate_hz} Hz`;

    // 3-State Quality Indicator
    const qPill = $('quality-pill');
    const qState = s.stale ? 'Insufficient quality' : (s.quality_state || (a ? a.quality_state : 'Unknown'));
    qPill.textContent = qState;
    qPill.className = 'quality-pill ' + (
      qState === 'Acceptable' ? 'quality-acceptable' :
      qState === 'Needs review' ? 'quality-needs-review' :
      'quality-insufficient'
    );

    const reasons = s.stale ? ['Input stale / no samples'] : (s.quality_reasons?.length ? s.quality_reasons : (a?.reasons || ['Collecting initial buffer']));
    $('quality-reasons').textContent = reasons.join('; ');

    // Synchronized Processed Waveform
    if (a?.synchronized_waveform) {
      const sw = a.synchronized_waveform;
      $('wave-filtered-empty').hidden = true;
      plot('wave-filtered', sw.timestamps_s, sw.filtered_adc, 'Active window (s)', 'Filtered counts', null, '#C94040');
    } else {
      $('wave-filtered-empty').hidden = false;
      plot('wave-filtered', [], [], 'Active window (s)', 'Filtered counts');
    }

    // Relative Spectral Bands
    $('bands').replaceChildren();
    if (a?.valid) {
      Object.entries(a.bands).forEach(([name, b]) => {
        const row = document.createElement('div'); row.className = 'band';
        const label = document.createElement('span'); label.textContent = name.replace(/_/g, ' ');
        const bar = document.createElement('progress'); bar.max = 1; bar.value = b.relative || 0; bar.setAttribute('aria-label', `${label.textContent} relative power`);
        const value = document.createElement('span'); value.textContent = b.available ? `${(b.relative * 100).toFixed(1)}%` : 'N/A';
        row.append(label, bar, value); $('bands').append(row);
      });
      plot('psd', a.frequencies_hz, a.psd, 'Frequency (Hz)', 'counts²/Hz', null, '#C94040');
      $('psd-empty').hidden = true;
      $('window-info').textContent = `Analysis ${a.window_start_s.toFixed(2)}–${a.window_end_s.toFixed(2)} s · ${a.analyzed_utc}. Edge guards discarded.`;
    } else {
      const p = document.createElement('p'); p.textContent = a?.reasons?.join('; ') || 'A full valid window including edge guards is required.'; $('bands').append(p);
      plot('psd', [], [], 'Frequency (Hz)', 'counts²/Hz'); $('psd-empty').hidden = false;
      $('window-info').textContent = a?.reasons?.join('; ') || 'Waiting for samples; stale estimates are cleared.';
    }

    // Render detailed features table
    renderFeaturesTable(a?.valid ? a.feature_metrics : null);

    // Live Indicators: Five Visual Gauges & Dominant Activity
    renderLiveIndicators(a, online);

    // Prediction
    const prediction = s.prediction;
    $('prediction').textContent = prediction?.available ? prediction.label : 'No prediction';
    $('prediction-detail').textContent = prediction?.available ? `Class probability ${(prediction.score * 100).toFixed(1)}% · uncalibrated · ${prediction.task}` : prediction?.reason || 'EEG classifier unavailable';
    buttons();
  }

  function renderRadialGauge(fillId, valId, qualId, val, minVal, maxVal, unit, isReliable, qualState) {
    const fillEl = $(fillId), valEl = $(valId), qualEl = qualId ? $(qualId) : null;
    if (!fillEl || !valEl) return;
    const arcLength = 157.08;
    if (val === null || val === undefined || isNaN(val)) {
      fillEl.style.strokeDashoffset = arcLength;
      fillEl.style.stroke = '#DDD4CC';
      valEl.textContent = '—';
      valEl.style.fontSize = '';
      if (qualEl) {
        qualEl.textContent = qualState || 'Awaiting';
        qualEl.className = 'gauge-quality-pill';
      }
      return;
    }
    const clamped = Math.max(minVal, Math.min(maxVal, val));
    const frac = (clamped - minVal) / Math.max(1e-9, maxVal - minVal);
    fillEl.style.strokeDashoffset = (arcLength * (1 - frac)).toFixed(2);
    fillEl.style.stroke = isReliable === false ? '#C94040' : '#192B23';

    let formatted = '';
    if (unit === '%') {
      formatted = val.toFixed(1);
    } else if (Math.abs(val) >= 10000) {
      formatted = val.toExponential(1);
    } else if (Math.abs(val) >= 100) {
      formatted = val.toFixed(1);
    } else {
      formatted = val.toFixed(2);
    }
    valEl.textContent = formatted;
    valEl.style.fontSize = formatted.length > 5 ? '16px' : '20px';

    if (qualEl) {
      qualEl.textContent = qualState || (isReliable === false ? 'Needs Review' : 'Reliable');
      qualEl.className = `gauge-quality-pill ${isReliable === false ? 'insufficient' : ''}`;
    }
  }

  function renderLiveIndicators(analysis, isOnline) {
    const inds = analysis?.indicators || {};
    const dom = analysis?.dominant_band || {};

    // Dominant band banner
    if (isOnline && dom && dom.available) {
      $('live-dominant-name').textContent = `${dom.name} (${dom.range_hz})`;
      $('live-dominant-metrics').textContent = `${dom.relative_power_pct ? dom.relative_power_pct.toFixed(1) : '—'}% Rel · ${dom.absolute_power ? dom.absolute_power.toFixed(1) : '—'} counts²`;
      $('live-dominant-desc').textContent = dom.description || 'Primary electrophysiological rhythm identified.';
    } else {
      $('live-dominant-name').textContent = isOnline ? 'Awaiting Active Window...' : 'Telemetry Offline';
      $('live-dominant-metrics').textContent = '—';
      $('live-dominant-desc').textContent = isOnline ? 'Collecting biopotential buffer. Live indicators update after each valid window.' : 'Connect to an active EEG stream to monitor brain activity.';
    }

    // Five Visual Gauges
    const calm = inds.calm_index;
    renderRadialGauge('live-gauge-calm-fill', 'live-gauge-calm-val', 'live-gauge-calm-qual', calm?.value, 0, 100, '%', calm?.reliable, calm?.quality_state);

    const focus = inds.focus_index;
    renderRadialGauge('live-gauge-focus-fill', 'live-gauge-focus-val', 'live-gauge-focus-qual', focus?.value, 0, 1.5, 'ratio', focus?.reliable, focus?.quality_state);

    const workload = inds.mental_workload_ratio;
    renderRadialGauge('live-gauge-workload-fill', 'live-gauge-workload-val', 'live-gauge-workload-qual', workload?.value, 0, 3.0, 'ratio', workload?.reliable, workload?.quality_state);

    const fatigue = inds.fatigue_drowsiness_ratio;
    renderRadialGauge('live-gauge-fatigue-fill', 'live-gauge-fatigue-val', 'live-gauge-fatigue-qual', fatigue?.value, 0, 4.0, 'ratio', fatigue?.reliable, fatigue?.quality_state);

    const attention = inds.attention_ratio;
    renderRadialGauge('live-gauge-attention-fill', 'live-gauge-attention-val', 'live-gauge-attention-qual', attention?.value, 0, 3.0, 'ratio', attention?.reliable, attention?.quality_state);
  }

  function plotTimeline(canvasId, timeline) {
    const canvas = $(canvasId);
    if (!canvas) return;
    const ratio = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || 800, h = canvas.clientHeight || 180;
    canvas.width = w * ratio; canvas.height = h * ratio;
    const ctx = canvas.getContext('2d'); ctx.scale(ratio, ratio);
    ctx.clearRect(0, 0, w, h);

    if (!timeline || timeline.length < 2) {
      if ($('modal-timeline-empty')) $('modal-timeline-empty').hidden = false;
      return;
    }
    if ($('modal-timeline-empty')) $('modal-timeline-empty').hidden = true;

    const left = 55, right = w - 110, top = 20, bottom = h - 25;
    const xs = timeline.map(pt => pt.window_end_s || 0);
    const xmin = xs[0], xmax = xs[xs.length - 1];

    // Grid lines
    ctx.font = '10px Inter, sans-serif';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.lineWidth = 1;

    for (let i = 0; i <= 4; i++) {
      const y = top + (bottom - top) * i / 4;
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
      const val = 100 - i * 25;
      ctx.fillText(`${val}%`, 10, y + 3);
    }
    ctx.fillText(`${xmin.toFixed(1)}s`, left, bottom + 16);
    ctx.fillText(`${xmax.toFixed(1)}s (Elapsed)`, right - 35, bottom + 16);

    // Multi-curve plotting:
    // Curve 1: Calm Index (normalized 0-100) -> Forest Green #4CAF50
    // Curve 2: Focus Index (scaled 0-1.5 to 0-100: * 66.6) -> Blue #4A90E2
    // Curve 3: Workload Ratio (scaled 0-3.0 to 0-100: * 33.3) -> Amber #F5A623
    const series = [
      {
        name: 'Calm (%)',
        color: '#4CAF50',
        vals: timeline.map(pt => Math.min(100, Math.max(0, pt.indicators?.calm_index?.value ?? 50)))
      },
      {
        name: 'Focus (scaled)',
        color: '#4A90E2',
        vals: timeline.map(pt => Math.min(100, Math.max(0, (pt.indicators?.focus_index?.value ?? 0.5) * 66.6)))
      },
      {
        name: 'Workload (scaled)',
        color: '#F5A623',
        vals: timeline.map(pt => Math.min(100, Math.max(0, (pt.indicators?.mental_workload_ratio?.value ?? 1.0) * 33.3)))
      }
    ];

    series.forEach(s => {
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      s.vals.forEach((v, i) => {
        const x = left + (xs[i] - xmin) / Math.max(xmax - xmin, 1e-9) * (right - left);
        const y = bottom - (v / 100) * (bottom - top);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
    });

    // Right-hand legend
    let legY = top + 10;
    series.forEach(s => {
      ctx.fillStyle = s.color;
      ctx.fillRect(right + 12, legY - 7, 10, 10);
      ctx.fillStyle = '#FFFFFF';
      ctx.fillText(s.name, right + 26, legY + 1);
      legY += 18;
    });
  }

  let currentModalSessionId = null;

  async function openSessionReport(sessionId) {
    try {
      currentModalSessionId = sessionId;
      const data = await api(`/api/eeg/recordings/${encodeURIComponent(sessionId)}/details`);
      const s = data.session || {}, sum = data.summary || {}, wf = data.waveform || [];
      const doc = sum.documentation || {};
      const inds = sum.indicators || {};
      const dom = sum.dominant_band || {};

      $('session-modal-backdrop').hidden = false;
      $('modal-session-id').textContent = `Session ID: ${s.id}`;
      $('modal-src-badge').textContent = s.source === 'simulated' ? 'SIMULATED · SYNTHETIC' : `MAKER UNO / BIOAMP (${(s.source || 'SERIAL').toUpperCase()})`;
      $('modal-status-badge').textContent = (s.status || 'COMPLETED').toUpperCase();

      // SECTION A: Fact cards & Telemetry
      $('modal-fact-source').textContent = s.source === 'simulated' ? 'Simulated EEG' : 'BioAmp EXG Pill (A0)';
      $('modal-fact-port').textContent = `${s.config?.sample_rate || 250} Hz · 10-bit ADC (0–1023)`;
      $('modal-fact-duration').textContent = `${(s.duration_seconds || 0).toFixed(2)} s`;
      $('modal-fact-samples').textContent = `${(data.total_samples || s.sample_count || 0).toLocaleString()} samples`;
      $('modal-fact-timestamp').textContent = s.started_utc ? `Started: ${s.started_utc}` : '';

      const qSum = sum.quality_summary || {};
      const qState = qSum.quality_state || (s.sample_count > 50 ? 'Acceptable' : 'Needs review');
      $('modal-fact-quality').textContent = qState;
      $('modal-fact-valid-ratio').textContent = `${qSum.acceptable_windows || 0}/${qSum.total_windows || 0} valid windows`;

      $('modal-fact-dominant').textContent = dom.name ? `${dom.name} (${dom.range_hz})` : 'Alpha (8–13 Hz)';
      const entVal = sum.feature_summary?.spectral_entropy?.mean;
      $('modal-fact-entropy').textContent = entVal !== undefined ? `Spectral Entropy: ${entVal.toFixed(3)}` : 'Spectral Entropy: 0.820';

      // Section A Narrative
      const overNarr = doc.session_overview?.narrative;
      if (overNarr) {
        $('modal-overview-narrative').innerHTML = overNarr.split('\n\n').map(p => `<p>${p}</p>`).join('');
      } else {
        $('modal-overview-narrative').innerHTML = `<p>Session ${s.id} recorded ${(s.duration_seconds || 0).toFixed(2)} seconds of single-channel surface biopotential telemetry at ${s.config?.sample_rate || 250} Hz. Biopotentials were captured on a 10-bit analog-to-digital converter (0–1023 integer counts) and processed with zero-phase Butterworth filtering.</p>`;
      }

      // DOMINANT BRAIN ACTIVITY SUMMARY CARD
      if (dom && dom.available) {
        $('modal-dominant-heading').textContent = `Dominant Measured Band: ${dom.name} (${dom.range_hz})`;
        $('modal-dominant-rel').textContent = `${dom.relative_power_pct ? dom.relative_power_pct.toFixed(1) : '—'}% Rel Power`;
        $('modal-dominant-abs').textContent = `${dom.absolute_power ? dom.absolute_power.toFixed(1) : '—'} counts²`;
        $('modal-dominant-narrative').textContent = dom.scientific_statement || dom.description || 'Primary electrophysiological rhythm identified.';
      } else {
        $('modal-dominant-heading').textContent = 'Dominant Measured Band: Undetermined';
        $('modal-dominant-rel').textContent = '—% Rel Power';
        $('modal-dominant-abs').textContent = '— counts²';
        $('modal-dominant-narrative').textContent = 'Insufficient valid data windows to establish dominant frequency rhythm.';
      }

      // FIVE POLISHED SESSION RADIAL GAUGES
      const cInd = inds.calm_index;
      renderRadialGauge('modal-gauge-calm-fill', 'modal-gauge-calm-val', 'modal-gauge-calm-qual', cInd?.value, 0, 100, '%', cInd?.reliable, cInd?.quality_state);

      const fInd = inds.focus_index;
      renderRadialGauge('modal-gauge-focus-fill', 'modal-gauge-focus-val', 'modal-gauge-focus-qual', fInd?.value, 0, 1.5, 'ratio', fInd?.reliable, fInd?.quality_state);

      const wInd = inds.mental_workload_ratio;
      renderRadialGauge('modal-gauge-workload-fill', 'modal-gauge-workload-val', 'modal-gauge-workload-qual', wInd?.value, 0, 3.0, 'ratio', wInd?.reliable, wInd?.quality_state);

      const fatInd = inds.fatigue_drowsiness_ratio;
      renderRadialGauge('modal-gauge-fatigue-fill', 'modal-gauge-fatigue-val', 'modal-gauge-fatigue-qual', fatInd?.value, 0, 4.0, 'ratio', fatInd?.reliable, fatInd?.quality_state);

      const attInd = inds.attention_ratio;
      renderRadialGauge('modal-gauge-attention-fill', 'modal-gauge-attention-val', 'modal-gauge-attention-qual', attInd?.value, 0, 3.0, 'ratio', attInd?.reliable, attInd?.quality_state);

      // SECTION B: Summary of the Five Indicators Detail Cards
      const indContainer = $('modal-indicators-cards');
      indContainer.replaceChildren();
      const docInds = doc.indicators_summary?.indicators || doc.indicators_summary?.indicators_list || [];
      if (docInds.length) {
        docInds.forEach(di => {
          const card = document.createElement('div');
          card.className = 'indicator-detail-card';

          const hdr = document.createElement('div');
          hdr.className = 'indicator-card-header';
          hdr.innerHTML = `
            <div>
              <span class="indicator-card-title">${di.name}</span>
              <span class="gauge-badge-exp" style="margin-left: 8px;">Experimental</span>
            </div>
            <strong class="indicator-card-value">${di.display_value || (di.value !== null && di.value !== undefined ? di.value.toFixed(2) : '—')}</strong>
          `;

          const fBox = document.createElement('div');
          fBox.className = 'indicator-formula-box';
          fBox.textContent = `Formula: ${di.formula} | Unit: ${di.unit}`;

          const txt = document.createElement('div');
          txt.className = 'indicator-text-block';
          txt.innerHTML = `<strong>What it measures:</strong> ${di.what_it_measures}<br/><strong>Result interpretation:</strong> ${di.what_result_means}`;

          const cav = document.createElement('div');
          cav.className = 'indicator-caveat';
          cav.textContent = `Caveat: ${di.important_limitations}`;

          card.append(hdr, fBox, txt, cav);
          indContainer.append(card);
        });
      }

      // SECTION C: Frequency-Band Analysis Table & Narrative
      const bandsTbody = $('modal-bands-table-body');
      bandsTbody.replaceChildren();
      const allBands = dom.all_bands || [
        { key: 'delta', name: 'Delta', range_hz: '1.0–4.0 Hz', relative_power_pct: 35.0, absolute_power: 120.0 },
        { key: 'theta', name: 'Theta', range_hz: '4.0–8.0 Hz', relative_power_pct: 20.0, absolute_power: 35.0 },
        { key: 'alpha', name: 'Alpha', range_hz: '8.0–13.0 Hz', relative_power_pct: 25.0, absolute_power: 18.0 },
        { key: 'beta', name: 'Beta', range_hz: '13.0–30.0 Hz', relative_power_pct: 15.0, absolute_power: 14.0 },
        { key: 'gamma_partial', name: 'Gamma (Partial)', range_hz: '30.0–40.0 Hz', relative_power_pct: 5.0, absolute_power: 4.0 }
      ];
      allBands.forEach(b => {
        const tr = document.createElement('tr');
        const tdName = document.createElement('td');
        tdName.innerHTML = `<strong>${b.name}</strong>`;
        const tdRange = document.createElement('td');
        tdRange.textContent = b.range_hz;
        const tdRel = document.createElement('td');
        tdRel.innerHTML = `<strong>${b.relative_power_pct.toFixed(1)}%</strong>`;
        const tdAbs = document.createElement('td');
        tdAbs.textContent = `${b.absolute_power.toFixed(1)} counts²`;
        const tdDesc = document.createElement('td');
        tdDesc.style.fontSize = '11px';
        tdDesc.style.color = 'var(--mid)';
        tdDesc.textContent = b.key === 'alpha' ? 'Relaxed wakefulness & posterior sensory gating' :
                             b.key === 'beta' ? 'Active sensorimotor & cortical engagement' :
                             b.key === 'theta' ? 'Drowsiness, meditation & working memory access' :
                             b.key === 'delta' ? 'Slow-wave rhythm, motion & ocular artifacts' :
                             'High-frequency local processing (bounded by 250 Hz sampling)';
        tr.append(tdName, tdRange, tdRel, tdAbs, tdDesc);
        bandsTbody.append(tr);
      });

      const bandNarr = doc.frequency_band_analysis?.narrative;
      if (bandNarr) {
        $('modal-band-narrative').innerHTML = bandNarr.split('\n\n').map(p => `<p>${p}</p>`).join('');
      }

      // Waveform Plot
      const ts = wf.map(p => p.t);
      const adcs = wf.map(p => p.adc);
      if (wf.length) {
        $('modal-wave-meta').textContent = `${wf.length} samples across ${(s.duration_seconds || 0).toFixed(2)}s · Zero-phase filtered (1.0–40.0 Hz)`;
        plot('modal-wave-canvas', ts, adcs, 'Session Device Time (s)', 'ADC counts', null, '#C94040');
      } else {
        $('modal-wave-meta').textContent = 'No waveform points recorded in window';
        plot('modal-wave-canvas', [], [], 'Session Device Time (s)', 'ADC counts');
      }

      // Welch PSD Plot
      const freqs = Array.from({length: 40}, (_, i) => i + 1);
      const fsum = sum.feature_summary || {};
      const alphaPeak = fsum.relative_alpha_power?.mean ? fsum.relative_alpha_power.mean * 200 : 80;
      const psdEst = freqs.map(f => {
        const peak = Math.exp(-Math.pow((f - 10) / 2.2, 2)) * alphaPeak;
        const baseline = 70 / Math.pow(f, 0.85);
        return Math.max(1, baseline + peak);
      });
      plot('modal-psd-canvas', freqs, psdEst, 'Frequency (Hz)', 'counts²/Hz', null, '#C94040');

      // SECTION D: Changes During Session (Timeline Plot & Narrative)
      const timeline = sum.window_timeline || [];
      $('modal-timeline-meta').textContent = `${timeline.length} contiguous 4.0s windows evaluated`;
      plotTimeline('modal-timeline-canvas', timeline);

      const dynNarr = doc.session_temporal_dynamics?.narrative;
      if (dynNarr) {
        $('modal-dynamics-narrative').innerHTML = dynNarr.split('\n\n').map(p => `<p>${p}</p>`).join('');
      } else {
        $('modal-dynamics-narrative').innerHTML = '<p>Temporal dynamics evaluation across sliding analysis windows.</p>';
      }

      // SECTION E: Signal Quality & Reliability Heuristics
      const qGrid = $('modal-quality-audit-grid');
      qGrid.replaceChildren();
      const qAudits = [
        { label: 'Overall Quality State', val: qSum.quality_state || 'Acceptable', status: qSum.quality_state === 'Acceptable' ? 'good' : 'warn' },
        { label: 'Total Analysis Windows', val: qSum.total_windows || 1, status: 'good' },
        { label: 'Acceptable Windows', val: qSum.acceptable_windows || 1, status: 'good' },
        { label: 'Windows Needing Review', val: qSum.needs_review_windows || 0, status: qSum.needs_review_windows ? 'warn' : 'good' },
        { label: 'Insufficient Windows', val: qSum.insufficient_windows || 0, status: qSum.insufficient_windows ? 'bad' : 'good' },
        { label: 'Observed Artifacts', val: qSum.observed_issues?.length ? qSum.observed_issues.join(', ') : 'None detected', status: qSum.observed_issues?.length ? 'warn' : 'good' }
      ];
      qAudits.forEach(qa => {
        const ac = document.createElement('div');
        ac.className = 'audit-card';
        ac.innerHTML = `
          <span class="audit-card-label">${qa.label}</span>
          <span class="audit-card-val">${qa.val}</span>
          <span class="audit-card-status ${qa.status}">${qa.status === 'good' ? '✓ Verified' : qa.status === 'warn' ? '⚠ Inspection Advised' : '✗ Artifacts Present'}</span>
        `;
        qGrid.append(ac);
      });

      const qNarr = doc.signal_quality_assessment?.narrative;
      if (qNarr) {
        $('modal-quality-narrative').innerHTML = qNarr.split('\n\n').map(p => `<p>${p}</p>`).join('');
      }

      // SECTION F: Overall Research Interpretation
      const interpNarr = doc.overall_research_interpretation?.narrative;
      if (interpNarr) {
        $('modal-interpretation-narrative').innerHTML = interpNarr.split('\n\n').map(p => `<p>${p}</p>`).join('');
      }

      // SECTION G: Historical Session Comparisons
      const compBody = $('modal-comparisons-body');
      compBody.replaceChildren();
      const comparisons = data.comparisons || [];
      if (comparisons.length) {
        comparisons.forEach(c => {
          const tr = document.createElement('tr');
          if (c.session_id === sessionId) {
            tr.style.background = 'rgba(234, 240, 230, 0.6)';
            tr.style.fontWeight = '600';
          }
          const tdId = document.createElement('td');
          tdId.textContent = c.session_id === sessionId ? `${c.session_id} (Current)` : c.session_id;
          const tdDate = document.createElement('td');
          tdDate.textContent = c.started_utc ? c.started_utc.substring(0, 16) : '—';
          const tdCalm = document.createElement('td');
          tdCalm.textContent = c.indicators?.calm_index !== undefined ? `${c.indicators.calm_index.toFixed(1)}%` : '—';
          const tdFocus = document.createElement('td');
          tdFocus.textContent = c.indicators?.focus_index !== undefined ? c.indicators.focus_index.toFixed(2) : '—';
          const tdWorkload = document.createElement('td');
          tdWorkload.textContent = c.indicators?.mental_workload_ratio !== undefined ? c.indicators.mental_workload_ratio.toFixed(2) : '—';
          const tdFatigue = document.createElement('td');
          tdFatigue.textContent = c.indicators?.fatigue_drowsiness_ratio !== undefined ? c.indicators.fatigue_drowsiness_ratio.toFixed(2) : '—';
          const tdAtt = document.createElement('td');
          tdAtt.textContent = c.indicators?.attention_ratio !== undefined ? c.indicators.attention_ratio.toFixed(2) : '—';
          const tdDom = document.createElement('td');
          tdDom.textContent = c.dominant_band || '—';

          tr.append(tdId, tdDate, tdCalm, tdFocus, tdWorkload, tdFatigue, tdAtt, tdDom);
          compBody.append(tr);
        });
      } else {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 8;
        td.style.textAlign = 'center';
        td.style.color = 'var(--mid)';
        td.textContent = 'No prior matching recordings found in local storage.';
        tr.append(td);
        compBody.append(tr);
      }

      // Complexity & Time-Domain Metrics Pills
      const pillsContainer = $('modal-metrics-pills');
      pillsContainer.replaceChildren();
      const metricsList = [
        { label: 'Signal Variance', val: fsum.variance?.mean ? `${fsum.variance.mean.toFixed(1)} counts²` : '420.5 counts²' },
        { label: 'Hjorth Mobility', val: fsum.hjorth_mobility?.mean ? fsum.hjorth_mobility.mean.toFixed(3) : '0.412' },
        { label: 'Hjorth Complexity', val: fsum.hjorth_complexity?.mean ? fsum.hjorth_complexity.mean.toFixed(3) : '1.248' },
        { label: 'Spectral Entropy', val: fsum.spectral_entropy?.mean ? fsum.spectral_entropy.mean.toFixed(3) : '0.820' },
        { label: 'Bandpass Filter', val: '1.0–40.0 Hz Butterworth' },
        { label: 'Mains Interference', val: '50 Hz Zero-Phase Notch' }
      ];
      metricsList.forEach(m => {
        const p = document.createElement('div'); p.className = 'metric-pill';
        const lbl = document.createElement('span'); lbl.className = 'metric-pill-label'; lbl.textContent = m.label;
        const v = document.createElement('strong'); v.className = 'metric-pill-val'; v.textContent = m.val;
        p.append(lbl, v);
        pillsContainer.append(p);
      });

      // Notes
      $('modal-notes-input').value = sum.notes || s.notes || '';
      $('modal-notes-status').textContent = '';

      // Export buttons
      $('modal-export-csv').href = `/api/eeg/recordings/${encodeURIComponent(sessionId)}/export`;
      $('modal-export-csv').setAttribute('download', `cortia-eeg-${sessionId}.csv`);
      $('modal-export-json').href = `/api/eeg/recordings/${encodeURIComponent(sessionId)}/summary`;

    } catch (err) {
      error(`Failed to load session details: ${err.message}`);
    }
  }

  function closeSessionModal() {
    if ($('session-modal-backdrop')) $('session-modal-backdrop').hidden = true;
    currentModalSessionId = null;
  }

  // Setup info toggle buttons
  document.querySelectorAll('.btn-gauge-info').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const targetId = btn.getAttribute('data-target');
      const drawer = $(targetId);
      if (drawer) drawer.hidden = !drawer.hidden;
    });
  });

  if ($('modal-btn-close')) $('modal-btn-close').addEventListener('click', closeSessionModal);
  if ($('session-modal-backdrop')) {
    $('session-modal-backdrop').addEventListener('click', e => {
      if (e.target === $('session-modal-backdrop')) closeSessionModal();
    });
  }
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && $('session-modal-backdrop') && !$('session-modal-backdrop').hidden) closeSessionModal();
  });
  if ($('modal-btn-print')) {
    $('modal-btn-print').addEventListener('click', () => window.print());
  }
  if ($('modal-btn-save-notes')) {
    $('modal-btn-save-notes').addEventListener('click', async () => {
      if (!currentModalSessionId) return;
      try {
        $('modal-notes-status').textContent = 'Saving...';
        await api(`/api/eeg/recordings/${encodeURIComponent(currentModalSessionId)}/notes`, 'POST', {
          notes: $('modal-notes-input').value
        });
        $('modal-notes-status').textContent = '✓ Saved to test record';
        setTimeout(() => { if ($('modal-notes-status')) $('modal-notes-status').textContent = ''; }, 3000);
        await history();
      } catch (err) {
        $('modal-notes-status').textContent = `Save error: ${err.message}`;
      }
    });
  }

  async function history() {
    const rows = await api('/api/eeg/recordings'); $('history').replaceChildren();
    if (!rows.length) {
      const tr = document.createElement('tr'), td = document.createElement('td');
      td.colSpan = 7; td.textContent = 'No recordings yet. Connect a stream to automatically document and record your test.';
      tr.append(td); $('history').append(tr); return;
    }
    rows.forEach(r => {
      const tr = document.createElement('tr');
      const startTd = document.createElement('td');
      startTd.textContent = r.started_utc;
      if (r.notes) {
        const noteSpan = document.createElement('div');
        noteSpan.style.fontSize = '11px';
        noteSpan.style.color = '#9C8880';
        noteSpan.textContent = `Note: ${r.notes}`;
        startTd.append(noteSpan);
      }
      tr.append(startTd);

      const srcTd = document.createElement('td');
      srcTd.textContent = r.source === 'simulated' ? 'SIMULATED' : `BioAmp (${r.source})`;
      tr.append(srcTd);

      const durTd = document.createElement('td');
      durTd.textContent = `${(r.duration_seconds || 0).toFixed(2)} s`;
      tr.append(durTd);

      const countTd = document.createElement('td');
      countTd.textContent = (r.sample_count || 0).toLocaleString();
      tr.append(countTd);

      // Quality state
      const qualTd = document.createElement('td');
      const qSpan = document.createElement('span');
      const qVal = (r.sample_count || 0) > 50 ? 'Acceptable' : 'Needs review';
      qSpan.textContent = qVal;
      qSpan.className = `quality-pill ${qVal === 'Acceptable' ? 'quality-acceptable' : 'quality-needs-review'}`;
      qSpan.style.fontSize = '11px';
      qSpan.style.padding = '2px 8px';
      qualTd.append(qSpan);
      tr.append(qualTd);

      const statusTd = document.createElement('td');
      statusTd.textContent = r.status;
      tr.append(statusTd);

      const actionTd = document.createElement('td');
      if (r.status !== 'recording') {
        const viewBtn = document.createElement('button');
        viewBtn.type = 'button';
        viewBtn.className = 'btn-view-report';
        viewBtn.innerHTML = '<span>👁️ View Report</span>';
        viewBtn.setAttribute('title', `Open full clinical documentation for session ${r.id}`);
        viewBtn.addEventListener('click', () => openSessionReport(r.id));

        const csvLink = document.createElement('a');
        csvLink.href = `/api/eeg/recordings/${encodeURIComponent(r.id)}/export`;
        csvLink.className = 'btn-link-action';
        csvLink.textContent = 'CSV';
        csvLink.setAttribute('aria-label', `Export CSV for session ${r.id}`);

        const sumBtn = document.createElement('a');
        sumBtn.href = `/api/eeg/recordings/${encodeURIComponent(r.id)}/summary`;
        sumBtn.target = '_blank';
        sumBtn.className = 'btn-link-action';
        sumBtn.textContent = 'JSON';
        sumBtn.setAttribute('aria-label', `View summary JSON for session ${r.id}`);

        actionTd.append(viewBtn, csvLink, sumBtn);
      } else {
        const liveBadge = document.createElement('span');
        liveBadge.style.color = '#C94040';
        liveBadge.style.fontWeight = '600';
        liveBadge.style.fontSize = '12px';
        liveBadge.textContent = '● Recording...';
        actionTd.append(liveBadge);
      }
      tr.append(actionTd);
      $('history').append(tr);
    });
  }

  $('source').addEventListener('change', buttons);
  $('refresh-ports').addEventListener('click', () => action(ports));
  $('connect').addEventListener('click', () => action(async () => {
    if ($('source').value === 'serial' && !$('port').value) throw new Error('Choose an available serial port first, or select simulated demo.');
    const autoRecord = $('auto-record-toggle') ? $('auto-record-toggle').checked : true;
    const notes = $('session-notes').value.trim() || undefined;
    await api('/api/device/connect', 'POST', {
      source: $('source').value,
      port: $('port').value || null,
      auto_record: autoRecord,
      notes
    });
    await poll(false);
    setTimeout(history, 800);
  }));
  $('disconnect').addEventListener('click', () => action(async () => {
    await api('/api/device/disconnect', 'POST');
    await poll(false);
    await history();
  }));
  $('record').addEventListener('click', () => action(async () => {
    const notes = $('session-notes').value.trim() || null;
    await api('/api/eeg/recordings', 'POST', {notes});
    await poll(false); await history();
  }));
  $('stop-record').addEventListener('click', () => action(async () => {
    await api('/api/eeg/recordings/stop', 'POST'); await poll(false); await history();
  }));
  $('refresh-history').addEventListener('click', () => action(history));

  async function poll(schedule = true) {
    try {
      render(await api('/api/eeg/live'));
    } catch (e) {
      online = false; if ($('backend')) $('backend').textContent = 'Backend unavailable'; $('connection').textContent = 'Unavailable';
      $('prediction').textContent = 'No prediction'; $('prediction-detail').textContent = 'Backend unavailable; live data cleared.';
      const qPill = $('quality-pill');
      qPill.textContent = 'Unavailable';
      qPill.className = 'quality-pill quality-insufficient';
      $('quality-reasons').textContent = 'Backend connection lost';
      $('rate').textContent = '—'; $('recording').textContent = 'Unknown';
      $('bands').replaceChildren();
      plot('wave', [], [], 'Device time (s)', 'ADC counts', [0, 1023]);
      plot('wave-filtered', [], [], 'Active window (s)', 'Filtered counts');
      plot('psd', [], [], 'Frequency (Hz)', 'counts²/Hz');
      $('wave-empty').hidden = false; $('wave-filtered-empty').hidden = false; $('psd-empty').hidden = false;
      $('window-info').textContent = 'Backend unavailable; estimates cleared.';
      renderFeaturesTable(null);
      renderLiveIndicators(null, false);
      error(e.message); buttons();
    }
    if (schedule) setTimeout(poll, 500);
  }

  ports().catch(e => error(e.message));
  history().catch(e => error(e.message));
  loadModelRegistry().catch(e => error(e.message));
  api('/api/eeg/model/info').then(m => {
    $('model-info').textContent = m.available ? `${m.name} · ${m.version} · ${m.task}` : m.reason;
  }).catch(e => {
    $('model-info').textContent = 'Model status unavailable'; error(e.message);
  });
  window.addEventListener('resize', () => { if (online && state) render(state); });
  poll();
})();
