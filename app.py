#!/usr/bin/env python3
"""
Flask Web Server for Solrock Agent
Provides a beautiful glassmorphic UI for the chatbot
"""

import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from code_helper_agent import CodeHelperAgent, CodeExplanation, CodeImprovement

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Suppress LangChain warnings
logging.getLogger("langchain_core.callbacks.manager").setLevel(logging.ERROR)
logging.getLogger("langchain_core.tracers").setLevel(logging.ERROR)

# Initialize Flask app
app = Flask(__name__, static_folder="ui", static_url_path="")
CORS(app)

# Initialize Solrock Agent
try:
    agent = CodeHelperAgent(temperature=0.3, max_tokens=2000)
    logger.info("✅ Solrock Agent initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize agent: {e}")
    agent = None


@app.route("/")
def index():
    """Serve the main page"""
    return send_from_directory("ui", "index.html")


@app.route("/<path:path>")
def static_files(path):
    """Serve static files (CSS, JS, etc.)"""
    return send_from_directory("ui", path)


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Handle chat messages from the user

    Request JSON:
        {
            "message": str,
            "session_id": str
        }

    Response JSON:
        {
            "response": str | dict,
            "type": str,  # "text", "code_explanation", "code_improvement"
            "session_id": str
        }
    """
    if not agent:
        return jsonify(
            {
                "error": "Agent not initialized. Please check server logs.",
                "response": "❌ **Error**: The AI agent is not available. Please contact the administrator.",
                "type": "error",
            }
        ), 500

    try:
        data = request.get_json()
        message = data.get("message", "").strip()
        session_id = data.get("session_id", "default")

        if not message:
            return jsonify(
                {
                    "error": "Empty message",
                    "response": "Please provide a message or code snippet.",
                    "type": "error",
                }
            ), 400

        logger.info(f"Processing message from session {session_id}: {message[:50]}...")

        # Process with agent
        result = agent.run(message, session_id=session_id)

        # Format response based on result type
        if isinstance(result, CodeExplanation):
            response_data = {
                "response": {
                    "language": result.language,
                    "detailed_explanation": result.detailed_explanation,
                    "key_concepts": result.key_concepts,
                },
                "type": "code_explanation",
                "session_id": session_id,
            }
        elif isinstance(result, CodeImprovement):
            response_data = {
                "response": {
                    "original_issues": result.original_issues,
                    "suggestions": result.suggestions,
                    "improved_code": result.improved_code,
                    "explanation": result.explanation,
                },
                "type": "code_improvement",
                "session_id": session_id,
            }
        else:
            # General Q&A response (string)
            response_data = {
                "response": str(result),
                "type": "text",
                "session_id": session_id,
            }

        logger.info(f"✅ Response generated (type: {response_data['type']})")
        return jsonify(response_data)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return jsonify(
            {
                "error": str(e),
                "response": f"❌ **Invalid Input**: {str(e)}",
                "type": "error",
            }
        ), 400

    except RuntimeError as e:
        logger.error(f"Runtime error: {e}")
        return jsonify(
            {
                "error": str(e),
                "response": f"❌ **Processing Error**: {str(e)}\n\n**Suggestions:**\n- Check your internet connection\n- Verify your GITHUB_TOKEN is valid\n- Try rephrasing your question",
                "type": "error",
            }
        ), 500

    except Exception as e:
        logger.exception("Unexpected error during chat processing")
        return jsonify(
            {
                "error": str(e),
                "response": "❌ **Unexpected Error**: An error occurred while processing your request. Please try again.",
                "type": "error",
            }
        ), 500


@app.route("/api/clear", methods=["POST"])
def clear_memory():
    """
    Clear conversation memory for a session

    Request JSON:
        {
            "session_id": str
        }

    Response JSON:
        {
            "success": bool,
            "message": str
        }
    """
    if not agent:
        return jsonify({"success": False, "message": "Agent not initialized"}), 500

    try:
        data = request.get_json()
        session_id = data.get("session_id", "default")

        agent.clear_memory(session_id=session_id)
        logger.info(f"✅ Memory cleared for session {session_id}")

        return jsonify(
            {"success": True, "message": f"Memory cleared for session {session_id}"}
        )

    except Exception as e:
        logger.exception("Error clearing memory")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/memory", methods=["POST"])
def get_memory():
    """
    Get conversation memory for a session

    Request JSON:
        {
            "session_id": str,
            "max_chars": int (optional, default=200)
        }

    Response JSON:
        {
            "session_id": str,
            "message_count": int,
            "messages": list[dict]
        }
    """
    if not agent:
        return jsonify({"error": "Agent not initialized", "messages": []}), 500

    try:
        data = request.get_json()
        session_id = data.get("session_id", "default")
        max_chars = data.get("max_chars", 200)

        memory = agent.get_memory(session_id=session_id)
        messages = memory.get("messages", [])

        # Format messages for display
        formatted_messages = []
        for msg in messages:
            msg_type = getattr(msg, "type", "unknown")
            msg_content = getattr(msg, "content", str(msg))
            formatted_messages.append(
                {
                    "type": msg_type,
                    "content": msg_content[:max_chars]
                    + ("..." if len(msg_content) > max_chars else ""),
                }
            )

        logger.info(
            f"✅ Retrieved memory for session {session_id} ({len(messages)} messages)"
        )

        return jsonify(
            {
                "session_id": session_id,
                "message_count": len(messages),
                "messages": formatted_messages,
            }
        )

    except Exception as e:
        logger.exception("Error retrieving memory")
        return jsonify({"error": str(e), "messages": []}), 500


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """
    Get agent statistics

    Response JSON:
        {
            "active_sessions": int,
            "total_messages": int,
            "session_ids": list[str]
        }
    """
    if not agent:
        return jsonify(
            {"active_sessions": 0, "total_messages": 0, "session_ids": []}
        ), 500

    try:
        stats = agent.get_stats()
        logger.info("✅ Stats retrieved")

        return jsonify(stats)

    except Exception as e:
        logger.exception("Error retrieving stats")
        return jsonify(
            {
                "error": str(e),
                "active_sessions": 0,
                "total_messages": 0,
                "session_ids": [],
            }
        ), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy" if agent else "degraded",
            "agent_initialized": agent is not None,
        }
    )


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify(
        {"error": "Not found", "message": "The requested endpoint does not exist"}
    ), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    logger.exception("Internal server error")
    return jsonify(
        {"error": "Internal server error", "message": "An unexpected error occurred"}
    ), 500


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🚀 Solrock Agent - Web UI")
    print("=" * 70)
    print("\n✨ Features:")
    print("  • Glassmorphic UI with 3-tone gradient")
    print("  • Custom animated cursor")
    print("  • Real-time chat with AI")
    print("  • Code explanation & improvement")
    print("  • Conversation memory (25 messages)")
    print("\n📖 Documentation:")
    print("  • Paste code directly or ask questions")
    print("  • Use markdown for formatting")
    print("  • Code blocks are automatically formatted")
    print("\n🔧 Quick Actions:")
    print("  • Clear chat: Click trash icon")
    print("  • View memory: Click eye icon")
    print("  • Statistics: Click chart icon")
    print("\n" + "=" * 70)
    print("\n🌐 Server starting...")
    print("   URL: http://localhost:5000")
    print(f"   Agent Status: {'✅ Ready' if agent else '❌ Not initialized'}")
    print("\n💡 Press Ctrl+C to stop the server\n")

    # Run Flask app
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
