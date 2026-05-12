"""
JARVIS Phase 2: AI Conversation Engine

Transforms voice commands into intelligent conversations.
Bridges VoiceManager (what user said) with ReActAgent (what JARVIS thinks).
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Callable, Any
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class ConversationRole(Enum):
    """Conversation participant roles."""
    USER = "user"
    ASSISTANT = "jarvis"
    SYSTEM = "system"


@dataclass(frozen=True)
class ConversationMessage:
    """Immutable conversation message."""
    role: ConversationRole
    content: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntentResult:
    """Result of intent extraction."""
    intent: str
    confidence: float  # 0.0-1.0
    entities: Dict[str, Any]
    executable: bool
    requires_confirmation: bool
    explanation: str


@dataclass
class ExecutionResult:
    """Result of command execution."""
    success: bool
    output: str
    error: Optional[str] = None
    duration_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationMemory:
    """
    Manages conversation history and user context.
    Thread-safe with readonly message snapshots.
    """

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._history: List[ConversationMessage] = []
        self._lock = threading.RLock()
        self.user_preferences: Dict[str, Any] = {}
        self.session_start = datetime.now()

    def add_message(
        self,
        role: ConversationRole,
        content: str,
        metadata: Optional[Dict] = None
    ) -> ConversationMessage:
        """Add immutable message to conversation."""
        with self._lock:
            message = ConversationMessage(
                role=role,
                content=content,
                timestamp=datetime.now().isoformat(),
                metadata=metadata or {}
            )
            self._history.append(message)

            # Keep only recent messages
            if len(self._history) > self.max_history:
                self._history = self._history[-self.max_history:]

            logger.debug(f"[MEMORY] {role.value}: {content[:50]}...")
            return message

    def get_history(self, num_messages: int = 10) -> List[ConversationMessage]:
        """Get recent conversation history (snapshot)."""
        with self._lock:
            return self._history[-num_messages:].copy()

    def get_context_string(self, num_messages: int = 10) -> str:
        """Get conversation context as formatted string for LLM."""
        messages = self.get_history(num_messages)
        context = ""
        for msg in messages:
            context += f"{msg.role.value}: {msg.content}\n"
        return context

    def extract_preference(self, key: str, value: Any) -> None:
        """Store user preference for personalization."""
        with self._lock:
            self.user_preferences[key] = value
            logger.debug(f"[MEMORY] Preference updated: {key} = {value}")

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Retrieve stored user preference."""
        with self._lock:
            return self.user_preferences.get(key, default)

    def get_session_duration_minutes(self) -> int:
        """Get conversation session duration."""
        return int((datetime.now() - self.session_start).total_seconds() / 60)

    def clear_history(self) -> None:
        """Clear conversation history (for new session)."""
        with self._lock:
            self._history.clear()
            logger.info("[MEMORY] Conversation history cleared")

    def __len__(self) -> int:
        """Get number of messages in history."""
        with self._lock:
            return len(self._history)


