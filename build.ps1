$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& '.\setup.ps1'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& '.\.venv\Scripts\python.exe' -m pip install pyinstaller
& '.\.venv\Scripts\python.exe' build_ui.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& '.\.venv\Scripts\python.exe' -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm BMS-Korean-Briefing.spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm --onefile --windowed --name BMS-Korean-Briefing-Viewer manual_launcher.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& '.\.venv\Scripts\python.exe' prepare_release.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& '.\.venv\Scripts\python.exe' -m PyInstaller --noconfirm --onefile --windowed --name BMS-Korean-Briefing-Setup --add-data 'payload;payload' installer.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& '.\.venv\Scripts\python.exe' prepare_release.py --package
