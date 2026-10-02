# pythonanywhere_wsgi.py
import sys
import os

path = '/home/username/WEB'
if path not in sys.path:
    sys.path.append(path)

from app import app as application
