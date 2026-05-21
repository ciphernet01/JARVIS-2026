"""Compatibility shim for Windows `wmi` module used in tests.
Provides a minimal `WMI` class to satisfy imports and basic attribute access.
"""
class WMI:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        def _missing(*a, **k):
            return None
        return _missing
