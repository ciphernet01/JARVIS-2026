"""
Agent Tools for JARVIS
Shell, file system, code execution, and web access.
Each tool returns a dict with: success, output, error.
"""

from .shell import run_shell
from .files import write_file, read_file, list_directory
from .code_runner import run_python, run_node
from .web import search_web, fetch_url

__all__ = [
    "run_shell",
    "write_file",
    "read_file",
    "list_directory",
    "run_python",
    "run_node",
    "search_web",
    "fetch_url",
]
