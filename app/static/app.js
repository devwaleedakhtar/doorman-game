// State
const state = {
    sessionId: null,
    gameState: null,  // null until game starts
    score: 30,
    isLoading: false,
    sessions: []
};

// Config
const API_BASE = '';
const WIN_THRESHOLD = 100;
const LOSE_THRESHOLD = -50;

// DOM Elements
const elements = {
    sidebar: document.getElementById('sidebar'),
    menuToggle: document.getElementById('menuToggle'),
    sessionsList: document.getElementById('sessionsList'),
    newGameBtn: document.getElementById('newGameBtn'),
    messages: document.getElementById('messages'),
    messagesContainer: document.getElementById('messagesContainer'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    wordCount: document.getElementById('wordCount'),
    gameState: document.getElementById('gameState'),
    typingIndicator: document.getElementById('typingIndicator'),
    scoreFill: document.getElementById('scoreFill'),
    scoreText: document.getElementById('scoreText'),
    gameOverOverlay: document.getElementById('gameOverOverlay'),
    gameOverTitle: document.getElementById('gameOverTitle'),
    gameOverMessage: document.getElementById('gameOverMessage'),
    gameOverNewBtn: document.getElementById('gameOverNewBtn'),
    inputContainer: document.getElementById('inputContainer'),
    emptyState: document.getElementById('emptyState'),
    emptyStateNewBtn: document.getElementById('emptyStateNewBtn')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadSessions();
    setupEventListeners();
    updateGameState();  // Show initial state

    // Check for saved session
    const savedSessionId = localStorage.getItem('doorman_session_id');
    if (savedSessionId) {
        resumeSession(savedSessionId);
    }
});

function setupEventListeners() {
    // New game buttons
    elements.newGameBtn.addEventListener('click', startNewGame);
    elements.gameOverNewBtn.addEventListener('click', startNewGame);
    elements.emptyStateNewBtn.addEventListener('click', startNewGame);

    // Send message
    elements.sendBtn.addEventListener('click', sendMessage);
    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Input handling
    elements.messageInput.addEventListener('input', handleInputChange);

    // Mobile menu
    elements.menuToggle.addEventListener('click', toggleSidebar);

    // Close sidebar on outside click (mobile)
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 768 &&
            elements.sidebar.classList.contains('open') &&
            !elements.sidebar.contains(e.target) &&
            !elements.menuToggle.contains(e.target)) {
            elements.sidebar.classList.remove('open');
        }
    });
}

function toggleSidebar() {
    elements.sidebar.classList.toggle('open');
}

// API Calls
async function apiCall(endpoint, options = {}) {
    const fetchOptions = { ...options };

    // Only set Content-Type for requests with a body
    if (options.body) {
        fetchOptions.headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
    }

    const response = await fetch(`${API_BASE}${endpoint}`, fetchOptions);

    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error?.message || `HTTP ${response.status}`);
    }

    return response.json();
}

async function loadSessions() {
    try {
        state.sessions = await apiCall('/game/sessions');
        renderSessions();
    } catch (err) {
        console.error('Failed to load sessions:', err);
    }
}

async function startNewGame() {
    try {
        setLoading(true);
        hideGameOver();
        clearMessages();

        const data = await apiCall('/game/start', { method: 'POST' });

        state.sessionId = data.session_id;
        state.gameState = data.game_state;
        state.score = data.current_score;

        localStorage.setItem('doorman_session_id', state.sessionId);

        addMessage('doorman', data.doorman_message);
        updateScoreDisplay();
        updateGameState();

        await loadSessions();
        highlightActiveSession();

        // Close sidebar on mobile
        if (window.innerWidth <= 768) {
            elements.sidebar.classList.remove('open');
        }
    } catch (err) {
        showError(err.message);
    } finally {
        setLoading(false);
    }
}

