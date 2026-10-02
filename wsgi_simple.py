# wsgi_simple.py
import sys
import os

project_home = '/home/username/WEB'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

from app import app as application
