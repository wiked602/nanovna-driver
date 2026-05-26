@echo off
REM Simple script to start the mock LiteVNA TCP server
REM Usage: run_mock_litevna.bat [PORT]

set PORT=%1
if "%PORT%"=="" set PORT=12346

echo Starting mock LiteVNA server on port %PORT%...
python mock_litevna.py --port %PORT% --verbose