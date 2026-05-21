"""Compatibility shim for `comtypes` used on Windows.
Provides `CoInitialize` and `CoUninitialize` no-op functions.
"""
def CoInitialize():
    return None


def CoUninitialize():
    return None
