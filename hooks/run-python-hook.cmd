: << 'PYBLOCK'
@echo off
REM Cross-platform Python hook wrapper for ieidev-memory
REM Windows: prefers py -3 (most reliable), then python, then python3
REM Unix: the shell interprets this as a script (: is a no-op in bash)

set "SCRIPT=%~1"
if "%SCRIPT%"=="" exit /b 0

set "HOOK_DIR=%~dp0"

REM Primary: py -3 (Windows Python launcher, guaranteed Python 3)
py -3 "%HOOK_DIR%%SCRIPT%" %2 %3 %4 %5 %6 %7 %8 %9
if %ERRORLEVEL% equ 0 exit /b 0

REM Secondary: python (common on most Windows setups)
python "%HOOK_DIR%%SCRIPT%" %2 %3 %4 %5 %6 %7 %8 %9
if %ERRORLEVEL% equ 0 exit /b 0

REM Fallback: python3 (may be Windows Store stub on some systems)
python3 "%HOOK_DIR%%SCRIPT%" %2 %3 %4 %5 %6 %7 %8 %9
exit /b %ERRORLEVEL%

PYBLOCK
# Unix/Mac: use python3 first (standard on modern Unix), fall back to python
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_NAME="$1"
shift
python3 "${SCRIPT_DIR}/${SCRIPT_NAME}" "$@" 2>/dev/null || python "${SCRIPT_DIR}/${SCRIPT_NAME}" "$@"