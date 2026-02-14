"""
Solrock Agent - LangChain-based conversational code assistant
Uses GitHub Models (openai/gpt-4o-mini) with 6 LangChain components

This module implements a sophisticated code helper agent that:
- Explains code snippets with structured outputs
- Suggests code improvements
- Answers general programming questions
- Maintains conversation context across sessions
- Uses LangChain's modern patterns (RunnableWithMessageHistory, LCEL chains)
"""

import os
import re
import time
import logging
from typing import Union
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from langchain_core.tools import tool
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.exceptions import OutputParserException
from langchain_community.chat_message_histories import ChatMessageHistory
from pydantic import BaseModel, Field, ValidationError
from openai import RateLimitError

# Try new import path first, fall back to deprecated if needed
try:
    from langchain.agents import create_react_agent
except ImportError:
    from langgraph.prebuilt import create_react_agent

# Load environment variables
load_dotenv()

# Configure module-level logger (no basicConfig here — leave that to main.py)
logger = logging.getLogger(__name__)

# Suppress noisy third-party loggers
logging.getLogger("langchain_core.callbacks.manager").setLevel(logging.ERROR)
logging.getLogger("langchain_core.tracers").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)


# ============================================================================
# Component 5: Pydantic Output Models (for PydanticOutputParser)
# ============================================================================


class CodeExplanation(BaseModel):
    """Structured output for code explanation"""

    language: str = Field(description="Programming language detected")
    detailed_explanation: str = Field(
        description="Detailed explanation of what the code does"
    )
    key_concepts: list[str] = Field(description="List of key programming concepts used")


class CodeImprovement(BaseModel):
    """Structured output for code improvement suggestions"""

    original_issues: list[str] = Field(description="Issues found in the original code")
    suggestions: list[str] = Field(description="Specific improvement suggestions")
    improved_code: str = Field(description="The improved version of the code")
    explanation: str = Field(description="Explanation of the improvements made")


# ============================================================================
# Component 4: Custom Tool - analyze_code
# ============================================================================


@tool
def analyze_code(code: str) -> str:
    """
    Analyze code and return metadata like line count, function/class counts, and detected language.

    This tool performs static analysis on code snippets to extract structural information
    that can help with understanding and explaining code.

    Args:
        code: The code snippet to analyze

    Returns:
        A formatted string with code analysis metadata
    """
    lines = code.strip().split("\n")
    line_count = len(lines)

    # Detect language based on common patterns
    language = "unknown"
    if "def " in code or "import " in code or "class " in code:
        language = "Python"
    elif "function" in code or "const " in code or "let " in code or "=>" in code:
        language = "JavaScript"
    elif "public class" in code or "private " in code or "void " in code:
        language = "Java"
    elif "#include" in code or "int main" in code:
        language = "C/C++"

    # Count functions and classes (simplified patterns)
    function_count = len(re.findall(r"\bdef\s+\w+|function\s+\w+|fn\s+\w+", code))
    class_count = len(re.findall(r"\bclass\s+\w+", code))

    # Calculate basic complexity hints
    complexity_hints = []
    if line_count > 50:
        complexity_hints.append("Large code block (>50 lines)")
    if code.count("for ") + code.count("while ") > 3:
        complexity_hints.append("Multiple loops detected")
    if code.count("if ") > 5:
        complexity_hints.append("High branching complexity")

    result = f"""Code Analysis:
- Language: {language}
- Lines: {line_count}
- Functions: {function_count}
- Classes: {class_count}
- Complexity hints: {", ".join(complexity_hints) if complexity_hints else "Simple structure"}
"""
    return result


# ============================================================================
# Main Agent Class
# ============================================================================


