@echo off
REM Syntax-check bin/sage with bash -n, and print a marker.
REM
REM bin/sage carries two platform-routing fixes (the --platform allowlist and
REM the run_generators default). A syntax error there breaks EVERY platform's
REM init, not just this one, so it is gated.
REM
REM `bash -n` is silent on success, so the command emits its own marker — a
REM gate whose EXPECT could never match is a gate that can never pass.
setlocal
set BASH=C:\Program Files\Git\bin\bash.exe

"%BASH%" -n "C:/Users/willi/Documents/GitHub/sage/bin/sage"
if errorlevel 1 (
  echo BASH_SYNTAX_BAD
) else (
  echo BASH_SYNTAX_OK
)
endlocal
