/**
 * CORTIA Universal Collapsible Sidebar & Hamburger Controller
 * Works across all workspace pages: MRI, EEG, AI, Insights, History, Chats, Portal.
 */

(function() {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
  });

  function initSidebar() {
    // 1. Ensure backdrop element exists in the DOM
    let backdrop = document.getElementById('cortia-sidebar-backdrop');
    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.id = 'cortia-sidebar-backdrop';
      backdrop.className = 'sidebar-backdrop';
      document.body.appendChild(backdrop);
    }

    // 2. Ensure close button exists in sidebar-brand
    const sidebarBrand = document.querySelector('.sidebar .sidebar-brand, .neuro-rail .sidebar-brand');
    if (sidebarBrand && !document.getElementById('cortia-sidebar-close')) {
      const closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.id = 'cortia-sidebar-close';
      closeBtn.className = 'sidebar-close-btn';
      closeBtn.title = 'Close Navigation Menu';
      closeBtn.setAttribute('aria-label', 'Close Navigation Menu');
      closeBtn.innerHTML = '&times;';
      sidebarBrand.appendChild(closeBtn);
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        closeSidebar();
      });
    }

    // 3. Ensure hamburger toggle exists in topbar or as edge fallback
    const headerContainer = document.querySelector('.neuro-header .header-left, .neuro-header');
    let toggleBtn = document.getElementById('cortia-sidebar-toggle');
    if (!toggleBtn && headerContainer) {
      toggleBtn = document.createElement('button');
      toggleBtn.type = 'button';
      toggleBtn.id = 'cortia-sidebar-toggle';
      toggleBtn.className = 'sidebar-toggle-btn';
      toggleBtn.title = 'Toggle Navigation Menu';
      toggleBtn.setAttribute('aria-label', 'Toggle Navigation Menu');
      toggleBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none">
          <line x1="3" y1="6" x2="21" y2="6"></line>
          <line x1="3" y1="12" x2="21" y2="12"></line>
          <line x1="3" y1="18" x2="21" y2="18"></line>
        </svg>
      `;
      headerContainer.insertBefore(toggleBtn, headerContainer.firstChild);
    } else if (!toggleBtn && !headerContainer) {
      // Edge fallback for landing page or pages without neuro-header
      toggleBtn = document.createElement('button');
      toggleBtn.type = 'button';
      toggleBtn.id = 'cortia-sidebar-toggle';
      toggleBtn.className = 'sidebar-edge-fallback-btn';
      toggleBtn.title = 'Toggle Navigation Menu';
      toggleBtn.setAttribute('aria-label', 'Toggle Navigation Menu');
      toggleBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none">
          <line x1="3" y1="6" x2="21" y2="6"></line>
          <line x1="3" y1="12" x2="21" y2="12"></line>
          <line x1="3" y1="18" x2="21" y2="18"></line>
        </svg>
      `;
      document.body.appendChild(toggleBtn);
    }

    // 4. Attach event listeners
    document.querySelectorAll('#cortia-sidebar-toggle, .sidebar-toggle-btn, .sidebar-edge-fallback-btn').forEach(btn => {
      // Avoid duplicate listener
      if (!btn.dataset.sidebarBound) {
        btn.dataset.sidebarBound = 'true';
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          toggleSidebar();
        });
      }
    });

    backdrop.addEventListener('click', () => {
      closeSidebar();
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && document.body.classList.contains('sidebar-open')) {
        closeSidebar();
      }
    });

    // Auto-close on small screens when a rail navigation link is clicked
    document.querySelectorAll('.sidebar .nav-item, .neuro-rail .nav-item').forEach(link => {
      link.addEventListener('click', () => {
        if (window.innerWidth <= 1024) {
          closeSidebar();
        }
      });
    });
  }

  function toggleSidebar() {
    if (document.body.classList.contains('sidebar-open')) {
      closeSidebar();
    } else {
      openSidebar();
    }
  }

  function openSidebar() {
    document.body.classList.add('sidebar-open');
    try { localStorage.setItem('cortia_sidebar_open', '1'); } catch(e) {}
  }

  function closeSidebar() {
    document.body.classList.remove('sidebar-open');
    try { localStorage.setItem('cortia_sidebar_open', '0'); } catch(e) {}
  }

  // Expose global methods for tests and manual control
  window.cortiaOpenSidebar = openSidebar;
  window.cortiaCloseSidebar = closeSidebar;
  window.cortiaToggleSidebar = toggleSidebar;
})();
