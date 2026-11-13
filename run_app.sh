#!/bin/bash
export PATH="/usr/local/bin:/root/.local/bin:$PATH"

# Auto-link pip/pip3 if installed in /root/.local/bin
if [ -f /root/.local/bin/pip3 ] && [ ! -f /usr/local/bin/pip3 ]; then
    ln -sf /root/.local/bin/pip3 /usr/local/bin/pip3 2>/dev/null || true
    ln -sf /root/.local/bin/pip /usr/local/bin/pip 2>/dev/null || true
fi

# Auto-install dependencies if running in a fresh container
if ! python3 -c "import flask, flask_sqlalchemy, flask_wtf, openpyxl" 2>/dev/null; then
    echo "[AI Studio] Installing Python dependencies..."
    if ! command -v pip3 &>/dev/null && ! command -v pip &>/dev/null; then
        if [ -f "get-pip.py" ]; then
            python3 get-pip.py --user
            ln -sf /root/.local/bin/pip3 /usr/local/bin/pip3 2>/dev/null || true
            ln -sf /root/.local/bin/pip /usr/local/bin/pip 2>/dev/null || true
        fi
    fi
    if command -v pip3 &>/dev/null; then
        pip3 install --user Flask Werkzeug openpyxl Flask-SQLAlchemy Flask-Migrate SQLAlchemy Flask-WTF
    elif [ -f /root/.local/bin/pip ]; then
        /root/.local/bin/pip install --user Flask Werkzeug openpyxl Flask-SQLAlchemy Flask-Migrate SQLAlchemy Flask-WTF
    fi
fi

echo "[AI Studio] Starting Python Flask application on port 3000..."
exec python3 app.py
