/**
 * Global Floating CORTIA AI Assistant Modal Controller
 */

(function() {
  let drawerOverlay = null;
  let drawerPanel = null;
  let drawerMessages = null;
  let drawerInput = null;
  let drawerSendBtn = null;
  let drawerConvId = null;

  document.addEventListener('DOMContentLoaded', () => {
    initAssistantModal();
  });

  function initAssistantModal() {
    let trigger = document.getElementById('cortia-ai-floating-trigger');
    if (!trigger) {
      trigger = document.createElement('div');
      trigger.id = 'cortia-ai-floating-trigger';
      trigger.className = 'floating-assistant-btn';
      trigger.title = 'Open CORTIA AI Assistant';
      trigger.innerHTML = `
        <span style="font-size: 16px; line-height: 1;">✦</span>
        <span>Ask CORTIA AI</span>
      `;
      document.body.appendChild(trigger);
    }

    // Create Drawer DOM
    drawerOverlay = document.createElement('div');
    drawerOverlay.className = 'cortia-drawer-overlay';

    drawerPanel = document.createElement('div');
    drawerPanel.className = 'cortia-drawer-panel';
    drawerPanel.innerHTML = `
      <div class="drawer-header">
        <div class="drawer-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="#C94040" stroke-width="2" width="20" height="20">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            <circle cx="9" cy="10" r="1" fill="currentColor" />
            <circle cx="15" cy="10" r="1" fill="currentColor" />
          </svg>
          <span>CORTIA AI Quick Assistant</span>
        </div>
        <div style="display:flex;align-items:center;gap:6px;">
          <a href="/ai" class="btn-pacs-secondary" style="font-size:0.75rem;padding:4px 8px;" title="Open Full Screen AI Workspace">Full View &rarr;</a>
          <button class="drawer-close-btn" id="drawer-close-btn">&times;</button>
        </div>
      </div>
      <div class="drawer-messages-scroll" id="drawer-messages">
        <div class="chat-msg assistant">
          <div class="msg-avatar ai-av" style="width:28px;height:28px;font-size:0.7rem;">AI</div>
          <div class="msg-body">
            <div class="msg-bubble" style="font-size:0.8125rem;padding:10px 14px;">
              Hello researcher. How can I assist you with neuroscience concepts, Grad-CAM mechanics, or application telemetry?
            </div>
          </div>
        </div>
      </div>
      <div class="drawer-input-bar">
        <input type="text" id="drawer-input-field" class="ai-input-field" placeholder="Ask a question..." style="min-height:40px;height:40px;padding:8px 12px;font-size:0.8125rem;">
        <button id="drawer-send-btn" class="ai-send-btn" style="width:40px;height:40px;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    `;

    document.body.appendChild(drawerOverlay);
    document.body.appendChild(drawerPanel);

    drawerMessages = drawerPanel.querySelector('#drawer-messages');
    drawerInput = drawerPanel.querySelector('#drawer-input-field');
    drawerSendBtn = drawerPanel.querySelector('#drawer-send-btn');

    trigger.addEventListener('click', openDrawer);
    drawerOverlay.addEventListener('click', closeDrawer);
    drawerPanel.querySelector('#drawer-close-btn').addEventListener('click', closeDrawer);

    drawerSendBtn.addEventListener('click', sendDrawerMessage);
    drawerInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendDrawerMessage();
      }
    });
  }

  function openDrawer() {
    drawerOverlay.classList.add('active');
    drawerPanel.classList.add('active');
    setTimeout(() => drawerInput?.focus(), 300);
  }

  function closeDrawer() {
    drawerOverlay.classList.remove('active');
    drawerPanel.classList.remove('active');
  }

  async function sendDrawerMessage() {
    const text = drawerInput.value.trim();
    if (!text) return;

    drawerInput.value = '';
    drawerInput.disabled = true;
    drawerSendBtn.disabled = true;

    // Render user message
    appendDrawerMsg('user', text);

    const payload = {
      message: text,
      conversation_id: drawerConvId
    };

    try {
      const res = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        appendDrawerMsg('assistant', 'Error formulating response. Please retry.');
        return;
      }
      const data = await res.json();
      drawerConvId = data.conversation_id;
      appendDrawerMsg('assistant', data.message.content);
    } catch (err) {
      appendDrawerMsg('assistant', `Connection error: ${err.message}`);
    } finally {
      drawerInput.disabled = false;
      drawerSendBtn.disabled = false;
      drawerInput.focus();
    }
  }

  function appendDrawerMsg(role, content) {
    const isUser = (role === 'user');
    const msgEl = document.createElement('div');
    msgEl.className = `chat-msg ${role}`;
    msgEl.style.maxWidth = '92%';
    msgEl.innerHTML = `
      <div class="msg-avatar ${isUser ? 'user-av' : 'ai-av'}" style="width:28px;height:28px;font-size:0.7rem;">${isUser ? 'ME' : 'AI'}</div>
      <div class="msg-body">
        <div class="msg-bubble" style="font-size:0.8125rem;padding:10px 14px;">
          ${content.replace(/\n/g, '<br>')}
        </div>
      </div>
    `;
    drawerMessages.appendChild(msgEl);
    drawerMessages.scrollTop = drawerMessages.scrollHeight;
  }
})();
