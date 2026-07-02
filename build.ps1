# build.ps1 — Genera SKU_Generator.exe listo para distribuir
# Ejecutar desde la carpeta sku_manager:  .\build.ps1

$ErrorActionPreference = "Stop"

Write-Host "Instalando PyInstaller..." -ForegroundColor Cyan
venv\Scripts\pip install pyinstaller --quiet

Write-Host "Construyendo ejecutable..." -ForegroundColor Cyan

venv\Scripts\pyinstaller `
    --onefile `
    --windowed `
    --name "SKU_Generator" `
    --add-data "config.example.json;." `
    --add-data "latest_version.json;." `
    --hidden-import "sqlalchemy.dialects.sqlite" `
    --hidden-import "sqlalchemy.pool.impl" `
    --hidden-import "sqlalchemy.sql.default_comparator" `
    --hidden-import "babel.numbers" `
    main.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Listo! El ejecutable está en:" -ForegroundColor Green
    Write-Host "  dist\SKU_Generator.exe" -ForegroundColor Green
    Write-Host ""
    Write-Host "Pasos para publicar una nueva version:" -ForegroundColor Yellow
    Write-Host "  1. Actualizá version.py con el nuevo numero"
    Write-Host "  2. Actualizá latest_version.json con la nueva version y URL del release"
    Write-Host "  3. Corré este script para generar el .exe"
    Write-Host "  4. En GitHub: crear un nuevo Release, subir dist\SKU_Generator.exe"
    Write-Host "  5. git add version.py latest_version.json && git push"
} else {
    Write-Host "Error al construir el ejecutable." -ForegroundColor Red
    exit 1
}
