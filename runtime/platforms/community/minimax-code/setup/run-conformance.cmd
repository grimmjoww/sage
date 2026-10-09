@echo off
REM Runs Sage's own conformance suite for this platform and reports a single
REM ASCII marker.
REM
REM Why a .cmd shim: gate-check executes CHECK lines through cmd.exe, whose
REM /s flag mangles a command that BEGINS with a quoted path — and the Git
REM Bash location ("C:\Program Files\Git\bin\bash.exe") has a space in it. The
REM quoting is done here, where it is unambiguous, instead of in GATES.md.
REM
REM The marker is derived from the suite's EXIT CODE, not from grepping its
REM prose. Parsing coloured output for a word is how a gate passes for the
REM wrong reason.
setlocal
set BASH=C:\Program Files\Git\bin\bash.exe
set REPO=C:/Users/willi/Documents/GitHub/sage

"%BASH%" -c "cd %REPO% && develop/conformance/run-conformance.sh minimax-code --level 1,3" 2>&1
set RC=%ERRORLEVEL%

if "%RC%"=="0" (
  echo CONFORMANCE_PASS
) else (
  echo CONFORMANCE_FAIL rc=%RC%
)
endlocal
