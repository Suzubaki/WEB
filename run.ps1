# PowerShell скрипт запуска
Write-Host "========================================================" -ForegroundColor Green
Write-Host " Запуск системы: ОАО «Новая Припять» (Учёт выбытия КРС) " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Green

if (-Not (Test-Path "venv")) {
    Write-Host "[1/3] Создание виртуального окружения Python..." -ForegroundColor Yellow
    python -m venv venv
}

Write-Host "[2/3] Активация окружения и установка зависимостей..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"
pip install -r requirements.txt --quiet

Write-Host "[3/3] Запуск приложения Flask..." -ForegroundColor Green
Write-Host "Откройте браузер по ссылке: http://127.0.0.1:3000" -ForegroundColor Cyan
Write-Host "Учётные записи по умолчанию:" -ForegroundColor White
Write-Host "  - Администратор: admin / admin123" -ForegroundColor Gray
Write-Host "  - Ферма 1:       farm1 / farm123" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Green

python app.py
