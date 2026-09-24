; Nmap Studio — Windows installer
;
; Produces NmapStudio-Setup.exe: Start-menu entry, desktop shortcut, an
; uninstaller and an "Apps & features" entry, like any other Windows program.
;
; What it carries is decided at build time by what is present:
;   build\winruntime\   a private Python + PyQt6   -> nothing to install first
;   build\winnmap\      nmap.exe and its data files -> nmap comes with the app
;   dist\NmapStudio.exe a frozen single-file build  -> used instead of the above
;
; Npcap is deliberately NOT bundled: its licence forbids redistribution. It is
; only needed for raw-socket scans (-sS, -O, --traceroute); connect scans,
; version detection and the whole NSE library work without it.

Unicode true
SetCompressor /SOLID lzma

!define APPNAME      "Nmap Studio"
!define COMPANY      "oph  (github.com/op-h)"
!define VERSIONMAJOR 1
!define VERSIONMINOR 0
!define HELPURL      "https://github.com/op-h"
!define UNINSTKEY    "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"

!ifndef ROOT
  !define ROOT ".."
!endif

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "WordFunc.nsh"

Name "${APPNAME}"
OutFile "${ROOT}\dist\NmapStudio-Setup.exe"
InstallDir "$PROGRAMFILES64\${APPNAME}"
InstallDirRegKey HKLM "Software\${APPNAME}" "InstallDir"
RequestExecutionLevel admin

!define MUI_ICON "${ROOT}\nmapgui\assets\icon.ico"
!define MUI_UNICON "${ROOT}\nmapgui\assets\icon.ico"
!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\launch.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Start ${APPNAME}"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Var PythonExe

; ---------------------------------------------------------------- helpers

Function FindPython
  StrCpy $PythonExe ""
  nsExec::ExecToStack 'cmd /c where pythonw.exe'
  Pop $0
  Pop $1
  ${If} $0 == 0
    ${WordFind} "$1" "$\r" "+1{" $2
    StrCpy $PythonExe $2
    Return
  ${EndIf}
  StrCpy $0 ""
  ReadRegStr $0 HKCU "Software\Python\PythonCore\3.13\InstallPath" ""
  ${If} $0 == ""
    ReadRegStr $0 HKCU "Software\Python\PythonCore\3.12\InstallPath" ""
  ${EndIf}
  ${If} $0 == ""
    ReadRegStr $0 HKLM "Software\Python\PythonCore\3.12\InstallPath" ""
  ${EndIf}
  ${If} $0 != ""
    StrCpy $PythonExe "$0pythonw.exe"
  ${EndIf}
FunctionEnd

; ---------------------------------------------------------------- install

Section "Nmap Studio" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"

  File "${ROOT}\README.md"
  File /oname=icon.ico "${ROOT}\nmapgui\assets\icon.ico"

!if /FileExists "${ROOT}\dist\NmapStudio.exe"

  ; ---------- (1) frozen single-file build
  DetailPrint "Installing the self-contained build..."
  File "${ROOT}\dist\NmapStudio.exe"
  FileOpen $0 "$INSTDIR\launch.bat" w
  FileWrite $0 '@echo off$\r$\n'
  FileWrite $0 'start "" "%~dp0NmapStudio.exe" %*$\r$\n'
  FileClose $0
  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" \
                 "$INSTDIR\NmapStudio.exe" "" "$INSTDIR\icon.ico"
  CreateShortcut "$DESKTOP\${APPNAME}.lnk" \
                 "$INSTDIR\NmapStudio.exe" "" "$INSTDIR\icon.ico"

!else

  File "${ROOT}\nmap-studio"
  File "${ROOT}\selftest.py"
  SetOutPath "$INSTDIR\nmapgui"
  File /r /x __pycache__ /x "*.pyc" "${ROOT}\nmapgui\*.*"
  SetOutPath "$INSTDIR"

  !if /FileExists "${ROOT}\build\winruntime\pythonw.exe"

    ; ---------- (2) private Python + PyQt6 travel with the app
    DetailPrint "Installing the bundled Python runtime..."
    SetOutPath "$INSTDIR\runtime"
    File /r "${ROOT}\build\winruntime\*.*"
    SetOutPath "$INSTDIR"
    StrCpy $PythonExe "$INSTDIR\runtime\pythonw.exe"

    FileOpen $0 "$INSTDIR\launch.bat" w
    FileWrite $0 '@echo off$\r$\n'
    FileWrite $0 'start "" "%~dp0runtime\pythonw.exe" "%~dp0nmap-studio" %*$\r$\n'
    FileClose $0

    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" \
                   "$INSTDIR\runtime\pythonw.exe" '"$INSTDIR\nmap-studio"' \
                   "$INSTDIR\icon.ico"
    CreateShortcut "$DESKTOP\${APPNAME}.lnk" \
                   "$INSTDIR\runtime\pythonw.exe" '"$INSTDIR\nmap-studio"' \
                   "$INSTDIR\icon.ico"

  !else

    ; ---------- (3) use the Python already on the machine
    Call FindPython
    ${If} $PythonExe == ""
      MessageBox MB_ICONEXCLAMATION|MB_OK \
        "Python was not found on this computer.$\r$\n$\r$\n\
Nmap Studio will still be installed, but it needs Python 3.10 or newer.$\r$\n\
Install it from python.org (tick 'Add python.exe to PATH'), then run:$\r$\n$\r$\n\
    pip install PyQt6"
      StrCpy $PythonExe "pythonw.exe"
    ${Else}
      nsExec::ExecToStack '"$PythonExe" -c "import PyQt6.QtWidgets"'
      Pop $0
      Pop $1
      ${If} $0 != 0
        MessageBox MB_ICONQUESTION|MB_YESNO \
          "Nmap Studio needs the PyQt6 package, which is not installed.$\r$\n$\r$\n\
Install it now with pip? (needs an internet connection)" IDNO skip_pyqt
          DetailPrint "Installing PyQt6..."
          nsExec::ExecToLog '"$PythonExe" -m pip install PyQt6'
          Pop $0
        skip_pyqt:
      ${EndIf}
    ${EndIf}

    FileOpen $0 "$INSTDIR\launch.bat" w
    FileWrite $0 '@echo off$\r$\n'
    FileWrite $0 'start "" "$PythonExe" "%~dp0nmap-studio" %*$\r$\n'
    FileClose $0

    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" \
                   "$PythonExe" '"$INSTDIR\nmap-studio"' "$INSTDIR\icon.ico"
    CreateShortcut "$DESKTOP\${APPNAME}.lnk" \
                   "$PythonExe" '"$INSTDIR\nmap-studio"' "$INSTDIR\icon.ico"
  !endif
