/**
 * CORTIA AI Assistant Client Controller
 */

let activeConversationId = null;
let currentAnalysisContext = {
  type: null,
  id: null
};

document.addEventListener('DOMContentLoaded', () => {
  initURLParams();
  loadCapabilities();
  loadConversations();

  const sendBtn = document.getElementById('chat-send-btn');
  const textarea = document.getElementById('chat-textarea');
  const newConvBtn = document.getElementById('new-conv-btn');
  const deleteCurrBtn = document.getElementById('delete-curr-conv-btn');
  const clearAllBtn = document.getElementById('clear-all-convs-btn');

  sendBtn?.addEventListener('click', handleSendMessage);
  textarea?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  newConvBtn?.addEventListener('click', () => {
    activeConversationId = null;
    document.getElementById('messages-container').innerHTML = '';
    document.getElementById('active-conv-title').textContent = 'New Research Inquiry';
    appendAssistantWelcome();
    loadConversations();
  });

  deleteCurrBtn?.addEventListener('click', async () => {
    if (!activeConversationId) return;
    if (confirm('Delete this conversation?')) {
      await fetch(`/api/ai/conversations/${activeConversationId}`, { method: 'DELETE' });
      activeConversationId = null;
      document.getElementById('messages-container').innerHTML = '';
      appendAssistantWelcome();
      loadConversations();
    }
  });

  clearAllBtn?.addEventListener('click', async () => {
    if (confirm('Clear all conversation history?')) {
      await fetch('/api/ai/clear', { method: 'POST' });
      activeConversationId = null;
      document.getElementById('messages-container').innerHTML = '';
      appendAssistantWelcome();
      loadConversations();
    }
  });
});

function initURLParams() {
  const params = new URLSearchParams(window.location.search);
  const type = params.get('analysis_type') || params.get('type');
  const id = params.get('analysis_id') || params.get('id');

  if (type && id) {
    currentAnalysisContext.type = type;
    currentAnalysisContext.id = id;
    const badge = document.getElementById('active-context-badge');
    if (badge) {
      badge.style.display = 'inline-block';
      badge.textContent = `Attached: ${type.toUpperCase()} #${id}`;
    }

    // Auto-prompt starter
    const promptText = type === 'mri'
      ? `Explain the Grad-CAM visualization and findings for MRI scan #${id}.`
      : `Summarize the signal features and quality for EEG session #${id}.`;

    setTimeout(() => {
      const textarea = document.getElementById('chat-textarea');
      if (textarea) textarea.value = promptText;
    }, 300);
  }
}

async function loadCapabilities() {
  try {
    const res = await fetch('/api/ai/capabilities');
    if (!res.ok) return;
    const data = await res.json();

    const provBadge = document.getElementById('ai-provider-badge');
    if (provBadge) {
      provBadge.textContent = data.active_provider.replace('Provider', '').replace('Engine', ' Engine');
    }

    const promptBar = document.getElementById('suggested-prompts-bar');
    if (promptBar && data.starter_prompts) {
      promptBar.innerHTML = '';
      data.starter_prompts.forEach(pText => {
        const pill = document.createElement('button');
        pill.className = 'prompt-pill';
        pill.textContent = pText;
        pill.addEventListener('click', () => {
          const textarea = document.getElementById('chat-textarea');
          if (textarea) {
            textarea.value = pText;
            handleSendMessage();
          }
        });
        promptBar.appendChild(pill);
      });
    }
  } catch (err) {
    console.error('Failed to load capabilities:', err);
  }
}

