Option Explicit
Dim fso, shell, base, pythonw, script, installer, cmd, rc
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
base = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = base & "\.venv\Scripts\pythonw.exe"
script = base & "\revisao_web.py"
installer = base & "\instalar.bat"

If Not fso.FileExists(pythonw) Then
  If Not fso.FileExists(installer) Then
    MsgBox "Instalador do Editor de Ensaios nao encontrado: " & installer, vbCritical, "Editor de Ensaios"
    WScript.Quit 1
  End If
  rc = shell.Run(Chr(34) & installer & Chr(34), 1, True)
  If rc <> 0 Or Not fso.FileExists(pythonw) Then
    MsgBox "Nao foi possivel preparar o ambiente Python do Editor de Ensaios.", vbCritical, "Editor de Ensaios"
    WScript.Quit 1
  End If
End If

shell.CurrentDirectory = base
cmd = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & script & Chr(34)
shell.Run cmd, 0, False
