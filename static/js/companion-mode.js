/**
 * CORTIA Everyday Companion & Dual-Persona Switch Controller
 * Supports everyday users, patients, and families with plain-English insights,
 * guided calmness biofeedback, and doctor-visit question checklists.
 */

(function() {
  const STORAGE_KEY = 'cortia_persona_mode';
  let currentMode = localStorage.getItem(STORAGE_KEY) || 'everyday'; // 'everyday' or 'research'
  let breathingInterval = null;
  let breathingPhase = 'Inhale';

  document.addEventListener('DOMContentLoaded', () => {
    applyPersonaMode(currentMode);
    injectPersonaSwitcher();
    setupEverydayUIComponents();
  });

  function applyPersonaMode(mode) {
    currentMode = mode;
    localStorage.setItem(STORAGE_KEY, mode);

    document.body.classList.remove('mode-everyday', 'mode-research');
    document.body.classList.add(`mode-${mode}`);

    // Update active button state
    document.querySelectorAll('.persona-toggle-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    // Update header branding text if present
    const badge = document.querySelector('.brand-badge');
    const subtitle = document.querySelector('.brand-subtitle');

    if (badge && subtitle) {
      if (mode === 'everyday') {
        badge.textContent = 'Patient & Health Companion';
        badge.style.background = '#D8EDD8';
        badge.style.color = '#5A8A5A';
        subtitle.textContent = 'Plain-language brain scan understanding, mental calmness tracking, and doctor visit prep';
      } else {
        badge.textContent = 'Research Workspace';
        badge.style.background = '#F0D0D0';
        badge.style.color = '#C94040';
        subtitle.textContent = 'Clinical research environment • Not for diagnostic use';
      }
    }

    // Trigger custom event for other page scripts
    window.dispatchEvent(new CustomEvent('cortia-mode-change', { detail: { mode } }));
  }

  function injectPersonaSwitcher() {
    if (document.body && document.body.dataset.page === 'mri') return;
    const headerActions = document.querySelector('.neuro-header .header-actions');
    if (!headerActions || document.getElementById('persona-toggle-wrap')) return;

    const wrap = document.createElement('div');
    wrap.id = 'persona-toggle-wrap';
    wrap.className = 'persona-toggle-wrap';
    wrap.innerHTML = `
      <button type="button" class="persona-toggle-btn ${currentMode === 'everyday' ? 'active' : ''}" data-mode="everyday" title="Patient & Everyday Consumer Mode">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
        </svg>
        <span>Everyday Mode</span>
      </button>
      <button type="button" class="persona-toggle-btn ${currentMode === 'research' ? 'active' : ''}" data-mode="research" title="Research & Evaluator Mode">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <circle cx="12" cy="12" r="9"/>
          <path d="M12 3a9 9 0 0 0 0 18M12 3v18M3 12h18"/>
        </svg>
        <span>Research Mode</span>
      </button>
    `;

    wrap.querySelectorAll('.persona-toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        applyPersonaMode(btn.dataset.mode);
      });
    });

    headerActions.insertBefore(wrap, headerActions.firstChild);
  }

  function setupEverydayUIComponents() {
    // 1. If on MRI Page (index.html), listen for scan results to render Patient Plain-English findings
    injectHowItWorksBanner();
    setupMRICompanionHooks();
    setupEEGCalmnessHooks();
  }

  function injectHowItWorksBanner() {
    if (document.body && document.body.dataset.page === 'mri') return;
    const pageTitle = document.querySelector('.page-title-section');
    if (!pageTitle || document.getElementById('how-it-works-banner')) return;

    const banner = document.createElement('div');
    banner.id = 'how-it-works-banner';
    banner.className = 'how-it-works-banner mode-everyday-only';
    banner.innerHTML = `
      <div class="step-item">
        <div class="step-num">1</div>
        <div class="step-desc"><strong>Upload or Wear</strong><br>Upload hospital MRI or wear single-channel headband.</div>
      </div>
      <div class="step-item">
        <div class="step-num">2</div>
        <div class="step-desc"><strong>Visual AI Review</strong><br>AI detects focal regions and tracks mental calm states.</div>
      </div>
      <div class="step-item">
        <div class="step-num">3</div>
        <div class="step-desc"><strong>Doctor Consultation Prep</strong><br>Get plain-English findings &amp; high-value doctor questions.</div>
      </div>
    `;

    pageTitle.parentNode.insertBefore(banner, pageTitle.nextSibling);
  }

  function setupMRICompanionHooks() {
    // Check if on MRI page (has #results-section or #mri-results)
    const resultsSec = document.getElementById('results-section') || document.querySelector('.results-card');
    if (!resultsSec) return;

    // Create container for Patient Plain-English Finding Card & Doctor Questions
    let companionContainer = document.getElementById('mri-companion-container');
    if (!companionContainer) {
      companionContainer = document.createElement('div');
      companionContainer.id = 'mri-companion-container';
      companionContainer.className = 'mode-everyday-only';
      resultsSec.parentNode.insertBefore(companionContainer, resultsSec);
    }
  }

  function setupEEGCalmnessHooks() {
    // Check if on EEG page (has #controls-section or #telemetry-stats)
    const eegControls = document.getElementById('controls-section') || document.querySelector('.eeg-controls');
    if (!eegControls) return;

    // Create Calmness Meter and Breathing Pacer if not present
    let calmnessContainer = document.getElementById('eeg-calmness-widget');
    if (!calmnessContainer) {
      calmnessContainer = document.createElement('div');
      calmnessContainer.id = 'eeg-calmness-widget';
      calmnessContainer.className = 'mode-everyday-only';
      calmnessContainer.innerHTML = `
        <div class="calmness-widget-card">
          <div class="calmness-dial-wrap">
            <div class="calmness-score-circle" id="calm-score-circle">
              <span class="calmness-score-num" id="calm-score-num">--</span>
              <span class="calmness-score-lbl">Calmness Index</span>
            </div>
            <span class="badge" id="sensor-fit-badge" style="background:#E6F4EA;color:#137333;">Sensor Connected</span>
          </div>

          <div class="calmness-info-wrap">
            <div class="calmness-level-tag" id="calm-level-tag">Calmness &amp; Mindfulness Tracker</div>
            <p class="calmness-guidance-text" id="calm-guidance-text">
              Put on your single-channel forehead sensor and sit comfortably. When you close your eyes and relax,
              your <strong>Alpha brainwaves (8–13 Hz)</strong> naturally synchronize, raising your Calmness Score.
            </p>
            <div style="display:flex;gap:12px;margin-top:8px;">
              <button type="button" class="btn-pacs-primary" id="start-pacer-btn">Start 2-Min Guided Breathing &rarr;</button>
            </div>
          </div>
        </div>

        <div class="breathing-pacer-card" id="breathing-pacer-panel" style="display:none;">
          <div style="display:flex;align-items:center;gap:16px;">
            <div class="breathing-circle" id="breathing-circle">Inhale</div>
            <div>
              <div style="font-weight:700;color:#202124;" id="pacer-step-title">Inhale Gently Through Nose (4s)</div>
              <div style="font-size:0.8125rem;color:#5F6368;" id="pacer-step-desc">Follow the circle. Notice your facial muscles relaxing.</div>
            </div>
          </div>
          <button type="button" class="btn-pacs-secondary" id="stop-pacer-btn" style="font-size:0.75rem;">Stop Exercise</button>
        </div>
      `;

      eegControls.parentNode.insertBefore(calmnessContainer, eegControls);

      document.getElementById('start-pacer-btn')?.addEventListener('click', startBreathingPacer);
      document.getElementById('stop-pacer-btn')?.addEventListener('click', stopBreathingPacer);
    }

    // Hook into live telemetry polling
    setInterval(pollLiveEEGForCalmness, 1500);
  }

  async function pollLiveEEGForCalmness() {
    if (document.body.classList.contains('mode-research')) return;
    try {
      const res = await fetch('/api/eeg/live');
      if (!res.ok) return;
      const snap = await res.json();
      if (!snap || snap.state === 'disconnected') {
        const scoreNum = document.getElementById('calm-score-num');
        if (scoreNum) scoreNum.textContent = '--';
        return;
      }

      const feats = snap.analysis?.feature_metrics || snap.analysis || {};
      const qState = snap.quality_state || 'Acceptable';

      let alphaPct = 25.0;
      if (feats.relative_alpha_power?.value) {
        alphaPct = feats.relative_alpha_power.value;
      } else if (feats.relative_band_power?.alpha) {
        alphaPct = feats.relative_band_power.alpha;
      }

      // Compute friendly score
      let score = Math.min(100, Math.max(10, Math.round((alphaPct / 45.0) * 100)));
      if (qState === 'Insufficient quality') score = 20;

      const scoreNum = document.getElementById('calm-score-num');
      const levelTag = document.getElementById('calm-level-tag');
      const guidance = document.getElementById('calm-guidance-text');
      const circle = document.getElementById('calm-score-circle');

      if (scoreNum) scoreNum.textContent = score;

      if (score >= 70) {
        if (levelTag) levelTag.textContent = 'Deeply Calm & Relaxed';
        if (circle) circle.style.borderTopColor = '#5A8A5A';
        if (guidance) guidance.textContent = 'High Alpha rhythm synchronization detected. Your brain is in a peaceful, restful state.';
      } else if (score >= 45) {
        if (levelTag) levelTag.textContent = 'Balanced & Mindful';
        if (circle) circle.style.borderTopColor = '#C94040';
        if (guidance) guidance.textContent = 'Normal resting alertness. Try closing your eyes for 30 seconds to boost alpha calmness.';
      } else {
        if (levelTag) levelTag.textContent = 'Active / Mental Engagement';
        if (circle) circle.style.borderTopColor = '#C07830';
        if (guidance) guidance.textContent = 'Active cognitive state or forehead muscle activity detected. Relax your jaw and brow.';
      }
    } catch {
      // Telemetry idle
    }
  }

  function startBreathingPacer() {
    const panel = document.getElementById('breathing-pacer-panel');
    const startBtn = document.getElementById('start-pacer-btn');
    if (panel) panel.style.display = 'flex';
    if (startBtn) startBtn.style.display = 'none';

    const circle = document.getElementById('breathing-circle');
    const title = document.getElementById('pacer-step-title');

    let count = 0;
    const cycle = () => {
      count++;
      if (count % 3 === 1) {
        circle.className = 'breathing-circle inhale';
        circle.textContent = 'Inhale';
        title.textContent = 'Inhale slowly through your nose (4s)...';
      } else if (count % 3 === 2) {
        circle.textContent = 'Hold';
        title.textContent = 'Hold gently (2s)...';
      } else {
        circle.className = 'breathing-circle exhale';
        circle.textContent = 'Exhale';
        title.textContent = 'Exhale softly through your mouth (4s)...';
      }
    };

    cycle();
    breathingInterval = setInterval(cycle, 3500);
  }

  function stopBreathingPacer() {
    clearInterval(breathingInterval);
    const panel = document.getElementById('breathing-pacer-panel');
    const startBtn = document.getElementById('start-pacer-btn');
    if (panel) panel.style.display = 'none';
    if (startBtn) startBtn.style.display = 'inline-block';
  }

  // Global helper to render patient findings on scan completion
  window.renderPatientMRICompanion = function(companionData) {
    const container = document.getElementById('mri-companion-container');
    if (!container || !companionData) return;

    let questionsHtml = '';
    (companionData.doctor_questions || []).forEach((q, idx) => {
      questionsHtml += `
        <li class="doctor-question-item">
          <span class="question-check-icon">[Q${idx + 1}]</span>
          <span>${q}</span>
        </li>
      `;
    });

    container.innerHTML = `
      <div class="patient-finding-card">
        <div class="patient-finding-header">
          <div class="patient-finding-title">
            <svg viewBox="0 0 24 24" fill="none" stroke="#C94040" stroke-width="2" width="22" height="22">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
            ${companionData.finding_title}
          </div>
          <span class="patient-urgency-badge">${companionData.urgency_guidance}</span>
        </div>
        <p class="patient-finding-body">${companionData.summary}</p>
        <p style="font-size:0.8125rem;color:#5F6368;margin-top:8px;">
          <em>${companionData.saliency_plain_explanation}</em>
        </p>
      </div>

      <div class="doctor-questions-card">
        <div class="doctor-questions-header">
          <div>
            <h3 style="font-size:1rem;font-weight:700;color:#202124;margin:0;">Recommended Questions for Your Doctor</h3>
            <span style="font-size:0.75rem;color:#5F6368;">Take these specific questions to your next neurology or neurosurgery consultation</span>
          </div>
          <button type="button" class="btn-pacs-secondary" id="copy-questions-btn" style="font-size:0.75rem;padding:6px 12px;">
            Copy Questions Checklist
          </button>
        </div>
        <ul class="doctor-questions-list">
          ${questionsHtml}
        </ul>
        <div style="margin-top:14px;padding-top:10px;border-top:1px solid #DADCE0;font-size:0.75rem;color:#5F6368;">
          ${companionData.important_reminder}
        </div>
      </div>
    `;

    document.getElementById('copy-questions-btn')?.addEventListener('click', () => {
      const qText = companionData.doctor_questions.map((q, i) => `${i + 1}. ${q}`).join('\n');
      navigator.clipboard.writeText(`CORTIA Scan Questions for Doctor Consultation:\n\n${qText}`).then(() => {
        const btn = document.getElementById('copy-questions-btn');
        if (btn) btn.textContent = 'Copied to Clipboard!';
        setTimeout(() => { if (btn) btn.textContent = 'Copy Questions Checklist'; }, 2500);
      });
    });
  };
})();
