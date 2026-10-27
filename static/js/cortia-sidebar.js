/**
 * CORTIA Universal Navigation Controller
 * The platform uses a permanent horizontal top navigation bar matching the design reference.
 * Legacy hamburger toggles and hidden drawers are disabled.
 */
(function() {
  'use strict';
  document.addEventListener('DOMContentLoaded', () => {
    // Remove any legacy sidebar toggle or drawer elements if dynamically created
    const legacyElements = document.querySelectorAll('#cortia-sidebar-toggle, .sidebar-toggle-btn, .sidebar-edge-fallback-btn, .sidebar, .neuro-rail, #cortia-sidebar-backdrop');
    legacyElements.forEach(el => el.remove());
    document.body.classList.remove('sidebar-open');
  });
})();