class IntentExtractor:
    """
    Extracts user intent from natural language.
    Uses ReActAgent or LLM for semantic understanding.
    """

    def __init__(self, react_agent=None, llm=None):
        """
        Initialize with optional ReActAgent or LLM backend.
        
        Args:
            react_agent: ReActAgent instance for skill routing
            llm: LLM interface for intent extraction
        """
        self.react_agent = react_agent
        self.llm = llm
        self.known_intents = {
            "INCREASE_VOLUME": ["turn up", "louder", "volume up"],
            "DECREASE_VOLUME": ["turn down", "quieter", "volume down"],
            "QUERY_TIME": ["what time", "current time", "tell me the time"],
            "QUERY_DATE": ["what date", "today", "what's today"],
            "OPEN_APP": ["open", "launch", "start"],
            "INCREASE_BRIGHTNESS": ["brighter", "brightness up", "increase brightness"],
            "DECREASE_BRIGHTNESS": ["darker", "brightness down", "decrease brightness"],
            "TAKE_SCREENSHOT": ["screenshot", "capture screen", "take screenshot"],
            "QUERY_WEATHER": ["weather", "forecast", "raining"],
            "SET_REMINDER": ["remind me", "reminder", "set alarm"],
        }

    async def extract(self, user_text: str, context: str = "") -> IntentResult:
        """
        Extract intent from user input.
        
        Args:
            user_text: User's natural language input
            context: Conversation context for understanding
            
        Returns:
            IntentResult with intent, entities, confidence
        """
        try:
            # Try LLM-based extraction first (more accurate)
            if self.llm:
                return await self._extract_via_llm(user_text, context)

            # Fall back to pattern matching
            return self._extract_via_patterns(user_text)

        except Exception as e:
            logger.error(f"Intent extraction error: {e}")
            return IntentResult(
                intent="OTHER",
                confidence=0.0,
                entities={},
                executable=False,
                requires_confirmation=False,
                explanation=f"Error: {str(e)}"
            )

    async def _extract_via_llm(self, user_text: str, context: str) -> IntentResult:
        """Extract intent using LLM backend."""
        prompt = f"""
Analyze this user request and extract the intent.

Context:
{context}

User request: "{user_text}"

Respond ONLY with valid JSON (no markdown, no extra text):
{{
    "intent": "INTENT_NAME",
    "entities": {{"key": "value"}},
    "confidence": 0.95,
    "executable": true,
    "requires_confirmation": false,
    "explanation": "Why this intent makes sense"
}}

Known intents: {', '.join(self.known_intents.keys())}
"""
        try:
            response = await self.llm.generate(prompt)
            data = json.loads(response)
            return IntentResult(**data)
        except json.JSONDecodeError:
            # Fallback to patterns if JSON parsing fails
            return self._extract_via_patterns(user_text)

    def _extract_via_patterns(self, user_text: str) -> IntentResult:
        """Extract intent using pattern matching (fallback)."""
        user_lower = user_text.lower()

        # Check known patterns
        for intent, patterns in self.known_intents.items():
            for pattern in patterns:
                if pattern in user_lower:
                    return IntentResult(
                        intent=intent,
                        confidence=0.85,
                        entities={"text": user_text},
                        executable=True,
                        requires_confirmation=False,
                        explanation=f"Matched pattern: '{pattern}'"
                    )

        # Unknown intent
        return IntentResult(
            intent="OTHER",
            confidence=0.5,
            entities={"text": user_text},
            executable=False,
            requires_confirmation=False,
            explanation="Intent not recognized"
        )


