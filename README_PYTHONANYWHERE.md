# Инструкция по развертыванию на PythonAnywhere

## Шаги для запуска:
1. Загрузите файлы проекта в директорию `/home/<ваш-логин>/WEB`
2. Откройте консоль Bash на PythonAnywhere и выполните:
   ```bash
   cd ~/WEB
   pip install --user -r requirements.txt
   python3 create_users.py
   python3 check_system.py
   ```
3. В разделе **Web** на PythonAnywhere:
   - В поле **Source code** укажите: `/home/<ваш-логин>/WEB`
   - В поле **Working directory** укажите: `/home/<ваш-логин>/WEB`
   - Откройте файл конфигурации **WSGI** (ссылка на странице Web) и вставьте:
     ```python
     import sys
     import os

     path = '/home/<ваш-логин>/WEB'
     if path not in sys.path:
         sys.path.insert(0, path)

     os.chdir(path)

     from app import app as application
     ```
4. Нажмите большую зелёную кнопку **Reload <ваш-логин>.pythonanywhere.com**.
5. Логин администратора: `admin` / Пароль: `admin123`.