!endif

  ; ---------- nmap itself
!if /FileExists "${ROOT}\build\winnmap\nmap.exe"
  DetailPrint "Installing the bundled nmap..."
  SetOutPath "$INSTDIR\nmap"
  File /r "${ROOT}\build\winnmap\*.*"
  SetOutPath "$INSTDIR"
!else
  nsExec::ExecToStack 'cmd /c where nmap.exe'
  Pop $0
  Pop $1
  ${If} $0 != 0
    IfFileExists "$PROGRAMFILES32\Nmap\nmap.exe" nmap_ok 0
      MessageBox MB_ICONINFORMATION|MB_OK \
        "nmap itself was not found.$\r$\n$\r$\n\
Nmap Studio is the interface — it still needs nmap installed.$\r$\n\
Get it from https://nmap.org/download.html and keep Npcap ticked."
    nmap_ok:
  ${EndIf}
!endif

  CreateShortcut "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk" \
                 "$INSTDIR\uninstall.exe"

  ; ---------- registry: Apps & features
  WriteRegStr   HKLM "Software\${APPNAME}" "InstallDir" "$INSTDIR"
  WriteRegStr   HKLM "${UNINSTKEY}" "DisplayName"     "${APPNAME}"
  WriteRegStr   HKLM "${UNINSTKEY}" "DisplayIcon"     "$INSTDIR\icon.ico"
  WriteRegStr   HKLM "${UNINSTKEY}" "DisplayVersion"  "${VERSIONMAJOR}.${VERSIONMINOR}"
  WriteRegStr   HKLM "${UNINSTKEY}" "Publisher"       "${COMPANY}"
  WriteRegStr   HKLM "${UNINSTKEY}" "HelpLink"        "${HELPURL}"
  WriteRegStr   HKLM "${UNINSTKEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr   HKLM "${UNINSTKEY}" "InstallLocation" "$INSTDIR"
  WriteRegDWORD HKLM "${UNINSTKEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINSTKEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "${UNINSTKEY}" "EstimatedSize" "$0"

  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; ---------- Npcap note, once, at the end
  IfFileExists "$SYSDIR\Npcap\wpcap.dll" npcap_present 0
  IfFileExists "$SYSDIR\wpcap.dll" npcap_present 0
    MessageBox MB_ICONINFORMATION|MB_OK \
      "Nmap Studio is ready to use — nothing else to install.$\r$\n$\r$\n\
One optional extra: SYN scans (-sS), OS detection (-O) and traceroute need \
Npcap, which cannot be redistributed and so is not included.$\r$\n$\r$\n\
Everything else works right now: connect scans, version detection and all \
600+ NSE scripts. To add Npcap later, get it from https://npcap.com"
  npcap_present:
SectionEnd

; -------------------------------------------------------------- uninstall

Section "Uninstall"
  Delete "$INSTDIR\uninstall.exe"
  Delete "$INSTDIR\launch.bat"
  Delete "$INSTDIR\icon.ico"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\NmapStudio.exe"
  Delete "$INSTDIR\nmap-studio"
  Delete "$INSTDIR\selftest.py"
  RMDir /r "$INSTDIR\nmapgui"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\nmap"
  RMDir "$INSTDIR"

  Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
  Delete "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk"
  RMDir  "$SMPROGRAMS\${APPNAME}"
  Delete "$DESKTOP\${APPNAME}.lnk"

  DeleteRegKey HKLM "${UNINSTKEY}"
  DeleteRegKey HKLM "Software\${APPNAME}"

  MessageBox MB_ICONINFORMATION|MB_OK \
    "Nmap Studio has been removed.$\r$\n$\r$\n\
Your scans and settings in %APPDATA%\NmapStudio were kept."
SectionEnd
