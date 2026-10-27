
let currentAttachedBase64 = null;
let currentAttachedType = 'image/jpeg';
let currentAttachedName = '';

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
  initCloudModelModal();
  loadCloudConfig();
  loadConversations();

  const sendBtn = document.getElementById('chat-send-btn');
  const textarea = document.getElementById('chat-textarea');
  const newConvBtn = document.getElementById('new-conv-btn');
  const deleteCurrBtn = document.getElementById('delete-curr-conv-btn');
  const clearAllBtn = document.getElementById('clear-all-convs-btn');

  sendBtn?.addEventListener('click', handleSendMessage);

  // Attachment controls
  const attachBtn = document.getElementById('btn-attach-image');
  const fileInput = document.getElementById('chat-file-input');
  const previewBar = document.getElementById('attachment-preview-bar');
  const previewImg = document.getElementById('attachment-thumb');
  const previewName = document.getElementById('attachment-filename');
  const removeAttachBtn = document.getElementById('btn-remove-attachment');

  attachBtn?.addEventListener('click', () => fileInput?.click());
  fileInput?.addEventListener('change', (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    currentAttachedName = file.name;
    currentAttachedType = file.type || 'image/jpeg';
    const reader = new FileReader();
    reader.onload = (evt) => {
      currentAttachedBase64 = evt.target.result;
      if (previewImg) previewImg.src = currentAttachedBase64;
      if (previewName) previewName.textContent = currentAttachedName;
      if (previewBar) previewBar.style.display = 'flex';
    };
    reader.readAsDataURL(file);
  });

  removeAttachBtn?.addEventListener('click', () => {
    currentAttachedBase64 = null;
    currentAttachedName = '';
    if (fileInput) fileInput.value = '';
    if (previewBar) previewBar.style.display = 'none';
  });
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
  const convId = params.get('conv') || params.get('conversation_id');

  if (convId) {
    activeConversationId = convId;
    setTimeout(() => {
      switchConversation(convId);
    }, 200);
  }

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

  const langSelect = document.getElementById('chat-lang-select');
  const selectedLang = langSelect ? langSelect.value : 'en';

  const payload = {
    message: message,
    conversation_id: activeConversationId,
    analysis_type: currentAnalysisContext.type,
    analysis_id: currentAnalysisContext.id,
    language: selectedLang,
    image_base64: currentAttachedBase64,
    media_type: currentAttachedType
  };

  // Reset attachment bar
  const prevBase64 = currentAttachedBase64;
  currentAttachedBase64 = null;
  currentAttachedName = '';
  const previewBar = document.getElementById('attachment-preview-bar');
  if (previewBar) previewBar.style.display = 'none';

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
            ${c.url ? `<a href="${c.url}" target="_blank" rel="noopener" style="font-size:0.75rem;color:var(--red);">[DOI / Link &rarr;]</a>` : ''}
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
  
  // CliniQ section wrappers
  let formatted = text
    .replace(/### Clinical Drug Interaction Alert([\s\S]*?)(?=###|$)/gi, (m, p1) => {
      return `<div style="background:#FDF4F2;border:1px solid rgba(217,107,79,0.3);border-left:4px solid #D96B4F;border-radius:8px;padding:12px 16px;margin:12px 0;">
        <div style="font-size:12px;font-weight:700;color:#D96B4F;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Clinical Drug Interaction Alert</div>
        <div style="font-size:13.5px;color:#252B28;line-height:1.5;">${p1.trim()}</div>
      </div>`;
    })
    .replace(/### Clinical Impression([\s\S]*?)(?=###|$)/gi, (m, p1) => {
      return `<div style="background:#F0F1E8;border-left:4px solid #192B23;border-radius:8px;padding:12px 16px;margin:12px 0;">
        <div style="font-size:12px;font-weight:700;color:#192B23;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Clinical Impression</div>
        <div style="font-size:13.5px;color:#252B28;line-height:1.5;">${p1.trim()}</div>
      </div>`;
    })
    .replace(/### Recommended Specialist & Action Plan([\s\S]*?)(?=###|$)/gi, (m, p1) => {
      return `<div style="background:#FCFBF8;border:1px solid #E5E4DC;border-radius:8px;padding:12px 16px;margin:12px 0;">
        <div style="font-size:12px;font-weight:700;color:#3F775B;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Recommended Specialist & Next Steps</div>
        <div style="font-size:13.5px;color:#252B28;line-height:1.5;">${p1.trim()}</div>
      </div>`;
    });
  text = formatted;
  if (!text) return '';
  return text
    .replace(/^### (.*$)/gim, '<h3 style="font-size:1rem;margin:8px 0 4px 0;font-weight:600;">$1</h3>')
    .replace(/^## (.*$)/gim, '<h2 style="font-size:1.1rem;margin:10px 0 6px 0;font-weight:700;">$1</h2>')
    .replace(/^# (.*$)/gim, '<h1 style="font-size:1.25rem;margin:12px 0 8px 0;font-weight:700;">$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code style="background:#F1F3F4;padding:2px 4px;border-radius:4px;font-family:monospace;font-size:0.8125rem;">$1</code>')
    .replace(/^\> (.*$)/gim, '<blockquote style="border-left:3px solid var(--red);margin:8px 0;padding-left:12px;color:var(--md-text-secondary);">$1</blockquote>')
    .replace(/\n\n/g, '</p><p style="margin:6px 0;">')
    .replace(/\n/g, '<br>');
}


/* ==========================================================================
   Cloud Model Integration Controller (Gemini, Groq, OpenAI, OpenRouter)
   ========================================================================== */

let currentCloudConfig = null;
let selectedProviderId = 'gemini';

function initCloudModelModal() {
  const modal = document.getElementById('cloud-model-modal');
  const openTopBtn = document.getElementById('btn-cloud-config');
  const openBadgeBtn = document.getElementById('ai-provider-badge');
  const closeBtn = document.getElementById('btn-close-cloud-modal');
  const cancelBtn = document.getElementById('btn-cancel-cloud');
  const testBtn = document.getElementById('btn-test-cloud');
  const saveBtn = document.getElementById('btn-save-cloud');
  const toggleKeyBtn = document.getElementById('btn-toggle-key');
  const keyInput = document.getElementById('cloud-api-key-input');

  function openModal() {
    if (modal) {
      modal.classList.add('open');
      renderCloudModalForm();
    }
  }

  function closeModal() {
    if (modal) {
      modal.classList.remove('open');
      const feedback = document.getElementById('cloud-test-feedback');
      if (feedback) feedback.style.display = 'none';
    }
  }

  openTopBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    openModal();
  });

  openBadgeBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    openModal();
  });

  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);

  modal?.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal?.classList.contains('open')) {
      closeModal();
    }
  });

  testBtn?.addEventListener('click', handleTestCloudConnection);
  saveBtn?.addEventListener('click', handleSaveCloudConfig);

  toggleKeyBtn?.addEventListener('click', () => {
    if (keyInput) {
      if (keyInput.type === 'password') {
        keyInput.type = 'text';
        toggleKeyBtn.innerHTML = '&#128064;';
      } else {
        keyInput.type = 'password';
        toggleKeyBtn.innerHTML = '&#128065;';
      }
    }
  });
}

