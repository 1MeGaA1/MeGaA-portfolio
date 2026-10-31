"""Vortex Client - the locked kiosk shell that runs on every gaming PC.

A WebView2 window (through pywebview) shows ui/index.html; this package does the
parts a web page cannot: talk to the server, block Windows shortcuts, launch and
track games, and re-lock the PC when the server says the session is over.
"""

__version__ = "0.1.0"