class SkillExecutor:
    """
    Executes recognized intents using system skills/managers.
    Routes to appropriate OS managers or ReActAgent skills.
    """

    def __init__(self, react_agent=None, managers: Dict = None):
        """
        Initialize with ReActAgent and service managers.
        
        Args:
            react_agent: ReActAgent for complex tasks
            managers: Dict of available managers (audio, camera, power, etc.)
        """
        self.react_agent = react_agent
        self.managers = managers or {}
        self.intent_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register handlers for common intents."""
        self.register("INCREASE_VOLUME", self._handle_increase_volume)
        self.register("DECREASE_VOLUME", self._handle_decrease_volume)
        self.register("QUERY_TIME", self._handle_query_time)
        self.register("QUERY_DATE", self._handle_query_date)

    def register(self, intent: str, handler: Callable) -> None:
        """Register custom handler for an intent."""
        self.intent_handlers[intent] = handler
        logger.debug(f"[SKILLS] Registered handler for: {intent}")

    async def execute(self, intent_result: IntentResult) -> ExecutionResult:
        """Execute action based on extracted intent."""
        try:
            if not intent_result.executable:
                return ExecutionResult(
                    success=False,
                    output="",
                    error=f"Intent not executable: {intent_result.intent}"
                )

            # Check if custom handler exists
            if intent_result.intent in self.intent_handlers:
                handler = self.intent_handlers[intent_result.intent]
                result = await handler(intent_result.entities)
                return result

            # Try ReActAgent for complex tasks
            if self.react_agent:
                result = await self.react_agent.process_input(
                    f"Execute intent: {intent_result.intent} with entities: {intent_result.entities}"
                )
                return ExecutionResult(
                    success=True,
                    output=result.get("text", "Executed"),
                    metadata={"via_react_agent": True}
                )

            # Unknown intent
            return ExecutionResult(
                success=False,
                output="",
                error=f"No handler for intent: {intent_result.intent}"
            )

        except Exception as e:
            logger.error(f"Skill execution error: {e}")
            return ExecutionResult(
                success=False,
                output="",
                error=str(e)
            )

    async def _handle_increase_volume(self, entities: Dict) -> ExecutionResult:
        """Handle volume increase."""
        try:
            audio_mgr = self.managers.get("audio")
            if not audio_mgr:
                return ExecutionResult(
                    success=False,
                    output="",
                    error="Audio manager not available"
                )

            amount = int(entities.get("amount", 10))
            current = audio_mgr.get_volume()
            new_volume = min(100, current + amount)
            audio_mgr.set_volume(new_volume)

            return ExecutionResult(
                success=True,
                output=f"Volume increased to {new_volume}%",
                metadata={"new_volume": new_volume}
            )
        except Exception as e:
            return ExecutionResult(success=False, output="", error=str(e))

    async def _handle_decrease_volume(self, entities: Dict) -> ExecutionResult:
        """Handle volume decrease."""
        try:
            audio_mgr = self.managers.get("audio")
            if not audio_mgr:
                return ExecutionResult(
                    success=False,
                    output="",
                    error="Audio manager not available"
                )

            amount = int(entities.get("amount", 10))
            current = audio_mgr.get_volume()
            new_volume = max(0, current - amount)
            audio_mgr.set_volume(new_volume)

            return ExecutionResult(
                success=True,
                output=f"Volume decreased to {new_volume}%",
                metadata={"new_volume": new_volume}
            )
        except Exception as e:
            return ExecutionResult(success=False, output="", error=str(e))

    async def _handle_query_time(self, entities: Dict) -> ExecutionResult:
        """Handle time query."""
        from datetime import datetime
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        return ExecutionResult(
            success=True,
            output=f"The current time is {time_str}",
            metadata={"time": time_str}
        )

    async def _handle_query_date(self, entities: Dict) -> ExecutionResult:
        """Handle date query."""
        from datetime import datetime
        today = datetime.now()
        date_str = today.strftime("%A, %B %d, %Y")
        return ExecutionResult(
            success=True,
            output=f"Today is {date_str}",
            metadata={"date": date_str}
        )


class AIConversationEngine:
    """
    Main AI conversation engine for JARVIS.
    Orchestrates voice input → understanding → execution → response.
    
    This is the missing piece that makes JARVIS intelligent.
    """

    def __init__(
        self,
        voice_manager=None,
        react_agent=None,
        llm=None,
        managers: Dict = None
    ):
        """
        Initialize AI conversation engine.
        
        Args:
            voice_manager: VoiceManager for voice I/O
            react_agent: ReActAgent for complex reasoning
            llm: LLM interface (optional for intent extraction)
            managers: Dict of available system managers
        """
        self.voice_manager = voice_manager
        self.react_agent = react_agent
        self.llm = llm
        self.managers = managers or {}

        # Core components
        self.memory = ConversationMemory()
        self.intent_extractor = IntentExtractor(react_agent, llm)
        self.skill_executor = SkillExecutor(react_agent, managers)

        # Callbacks
        self._response_callbacks: List[Callable] = []

        logger.info("[AI] Conversation engine initialized")

    def register_response_callback(self, callback: Callable) -> None:
        """Register callback for responses (for UI updates, etc.)."""
        self._response_callbacks.append(callback)

    async def process_voice_input(
        self,
        voice_text: str,
        confidence: float = 0.85
    ) -> str:
        """
        End-to-end voice command processing.
        
        Voice → Understanding → Execution → Response → TTS
        
        Args:
            voice_text: Raw text from speech recognition
            confidence: Confidence score from voice recognition
            
        Returns:
            Response text to speak to user
        """
        logger.info(f"[AI] Processing: '{voice_text}' (confidence: {confidence:.2%})")

        # 1. Check confidence threshold
        if confidence < 0.6:
            response = "I didn't catch that clearly. Could you repeat it?"
            self.memory.add_message(ConversationRole.SYSTEM, response)
            await self._fire_callbacks(response)
            return response

        # 2. Add user message to memory
        self.memory.add_message(
            ConversationRole.USER,
            voice_text,
            metadata={"confidence": confidence, "source": "voice"}
        )

        # 3. Extract intent from user input
        context = self.memory.get_context_string(num_messages=5)
        intent_result = await self.intent_extractor.extract(voice_text, context)
        logger.debug(f"[AI] Intent: {intent_result.intent} ({intent_result.confidence:.2%})")

        # 4. Handle confirmation if needed
        if intent_result.requires_confirmation:
            confirmation = f"Just to confirm, you want to {intent_result.explanation}? Say yes or no."
            self.memory.add_message(ConversationRole.ASSISTANT, confirmation)
            await self._fire_callbacks(confirmation)
            return confirmation

        # 5. Execute the recognized intent
        execution_result = await self.skill_executor.execute(intent_result)

        # 6. Generate response
        response = await self._generate_response(
            voice_text,
            intent_result,
            execution_result
        )

        # 7. Add response to memory
        self.memory.add_message(
            ConversationRole.ASSISTANT,
            response,
            metadata={
                "intent": intent_result.intent,
                "execution_success": execution_result.success
            }
        )

        # 8. Fire callbacks
        await self._fire_callbacks(response)

        # 9. Speak response if voice manager available
        if self.voice_manager:
            await self.voice_manager.speak_response(response)

        logger.info(f"[AI] Response: '{response}'")
        return response

    async def _generate_response(
        self,
        user_input: str,
        intent_result: IntentResult,
        execution_result: ExecutionResult
    ) -> str:
        """Generate natural language response to user."""
        # If execution failed
        if not execution_result.success:
            return f"I wasn't able to {intent_result.intent.lower()}. {execution_result.error or 'Something went wrong.'}"

        # If LLM available, generate natural response
        if self.llm:
            prompt = f"""
