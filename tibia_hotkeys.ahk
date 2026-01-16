#Requires AutoHotkey v2.0
#SingleInstance Force
mappingFile := A_ScriptDir "\tibia_hotkeys.map"
eventsFile := A_ScriptDir "\tibia_hotkeys.events"

ReloadMappings() {
    global mappingFile
    if !FileExist(mappingFile)
        return
    for line in StrSplit(FileRead(mappingFile), "`n", "`r") {
        line := Trim(line)
        if (line = "" or SubStr(line, 1, 1) = ";")
            continue
        parts := StrSplit(line, "=>")
        if (parts.Length < 2)
            continue
        hotkey := Trim(parts[1])
        action := Trim(parts[2])
        Hotkey(hotkey, (*) => TriggerAction(action), "On")
    }
}

TriggerAction(action) {
    global eventsFile
    FileAppend(action "`n", eventsFile, "UTF-8")
}

ReloadMappings()
