#Requires AutoHotkey v2.0
#SingleInstance Force
SetTitleMatchMode 2

#HotIf WinActive("ahk_exe client.exe")

~w::LogMove("UP")
~d::LogMove("RIGHT")
~s::LogMove("DOWN")
~a::LogMove("LEFT")
~!w::LogMove("UP")
~!d::LogMove("RIGHT")
~!s::LogMove("DOWN")
~!a::LogMove("LEFT")

#HotIf

LogMove(direction) {
    ts := FormatTime(A_Now, "yyyyMMddHHmmss")
    line := "MOVE|ts=" ts "|dir=" direction "`n"
    Loop 3 {
        try {
            FileAppend(line, A_ScriptDir "\cone_events.log", "UTF-8-RAW")
            return
        } catch {
            Sleep 5
        }
    }
}