async function loadConversations() {
  const listEl = document.getElementById('conv-list-container');
  if (!listEl) return;
  try {
    const res = await fetch('/api/ai/conversations');
    if (!res.ok) return;
    const convs = await res.json();
    listEl.innerHTML = '';
    if (convs.length === 0) {
      listEl.innerHTML = `<div style="padding:16px;font-size:0.75rem;color:var(--md-text-secondary);text-align:center;">No previous conversations.</div>`;
      return;
    }
    convs.forEach(c => {
      const item = document.createElement('div');
      item.className = `conv-item ${c.id === activeConversationId ? 'active' : ''}`;
      item.innerHTML = `
        <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px;">${c.title}</span>
        <button class="conv-delete-btn" title="Delete conversation">&times;</button>
      `;
      item.addEventListener('click', (e) => {
        if (e.target.classList.contains('conv-delete-btn')) {
          e.stopPropagation();
          deleteConversation(c.id);
        } else {
          switchConversation(c.id, c.title);
        }
      });
      listEl.appendChild(item);
    });
  } catch (err) {
    console.error('Failed to load conversations:', err);
  }
}

async function switchConversation(convId, title) {
  activeConversationId = convId;
  document.getElementById('active-conv-title').textContent = title || 'Research Inquiry';
  loadConversations();

  const container = document.getElementById('messages-container');
  container.innerHTML = `<div style="text-align:center;padding:24px;color:var(--md-text-secondary);">Loading messages...</div>`;

  try {
    const res = await fetch(`/api/ai/conversations/${convId}`);
    if (!res.ok) return;
    const data = await res.json();
    container.innerHTML = '';
    if (data.messages) {
      data.messages.forEach(msg => {
        renderMessage(msg);
      });
      container.scrollTop = container.scrollHeight;
    }
  } catch (err) {
    console.error('Failed to load conversation history:', err);
  }
}

async function deleteConversation(convId) {
  try {
    await fetch(`/api/ai/conversations/${convId}`, { method: 'DELETE' });
    if (activeConversationId === convId) {
      activeConversationId = null;
      document.getElementById('messages-container').innerHTML = '';
      appendAssistantWelcome();
    }
    loadConversations();
  } catch (err) {
    console.error('Failed to delete conversation:', err);
  }
}

async function handleSendMessage() {
  const textarea = document.getElementById('chat-textarea');
  const sendBtn = document.getElementById('chat-send-btn');
  const message = textarea.value.trim();
  if (!message) return;

  textarea.value = '';
  textarea.disabled = true;
  sendBtn.disabled = true;

  // Render user message immediately
  renderMessage({
    role: 'user',
    content: message,
    timestamp: new Date().toISOString()
  });

  // Render typing indicator
  const typingEl = showTypingIndicator();

  const payload = {
    message: message,
    conversation_id: activeConversationId,
    analysis_type: currentAnalysisContext.type,
    analysis_id: currentAnalysisContext.id
  };

  try {
    const res = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    typingEl.remove();

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      renderMessage({
        role: 'assistant',
        content: `**Request Error**: ${errData.detail || 'Failed to process AI response.'} Please check connection and retry.`,
        timestamp: new Date().toISOString()
      });
      return;
    }

    const data = await res.json();
    activeConversationId = data.conversation_id;

    renderMessage(data.message);

    // Update followups bar if supplied
    if (data.suggested_followups && data.suggested_followups.length > 0) {
      const promptBar = document.getElementById('suggested-prompts-bar');
      if (promptBar) {
        promptBar.innerHTML = '';
        data.suggested_followups.forEach(pText => {
          const pill = document.createElement('button');
          pill.className = 'prompt-pill';
          pill.textContent = pText;
          pill.addEventListener('click', () => {
            textarea.value = pText;
            handleSendMessage();
          });
          promptBar.appendChild(pill);
        });
      }
    }

    loadConversations();
  } catch (err) {
    typingEl.remove();
    console.error('Chat error:', err);
    renderMessage({
      role: 'assistant',
      content: `**Network Error**: Could not connect to assistant backend. (${err.message})`,
      timestamp: new Date().toISOString()
    });
  } finally {
    textarea.disabled = false;
    sendBtn.disabled = false;
    textarea.focus();
  }
}