async function resumeSession(sessionId) {
    try {
        setLoading(true);
        hideGameOver();
        clearMessages();

        // Load history
        const history = await apiCall(`/game/history/${sessionId}`);

        state.sessionId = history.session_id;
        state.gameState = history.game_state;
        state.score = history.current_score;

        localStorage.setItem('doorman_session_id', state.sessionId);

        // Render all messages
        if (history.messages.length === 0) {
            // No messages yet, show opening line
            const resumeData = await apiCall('/game/resume', {
                method: 'POST',
                body: JSON.stringify({ session_id: sessionId })
            });
            addMessage('doorman', resumeData.doorman_message);
        } else {
            for (const msg of history.messages) {
                addMessage(msg.role, msg.content, msg.score_delta, false);
            }
        }

        updateScoreDisplay();
        updateGameState();
        highlightActiveSession();
        scrollToBottom();

        // Close sidebar on mobile
        if (window.innerWidth <= 768) {
            elements.sidebar.classList.remove('open');
        }
    } catch (err) {
        showError(err.message);
        // If session not found, start new game
        if (err.message.includes('not found')) {
            localStorage.removeItem('doorman_session_id');
        }
    } finally {
        setLoading(false);
    }
}

async function sendMessage() {
    const message = elements.messageInput.value.trim();
    if (!message || !state.sessionId || state.isLoading || state.gameState !== 'active') return;

    try {
        setLoading(true);
        showTypingIndicator();

        // Add user message immediately
        addMessage('user', message);
        elements.messageInput.value = '';
        handleInputChange();

        const data = await apiCall('/game/message', {
            method: 'POST',
            body: JSON.stringify({
                session_id: state.sessionId,
                message: message
            })
        });

        hideTypingIndicator();

        state.score = data.current_score;
        state.gameState = data.game_state;

        // Add doorman response with score delta
        addMessage('doorman', data.doorman_response, data.score_delta);
        updateScoreDisplay(data.score_delta);
        updateGameState();

        await loadSessions();

        // Check for game over
        if (state.gameState !== 'active') {
            showGameOver();
        }
    } catch (err) {
        hideTypingIndicator();
        showError(err.message);
    } finally {
        setLoading(false);
    }
}

// UI Updates
function renderSessions() {
    elements.sessionsList.innerHTML = state.sessions.map(session => `
        <div class="session-item ${session.session_id === state.sessionId ? 'active' : ''}"
             data-session-id="${session.session_id}">
            <div class="session-status">
                <span class="status-badge ${session.game_state}">${session.game_state}</span>
                <span class="session-score">Score: ${session.current_score}</span>
            </div>
            <div class="session-date">${formatDate(session.created_at)} - ${session.message_count} messages</div>
        </div>
    `).join('');

    // Add click handlers
    elements.sessionsList.querySelectorAll('.session-item').forEach(item => {
        item.addEventListener('click', () => {
            const sessionId = item.dataset.sessionId;
            resumeSession(sessionId);
        });
    });
}

function highlightActiveSession() {
    elements.sessionsList.querySelectorAll('.session-item').forEach(item => {
        item.classList.toggle('active', item.dataset.sessionId === state.sessionId);
    });
}

function addMessage(role, content, scoreDelta = null, animate = true) {
    const avatarSrc = role === 'doorman'
        ? '/static/assets/doorman.png'
        : '/static/assets/user.png';

    let scoreHtml = '';
    if (role === 'user' && scoreDelta !== null) {
        const scoreClass = scoreDelta > 0 ? 'positive' : scoreDelta < 0 ? 'negative' : '';
        const scoreSign = scoreDelta > 0 ? '+' : '';
        scoreHtml = `<div class="message-score ${scoreClass}">${scoreSign}${scoreDelta}</div>`;
    }

    const messageEl = document.createElement('div');
    messageEl.className = `message ${role}`;
    if (!animate) messageEl.style.animation = 'none';

    messageEl.innerHTML = `
        <img src="${avatarSrc}" alt="${role}" class="message-avatar">
        <div class="message-content">
            ${escapeHtml(content)}
            ${scoreHtml}
        </div>
    `;

    elements.messages.appendChild(messageEl);
    scrollToBottom();
}

