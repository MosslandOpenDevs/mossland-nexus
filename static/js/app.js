// ===================================================
// Moss Nexus - Web UI JavaScript
// 채팅 인터페이스 로직
// ===================================================

// ─────────────────────────────────────────────────
// DOM Elements
// ─────────────────────────────────────────────────
const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const questionInput = document.getElementById('question-input');
const sendButton = document.getElementById('send-button');
const charCount = document.getElementById('char-count');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');
const sourceModal = document.getElementById('source-modal');
const sourceList = document.getElementById('source-list');

// ─────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────
let isProcessing = false;
let currentSources = [];

// ─────────────────────────────────────────────────
// Initialization
// ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    // Check API health
    await checkHealth();

    // Setup event listeners
    setupEventListeners();

    // Auto-resize textarea
    autoResizeTextarea();

    // Focus input
    questionInput.focus();
}

// ─────────────────────────────────────────────────
// Health Check
// ─────────────────────────────────────────────────
async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();

        if (data.status === 'healthy') {
            setStatus('connected', '연결됨');
        } else {
            setStatus('warning', '일부 기능 제한');
        }
    } catch (error) {
        console.error('Health check failed:', error);
        setStatus('error', '연결 실패');
    }
}

function setStatus(status, text) {
    statusIndicator.className = 'status-dot';
    if (status === 'connected') {
        statusIndicator.classList.add('connected');
    } else if (status === 'error') {
        statusIndicator.classList.add('error');
    }
    statusText.textContent = text;
}

// ─────────────────────────────────────────────────
// Event Listeners
// ─────────────────────────────────────────────────
function setupEventListeners() {
    // Form submission
    chatForm.addEventListener('submit', handleSubmit);

    // Input handling
    questionInput.addEventListener('input', handleInput);
    questionInput.addEventListener('keydown', handleKeyDown);

    // Modal close on background click
    sourceModal.addEventListener('click', (e) => {
        if (e.target === sourceModal) {
            closeSourceModal();
        }
    });

    // ESC to close modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sourceModal.classList.contains('active')) {
            closeSourceModal();
        }
    });
}

function handleInput(e) {
    const length = e.target.value.length;
    charCount.textContent = length;

    // Enable/disable send button
    sendButton.disabled = length === 0 || isProcessing;

    // Auto-resize
    autoResizeTextarea();
}

function handleKeyDown(e) {
    // Enter to send (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!sendButton.disabled) {
            chatForm.dispatchEvent(new Event('submit'));
        }
    }
}

function autoResizeTextarea() {
    questionInput.style.height = 'auto';
    questionInput.style.height = Math.min(questionInput.scrollHeight, 120) + 'px';
}

// ─────────────────────────────────────────────────
// Form Submission
// ─────────────────────────────────────────────────
async function handleSubmit(e) {
    e.preventDefault();

    const question = questionInput.value.trim();
    if (!question || isProcessing) return;

    isProcessing = true;
    sendButton.disabled = true;

    // Add user message
    addMessage('user', question);

    // Clear input
    questionInput.value = '';
    charCount.textContent = '0';
    autoResizeTextarea();

    // Add loading message
    const loadingId = addLoadingMessage();

    try {
        const response = await fetch('/api/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ question }),
        });

        const data = await response.json();

        // Remove loading message
        removeMessage(loadingId);

        if (response.ok) {
            // Add assistant message with sources
            addMessage('assistant', data.answer, data.sources, data.processing_time);
        } else {
            addErrorMessage(data.detail || '오류가 발생했습니다.');
        }
    } catch (error) {
        console.error('Query failed:', error);
        removeMessage(loadingId);
        addErrorMessage('서버 연결에 실패했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
        isProcessing = false;
        sendButton.disabled = questionInput.value.length === 0;
        questionInput.focus();
    }
}

// ─────────────────────────────────────────────────
// Message Rendering
// ─────────────────────────────────────────────────
function addMessage(type, content, sources = [], processingTime = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    const time = new Date().toLocaleTimeString('ko-KR', {
        hour: '2-digit',
        minute: '2-digit'
    });

    if (type === 'user') {
        messageDiv.innerHTML = `
            <div class="message-avatar">You</div>
            <div class="message-content">
                <div class="message-text">${escapeHtml(content)}</div>
                <div class="message-time">${time}</div>
            </div>
        `;
    } else {
        const sourceButton = sources.length > 0
            ? `<button class="source-button" onclick="showSources(${chatMessages.children.length})">
                 📄 참조 문서 ${sources.length}개
               </button>`
            : '';

        const processingTimeHtml = processingTime
            ? `<div class="processing-time">⏱️ ${processingTime}초</div>`
            : '';

        messageDiv.innerHTML = `
            <div class="message-avatar">🌿</div>
            <div class="message-content">
                <div class="message-text">${formatContent(content)}</div>
                ${sourceButton}
                ${processingTimeHtml}
                <div class="message-time">${time}</div>
            </div>
        `;

        // Store sources for this message
        messageDiv.dataset.sources = JSON.stringify(sources);
    }

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv.id;
}

function addLoadingMessage() {
    const id = 'loading-' + Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.id = id;
    messageDiv.className = 'message assistant-message loading';
    messageDiv.innerHTML = `
        <div class="message-avatar">🌿</div>
        <div class="message-content">
            <div class="message-text">
                <span>문서를 분석하고 있습니다</span>
                <div class="loading-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return id;
}

function addErrorMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant-message error';
    messageDiv.innerHTML = `
        <div class="message-avatar">⚠️</div>
        <div class="message-content">
            <div class="message-text">${escapeHtml(message)}</div>
            <div class="message-time">${new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}</div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

function removeMessage(id) {
    const message = document.getElementById(id);
    if (message) {
        message.remove();
    }
}

// ─────────────────────────────────────────────────
// Source Modal
// ─────────────────────────────────────────────────
function showSources(messageIndex) {
    const messages = chatMessages.querySelectorAll('.assistant-message');
    // Find the correct message by counting assistant messages only
    let assistantIndex = 0;
    for (const msg of chatMessages.children) {
        if (msg.classList.contains('assistant-message') && !msg.classList.contains('loading')) {
            if (assistantIndex === messageIndex - 1) {  // Adjust for welcome message
                const sourcesData = msg.dataset.sources;
                if (sourcesData) {
                    currentSources = JSON.parse(sourcesData);
                    renderSources();
                    sourceModal.classList.add('active');
                }
                return;
            }
            assistantIndex++;
        }
    }
}

function renderSources() {
    sourceList.innerHTML = currentSources.map((source, index) => `
        <div class="source-item">
            <div class="source-item-header">
                <span>📄</span>
                <span>${escapeHtml(source.filename)}</span>
            </div>
            <div class="source-item-content">${escapeHtml(source.content)}</div>
        </div>
    `).join('');
}

function closeSourceModal() {
    sourceModal.classList.remove('active');
}

// ─────────────────────────────────────────────────
// Utility Functions
// ─────────────────────────────────────────────────
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatContent(content) {
    // Convert markdown-like syntax to HTML
    let formatted = escapeHtml(content);

    // Bold: **text**
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Line breaks
    formatted = formatted.replace(/\n/g, '<br>');

    // Source citation: [Source: filename]
    formatted = formatted.replace(
        /\[Source:\s*(.*?)\]/g,
        '<span style="color: var(--color-primary); font-size: 0.875rem;">📄 $1</span>'
    );

    return formatted;
}

function scrollToBottom() {
    chatMessages.scrollTo({
        top: chatMessages.scrollHeight,
        behavior: 'smooth'
    });
}
