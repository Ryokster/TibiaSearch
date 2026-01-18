#Requires AutoHotkey v2.0
#SingleInstance Force
SetTitleMatchMode 2

#HotIf WinActive("Tibia")

MButton::Send "{F4}"
!MButton::Send "{F5}"
^MButton::Send "{F6}"
XButton1::Send "{F10}"
$WheelUp::SendEvent "!r"
$WheelDown::Send "!q"

F9::DebugPing()

#HotIf

DebugPing() {
    ToolTip "Script gestartet", 10, 10
    SetTimer () => ToolTip(), -1000
}
