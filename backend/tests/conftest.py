import pytest
import os
import requests

# By default skip backend integration tests unless SKIP_BACKEND_INTEGRATION=0
if os.environ.get('SKIP_BACKEND_INTEGRATION', '1') != '0':
    pytest.skip("Skipping backend integration tests by default (set SKIP_BACKEND_INTEGRATION=0 to enable)", allow_module_level=True)

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', os.environ.get('JARVIS_TEST_BACKEND_URL', 'http://127.0.0.1:8001')).rstrip('/')