async function loadCloudConfig() {
  try {
    const res = await fetch('/api/ai/config');
    if (!res.ok) return;
    currentCloudConfig = await res.json();
    selectedProviderId = currentCloudConfig.active_provider || 'gemini';
    updateCloudStatusBadges();
  } catch (err) {
    console.error('Failed to load cloud AI config:', err);
  }
}

function updateCloudStatusBadges() {
  if (!currentCloudConfig) return;

  const topbarLabel = document.getElementById('topbar-cloud-label');
  const topbarBtn = document.getElementById('btn-cloud-config');
  const badgeText = document.getElementById('provider-badge-text');
  const badgeBtn = document.getElementById('ai-provider-badge');

  if (currentCloudConfig.is_cloud) {
    const shortName = currentCloudConfig.provider_name.replace(' (Ultra Fast)', '').replace(' (Fast & Free)', '');
    const modelShort = currentCloudConfig.model_name || '';
    if (topbarLabel) topbarLabel.textContent = `☁️ ${shortName}: Active`;
    if (topbarBtn) topbarBtn.classList.add('cloud-connected');
    if (badgeText) badgeText.textContent = `☁️ ${shortName} (${modelShort})`;
    if (badgeBtn) badgeBtn.classList.add('cloud-active');
  } else {
    if (topbarLabel) topbarLabel.textContent = '☁️ Cloud Model: Connect';
    if (topbarBtn) topbarBtn.classList.remove('cloud-connected');
    if (badgeText) badgeText.textContent = 'Local Grounded Engine';
    if (badgeBtn) badgeBtn.classList.remove('cloud-active');
  }
}