function renderMessage(msg) {
  const container = document.getElementById('messages-container');
  const msgEl = document.createElement('div');
  msgEl.className = `chat-msg ${msg.role}`;

  const isUser = (msg.role === 'user');
  const avatarText = isUser ? 'ME' : 'AI';
  const avatarClass = isUser ? 'user-av' : 'ai-av';

  let bodyHtml = `<div class="msg-bubble">${formatMarkdown(msg.content)}</div>`;

  // Warning banner if present
  if (msg.simulated_warning) {
    bodyHtml = `
      <div class="simulated-warning-chip">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span>${msg.simulated_warning}</span>
      </div>
    ` + bodyHtml;
  }

  // Citations
  if (msg.citations && msg.citations.length > 0) {
    let citHtml = `<div class="citations-box"><div class="citations-title"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg> Verified Scientific Sources:</div>`;
    msg.citations.forEach(c => {
      citHtml += `
        <div class="citation-card">
          <div class="citation-card-header">
            <span>${c.title} (${c.publication_year || 'N/A'})</span>
            ${c.url ? `<a href="${c.url}" target="_blank" rel="noopener" style="font-size:0.75rem;color:var(--md-blue-primary);">[DOI / Link &rarr;]</a>` : ''}
          </div>
          <div class="citation-snippet">${c.relevance_snippet}</div>
        </div>
      `;
    });
    citHtml += `</div>`;
    bodyHtml += citHtml;
  }

  // Deep Link References
  if (msg.analysis_references && msg.analysis_references.length > 0) {
    let refHtml = `<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:8px;">`;
    msg.analysis_references.forEach(r => {
      refHtml += `
        <a href="${r.deep_link}" class="analysis-ref-chip">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
          </svg>
          Inspect in Insights: ${r.title}
        </a>
      `;
    });
    refHtml += `</div>`;
    bodyHtml += refHtml;
  }

  const timeStr = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

  msgEl.innerHTML = `
    <div class="msg-avatar ${avatarClass}">${avatarText}</div>
    <div class="msg-body">
      ${bodyHtml}
      <div class="msg-time">${timeStr}</div>
    </div>
  `;

  container.appendChild(msgEl);
  container.scrollTop = container.scrollHeight;
}

function showTypingIndicator() {
  const container = document.getElementById('messages-container');
  const ind = document.createElement('div');
  ind.className = 'chat-msg assistant';
  ind.innerHTML = `
    <div class="msg-avatar ai-av">AI</div>
    <div class="msg-body">
      <div class="msg-bubble" style="padding:10px 14px;">
        <div class="typing-dots">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      </div>
    </div>
  `;
  container.appendChild(ind);
  container.scrollTop = container.scrollHeight;
  return ind;
}

function appendAssistantWelcome() {
  const container = document.getElementById('messages-container');
  const welcome = document.createElement('div');
  welcome.className = 'chat-msg assistant';
  welcome.innerHTML = `
    <div class="msg-avatar ai-av">AI</div>
    <div class="msg-body">
      <div class="msg-bubble">
        <p><strong>CORTIA AI Assistant ready.</strong></p>
        <p>How can I assist your neuroscience research today? You can choose a suggested question below or enter your inquiry.</p>
      </div>
      <div class="msg-time">Just now</div>
    </div>
  `;
  container.appendChild(welcome);
}

function formatMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/^### (.*$)/gim, '<h3 style="font-size:1rem;margin:8px 0 4px 0;font-weight:600;">$1</h3>')
    .replace(/^## (.*$)/gim, '<h2 style="font-size:1.1rem;margin:10px 0 6px 0;font-weight:700;">$1</h2>')
    .replace(/^# (.*$)/gim, '<h1 style="font-size:1.25rem;margin:12px 0 8px 0;font-weight:700;">$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code style="background:#F1F3F4;padding:2px 4px;border-radius:4px;font-family:monospace;font-size:0.8125rem;">$1</code>')
    .replace(/^\> (.*$)/gim, '<blockquote style="border-left:3px solid var(--md-blue-primary);margin:8px 0;padding-left:12px;color:var(--md-text-secondary);">$1</blockquote>')
    .replace(/\n\n/g, '</p><p style="margin:6px 0;">')
    .replace(/\n/g, '<br>');
}
