#Requires AutoHotkey v2.0
#SingleInstance Force
SetTitleMatchMode 2
#UseHook
SendMode "Event"

#HotIf WinActive("ahk_exe client.exe")

; --- BEGIN HOTKEYS ---
MButton::Send "{F4}"
!MButton::Send "{F5}"
^MButton::Send "{F6}"
XButton1::Send "{F10}"
$WheelUp::SendEvent "!r"
$WheelDown::Send "!q"
; --- END HOTKEYS ---

#HotIf
return