class CodeHelperAgent:
    """
    Conversational Solrock Agent with 6 LangChain components:
    1. PromptTemplate - System and user prompts for different intents
    2. LCEL Chain - Composable chains (prompt | llm | parser)
    3. Memory - ChatMessageHistory managed via RunnableWithMessageHistory
    4. Tool/Agent - analyze_code tool with ReAct agent for code analysis
    5. OutputParser - PydanticOutputParser for structured JSON responses
    6. RunnableWithMessageHistory - Automatic chat history injection per session
    """

    # Valid intent categories
    VALID_INTENTS = {"code_explanation", "code_improvement", "general_question"}

    # Memory window size (number of messages, not turns)
    MEMORY_WINDOW_SIZE = 25  # Increased from 10 to 25 for better context retention

    # Rate limit retry configuration
    MAX_RETRIES = 3
    RETRY_DELAYS = [5, 15, 30]  # seconds between retries (exponential backoff)

    def __init__(self, temperature: float = 0.3, max_tokens: int = 2000):
        """
        Initialize the Solrock Agent.

        Args:
            temperature: LLM temperature (0.0-2.0). Lower = more deterministic
            max_tokens: Maximum tokens in LLM response
        """
        logger.info("Initializing Solrock Agent...")

        # Validate environment
        if not os.environ.get("GITHUB_TOKEN"):
            raise ValueError("GITHUB_TOKEN environment variable not set")

        # Component 1: LLM Setup (GitHub Models)
        # Using the correct model name format from GitHub Models documentation
        self.llm = ChatOpenAI(
            base_url="https://models.github.ai/inference",
            model="openai/gpt-4.1-mini",  # Fixed: correct model name format
            api_key=os.environ.get("GITHUB_TOKEN"),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        logger.info(
            f"LLM configured: model=openai/gpt-4o-mini, temperature={temperature}"
        )

        # Component 3 & 6: Session store for RunnableWithMessageHistory
        # Maps session_id -> ChatMessageHistory
        self.store: dict[str, ChatMessageHistory] = {}

        # Component 1: PromptTemplates
        self._setup_prompts()

        # Component 5: Output Parsers
        self._setup_parsers()

        # Component 2: LCEL Chains
        self._setup_chains()

        # Component 4: Agent with Tools
        self._setup_agent()

        logger.info("Solrock Agent initialized successfully")

    def _setup_prompts(self):
        """Setup all prompt templates with chat_history placeholder and examples"""

        # Intent Classifier Prompt (WITH history so it can understand references like "this code")
        self.intent_classifier_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an intent classifier. Analyze the user's input and the conversation history, then classify it into ONE of these categories:
- code_explanation: User wants to understand what code does (including references to previously discussed code)
- code_improvement: User wants suggestions to improve code (including "improve this", "fix this", referencing prior code)
- general_question: User asks a general programming question

IMPORTANT: If the user refers to "this code", "the code", "it", etc., look at the conversation history to understand what they mean.

Examples:
Input: "Explain this code: def foo():" -> code_explanation
Input: "How can I make this faster?" -> code_improvement
Input: "Can you improve this code" (after previously discussing code) -> code_improvement
Input: "What is a decorator?" -> general_question

Respond with ONLY the category name, nothing else.""",
                ),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
            ]
        )

        # Code Explanation Prompt (with chat_history and analysis context)
        self.code_explanation_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a code explanation expert. Explain the provided code clearly and comprehensively.

CRITICAL: You MUST respond with valid JSON following the exact format specified below. Do not include any text outside the JSON structure.

IMPORTANT CONTEXT RULES:
- If the user's current message contains code, explain THAT code.
- If the user's current message references "this code", "the code above", etc. WITHOUT including new code, look at the CONVERSATION HISTORY to find the most recently discussed code and explain that.
- If the code provided is incomplete or contains errors, still explain what it attempts to do and note the issues.

If code analysis is provided, use it to enhance your explanation.

{format_instructions}

Remember: Your entire response must be valid JSON with no additional text.""",
                ),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
            ]
        )

        # Code Improvement Prompt (with chat_history and analysis context)
        self.code_improvement_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a code review expert. Analyze the code and provide specific, actionable improvements.

CRITICAL: You MUST respond with valid JSON following the exact format specified below. Do not include any text outside the JSON structure.

IMPORTANT CONTEXT RULES:
- If the user's current message contains code, improve THAT code.
- If the user's current message references "this code", "improve it", "fix this", etc. WITHOUT including new code, look at the CONVERSATION HISTORY to find the most recently discussed code and improve that.
- NEVER invent or fabricate code that wasn't discussed. Only improve code that exists in the current message or conversation history.

Focus on:
- Performance optimizations
- Code readability and maintainability
- Best practices and idioms
- Potential bugs or edge cases
- Fixing syntax errors

If the code is incomplete or contains errors, fix them and explain the fixes.

If code analysis is provided, use it to identify issues.

{format_instructions}

