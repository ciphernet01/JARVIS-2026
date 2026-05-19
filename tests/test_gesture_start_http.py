import urllib.request
import urllib.parse
import json

# Need a valid token to bypass 401
# Wait, do I have a token? Let's just create a new admin token in the server by patching SESSION_TOKENS temporarily or just let's check the terminal output for the server to see if it threw a 401 or 500 when the frontend started. 
