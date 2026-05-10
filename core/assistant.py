"""
Main JARVIS Assistant Class
Orchestrates all modules and manages the conversation flow
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from .config import ConfigManager
from .llm_router import LLMRouter
from .agent import ReActAgent
from modules.memory import MemoryManager
from modules.agent import AgentManager
from modules.tools import (
    run_shell,
    write_file,
    read_file,
    list_directory,
    run_python,
    run_node,
    search_web,
    fetch_url,
)

logger = logging.getLogger(__name__)


class Assistant:
    """Main JARVIS Assistant"""

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        skill_registry: Optional[Any] = None,
        synthesizer: Optional[Any] = None,
        recognizer: Optional[Any] = None,
        llm_manager: Optional[Any] = None,
        security_components: Optional[Dict[str, Any]] = None,
        persistence_components: Optional[Dict[str, Any]] = None,
        performance_manager: Optional[Any] = None,
    ):
        """
        Initialize JARVIS Assistant

        Args:
            config_manager: Configuration manager instance
            skill_registry: Skill registry instance
            synthesizer: Text-to-speech synthesizer
            recognizer: Speech-to-text recognizer
            llm_manager: Optional LLM manager (Ollama or compatible)
            security_components: Security components dict (vault, auth, privacy, etc.)
            persistence_components: Persistence components dict (db, stores, cache)
            performance_manager: Optional performance/cache helper
        """
        self.config = config_manager or ConfigManager()
        self.skill_registry = skill_registry
        self.synthesizer = synthesizer
        self.recognizer = recognizer
        self.llm_manager = llm_manager
        self.security = security_components or {}
        self.persistence = persistence_components or {}
        self.performance_manager = performance_manager
        self.memory = MemoryManager(self.persistence) if self.persistence else None
        self.agent_manager = AgentManager(
            llm_manager=self.llm_manager,
            skill_registry=self.skill_registry,
            persistence_components=self.persistence,
        ) if self.llm_manager and self.skill_registry else None

        # New ReAct agent loop (priority path per copilot instructions)
        self.llm_router: Optional[LLMRouter] = None
        self.react_agent: Optional[ReActAgent] = None
        if getattr(self.config, "llm", None) and self.config.llm.enabled:
            try:
                self.llm_router = LLMRouter(self.config)
                self.react_agent = ReActAgent(
                    llm_router=self.llm_router,
                    tools={
                        "run_shell": run_shell,
                        "write_file": write_file,
                        "read_file": read_file,
                        "list_directory": list_directory,
                        "run_python": run_python,
                        "run_node": run_node,
                        "search_web": search_web,
                        "fetch_url": fetch_url,
                    },
                )
                logger.info("ReActAgent initialized with tool suite")
            except Exception as exc:
                logger.warning(f"ReActAgent initialization failed: {exc}")

        self.is_running = False
        self.conversation_history: list = []
        self.user_context: Dict[str, Any] = {}
        self.on_response_callbacks: list = []
        self.session_token = None
        self.current_user_id: Optional[str] = None

        logger.info("JARVIS Assistant initialized")

    def add_response_callback(self, callback: Callable) -> None:
        """Register a callback for responses"""
        self.on_response_callbacks.append(callback)

    def _log_conversation(self, role: str, text: str) -> None:
        """Log conversation to history"""
        self.conversation_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "role": role,
                "text": text,
            }
        )

    def _build_llm_context(self, user_input: str) -> Dict[str, Any]:
        """Build a compact context payload for Ollama or similar LLMs."""
        recent_history = self.conversation_history[-8:]
        memory_summary = self.get_memory_summary(limit=8)
        available_skills = []
        if self.skill_registry:
            if hasattr(self.skill_registry, "list_skills"):
                try:
                    available_skills = self.skill_registry.list_skills()
                except Exception:
                    available_skills = []
            elif hasattr(self.skill_registry, "skills"):
                skills_obj = getattr(self.skill_registry, "skills", {})
                if isinstance(skills_obj, dict):
                    available_skills = []
                    for name, skill in skills_obj.items():
                        if callable(getattr(skill, "get_info", None)):
                            try:
                                available_skills.append(skill.get_info())
                                continue
                            except Exception:
                                pass
                        available_skills.append({"name": name})

        return {
            "user_input": user_input,
            "user_name": self.user_context.get("user_name", "Sir"),
            "user_id": self.current_user_id,
            "status": self.get_status(),
            "memory_summary": memory_summary,
            "memory_context": self.user_context.get("memory_context", ""),
            "recent_history": recent_history,
            "available_skills": available_skills,
        }

    def _save_conversation_to_persistence(
        self,
        user_input: str,
        response: str,
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        skill_used: Optional[str] = None,
    ) -> None:
        """Persist conversation if the persistence layer is available."""
        if not self.persistence or not self.current_user_id:
            return

        conversation_store = self.persistence.get("conversation_store")
        if not conversation_store:
            return

        try:
            conversation_store.save_conversation(
                user_id=self.current_user_id,
                query=user_input,
                response=response,
                intent=intent,
                confidence=confidence,
                skill_used=skill_used or "unknown",
            )
        except Exception as e:
            logger.warning(f"Failed to save conversation: {e}")

    def _run_agent_sync(self, user_input: str, context: Dict[str, Any]) -> str:
        """Run the async ReAct agent safely from a sync context."""
        if not self.react_agent:
            raise RuntimeError("ReActAgent not initialized")
        try:
            result = asyncio.run(self.react_agent.run(user_input, context))
            return result.answer
        except RuntimeError:
            # Already inside a running event loop (e.g., Jupyter, FastAPI)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, self.react_agent.run(user_input, context))
                return future.result().answer

    async def process_query_async(self, user_input: str) -> str:
        """Async entry point for the ReAct agent (used by FastAPI, etc.)."""
        self._log_conversation("user", user_input)
        logger.info(f"User input: {user_input}")

        if self.memory:
            self.memory.set_current_user(self.current_user_id)
            self.user_context["memory_context"] = self.memory.build_context_block()

        context = self._build_llm_context(user_input)

        if self.react_agent:
            try:
                result = await self.react_agent.run(user_input, context)
                response = result.answer
                self._log_conversation("assistant", response)
                self._save_conversation_to_persistence(
                    user_input,
                    response,
                    intent="agent",
                    confidence=1.0,
                    skill_used="react_agent",
                )
                return response
            except Exception as exc:
                logger.warning(f"ReActAgent failed, falling back to legacy paths: {exc}")

        # Fallback to legacy sync paths wrapped for async callers
        return self._process_input(user_input)

    def _process_input(
        self,
        user_input: str,
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        skill_used: Optional[str] = None,
    ) -> str:
        """
        Process user input and generate response.

        Priority: ReAct agent loop → legacy agent workflow → legacy LLM manager → skill registry.
        """
        self._log_conversation("user", user_input)
        logger.info(f"User input: {user_input}")

        if self.memory:
            self.memory.set_current_user(self.current_user_id)
            self.user_context["memory_context"] = self.memory.build_context_block()

        llm_context = self._build_llm_context(user_input)

        # Priority path: ReAct agent loop (per copilot instructions)
        if self.react_agent:
            try:
                response = self._run_agent_sync(user_input, llm_context)
                self._log_conversation("assistant", response)
                self._save_conversation_to_persistence(
                    user_input,
                    response,
                    intent="agent",
                    confidence=1.0,
                    skill_used="react_agent",
                )
                return response
            except Exception as exc:
                logger.warning(f"ReActAgent failed, falling back to legacy paths: {exc}")

        # Legacy multi-step workflow path
        if self.agent_manager and self.agent_manager.should_plan(user_input):
            try:
                plan = self.agent_manager.build_plan(user_input, llm_context)
                workflow = self.agent_manager.execute_plan(plan, user_input, llm_context)
                response = workflow.get("summary") or "Workflow completed."
                self._log_conversation("assistant", response)
                self._save_conversation_to_persistence(
                    user_input,
                    response,
                    intent="workflow",
                    confidence=1.0,
                    skill_used="agent_workflow",
                )
                return response
            except Exception as exc:
                logger.warning(f"Agent workflow failed, falling back to single-step handling: {exc}")

        # Legacy LLM + skill registry path
        if self.llm_manager:
            plan = self.llm_manager.decide_action(user_input, llm_context) or {}
            plan_type = (plan.get("type") or "answer").lower()
            response = ""

            if plan_type == "skill" and self.skill_registry:
                skill_name = plan.get("skill_name")
                skill_query = plan.get("skill_query") or user_input
                tool_result = None

                if skill_name and hasattr(self.skill_registry, "execute_skill"):
                    tool_result = self.skill_registry.execute_skill(skill_name, skill_query, llm_context)

                if not tool_result:
                    tool_result = self.skill_registry.execute_query(skill_query, llm_context)

                if tool_result:
                    response = self.llm_manager.refine_response(user_input, tool_result, llm_context)
                    if not response:
                        response = tool_result
                else:
                    response = plan.get("response") or "I could not execute the requested action."
            else:
                response = plan.get("response") or self.llm_manager.chat(user_input, llm_context)

            response = response or "I am online, but the local model returned no response."
            self._log_conversation("assistant", response)
            self._save_conversation_to_persistence(
                user_input,
                response,
                intent=plan_type,
                confidence=plan.get("confidence"),
                skill_used=plan.get("skill_name") if plan_type == "skill" else None,
            )
            if self.memory:
                self.memory.set_current_user(self.current_user_id)
            return response

        # Last resort: keyword skill registry
        if not self.skill_registry:
            response = "Skill registry not available"
        else:
            response = self.skill_registry.execute_query(user_input, self.user_context)
            if not response:
                response = f"I'm not sure how to handle that. You said: {user_input}"

        self._log_conversation("assistant", response)
        self._save_conversation_to_persistence(
            user_input,
            response,
            intent=intent,
            confidence=confidence,
            skill_used=skill_used,
        )
        if self.memory:
            self.memory.set_current_user(self.current_user_id)
        return response

    def _emit_response(self, response: str) -> None:
        """Emit response to callbacks"""
        for callback in self.on_response_callbacks:
            try:
                callback(response)
            except Exception as e:
                logger.error(f"Error in response callback: {e}")

    def interactive_mode(self) -> None:
        """
        Run JARVIS in interactive mode (console input)
        Useful for testing without microphone
        """
        logger.info("Starting JARVIS in interactive mode")
        self.is_running = True

        try:
            print("\n" + "=" * 50)
            print("JARVIS AI Assistant - Interactive Mode")
            print("=" * 50)
            print("Type 'exit' or 'quit' to stop\n")

            response = self._process_input("hello")
            if self.synthesizer:
                self.synthesizer.speak(response)
            print(f"JARVIS: {response}\n")

            while self.is_running:
                try:
                    user_input = input("You: ").strip()

                    if not user_input:
                        continue

                    if user_input.lower() in ["exit", "quit", "bye"]:
                        response = "Goodbye! Have a great day."
                        if self.synthesizer:
                            self.synthesizer.speak(response)
                        print(f"JARVIS: {response}")
                        break

                    response = self._process_input(user_input)

                    if self.synthesizer:
                        self.synthesizer.speak(response)

                    print(f"JARVIS: {response}\n")
                    self._emit_response(response)

                except KeyboardInterrupt:
                    print("\n\nShutting down...")
                    break
                except Exception as e:
                    logger.error(f"Error in interactive mode: {e}")
                    print(f"Error: {e}")

        finally:
            self.is_running = False
            logger.info("Interactive mode ended")

    def voice_mode(self) -> None:
        """
        Run JARVIS in voice mode (microphone input)
        Requires working speech recognition
        """
        if not self.recognizer:
            logger.error("Speech recognizer not available")
            print("Error: Speech recognizer not available")
            return

        logger.info("Starting JARVIS in voice mode")
        self.is_running = True

        try:
            print("\nVoice mode started... Listening for commands...")
            response = self._process_input("hello")
            if self.synthesizer:
                self.synthesizer.speak(response)

            while self.is_running:
                try:
                    user_input = self.recognizer.listen_once()

                    if not user_input:
                        continue

                    print(f"You: {user_input}")

                    if user_input.lower() in ["exit", "quit", "bye"]:
                        response = "Goodbye! Have a great day."
                        if self.synthesizer:
                            self.synthesizer.speak(response)
                        break

                    response = self._process_input(user_input)

                    if self.synthesizer:
                        self.synthesizer.speak(response)

                    print(f"JARVIS: {response}\n")
                    self._emit_response(response)

                except KeyboardInterrupt:
                    print("\n\nShutting down...")
                    break
                except Exception as e:
                    logger.error(f"Error in voice mode: {e}")

        finally:
            self.is_running = False
            logger.info("Voice mode ended")

    def stop(self) -> None:
        """Stop the assistant"""
        self.is_running = False
        logger.info("Assistant stopped")

    def get_conversation_history(self) -> list:
        """Get conversation history"""
        return self.conversation_history.copy()

    def clear_conversation_history(self) -> None:
        """Clear conversation history"""
        self.conversation_history.clear()
        logger.info("Conversation history cleared")

    def set_user_context(self, key: str, value: Any) -> None:
        """Set user context"""
        self.user_context[key] = value

        if self.memory and key in {"voice_gender", "speech_rate", "language", "theme"}:
            try:
                self.memory.remember_preference(key, value, self.current_user_id)
            except Exception as e:
                logger.warning(f"Failed to remember preference {key}: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get assistant status"""
        skills_available = 0
        if self.skill_registry:
            if hasattr(self.skill_registry, "skills") and isinstance(self.skill_registry.skills, dict):
                skills_available = len(self.skill_registry.skills)
            elif hasattr(self.skill_registry, "list_skills"):
                try:
                    skills_available = len(self.skill_registry.list_skills())
                except Exception:
                    skills_available = 0

        return {
            "is_running": self.is_running,
            "conversation_count": len(self.conversation_history),
            "skills_available": skills_available,
            "synthesizer_available": self.synthesizer is not None,
            "recognizer_available": self.recognizer is not None,
            "current_user_id": self.current_user_id,
            "persistence_enabled": bool(self.persistence),
            "memory_enabled": self.memory is not None,
            "llm_enabled": self.llm_manager is not None,
            "agent_enabled": self.agent_manager is not None,
            "react_agent_enabled": self.react_agent is not None,
            "llm_router_enabled": self.llm_router is not None,
        }

    def set_current_user(self, user_id: str) -> None:
        """Set current user for persistence"""
        self.current_user_id = user_id
        if self.memory:
            self.memory.set_current_user(user_id)
        logger.info(f"Current user set to: {user_id}")

    def get_conversation_statistics(self) -> Optional[Dict[str, Any]]:
        """Get conversation statistics from persistence"""
        if not self.persistence or not self.current_user_id:
            return None

        conversation_store = self.persistence.get("conversation_store")
        if conversation_store:
            return conversation_store.get_statistics(self.current_user_id)

        return None

    def log_audit_action(self, action: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log action to audit trail"""
        if not self.persistence:
            return

        audit_logger = self.persistence.get("audit_logger")
        if audit_logger:
            audit_logger.log_action(
                user_id=self.current_user_id,
                action=action,
                details=details,
            )

    def get_memory_summary(self, limit: int = 12) -> Optional[Dict[str, Any]]:
        """Get a memory summary for the active user."""
        if not self.memory:
            return None

        self.memory.set_current_user(self.current_user_id)
        return self.memory.summarize_memory(limit=limit)

    def search_memory(self, query: str, limit: int = 10) -> list:
        """Search conversation memory for relevant history."""
        if not self.memory:
            return []

        self.memory.set_current_user(self.current_user_id)
        return self.memory.search_memory(query, limit=limit)

    def remember_user_preference(self, key: str, value: Any) -> bool:
        """Store a user preference in the memory layer."""
        if not self.memory:
            return False

        self.memory.set_current_user(self.current_user_id)
        success = self.memory.remember_preference(key, value)
        if success:
            self.user_context[key] = value
        return success

    def remember_user_preferences(self, preferences: Dict[str, Any]) -> bool:
        """Store multiple user preferences in the memory layer."""
        if not self.memory:
            return False

        self.memory.set_current_user(self.current_user_id)
        success = self.memory.remember_preferences(preferences)
        if success:
            self.user_context.update({k: v for k, v in preferences.items() if v not in (None, "")})
        return success
