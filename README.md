# Solrock - AI-Powered Code Assistant

A LangChain-based conversational code assistant featuring structured code analysis, improvement suggestions, and interactive programming support through both CLI and web interfaces.

## Overview

Solrock is an intelligent programming assistant built on top of GitHub Models API (GPT-4o-mini) that integrates six core LangChain components to provide comprehensive code assistance. The project demonstrates modern AI application development patterns including prompt templates, LCEL chains, conversation memory, tool integration, structured output parsing, and session management.

## Features

### Core Capabilities
- **Code Explanation**: Detailed analysis of code snippets with structured outputs including language detection, detailed explanations, and key concept identification
- **Code Improvement**: Actionable suggestions for performance optimization, readability enhancements, and bug fixes
- **General Programming Q&A**: Natural language question answering with contextual awareness
- **Conversation Memory**: Maintains context across 25 messages per session for coherent multi-turn interactions
- **ReAct Agent**: Automatic code analysis through tool integration

### Interface Options
- **Command Line Interface**: Interactive REPL with multi-line code support, session management, and debug controls
- **Web Interface**: Modern glassmorphic UI with real-time chat, markdown rendering, and responsive design

## Technical Architecture

### LangChain Components
1. **PromptTemplate**: Context-aware system prompts for intent classification and task routing
2. **LCEL Chains**: Composable chains combining prompts, LLMs, and parsers
3. **Memory**: ChatMessageHistory with windowed retention
4. **Tools/Agent**: ReAct agent with custom code analysis tool
5. **OutputParser**: Pydantic-based structured JSON parsing for type-safe responses
6. **RunnableWithMessageHistory**: Automatic conversation history management

### Technology Stack
- **Framework**: LangChain 0.3+, LangGraph 0.2+
- **LLM Provider**: GitHub Models API (openai/gpt-4o-mini)
- **Web Framework**: Flask 3.0+ with CORS support
- **Data Validation**: Pydantic 2.0+
- **Testing**: pytest with coverage reporting

## Installation

### Prerequisites
- Python 3.10 or higher
- GitHub Personal Access Token with Models API access

### Setup Instructions

1. Clone the repository:
```bash
git clone https://github.com/Srajan04/Solrock-Coding-Pokemon.git
cd Solrock-Coding-Pokemon
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
# Create .env file
echo "GITHUB_TOKEN=your_github_token_here" > .env
```

To obtain a GitHub token:
- Visit https://github.com/settings/tokens
- Generate a new token with appropriate permissions
- Copy the token to your .env file

## Usage

### Command Line Interface

Run the interactive CLI:
```bash
python main.py
```

Available commands:
- `/clear` - Clear conversation memory
- `/memory` - View conversation history
- `/stats` - Show session statistics
- `/code` - Enter multi-line code mode
- `/debug` - Toggle debug logging
- `/quit` - Exit application

### Web Interface

Start the Flask server:
```bash
python app.py
```

Access the web UI at: http://localhost:5000

Features:
- Real-time chat with AI
- Markdown rendering for formatted responses
- Conversation management (clear, view history)
- Session statistics dashboard

## Project Structure

```
.
├── main.py                 # CLI entry point
├── app.py                  # Flask web server
├── code_helper_agent.py    # Core agent implementation
├── requirements.txt        # Python dependencies
└── ui/                     # Web interface assets
    ├── index.html          # Main HTML template
    ├── styles.css          # Glassmorphic styling
    ├── script.js           # Client-side logic
    └── favicon.svg         # Application icon
```

## API Endpoints

### POST /api/chat
Process chat messages with automatic intent classification and structured responses.

**Request:**
```json
{
  "message": "string",
  "session_id": "string"
}
```

**Response:**
```json
{
  "response": "string | object",
  "type": "text | code_explanation | code_improvement",
  "session_id": "string"
}
```

### POST /api/clear
Clear conversation memory for a specific session.

### POST /api/memory
Retrieve conversation history for a session.

### GET /api/stats
Get agent usage statistics across all sessions.

### GET /health
Health check endpoint for monitoring.

## Configuration

### Agent Parameters
Configure in `CodeHelperAgent` initialization:
- `temperature`: Controls response randomness (0.0-2.0, default: 0.3)
- `max_tokens`: Maximum response length (default: 2000)

### Memory Settings
- `MEMORY_WINDOW_SIZE`: Number of messages retained per session (default: 25)
- `MAX_RETRIES`: Rate limit retry attempts (default: 3)
- `RETRY_DELAYS`: Exponential backoff delays in seconds

## Development

### Running Tests
```bash
pytest
pytest --cov=. --cov-report=html
```

### Debug Mode
Enable verbose logging:
```bash
# CLI
/debug command in interactive mode

# Web
Set logging level in app.py
```

## Error Handling

The agent implements comprehensive error handling:
- **Rate Limiting**: Automatic retry with exponential backoff
- **Invalid JSON**: Graceful fallback to unstructured responses
- **Empty Input**: User-friendly validation errors
- **API Failures**: Detailed error messages with recovery suggestions

## License

This project is provided as-is for educational and development purposes.

## Contributing

Contributions are welcome. Please ensure:
- Code follows existing patterns and style
- Tests are included for new features
- Documentation is updated accordingly

## Acknowledgments

Built with LangChain framework and powered by GitHub Models API.
