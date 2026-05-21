"""Minimal pycaw shim for Linux testing environments.
This provides a `AudioUtilities` namespace with stub methods used in tests.
"""
class AudioUtilities:
    @staticmethod
    def GetSpeakers():
        return None
