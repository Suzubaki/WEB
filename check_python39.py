# check_python39.py
import sys
print(f"Python Version: {sys.version}")
try:
    import flask
    import werkzeug
    import openpyxl
    print("Flask:", flask.__version__)
    print("Werkzeug:", werkzeug.__version__)
    print("Openpyxl:", openpyxl.__version__)
    print("All packages successfully imported!")
except ImportError as e:
    print("Import error:", e)