function renderCloudModalForm() {
  if (!currentCloudConfig) return;

  const grid = document.getElementById('cloud-providers-grid');
  const modelSelect = document.getElementById('cloud-model-select');
  const keyGroup = document.getElementById('cloud-api-key-group');
  const keyInput = document.getElementById('cloud-api-key-input');
  const keyHint = document.getElementById('cloud-key-hint');
  const getKeyLink = document.getElementById('cloud-key-get-link');
  const feedback = document.getElementById('cloud-test-feedback');

  if (feedback) feedback.style.display = 'none';

  // Render provider selection cards
  if (grid) {
    grid.innerHTML = '';
    const icons = {
      'gemini': '🌟',
      'groq': '⚡',
      'openai': '🤖',
      'openrouter': '🌐',
      'local': '🖥️'
    };

    currentCloudConfig.available_providers.forEach(prov => {
      const card = document.createElement('div');
      card.className = `cloud-provider-card ${prov.id === selectedProviderId ? 'active' : ''}`;
      card.innerHTML = `
        <span class="provider-card-icon">${icons[prov.id] || '☁️'}</span>
        <span class="provider-card-name">${prov.name.split(' ')[0]}</span>
        <span class="provider-card-tag">${prov.free_tier ? 'Free Tier' : 'API Key'}</span>
      `;
      card.addEventListener('click', () => {
        selectedProviderId = prov.id;
        renderCloudModalForm();
      });
      grid.appendChild(card);
    });
  }

  const activeMeta = currentCloudConfig.available_providers.find(p => p.id === selectedProviderId) || currentCloudConfig.available_providers[0];

  // Populate models dropdown
  if (modelSelect) {
    modelSelect.innerHTML = '';
    activeMeta.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m;
      if (selectedProviderId === currentCloudConfig.active_provider && m === currentCloudConfig.model_name) {
        opt.selected = true;
      }
      modelSelect.appendChild(opt);
    });
  }

  // Handle API Key input display
  if (selectedProviderId === 'local') {
    if (keyGroup) keyGroup.style.display = 'none';
  } else {
    if (keyGroup) keyGroup.style.display = 'block';
    if (keyInput) {
      if (selectedProviderId === currentCloudConfig.active_provider && currentCloudConfig.has_api_key) {
        keyInput.placeholder = `Current Key: ${currentCloudConfig.masked_key} (Leave blank to keep)`;
        keyInput.value = '';
      } else {
        keyInput.placeholder = `Enter your ${activeMeta.name} API Key`;
        keyInput.value = '';
      }
    }

    if (getKeyLink) {
      if (activeMeta.key_url) {
        getKeyLink.style.display = 'inline-block';
        getKeyLink.href = activeMeta.key_url;
        getKeyLink.textContent = `Get ${activeMeta.name.split(' ')[0]} Key ↗`;
      } else {
        getKeyLink.style.display = 'none';
      }
    }

    if (keyHint) {
      keyHint.textContent = `${activeMeta.description} Key is saved locally in .env.`;
    }
  }
}