function clearMessages() {
    elements.messages.innerHTML = '';
}

function updateScoreDisplay(delta = null) {
    // Calculate percentage (score range: -50 to 100)
    const range = WIN_THRESHOLD - LOSE_THRESHOLD;
    const adjusted = state.score - LOSE_THRESHOLD;
    const percentage = Math.max(0, Math.min(100, (adjusted / range) * 100));

    elements.scoreFill.style.width = `${percentage}%`;

    let deltaText = '';
    if (delta !== null && delta !== 0) {
        deltaText = ` (${delta > 0 ? '+' : ''}${delta})`;
    }
    elements.scoreText.textContent = `Score: ${state.score}${deltaText}`;
}

function updateGameState() {
    if (!state.sessionId || !state.gameState) {
        // No game started - show empty state, hide input
        elements.emptyState.classList.remove('hidden');
        elements.inputContainer.style.display = 'none';
        elements.gameState.textContent = '';
    } else {
        // Game exists - hide empty state, show input
        elements.emptyState.classList.add('hidden');
        elements.inputContainer.style.display = 'block';

        if (state.gameState === 'active') {
            elements.gameState.textContent = '';
            elements.gameState.style.color = '';
            enableInput();
        } else if (state.gameState === 'won') {
            elements.gameState.textContent = 'YOU WON!';
            elements.gameState.style.color = 'var(--accent-green)';
            disableInput();
        } else if (state.gameState === 'lost') {
            elements.gameState.textContent = 'GAME OVER';
            elements.gameState.style.color = 'var(--accent-red)';
            disableInput();
        }
    }
}

function handleInputChange() {
    const text = elements.messageInput.value;
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;

    elements.wordCount.textContent = `${words}/150 words`;
    elements.wordCount.classList.remove('warning', 'error');

    if (words > 150) {
        elements.wordCount.classList.add('error');
    } else if (words > 120) {
        elements.wordCount.classList.add('warning');
    }

    elements.sendBtn.disabled = !text.trim() || words > 150 || !state.sessionId || state.isLoading || state.gameState !== 'active';

    // Auto-resize textarea
    elements.messageInput.style.height = 'auto';
    elements.messageInput.style.height = Math.min(elements.messageInput.scrollHeight, 120) + 'px';
}

function setLoading(loading) {
    state.isLoading = loading;
    elements.sendBtn.disabled = loading || !elements.messageInput.value.trim() || state.gameState !== 'active';
    elements.messageInput.disabled = loading;
}

function enableInput() {
    elements.inputContainer.style.display = 'block';
    elements.messageInput.disabled = false;
}

function disableInput() {
    elements.messageInput.disabled = true;
}

function showTypingIndicator() {
    elements.typingIndicator.classList.add('visible');
    scrollToBottom();
}

function hideTypingIndicator() {
    elements.typingIndicator.classList.remove('visible');
}

function showGameOver() {
    if (state.gameState === 'won') {
        elements.gameOverTitle.textContent = 'You Got In!';
        elements.gameOverTitle.className = 'won';
        elements.gameOverMessage.textContent = 'Viktor was impressed. Welcome to The Golden Palm.';
    } else {
        elements.gameOverTitle.textContent = 'Denied Entry';
        elements.gameOverTitle.className = 'lost';
        elements.gameOverMessage.textContent = 'Viktor has had enough. Better luck next time.';
    }
    elements.gameOverOverlay.classList.add('visible');
}

function hideGameOver() {
    elements.gameOverOverlay.classList.remove('visible');
}

function showError(message) {
    console.error(message);
    // Could add a toast notification here
    alert(`Error: ${message}`);
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    });
}

// Utilities
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString();
}
