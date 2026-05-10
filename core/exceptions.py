"""
Custom exceptions for JARVIS AI Assistant
"""


class JARVISException(Exception):
    """Base exception for all JARVIS errors"""
    pass


class ConfigurationError(JARVISException):
    """Raised when configuration is invalid or missing"""
    pass


class VoiceError(JARVISException):
    """Raised when voice processing fails"""
    pass


class SkillError(JARVISException):
    """Raised when a skill fails to execute"""
    pass


class AuthenticationError(JARVISException):
    """Raised when authentication fails"""
    pass


class IntegrationError(JARVISException):
    """Raised when external service integration fails"""
    pass


class PermissionError(JARVISException):
    """Raised when user lacks permission for action"""
    pass


class AgentError(JARVISException):
    """Raised when the ReAct agent loop encounters an error"""
    pass