async function handleTestCloudConnection() {
  const modelSelect = document.getElementById('cloud-model-select');
  const keyInput = document.getElementById('cloud-api-key-input');
  const feedback = document.getElementById('cloud-test-feedback');
  const spinner = document.getElementById('test-btn-spinner');
  const testBtn = document.getElementById('btn-test-cloud');

  const modelName = modelSelect?.value;
  let apiKey = keyInput?.value?.trim();

  // If blank but current provider matches and already has key, send empty or rely on server
  if (!apiKey && selectedProviderId === currentCloudConfig.active_provider && currentCloudConfig.has_api_key) {
    apiKey = '__KEEP_EXISTING__';
  }

  if (feedback) {
    feedback.style.display = 'none';
    feedback.className = 'cloud-feedback-box';
  }
  if (spinner) spinner.style.display = 'inline-block';
  if (testBtn) testBtn.disabled = true;

  try {
    const res = await fetch('/api/ai/config/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: selectedProviderId,
        api_key: apiKey === '__KEEP_EXISTING__' ? '' : apiKey,
        model_name: modelName
      })
    });

    const data = await res.json();
    if (spinner) spinner.style.display = 'none';
    if (testBtn) testBtn.disabled = false;

    if (feedback) {
      feedback.style.display = 'flex';
      if (data.success) {
        feedback.className = 'cloud-feedback-box success';
        feedback.innerHTML = `<strong>Connected!</strong> ${data.message || 'Verified successfully.'} (${data.latency_ms || 150}ms latency)`;
      } else {
        feedback.className = 'cloud-feedback-box error';
        feedback.innerHTML = `<strong>Connection Failed:</strong> ${data.error || 'Invalid API key or network error.'}`;
      }
    }
  } catch (err) {
    if (spinner) spinner.style.display = 'none';
    if (testBtn) testBtn.disabled = false;
    if (feedback) {
      feedback.style.display = 'flex';
      feedback.className = 'cloud-feedback-box error';
      feedback.innerHTML = `<strong>Error:</strong> Network request failed. ${err.message}`;
    }
  }
}

async function handleSaveCloudConfig() {
  const modelSelect = document.getElementById('cloud-model-select');
  const keyInput = document.getElementById('cloud-api-key-input');
  const feedback = document.getElementById('cloud-test-feedback');
  const saveBtn = document.getElementById('btn-save-cloud');

  const modelName = modelSelect?.value;
  const apiKey = keyInput?.value?.trim();

  if (saveBtn) saveBtn.disabled = true;

  try {
    const payload = {
      provider: selectedProviderId,
      model_name: modelName
    };
    if (apiKey) {
      payload.api_key = apiKey;
    }

    const res = await fetch('/api/ai/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (saveBtn) saveBtn.disabled = false;

    if (!res.ok) {
      const err = await res.json();
      if (feedback) {
        feedback.style.display = 'flex';
        feedback.className = 'cloud-feedback-box error';
        feedback.innerHTML = `<strong>Save Failed:</strong> ${err.detail || 'Could not update configuration.'}`;
      }
      return;
    }

    currentCloudConfig = await res.json();
    updateCloudStatusBadges();

    if (feedback) {
      feedback.style.display = 'flex';
      feedback.className = 'cloud-feedback-box success';
      feedback.innerHTML = `<strong>Active!</strong> Switched to ${currentCloudConfig.provider_name}. Ready to answer medical questions.`;
    }

    // Close modal after 800ms
    setTimeout(() => {
      const modal = document.getElementById('cloud-model-modal');
      if (modal) modal.classList.remove('open');
    }, 800);

  } catch (err) {
    if (saveBtn) saveBtn.disabled = false;
    if (feedback) {
      feedback.style.display = 'flex';
      feedback.className = 'cloud-feedback-box error';
      feedback.innerHTML = `<strong>Error:</strong> ${err.message}`;
    }
  }
}
