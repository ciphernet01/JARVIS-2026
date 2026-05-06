import base64
import logging
import io
from PIL import Image

logger = logging.getLogger(__name__)

class VisionSkill:
    """Skill for situational awareness using optical feeds"""
    
    def __init__(self, assistant, performance_manager=None):
        self.assistant = assistant
        self.performance_manager = performance_manager

    def analyze_optical_feed(self, prompt: str = "What do you see in the current view?") -> str:
        """
        Analyze the current camera feed/optical data to describe objects, people, or surroundings.
        This tool requires a recent frame captured from the HUD.
        """
        logger.info(f"Initiating Optical Analysis with prompt: {prompt}")
        
        # Pull the latest frame from the performance buffer
        if not self.performance_manager:
            return "My optical buffers are currently uninitialized, sir."

        latest_frame = self.performance_manager.get("latest_vision_frame")
        
        if not latest_frame:
             return "I'm sorry sir, but my optical sensors are currently recalibrating. Please ensure the HUD camera is active."

        try:
            # We use the assistant's gemini model for the analysis
            import google.generativeai as genai
            
            # Diagnostic: Check frame presence
            if not latest_frame:
                 logger.warning("Optical Feed Error: Frame buffer is empty.")
                 return "I'm sorry sir, but my optical sensors are currently recalibrating. Please ensure the HUD camera is active."

            # Ensure model identifier is correct for vision
            # Use 'gemini-1.5-flash' which is the vision-standard
            model_id = 'models/gemini-1.5-flash'
            logger.info(f"Targeting Vision Engine: {model_id}")
            model = genai.GenerativeModel(model_id)
            
            # Prepare image part
            image_data = base64.b64decode(latest_frame.split(',')[1])
            img = Image.open(io.BytesIO(image_data))
            
            logger.info("Executing Vision Analysis via Gemini...")
            response = model.generate_content([prompt, img])
            logger.info("Vision Analysis completed successfully.")
            return response.text
        except Exception as e:
            logger.error(f"MISSION CRITICAL: Optical analysis failed: {e}", exc_info=True)
            return f"My apologies sir, I encountered a glitch in the optical processing sub-routine: {str(e)}"
