'use strict';
(() => {
  const splash = document.getElementById('cortia-splash');
  if (!splash) return;

  const v = document.getElementById('cortia-v');
  const lockup = document.getElementById('cortia-lockup');
  const fin = document.getElementById('cortia-fin');
  const brain = document.getElementById('cortia-brain');
  const flier = document.getElementById('cortia-flier');
  const cta = document.getElementById('cortia-cta');
  const enterBtn = document.getElementById('cortia-enter-btn');
  const skipBtn = document.getElementById('cortia-skip');

  // If already seen in this tab session or skip param present, dismiss immediately
  const params = new URLSearchParams(window.location.search);
  if (sessionStorage.getItem('cortia_splash_dismissed') === '1' || params.has('skip_intro')) {
    splash.classList.add('dismissed');
    return;
  }

  let ended = false, finished = false;
  const timers = [];
  const REVEAL_DONE = 4.0;
  const BLOOM = [['R', 0, 1], ['C', 70, -1], ['T', 150, 1], ['I', 230, 1], ['A', 310, 1]];
  const EASE_FLY = 'cubic-bezier(.76,0,.24,1)';
  const EASE_BLOOM = 'cubic-bezier(.16,1,.3,1)';

  function dismissSplash() {
    sessionStorage.setItem('cortia_splash_dismissed', '1');
    timers.forEach(clearTimeout);
    if (v) v.pause();
    splash.classList.add('dismissed');
  }

  if (enterBtn) enterBtn.addEventListener('click', dismissSplash);
  if (skipBtn) skipBtn.addEventListener('click', dismissSplash);

  const pieces = fin ? [].slice.call(fin.querySelectorAll('.l')) : [];
  function byName(n) { return pieces.filter(p => p.getAttribute('data-l') === n)[0]; }

  function revealActions() {
    // Immediately dismiss splash and show the main dashboard
    dismissSplash();
  }

  function minimise(mode) {
    if (!lockup || !fin || !flier || !brain) {
      revealActions();
      return;
    }
    if (mode === true) {
      lockup.classList.add('gone');
      fin.classList.add('static');
      revealActions();
      return;
    }

    const lk = lockup.getBoundingClientRect();
    const sx = lk.left + lk.width * 0.1078125;
    const sy = lk.top + lk.height * 0.0907407;
    const sw = lk.width * 0.5125;

    flier.style.opacity = '1';
    const r = flier.getBoundingClientRect();
    const sc = sw / Math.max(r.width, 1);
    const dx = sx - r.left;
    const dy = sy - r.top;
    const T = 2200;
    const D = 100;

    lockup.classList.add('gone');

    // Brain flies into O slot
    flier.animate([
      { transform: `translate(${dx}px, ${dy}px) scale(${sc})` },
      { transform: 'translate(0,0) scale(1)' }
    ], { duration: T, delay: D, easing: EASE_FLY, fill: 'both' });

    flier.animate([{ opacity: 1 }, { opacity: 1, offset: 0.8 }, { opacity: 0 }], { duration: T + 400, delay: D, fill: 'both' });
    brain.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 500, delay: D + T - 260, easing: 'ease-out', fill: 'both' });
    brain.animate([{ transform: 'scale(1)' }, { transform: 'scale(1.05)', offset: 0.4 }, { transform: 'scale(1)' }], { duration: 1100, delay: D + T - 160, easing: 'ease-in-out', fill: 'both' });

    // Letters bloom outward
    const W = fin.getBoundingClientRect().width;
    BLOOM.forEach(b => {
      const p = byName(b[0]);
      if (!p) return;
      const d = b[2], shift = d * W * 0.13;
      p.style.transformOrigin = (d > 0 ? '0% 50%' : '100% 50%');
      p.animate([
        { opacity: 0, transform: `translateX(${-shift}px) scale(.5)`, filter: 'blur(16px)' },
        { opacity: 0.9, filter: 'blur(3px)', offset: 0.55 },
        { opacity: 1, transform: 'translateX(0) scale(1)', filter: 'blur(0)' }
      ], { duration: 1600, delay: D + T * 0.45 + b[1], easing: EASE_BLOOM, fill: 'both' });
    });

    timers.push(setTimeout(revealActions, D + T * 0.45 + 310 + 300));
  }

  function finish() {
    if (finished) return;
    finished = true;
    minimise();
  }

  function frame() {
    if (!ended && v && v.duration) {
      if (v.currentTime >= REVEAL_DONE) {
        ended = true;
        finish();
      }
    }
    if (!finished) requestAnimationFrame(frame);
  }

  if (v) {
    v.addEventListener('ended', () => { ended = true; finish(); });
    const p = v.play();
    if (p && p.catch) {
      p.catch(() => {
        // Autoplay restricted: perform instant bloom
        finish();
      });
    }
    requestAnimationFrame(frame);
  } else {
    finish();
  }
})();
