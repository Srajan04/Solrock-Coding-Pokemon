// ===================================
// CHAT FUNCTIONALITY
// ===================================

const messagesContainer = document.getElementById('messages');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const typingIndicator = document.getElementById('typingIndicator');
const clearBtn = document.getElementById('clearBtn');
const memoryBtn = document.getElementById('memoryBtn');
const statsBtn = document.getElementById('statsBtn');
const attachBtn = document.getElementById('attachBtn');
const tokenCount = document.getElementById('tokenCount');

// Session management
let sessionId = 'web-session-' + Date.now();
let messageHistory = [];

// Auto-resize textarea
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 180) + 'px';

    // Update token counter (rough estimate: 1 token ~ 4 characters)
    const tokens = Math.ceil(this.value.length / 4);
    tokenCount.textContent = tokens;

    if (tokens > 2000) {
        tokenCount.style.color = 'var(--color-rose)';
    } else {
        tokenCount.style.color = 'rgba(255, 255, 255, 0.6)';
    }
});

// Send message on Enter (without Shift)
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Send button click
sendBtn.addEventListener('click', sendMessage);

// ===================================
// SEND MESSAGE
// ===================================

async function sendMessage() {
    const message = userInput.value.trim();

    if (!message) return;

    // Disable input while processing
    userInput.disabled = true;
    sendBtn.disabled = true;

    // Add user message to UI
    addMessage(message, 'user');

    // Clear input
    userInput.value = '';
    userInput.style.height = 'auto';
    tokenCount.textContent = '0';

    // Show typing indicator
    typingIndicator.style.display = 'flex';
    scrollToBottom();

    try {
        // Send to backend
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const data = await response.json();

        // Hide typing indicator
        typingIndicator.style.display = 'none';

        // Add AI response to UI
        addMessage(data.response, 'ai', data.type);

        // Store in history
        messageHistory.push({
            user: message,
            ai: data.response,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        console.error('Error:', error);
        typingIndicator.style.display = 'none';

        // Show error message
        addMessage(
            '**Error**: Unable to connect to the server. Please make sure the backend is running.\n\n' +
            '**To start the server:**\n```bash\npython app.py\n```',
            'ai'
        );
    }

    // Re-enable input
    userInput.disabled = false;
    sendBtn.disabled = false;
    userInput.focus();
}

// ===================================
// ADD MESSAGE TO UI
// ===================================

function addMessage(content, sender, type = 'text') {
    const messageGroup = document.createElement('div');
    messageGroup.className = `message-group ${sender}-message`;

    // Avatar
    const avatar = document.createElement('div');
    avatar.className = `message-avatar ${sender}-avatar`;

    if (sender === 'ai') {
        avatar.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
                <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
    } else {
        avatar.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <circle cx="12" cy="7" r="4" stroke-width="2"/>
            </svg>
        `;
    }

    // Message content
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content glass-panel';

    // Header
    const messageHeader = document.createElement('div');
    messageHeader.className = 'message-header';
    messageHeader.innerHTML = `
        <span class="message-author">${sender === 'ai' ? 'Solrock' : 'You'}</span>
        <span class="message-time">${getTimeString()}</span>
    `;

    // Text content
    const messageText = document.createElement('div');
    messageText.className = 'message-text';

    // Format content based on type
    if (type === 'code_explanation' || type === 'code_improvement') {
        messageText.innerHTML = formatStructuredResponse(content, type);
    } else {
        messageText.innerHTML = formatMarkdown(content);
    }

    messageContent.appendChild(messageHeader);
    messageContent.appendChild(messageText);

    messageGroup.appendChild(avatar);
    messageGroup.appendChild(messageContent);

    messagesContainer.appendChild(messageGroup);
    scrollToBottom();
}

// ===================================
// FORMAT MARKDOWN
// ===================================

function formatMarkdown(text) {
    if (typeof text !== 'string') {
        text = JSON.stringify(text, null, 2);
    }

    // 1. EXTRACT AND HIGHLIGHT CODE BLOCKS
    const codeBlocks = [];
    text = text.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
        const language = lang || 'plaintext';
        let highlightedCode = code;

        // Try to highlight using the library you added
        try {
            if (window.hljs) {
                // Check if the specific language is loaded
                if (lang && hljs.getLanguage(lang)) {
                    highlightedCode = hljs.highlight(code.trim(), { language: lang }).value;
                } else {
                    // Fallback to auto-detection
                    highlightedCode = hljs.highlightAuto(code.trim()).value;
                }
            } else {
                highlightedCode = escapeHtml(code.trim());
            }
        } catch (e) {
            console.warn('Highlight error:', e);
            highlightedCode = escapeHtml(code.trim());
        }

        // Store the HTML safely
        codeBlocks.push(`
            <div class="code-block">
                <div class="code-header">
                    <span class="code-language">${language}</span>
                    <button class="copy-btn" onclick="copyCode(this)">Copy</button>
                </div>
                <pre><code class="hljs ${language}">${highlightedCode}</code></pre>
            </div>
        `);

        // Return a placeholder
        return `__CODE_BLOCK_${codeBlocks.length - 1}__`;
    });

    // 2. FORMAT NORMAL TEXT
    
    // Inline code
    text = text.replace(/`([^`]+)`/g, '<code style="background: rgba(232, 101, 10, 0.1); padding: 2px 5px; border-radius: 3px; color: var(--color-primary); font-family: var(--font-code); font-size: 0.88em;">$1</code>');

    // Bold
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic
    text = text.replace(/\*([^*]+)\*/g, '<em style="color: rgba(255, 255, 255, 0.8);">$1</em>');

    // Headers
    text = text.replace(/^### (.+)$/gm, '<h4 style="font-size: 1rem; margin: 0.75rem 0 0.4rem; color: var(--color-accent-light);">$1</h4>');
    text = text.replace(/^## (.+)$/gm, '<h3 style="font-size: 1.15rem; margin: 0.8rem 0 0.4rem; background: linear-gradient(135deg, var(--color-primary), var(--color-amber)); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">$1</h3>');

    // Lists
    text = text.replace(/^- (.+)$/gm, '<li style="margin-left: 1.2rem; margin-bottom: 0.3rem;">$1</li>');
    text = text.replace(/^(\d+)\. (.+)$/gm, '<li style="margin-left: 1.2rem; margin-bottom: 0.3rem;">$2</li>');

    // Line breaks (convert newlines to <br>)
    text = text.replace(/\n\n/g, '</p><p style="margin-bottom: 0.6rem;">');
    text = text.replace(/\n/g, '<br>');

    // 3. RESTORE CODE BLOCKS
    codeBlocks.forEach((html, index) => {
        text = text.replace(`__CODE_BLOCK_${index}__`, html);
    });

    return '<p style="margin-bottom: 0.6rem;">' + text + '</p>';
}

// ===================================
// FORMAT STRUCTURED RESPONSES
// ===================================

function formatStructuredResponse(data, type) {
    if (type === 'code_explanation') {
        return `
            <h3 style="display:flex;align-items:center;gap:6px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>
                Code Explanation
            </h3>
            <div style="background: rgba(232, 101, 10, 0.1); padding: 0.5rem 0.75rem; border-radius: 6px; margin: 0.5rem 0;">
                <strong style="color: var(--color-primary);">Language:</strong> ${data.language}
            </div>
            <h4>Summary</h4>
            <p>${data.summary}</p>
            <h4>Detailed Explanation</h4>
            <p>${data.detailed_explanation}</p>
            <h4>Key Concepts</h4>
            <ul style="margin-left: 1.2rem;">
                ${data.key_concepts.map(concept => `<li style="margin-bottom: 0.3rem;">${concept}</li>`).join('')}
            </ul>
        `;
    } else if (type === 'code_improvement') {
        return `
            <h3 style="display:flex;align-items:center;gap:6px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>
                Code Improvement
            </h3>
            <h4>Issues Found</h4>
            <ul style="margin-left: 1.2rem;">
                ${data.original_issues.map(issue => `<li style="margin-bottom: 0.3rem; color: var(--color-coral-light);">${issue}</li>`).join('')}
            </ul>
            <h4>Suggestions</h4>
            <ul style="margin-left: 1.2rem;">
                ${data.suggestions.map(suggestion => `<li style="margin-bottom: 0.3rem; color: var(--color-accent-light);">${suggestion}</li>`).join('')}
            </ul>
            <h4>Improved Code</h4>
            <div class="code-block">
                <div class="code-header">
                    <span class="code-language">improved</span>
                    <button class="copy-btn" onclick="copyCode(this)">Copy</button>
                </div>
                <pre><code>${escapeHtml(data.improved_code)}</code></pre>
            </div>
            <p><strong>Explanation:</strong> ${data.explanation}</p>
        `;
    }
    return formatMarkdown(data);
}

// ===================================
// UTILITY FUNCTIONS
// ===================================

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function getTimeString() {
    const now = new Date();
    return now.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });
}

function scrollToBottom() {
    setTimeout(() => {
        messagesContainer.scrollTo({
            top: messagesContainer.scrollHeight,
            behavior: 'smooth'
        });
    }, 100);
}

// Copy code to clipboard
window.copyCode = function(button) {
    const codeBlock = button.closest('.code-block');
    const code = codeBlock.querySelector('code').textContent;

    navigator.clipboard.writeText(code).then(() => {
        const originalText = button.textContent;
        button.textContent = 'Copied!';
        button.style.background = 'var(--color-primary)';
        button.style.color = '#fff';

        setTimeout(() => {
            button.textContent = originalText;
            button.style.background = '';
            button.style.color = '';
        }, 2000);
    });
};

// ===================================
// QUICK ACTIONS
// ===================================

clearBtn.addEventListener('click', async () => {
    if (confirm('Clear all messages? This will start a new conversation.')) {
        try {
            await fetch('/api/clear', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ session_id: sessionId })
            });

            // Clear UI
            messagesContainer.innerHTML = '';
            messageHistory = [];

            // Show confirmation
            addMessage('**Memory cleared!** Starting a fresh conversation.', 'ai');
        } catch (error) {
            console.error('Error clearing memory:', error);
            addMessage('**Error**: Could not clear memory. Please try again.', 'ai');
        }
    }
});

memoryBtn.addEventListener('click', async () => {
    try {
        const response = await fetch('/api/memory', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ session_id: sessionId })
        });

        const data = await response.json();

        let memoryText = '### Conversation Memory\n\n';
        memoryText += `**Session ID:** ${sessionId}\n\n`;
        memoryText += `**Messages in memory:** ${data.message_count}\n\n`;

        if (data.messages && data.messages.length > 0) {
            memoryText += '**Recent messages:**\n\n';
            data.messages.forEach((msg, idx) => {
                const role = msg.type === 'human' ? 'You' : 'AI';
                const content = msg.content.substring(0, 100) + (msg.content.length > 100 ? '...' : '');
                memoryText += `${idx + 1}. **${role}**: ${content}\n\n`;
            });
        } else {
            memoryText += '*No messages in memory yet.*';
        }

        addMessage(memoryText, 'ai');
    } catch (error) {
        console.error('Error fetching memory:', error);
        addMessage('**Error**: Could not fetch memory. Please try again.', 'ai');
    }
});

statsBtn.addEventListener('click', async () => {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        let statsText = '### Session Statistics\n\n';
        statsText += `**Active Sessions:** ${data.active_sessions}\n\n`;
        statsText += `**Total Messages:** ${data.total_messages}\n\n`;
        statsText += `**Current Session:** ${sessionId}\n\n`;

        if (messageHistory.length > 0) {
            statsText += `**Messages in this session:** ${messageHistory.length * 2}\n\n`;
            statsText += `**Session started:** ${new Date(messageHistory[0].timestamp).toLocaleString()}\n\n`;
        }

        addMessage(statsText, 'ai');
    } catch (error) {
        console.error('Error fetching stats:', error);
        addMessage('**Error**: Could not fetch statistics. Please try again.', 'ai');
    }
});

attachBtn.addEventListener('click', () => {
    addMessage('**File attachment** is coming soon! For now, you can paste code directly into the chat.', 'ai');
});

// ===================================
// INITIALIZE
// ===================================

console.log('Solrock Agent initialized');
console.log('Session ID:', sessionId);

// Initialize Lucide icons
lucide.createIcons();

// Focus input on load
userInput.focus();
