# create_deployment_archive.py
import zipfile
import os

def create_archive():
    archive_name = 'cattle_disposal_app.zip'
    with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('.'):
            if '.git' in root or '__pycache__' in root or 'node_modules' in root:
                continue
            for file in files:
                if file == archive_name:
                    continue
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, '.'))
    print(f"Архив {archive_name} успешно создан!")

if __name__ == '__main__':
    create_archive()
