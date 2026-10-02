# Инструкция по развертыванию на PythonAnywhere

## Шаги для запуска:
1. Загрузите файлы проекта в директорию `/home/username/WEB`
2. Откройте консоль Bash и выполните:
   ```bash
   pip install --user Flask==2.3.3 Werkzeug==2.3.7 openpyxl==3.1.2
   python3 create_users.py
   ```
3. В разделе Web на PythonAnywhere настройте WSGI файл (укажите путь к проекту и импортируйте `app as application`).
4. Нажмите **Reload**.