Remember: Your entire response must be valid JSON with no additional text.""",
                ),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
            ]
        )

        # General Q&A Prompt (with chat_history)
        self.general_qa_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a helpful programming assistant. Answer the user's question clearly and concisely.

IMPORTANT: When providing code examples:
- Default to Python unless the user specifically asks about another language
- If the conversation context involves a specific language (e.g., JavaScript, Java), continue using that language
- Only provide code examples in ONE language per response
- Do NOT provide the same example in multiple languages unless explicitly asked

Provide code examples when relevant to illustrate concepts.""",
                ),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
            ]
        )

    def _setup_parsers(self):
        """Setup output parsers for structured responses"""
        self.explanation_parser = PydanticOutputParser(pydantic_object=CodeExplanation)
        self.improvement_parser = PydanticOutputParser(pydantic_object=CodeImprovement)
        self.str_parser = StrOutputParser()

    def _setup_chains(self):
        """Setup LCEL chains with RunnableWithMessageHistory (Component #6)"""

        # Intent Classifier Chain (WITH history so it understands references)
        classify_chain_base = self.intent_classifier_prompt | self.llm | self.str_parser
        self.classify_chain = RunnableWithMessageHistory(
            classify_chain_base,
            self._get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

        # Base chains (prompt | llm | parser)
        explain_chain_base = (
            self.code_explanation_prompt | self.llm | self.explanation_parser
        )
        improve_chain_base = (
            self.code_improvement_prompt | self.llm | self.improvement_parser
        )
        qa_chain_base = self.general_qa_prompt | self.llm | self.str_parser

        # Wrap chains with RunnableWithMessageHistory for automatic history injection
        self.explain_chain = RunnableWithMessageHistory(
            explain_chain_base,
            self._get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

        self.improve_chain = RunnableWithMessageHistory(
            improve_chain_base,
            self._get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

        self.qa_chain = RunnableWithMessageHistory(
            qa_chain_base,
            self._get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

    def _setup_agent(self):
        """Setup ReAct agent with analyze_code tool"""
        tools = [analyze_code]
        self.agent_executor = create_react_agent(self.llm, tools)
        logger.info("ReAct agent configured with analyze_code tool")

    def _get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        """
        Get or create chat history for a session (for RunnableWithMessageHistory).

        Implements memory window truncation to keep only last N messages.
        """
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()

        # Truncate to last N messages to prevent token overflow
        history = self.store[session_id]
        if len(history.messages) > self.MEMORY_WINDOW_SIZE:
            history.messages = history.messages[-self.MEMORY_WINDOW_SIZE :]
            logger.debug(
                f"Truncated session {session_id} to {self.MEMORY_WINDOW_SIZE} messages"
            )

        return history

    def _call_with_retry(self, func, *args, **kwargs):
        """
        Call a function with exponential backoff retry on rate limit errors.
        """
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except RateLimitError:
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAYS[attempt]
                    logger.warning(
                        f"Rate limited (attempt {attempt + 1}/{self.MAX_RETRIES + 1}). "
                        f"Waiting {delay}s before retry..."
                    )
                    time.sleep(delay)
                else:
                    logger.error("Rate limit exceeded after all retries.")
                    raise

    def _use_agent_for_analysis(self, code_snippet: str) -> str:
        """
        Use the ReAct agent to analyze code via the analyze_code tool.

        This properly integrates Component #4 (Agent) into the workflow.
        """
        try:
            # Invoke agent with code analysis request
            result = self.agent_executor.invoke(
                {"messages": [("human", f"Analyze this code:\n{code_snippet}")]}
            )

            # Extract the analysis from agent output
            if isinstance(result, dict) and "messages" in result:
                last_message = result["messages"][-1]
                analysis = (
                    last_message.content
                    if hasattr(last_message, "content")
                    else str(last_message)
                )
                logger.info("Code analysis completed via ReAct agent")
                return analysis

            return "Code analysis unavailable"

        except Exception as e:
            logger.warning(f"Agent analysis failed: {e}")
            # Fallback to direct tool call
            return analyze_code.invoke({"code": code_snippet})

    def _classify_intent(self, user_input: str, session_id: str = "default") -> str:
        """
        Classify user intent with validation and fallback.

        Returns one of: code_explanation, code_improvement, general_question
        """
        try:
            raw_intent = (
                self._call_with_retry(
                    self.classify_chain.invoke,
                    {"input": user_input},
                    config={"configurable": {"session_id": session_id}},
                )
                .strip()
                .lower()
            )
            logger.info(f"Classified intent: {raw_intent}")

            # Validate intent - check if any valid intent is in the response
            for valid_intent in self.VALID_INTENTS:
                if (
                    valid_intent in raw_intent
                    or valid_intent.replace("_", " ") in raw_intent
                ):
                    return valid_intent

            # Fallback logic based on keywords
            if any(
                word in user_input.lower()
                for word in ["explain", "what does", "how does"]
            ):
                logger.warning(
                    f"Unexpected intent '{raw_intent}', falling back to code_explanation"
                )
                return "code_explanation"
            elif any(
                word in user_input.lower()
                for word in ["improve", "better", "optimize", "refactor"]
            ):
                logger.warning(
                    f"Unexpected intent '{raw_intent}', falling back to code_improvement"
                )
                return "code_improvement"
            else:
                logger.warning(
                    f"Unexpected intent '{raw_intent}', falling back to general_question"
                )
                return "general_question"

        except Exception as e:
            logger.error(
                f"Intent classification failed: {e}, defaulting to general_question"
            )
            return "general_question"

    def run(
        self, user_input: str, session_id: str = "default"
    ) -> Union[CodeExplanation, CodeImprovement, str]:
        """
        Main entry point for the agent with comprehensive error handling.

        Args:
            user_input: The user's query or code snippet
            session_id: Session identifier for conversation tracking

        Returns:
            Structured response (CodeExplanation, CodeImprovement) or string

        Raises:
            ValueError: If input is empty or invalid
            RuntimeError: If LLM API fails after retries
        """
        if not user_input or not user_input.strip():
            raise ValueError("Empty input provided")

        logger.info(f"Processing request for session: {session_id}")

        # Config for RunnableWithMessageHistory
        config = {"configurable": {"session_id": session_id}}

        # Step 1: Classify intent with validation
        intent = self._classify_intent(user_input, session_id=session_id)

        # Step 2: Route to appropriate chain based on intent
        # RunnableWithMessageHistory automatically loads/saves chat history
        try:
            if intent == "code_explanation":
                # For code explanation, use agent to analyze first
                logger.info("Using explanation chain")

                # Optionally run code analysis via agent (Component #4 integration)
                # This demonstrates proper use of the ReAct agent
                analysis_context = ""
                if len(user_input) > 20 and any(
                    keyword in user_input.lower()
                    for keyword in ["def ", "function", "class "]
                ):
                    try:
                        analysis_context = self._use_agent_for_analysis(user_input)
                        logger.debug(f"Analysis: {analysis_context[:100]}...")
                    except Exception as e:
                        logger.warning(f"Skipping analysis due to error: {e}")

                # Enhance input with analysis if available
                enhanced_input = user_input
                if analysis_context:
                    enhanced_input = (
                        f"{user_input}\n\n[Code Analysis]:\n{analysis_context}"
                    )

                result = self._call_with_retry(
                    self.explain_chain.invoke,
                    {
                        "input": enhanced_input,
                        "format_instructions": self.explanation_parser.get_format_instructions(),
                    },
                    config=config,
                )

            elif intent == "code_improvement":
                # For code improvement, also use agent analysis
                logger.info("Using improvement chain")

                analysis_context = ""
                if len(user_input) > 20 and any(
                    keyword in user_input.lower()
                    for keyword in ["def ", "function", "class "]
                ):
                    try:
                        analysis_context = self._use_agent_for_analysis(user_input)
                    except Exception as e:
                        logger.warning(f"Skipping analysis due to error: {e}")

                enhanced_input = user_input
                if analysis_context:
                    enhanced_input = (
                        f"{user_input}\n\n[Code Analysis]:\n{analysis_context}"
                    )

                result = self._call_with_retry(
                    self.improve_chain.invoke,
                    {
                        "input": enhanced_input,
                        "format_instructions": self.improvement_parser.get_format_instructions(),
                    },
                    config=config,
                )

            else:  # general_question
                # General question - no structured output needed
                logger.info("Using general Q&A chain")
                result = self._call_with_retry(
                    self.qa_chain.invoke, {"input": user_input}, config=config
                )

            logger.info(
                f"Request processed successfully, result type: {type(result).__name__}"
            )
            return result

        except (ValidationError, OutputParserException) as e:
            # LLM returned invalid JSON or plain text instead of structured format
            error_msg = str(e)
            if "Invalid json output" in error_msg or "JSONDecodeError" in error_msg:
                logger.warning(
                    f"LLM did not return valid JSON. Output: {error_msg[:200]}"
                )
            else:
                logger.error(f"Parsing error: {e}")

            logger.warning("Falling back to general Q&A due to parse error")

            # Fallback to unstructured response
            try:
                # Create a new query that doesn't expect structured output
                fallback_query = f"{user_input}\n\nPlease provide a clear explanation (no JSON formatting needed)."
                result = self.qa_chain.invoke({"input": fallback_query}, config=config)
                logger.info("Fallback successful, returning unstructured response")
                return result
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                # Return a helpful error message instead of crashing
                return f"I apologize, but I encountered an error processing your request. Please try:\n1. Rephrasing your question\n2. Providing more complete code\n3. Using the /clear command to reset the conversation\n\nError details: {str(e)[:100]}"

        except RateLimitError as e:
            logger.error(f"Rate limit error after retries: {e}")
            return (
                "⚠️ **Rate Limit Reached**\n\n"
                "The GitHub Models API is temporarily rate-limited. "
                "Please wait **30-60 seconds** and try again.\n\n"
                "**Tips to avoid this:**\n"
                "- Wait a few seconds between messages\n"
                "- Keep messages concise\n"
                "- Consider using a paid API key for higher limits"
            )

        except Exception as e:
            logger.error(f"Unexpected error in run(): {e}", exc_info=True)
            raise RuntimeError(f"Agent execution failed: {e}") from e

    def clear_memory(self, session_id: str = "default"):
        """
        Clear conversation memory for a specific session.

        Args:
            session_id: The session to clear (defaults to 'default')
        """
        if session_id in self.store:
            self.store[session_id].clear()
            logger.info(f"Cleared memory for session: {session_id}")
        else:
            logger.warning(f"Session {session_id} not found in store")

    def clear_all_sessions(self):
        """Clear all conversation sessions (use with caution)"""
        self.store.clear()
        logger.info("Cleared all session memory")

    def get_memory(self, session_id: str = "default") -> dict:
        """
        Get current memory state for a session.

        Returns:
            Dictionary with 'messages' key containing list of messages
        """
        if session_id in self.store:
            return {"messages": self.store[session_id].messages}
        return {"messages": []}

    def get_formatted_memory(
        self, session_id: str = "default", max_chars: int = 200
    ) -> str:
        """
        Get formatted memory for display in CLI.

        Args:
            session_id: The session to get memory from
            max_chars: Maximum characters to display per message

        Returns:
            Formatted string showing conversation history
        """
        memory = self.get_memory(session_id)
        messages = memory.get("messages", [])

        if not messages:
            return "No conversation history in this session."

        lines = [f"📝 Conversation History ({len(messages)} messages):"]
        lines.append("")

        for i, msg in enumerate(messages, 1):
            # Determine role
            if hasattr(msg, "type"):
                role = "🤖 Assistant" if msg.type == "ai" else "👤 User"
            else:
                role = "💬 Message"

            # Get content
            if hasattr(msg, "content"):
                content = str(msg.content)
            else:
                content = str(msg)

            # Truncate if too long
            if len(content) > max_chars:
                content = content[:max_chars] + "..."

            # Format message
            lines.append(f"{i}. {role}:")
            lines.append(f"   {content}")
            lines.append("")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        """Get agent usage statistics"""
        return {
            "active_sessions": len(self.store),
            "session_ids": list(self.store.keys()),
            "total_messages": sum(len(hist.messages) for hist in self.store.values()),
        }


# ============================================================================
# Utility Functions
# ============================================================================


def create_agent(temperature: float = 0.3, max_tokens: int = 2000) -> CodeHelperAgent:
    """
    Factory function to create a new agent instance.

    Args:
        temperature: LLM temperature (0.0-2.0)
        max_tokens: Maximum tokens in response

    Returns:
        Configured CodeHelperAgent instance
    """
    return CodeHelperAgent(temperature=temperature, max_tokens=max_tokens)


if __name__ == "__main__":
    # Quick test
    logger.info("Running quick test...")

    try:
        agent = create_agent()

        # Test explanation
        test_code = """
def factorial(n):
    return 1 if n <= 1 else n * factorial(n-1)
"""
        result = agent.run(f"Explain this code:\n{test_code}")
        print(f"\n✅ Test passed! Result type: {type(result).__name__}")
        print(f"Language: {result.language if hasattr(result, 'language') else 'N/A'}")

        # Show stats
        print(f"\nAgent Stats: {agent.get_stats()}")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise
