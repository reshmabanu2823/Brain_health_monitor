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
    $('recording').textContent = s.recording_id ? 'Recording' : 'Idle';
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

    // Prediction
    const prediction = s.prediction;
    $('prediction').textContent = prediction?.available ? prediction.label : 'No prediction';
    $('prediction-detail').textContent = prediction?.available ? `Class probability ${(prediction.score * 100).toFixed(1)}% · uncalibrated · ${prediction.task}` : prediction?.reason || 'EEG classifier unavailable';
    buttons();
  }

  async function history() {
    const rows = await api('/api/eeg/recordings'); $('history').replaceChildren();
    if (!rows.length) {
      const tr = document.createElement('tr'), td = document.createElement('td');
      td.colSpan = 6; td.textContent = 'No recordings yet. Connect a source, then start recording.';
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
      srcTd.textContent = r.source === 'simulated' ? 'SIMULATED' : r.source;
      tr.append(srcTd);

      const durTd = document.createElement('td');
      durTd.textContent = `${r.duration_seconds.toFixed(2)} s`;
      tr.append(durTd);

      const countTd = document.createElement('td');
      countTd.textContent = r.sample_count;
      tr.append(countTd);

      const statusTd = document.createElement('td');
      statusTd.textContent = r.status;
      tr.append(statusTd);

      const actionTd = document.createElement('td');
      if (r.status !== 'recording') {
        const a = document.createElement('a');
        a.href = `/api/eeg/recordings/${encodeURIComponent(r.id)}/export`;
        a.textContent = 'CSV';
        a.style.marginRight = '8px';
        a.setAttribute('aria-label', `Export ${r.source} session CSV from ${r.started_utc}`);

        const sumBtn = document.createElement('a');
        sumBtn.href = `/api/eeg/recordings/${encodeURIComponent(r.id)}/summary`;
        sumBtn.target = '_blank';
        sumBtn.textContent = 'Summary JSON';
        sumBtn.setAttribute('aria-label', `View session summary JSON for ${r.id}`);

        actionTd.append(a, sumBtn);
      } else {
        actionTd.textContent = 'Stop to export';
      }
      tr.append(actionTd);
      $('history').append(tr);
    });
  }

  $('source').addEventListener('change', buttons);
  $('refresh-ports').addEventListener('click', () => action(ports));
  $('connect').addEventListener('click', () => action(async () => {
    if ($('source').value === 'serial' && !$('port').value) throw new Error('Choose an available serial port first, or select simulated demo.');
    await api('/api/device/connect', 'POST', {source: $('source').value, port: $('port').value || null});
    await poll(false);
  }));
  $('disconnect').addEventListener('click', () => action(async () => {
    await api('/api/device/disconnect', 'POST'); await poll(false); await history();
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
