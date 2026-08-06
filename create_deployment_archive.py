#!/usr/bin/env python3
"""
Создание архива для развертывания на PythonAnywhere
"""

import os
import zipfile
import datetime
import shutil

def main():
    print("Создание архива для развертывания на PythonAnywhere")
    print("=" * 60)
    
    # Текущая папка проекта
    project_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Файлы для включения в архив
    required_files = [
        # Основные файлы
        'app.py', 'auth.py', 'database.py', 'config.py',
        'charts.py', 'models.py', 'requirements.txt',
        
        # WSGI файлы
        'pythonanywhere_wsgi.py', 'wsgi_simple.py',
        
        # Скрипты проверки
        'test_pythonanywhere.py', 'check_python39.py',
        
        # Модули отчетов
        'structured_report.py', 'matrix_report.py',
        'report_generator.py', 'generate_original_web.py',
        'fill_original_excel.py',
        
        # Инструкции
        'README_PYTHONANYWHERE.md', 'ФИНАЛЬНАЯ_ИНСТРУКЦИЯ.md',
        'ИТОГ_ПРОЕКТА.md', 'ФАЙЛЫ_ДЛЯ_ЗАГРУЗКИ.txt',
        
        # Скрипты
        'setup_pythonanywhere.sh', 'create_deployment_archive.py',
    ]
    
    # Папки для включения
    required_folders = ['templates', 'static']
    
    # Создаем временную папку
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_dir = os.path.join(project_dir, f'temp_deploy_{timestamp}')
    os.makedirs(temp_dir, exist_ok=True)
    
    print("Копирование файлов...")
    
    # Копируем файлы
    files_copied = 0
    for filename in required_files:
        source_path = os.path.join(project_dir, filename)
        if os.path.exists(source_path):
            shutil.copy2(source_path, os.path.join(temp_dir, filename))
            files_copied += 1
            print(f"  ✅ {filename}")
        else:
            print(f"  ⚠️  {filename} (не найден)")
    
    # Копируем папки
    for folder in required_folders:
        source_path = os.path.join(project_dir, folder)
        if os.path.exists(source_path):
            dest_path = os.path.join(temp_dir, folder)
            shutil.copytree(source_path, dest_path)
            print(f"  ✅ папка {folder}/")
            
            # Считаем файлы в папке
            folder_files = sum([len(files) for _, _, files in os.walk(dest_path)])
            files_copied += folder_files
        else:
            print(f"  ⚠️  папка {folder}/ (не найдена)")
    
    # Создаем папку reports (пустую)
    reports_dir = os.path.join(temp_dir, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    with open(os.path.join(reports_dir, '.gitkeep'), 'w') as f:
        f.write('')
    print(f"  ✅ создана папка reports/")
    
    # Создаем архив
    archive_name = f'livestock_accounting_pythonanywhere_{timestamp}.zip'
    archive_path = os.path.join(project_dir, archive_name)
    
    print(f"\nСоздание архива {archive_name}...")
    
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, arcname)
    
    # Очищаем временную папку
    shutil.rmtree(temp_dir)
    
    # Проверяем размер архива
    archive_size = os.path.getsize(archive_path)
    
    print(f"\n✅ Архив успешно создан!")
    print(f"   Имя: {archive_name}")
    print(f"   Размер: {archive_size / 1024:.1f} КБ")
    print(f"   Файлов скопировано: {files_copied}")
    
    print("\n" + "=" * 60)
    print("ИНСТРУКЦИЯ:")
    print("1. Загрузите архив на PythonAnywhere")
    print("2. Распакуйте в папку /home/Suzubaki/livestock_accounting/")
    print("3. Запустите скрипт настройки:")
    print("   bash setup_pythonanywhere.sh")
    print("4. Следуйте инструкции в ФИНАЛЬНАЯ_ИНСТРУКЦИЯ.md")
    print("=" * 60)
    
    print(f"\n📍 Архив создан по пути:")
    print(f"   {archive_path}")
    
    return archive_path

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()