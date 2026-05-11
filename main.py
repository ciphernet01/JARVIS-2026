"""
JARVIS Application Entry Point
Modern, modular startup script
"""

import sys
import logging
import argparse
import os
from pathlib import Path

# Load environment variables from .env first (before any LLM imports)
from dotenv import load_dotenv

project_env = Path(__file__).resolve().parent / ".env"
if project_env.exists():
    load_dotenv(project_env, override=True)

# Add jarvis-core to path
sys.path.insert(0, str(Path(__file__).parent))

from core import ConfigManager, Assistant
from modules.voice import Synthesizer, Recognizer
from modules.llm import create_llm_manager
from modules.skills import (
    SkillRegistry,
    TimeSkill,
    DateSkill,
    GreetingSkill,
    HelpSkill,
    StatusSkill,
    SkillFactory,
)
from modules.security import SecuritySetup
from modules.persistence import PersistenceFactory
from modules.vision import VisionSetup
from modules.ui import JARVISDashboard
from PyQt5 import QtWidgets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("jarvis.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def setup_voice(config: ConfigManager) -> tuple:
    """Setup voice I/O components"""
    try:
        # Initialize synthesizer
        synthesizer = Synthesizer(
            engine_type=config.voice.engine,
            voice_id=config.voice.voice_id,
        )
        synthesizer.set_rate(config.voice.speech_rate)
        synthesizer.set_volume(config.voice.volume)
        logger.info("Synthesizer initialized")
    except Exception as e:
        logger.warning(f"Synthesizer setup failed: {e}")
        synthesizer = None

    try:
        # Initialize recognizer
        recognizer = Recognizer(
            language=config.voice.recognizer_language,
            timeout=config.voice.recognizer_timeout,
        )
        logger.info("Recognizer initialized")
    except Exception as e:
        logger.warning(f"Recognizer setup failed: {e}")
        recognizer = None

    return synthesizer, recognizer


def setup_skills(registry: SkillRegistry) -> None:
    """Setup built-in skills"""
    skills = [
        GreetingSkill(),
        TimeSkill(),
        DateSkill(),
        HelpSkill(),
        StatusSkill(),
    ]

    for skill in skills:
        registry.register(skill)

    logger.info(f"Registered {len(skills)} built-in skills")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="JARVIS AI Assistant")
    parser.add_argument(
        "--mode",
        choices=["interactive", "web"],
        default="interactive",
        help="Running mode (interactive = CLI, web = FastAPI backend)",
    )
    parser.add_argument(
        "--config",
        help="Path to configuration directory",
    )
    parser.add_argument(
        "--setup-security",
        action="store_true",
        help="Setup security components and exit",
    )

    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("JARVIS AI Assistant Starting Up")
    logger.info("=" * 50)

    try:
        # Initialize configuration
        config = ConfigManager(config_dir=args.config)
        logger.info("Configuration loaded")

        # Setup security components
        logger.info("Initializing security...")
        security_components = SecuritySetup.initialize(
            config_dir=args.config,
            enable_encryption=config.security.enable_encryption,
        )

        if args.setup_security:
            logger.info("Security setup completed")
            print("\nSecurity setup complete!")
            print("- Encryption key generated and stored")
            print("- Credentials vault initialized")
            print("- Auth manager ready")
            print("\nNext: Configure your credentials by:")
            print("1. Copy .env.example to .env")
            print("2. Fill in your API keys and credentials")
            print("3. Run: python main.py --mode interactive")
            return 0

        # Setup persistence layer
        logger.info("Initializing persistence...")
        db_url = os.getenv("JARVIS_DATABASE_URL", "sqlite:///jarvis.db")
        persistence_components = PersistenceFactory.initialize(db_url)

        # Setup vision components
        logger.info("Initializing vision...")
        vision_components = VisionSetup.initialize()

        # Setup voice components
        synthesizer, recognizer = setup_voice(config)

        # Setup skills
        skill_registry = SkillFactory.create_default_registry()

        llm_manager = create_llm_manager(config) if getattr(config, "llm", None) and config.llm.enabled else None

        # Create main assistant
        assistant = Assistant(
            config_manager=config,
            skill_registry=skill_registry,
            synthesizer=synthesizer,
            recognizer=recognizer,
            llm_manager=llm_manager,
            security_components=security_components,
            persistence_components=persistence_components,
        )

        logger.info(f"Running in {args.mode} mode")

        # Set user context
        assistant.set_user_context("user_name", "Shrey")
        assistant.set_user_context("start_time", __import__("datetime").datetime.now())
        assistant.set_current_user("shrey_ceo")
        assistant.set_user_context("security", security_components)
        assistant.set_user_context("persistence", persistence_components)
        assistant.set_user_context("vision", vision_components)
        assistant.set_user_context("user_id", "default_user")

        # Add a simple callback
        def on_response(text):
            logger.info(f"Response: {text}")

        assistant.add_response_callback(on_response)

        # Run based on mode
        if args.mode == "web":
            logger.info("Starting JARVIS FastAPI backend...")
            PersistenceFactory.shutdown(persistence_components)
            import uvicorn

            host = os.getenv("JARVIS_HOST", "0.0.0.0")
            port = int(os.getenv("JARVIS_BACKEND_PORT", "8001"))
            print("\n" + "=" * 55)
            print("  JARVIS Backend API is online")
            print(f"  API      -> http://localhost:{port}")
            print("  Frontend -> http://localhost:3000")
            print("=" * 55 + "\n")
            uvicorn.run("backend.server:app", host=host, port=port)
        else:
            assistant.interactive_mode()

        # Save conversation history
        history = assistant.get_conversation_history()
        if history:
            logger.info(f"Conversation ended with {len(history)} messages")

        PersistenceFactory.shutdown(persistence_components)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1

    logger.info("JARVIS shutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
