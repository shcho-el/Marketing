' Fallback shortcut maker - no PowerShell required.
' Pure ASCII source; Korean names are built from code points so the file's
' encoding cannot corrupt them.
Option Explicit

Dim sh, fso, root, target, icon, desktop, consoleName, webName, lnk, p
Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root   = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
target = fso.BuildPath(root, "launch.bat")
icon   = fso.BuildPath(root, "assets\obliv.ico")

If Not fso.FileExists(target) Then
  WScript.Echo "launch.bat not found: " & target
  WScript.Quit 1
End If

' "Obliv Content Console" in Korean
consoleName = ChrW(&HC624) & ChrW(&HBE14) & ChrW(&HB9AC) & ChrW(&HBE0C) & " " & _
              ChrW(&HCF58) & ChrW(&HD150) & ChrW(&HCE20) & " " & _
              ChrW(&HCF58) & ChrW(&HC194)
' "Obliv Content Studio (Web)" in Korean
webName = ChrW(&HC624) & ChrW(&HBE14) & ChrW(&HB9AC) & ChrW(&HBE0C) & " " & _
          ChrW(&HCF58) & ChrW(&HD150) & ChrW(&HCE20) & " " & _
          ChrW(&HC0DD) & ChrW(&HC131) & ChrW(&HAE30) & " (" & ChrW(&HC6F9) & ")"

desktop = sh.SpecialFolders("Desktop")
If desktop = "" Or Not fso.FolderExists(desktop) Then
  desktop = fso.BuildPath(sh.ExpandEnvironmentStrings("%USERPROFILE%"), "Desktop")
End If
If Not fso.FolderExists(desktop) Then
  WScript.Echo "Desktop folder not found."
  WScript.Quit 1
End If

p = fso.BuildPath(desktop, consoleName & ".lnk")
Set lnk = sh.CreateShortcut(p)
lnk.TargetPath = target
lnk.WorkingDirectory = root
lnk.Description = "Obliv content console"
lnk.WindowStyle = 7
If fso.FileExists(icon) Then lnk.IconLocation = icon & ",0"
lnk.Hotkey = "CTRL+ALT+O"
lnk.Save

WScript.Echo ""
WScript.Echo "  Created: " & p
WScript.Echo "  Hotkey:  Ctrl + Alt + O"

' Browser shortcut
Dim url, envPath, ts, line, f
url = "https://claude.ai/code/artifact/0a65c72b-d85f-41bf-8c00-ea62ba8c0ec2"
envPath = fso.BuildPath(root, ".env")
If fso.FileExists(envPath) Then
  Set ts = fso.OpenTextFile(envPath, 1)
  Do Until ts.AtEndOfStream
    line = Trim(ts.ReadLine)
    If Left(line, 11) = "WEBAPP_URL=" Then url = Trim(Mid(line, 12))
  Loop
  ts.Close
End If

If Left(LCase(url), 4) = "http" Then
  p = fso.BuildPath(desktop, webName & ".url")
  Set f = fso.CreateTextFile(p, True)
  f.WriteLine "[InternetShortcut]"
  f.WriteLine "URL=" & url
  If fso.FileExists(icon) Then
    f.WriteLine "IconFile=" & icon
    f.WriteLine "IconIndex=0"
  End If
  f.Close
  WScript.Echo "  Created: " & p
End If
WScript.Echo ""
