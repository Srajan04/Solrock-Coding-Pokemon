#!/usr/bin/env python3
"""
Solrock Agent - Interactive CLI
Main entry point for the conversational code assistant

Features:
- Interactive REPL with multi-line code support
- Conversation memory across questions
- Structured JSON responses for code tasks
- Session management
- Comprehensive error handling
"""

import sys
import logging

# Configure logging BEFORE importing agent (so basicConfig takes effect first)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

from code_helper_agent import CodeHelperAgent, CodeExplanation, CodeImprovement


def print_banner():
    """Print welcome banner with feature overview"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║             Solrock Agent - LangChain Edition                ║
║                                                              ║
║  Your AI-powered programming assistant with 6 LangChain      ║
║  components: PromptTemplate, LCEL, Memory, Tools,            ║
║  OutputParser, and RunnableWithMessageHistory                ║
╚══════════════════════════════════════════════════════════════╝

✨ Features:
  • Explain code snippets with structured analysis
  • Get code improvement suggestions
  • Ask general programming questions
  • Conversation memory (last 25 messages)
  • Automatic code analysis via ReAct agent

📝 Commands:
  /clear   - Clear conversation memory
  /memory  - View conversation history
  /stats   - Show session statistics
  /quit    - Exit the application
  /code    - Enter multi-line code mode (type 'END' on a new line to finish)
  /debug   - Toggle debug logging

💡 Tips:
  - Paste code directly or use /code for multi-line input
  - Use triple backticks (```) for code blocks
  - Follow-up questions use conversation context
  - Type natural language questions

Type your question or paste code below:
"""
    print(banner)


def print_response(result):
    """
    Pretty-print the agent's response.

    Handles both structured (Pydantic models) and unstructured (string) responses.
    """
    if isinstance(result, str):
        # General Q&A response (unstructured)
        print("\n📝 Answer:")
        print(result)

    elif isinstance(result, CodeExplanation):
        # Structured code explanation
        print("\n📊 Code Explanation:")
        print(f"  Language: {result.language}")
        print(f"  Summary: {result.summary}")
        print(f"\n  Detailed Explanation:\n  {result.detailed_explanation}")
        print(f"\n  Key Concepts: {', '.join(result.key_concepts)}")

    elif isinstance(result, CodeImprovement):
        # Structured code improvement
        print("\n🔧 Code Improvement Suggestions:")
        print(f"\n  Issues Found:")
        for i, issue in enumerate(result.original_issues, 1):
            print(f"    {i}. {issue}")

        print(f"\n  Suggestions:")
        for i, suggestion in enumerate(result.suggestions, 1):
            print(f"    {i}. {suggestion}")

        print(f"\n  Improved Code:")
        print("  " + "\n  ".join(result.improved_code.split("\n")))

        print(f"\n  Explanation: {result.explanation}")

    else:
        # Fallback for unexpected types
        print(f"\n📄 Response: {result}")


def get_multiline_input():
    """Get multi-line code input from user"""
    print("\n📝 Enter your code (type 'END' on a new line to finish):")
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines)


def print_stats(agent: CodeHelperAgent):
    """Print agent usage statistics"""
    stats = agent.get_stats()
    print("\n📊 Session Statistics:")
    print(f"  Active sessions: {stats['active_sessions']}")
    print(f"  Total messages: {stats['total_messages']}")
    if stats["session_ids"]:
        print(f"  Session IDs: {', '.join(stats['session_ids'])}")


def main():
    """Main interactive loop with comprehensive error handling"""
    print_banner()

    # Initialize agent
    try:
        logger.info("Initializing Solrock Agent...")
        agent = CodeHelperAgent()
        print("✅ Agent initialized successfully!\n")
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\n💡 Setup Instructions:")
        print("   1. Install dependencies: pip install -r requirements.txt")
        print("   2. Create .env file: cp .env.example .env")
        print("   3. Add your GITHUB_TOKEN to .env file")
        print("   4. Get a token at: https://github.com/settings/tokens")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Initialization Error: {e}")
        logger.exception("Detailed error:")
        sys.exit(1)

    session_id = "cli-session"
    debug_mode = False

    # Main REPL loop
    print("🤖 Ready! Type your first question or command.\n")

    while True:
        try:
            # Get user input
            print("=" * 70)
            user_input = input("\n💬 You: ").strip()

            # Handle empty input
            if not user_input:
                continue

            # Handle commands
            if user_input.lower() == "/quit":
                print("\n👋 Goodbye! Happy coding!\n")
                break

            elif user_input.lower() == "/clear":
                agent.clear_memory(session_id=session_id)
                print("\n✅ Memory cleared! Starting fresh conversation.")
                continue

            elif user_input.lower() == "/stats":
                print_stats(agent)
                continue

            elif user_input.lower() == "/memory":
                memory_display = agent.get_formatted_memory(session_id=session_id)
                print(f"\n{memory_display}")
                continue

            elif user_input.lower() == "/debug":
                debug_mode = not debug_mode
                level = logging.DEBUG if debug_mode else logging.WARNING
                logging.getLogger().setLevel(level)
                print(f"\n🐛 Debug mode: {'ON' if debug_mode else 'OFF'}")
                continue

            elif user_input.lower() == "/code":
                user_input = get_multiline_input()
                if not user_input.strip():
                    print("\n⚠️  No code entered. Try again.")
                    continue

            elif user_input.lower() == "/help":
                print("\n📖 Help:")
                print("  /clear   - Clear conversation memory")
                print("  /memory  - View conversation history")
                print("  /stats   - Show session statistics")
                print("  /code    - Enter multi-line code mode")
                print("  /debug   - Toggle debug logging")
                print("  /help    - Show this help message")
                print("  /quit    - Exit the application")
                continue

            # Check for triple backtick code blocks
            elif user_input.startswith("```"):
                print(
                    "\n📝 Multi-line code detected. Continue pasting (type '```' to end):"
                )
                lines = [user_input]
                while True:
                    line = input()
                    lines.append(line)
                    if line.strip() == "```":
                        break
                user_input = "\n".join(lines)

            # Process with agent
            try:
                print("\n⏳ Processing...", end="", flush=True)
                result = agent.run(user_input, session_id=session_id)
                print("\r✅ Complete!      ")
                print_response(result)

            except ValueError as e:
                # Input validation error
                print(f"\n❌ Invalid Input: {e}")
                print("💡 Please provide a valid question or code snippet.")

            except RuntimeError as e:
                # Agent execution error
                print(f"\n❌ Processing Error: {e}")
                print("💡 Suggestions:")
                print("   - Check your internet connection")
                print("   - Verify your GITHUB_TOKEN is valid")
                print("   - Try rephrasing your question")
                if debug_mode:
                    logger.exception("Detailed error:")

            except Exception as e:
                # Unexpected error
                print(f"\n❌ Unexpected Error: {e}")
                print("💡 Try /clear to reset or /quit to exit")
                if debug_mode:
                    logger.exception("Detailed error:")

        except KeyboardInterrupt:
            print(
                "\n\n👋 Interrupted! Type /quit to exit or press Enter to continue.\n"
            )
            continue

        except EOFError:
            print("\n\n👋 Goodbye! (EOF received)\n")
            break

    # Cleanup and exit
    try:
        final_stats = agent.get_stats()
        print(
            f"\n📊 Final Stats: {final_stats['total_messages']} messages in this session"
        )
    except:
        pass


if __name__ == "__main__":
    main()
