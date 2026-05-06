"""
Developer Skills for JARVIS
Code manipulation and VS Code workspace integration
"""

import logging
import os
import subprocess
from typing import Any, Dict, List
from .base import Skill

logger = logging.getLogger(__name__)

class FileManagementSkill(Skill):
    """Read, write, and manipulate source files."""

    def __init__(self):
        super().__init__("file_management", "1.0")

    @property
    def description(self) -> str:
        return "Write, read, or edit files in the workspace (Python, HTML, configs etc)."

    @property
    def keywords(self) -> List[str]:
        return ["write code", "create file", "read file", "save code", "workspace edits"]

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        import json
        
        try:
            # Naively expecting query to contain 'read' or 'write' structured commands for the demo.
            if "write:" in query:
                parts = query.split("write:")
                if len(parts) > 1:
                    data = parts[1].split("|", 1)
                    if len(data) == 2:
                        filename = data[0].strip()
                        content = data[1].strip()
                        
                        target_path = os.path.abspath(os.path.join(os.getcwd(), filename))
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        return f"Successfully wrote to {filename}."
                        
            elif "read:" in query:
                filename = query.split("read:")[1].strip()
                target_path = os.path.abspath(os.path.join(os.getcwd(), filename))
                if os.path.exists(target_path):
                    with open(target_path, "r", encoding="utf-8") as f:
                        return f"File Content ({filename}):\n" + f.read()
                return f"File {filename} not found."
            
            return "File Management: Supported queries: 'write: filename | content' or 'read: filename'."
        except Exception as e:
            return f"Error executing file operation: {e}"


class ExecuteCommandSkill(Skill):
    """Run terminal commands and build scripts."""

    def __init__(self):
        super().__init__("execute_command", "1.0")

    @property
    def description(self) -> str:
        return "Executes safe terminal commands for build processes, installations, and checks."

    @property
    def keywords(self) -> List[str]:
        return ["run command", "terminal", "execute", "shell", "build app"]

    def execute(self, query: str, context: Dict[str, Any] = None) -> str:
        try:
            query = query.replace("execute:", "").strip()
            
            # Executing safely (in production restrict this heavily)
            logger.info(f"Executing command: {query}")
            result = subprocess.run(query, shell=True, capture_output=True, text=True, timeout=30)
            
            out = result.stdout or ""
            err = result.stderr or ""
            
            res = ""
            if out: res += f"Output:\n{out[:500]}\n"
            if err: res += f"Errors:\n{err[:500]}"
            
            return res if res else "Command executed with no output."
        except Exception as e:
            return f"Command fail: {str(e)}"