You are JARVIS, a helpful and friendly OS assistant.
Generate a brief 1-2 sentence response to the user.

User said: "{user_input}"
Intent: {intent_result.intent}
Action result: {execution_result.output}

Keep it conversational and friendly.
"""
            try:
                response = await self.llm.generate(prompt)
                return response.strip()
            except Exception as e:
                logger.warning(f"LLM response generation failed: {e}")

        # Fallback: Use execution result
        return execution_result.output or f"Done. {intent_result.intent.replace('_', ' ').lower()}."

    async def _fire_callbacks(self, response: str) -> None:
        """Call registered response callbacks."""
        for callback in self._response_callbacks:
            try:
                if callable(callback):
                    await callback(response) if hasattr(callback, '__await__') else callback(response)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def process_text_input(self, text: str) -> str:
        """
        Process text input (for chat interface).
        
        Args:
            text: User text input
            
        Returns:
            Response text
        """
        logger.info(f"[AI] Text input: '{text}'")
        return await self.process_voice_input(text, confidence=0.95)

    def get_memory(self) -> ConversationMemory:
        """Get conversation memory (for inspection/debugging)."""
        return self.memory

    def get_context_summary(self) -> Dict[str, Any]:
        """Get current conversation context."""
        return {
            "messages": len(self.memory),
            "duration_minutes": self.memory.get_session_duration_minutes(),
            "user_preferences": self.memory.user_preferences,
            "recent_intents": [
                msg.metadata.get("intent")
                for msg in self.memory.get_history(10)
                if msg.role == ConversationRole.ASSISTANT
            ]
        }


# Singleton instance
_instance = None
_lock = threading.Lock()


def get_conversation_engine(
    voice_manager=None,
    react_agent=None,
    llm=None,
    managers: Dict = None
) -> AIConversationEngine:
    """Get or create AI conversation engine singleton."""
    global _instance
    
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = AIConversationEngine(
                    voice_manager=voice_manager,
                    react_agent=react_agent,
                    llm=llm,
                    managers=managers
                )
    
    return _instance
