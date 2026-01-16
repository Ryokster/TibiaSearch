#Requires AutoHotkey v2.0
#SingleInstance Force
SetTitleMatchMode 2

; =========================
; CONFIG
; =========================
global TARGET_WIN := "Tibia - Ryokst" ; ggf. anpassen
global MAP_FILE   := A_ScriptDir "\hotkeys.map"
global EVENTS_LOG := A_ScriptDir "\hotkeys_events.log"

; =========================
; STARTUP
; =========================
global HOTKEY_MAP := Map() ; hotkeyStr -> actionId
LoadMappings()

; Register hotkeys dynamically (only active when Tibia is active)
RegisterHotkeys()

; Optional: hot reload via Ctrl+Shift+F12 (only when Tibia active)
#HotIf WinActive(TARGET_WIN)
^+F12::ReloadMappings()
#HotIf

return

; =========================
; MAPPINGS
; =========================
LoadMappings() {
    global HOTKEY_MAP, MAP_FILE

    HOTKEY_MAP.Clear()

    if !FileExist(MAP_FILE) {
        ; If no file exists yet, create a starter template.
        tpl :=
        (
        "MButton=>F4`n"
        "!MButton=>F5`n"
        "^MButton=>F6`n"
        "XButton1=>F10`n"
        "$WheelUp=>HASTE`n"
        "$WheelDown=>ALT_Q`n"
        "~3=>FIRE_WAVE`n"
        "~4=>GEB`n"
        "~!4=>EB`n"
        "~!2=>HELLS_CORE`n"
        "~!r=>HASTE`n"
        )
        FileAppend(tpl, MAP_FILE, "UTF-8")
    }

    for line in StrSplit(FileRead(MAP_FILE, "UTF-8"), "`n", "`r") {
        line := Trim(line)
        if (line = "") || SubStr(line, 1, 1) = ";" || SubStr(line, 1, 1) = "#"
            continue

        parts := StrSplit(line, "=>")
        if (parts.Length < 2)
            continue

        hk := Trim(parts[1])
        act := Trim(parts[2])
        if (hk = "") || (act = "")
            continue

        HOTKEY_MAP[hk] := act
    }
}

RegisterHotkeys() {
    global HOTKEY_MAP, TARGET_WIN

    ; Bind every hotkey in the map to a single handler that knows the actionId.
    for hk, act in HOTKEY_MAP {
        ; Create a closure per mapping
        fn := MakeHandler(act)

        ; Register hotkey with context: only when Tibia is active
        Hotkey(hk, fn, "On")
    }

    ; Apply conditional context
    ; Note: In AHK v2, #HotIf affects hotkeys declared after it, but dynamic Hotkey()
    ; uses the current HotIf criteria too. So we set a global criterion by calling HotIf().
    ; Safer approach: set HotIf function before registering and then reset after.
}

MakeHandler(actionId) {
    return (*) => HandleAction(actionId)
}

ReloadMappings() {
    ; Turn off currently registered hotkeys, reload map, re-register.
    global HOTKEY_MAP

    for hk, _ in HOTKEY_MAP {
        try Hotkey(hk, "Off")
    }

    LoadMappings()

    ; Ensure dynamic hotkeys are only active when Tibia is active:
    HotIf(() => WinActive(TARGET_WIN))
    RegisterHotkeys()
    HotIf() ; reset

    LogEvent("RELOADED")
}

; =========================
; ACTION EXECUTION + EVENT LOGGING
; =========================
HandleAction(actionId) {
    global TARGET_WIN

    ; Only act when Tibia is active (hard guard)
    if !WinActive(TARGET_WIN)
        return

    ; 1) Send keys (AHK remains responsible for SendEvent)
    ExecuteSend(actionId)

    ; 2) Notify Python by appending an event line
    LogEvent(actionId)
}

ExecuteSend(actionId) {
    ; Map ACTION_ID -> Send/SendEvent behavior.
    ; Keep this table small and explicit. Extend as needed.
    switch actionId {
        ; Simple remaps
        case "F4":  Send "{F4}"
        case "F5":  Send "{F5}"
        case "F6":  Send "{F6}"
        case "F10": Send "{F10}"

        ; Tibia actions (examples matching your original bindings)
        case "HASTE":      SendEvent "!r"
        case "ALT_Q":      Send "!q"

        case "FIRE_WAVE":  Send "3"      ; your "~3" was pass-through; here we actively send if used as action
        case "GEB":        Send "4"
        case "EB":         SendEvent "!4"
        case "HELLS_CORE": SendEvent "!2"

        ; Optional: allow direct send specs from mapping file:
        ; e.g. actionId: SEND:{F8} or SEND:!r or SEND:{Click}
        default:
            if RegExMatch(actionId, "^SEND\:(.*)$", &m) {
                spec := m[1]
                Send spec
            }
    }
}

LogEvent(actionId) {
    global EVENTS_LOG
    ; Minimal, parse-friendly line format:
    ; TRIGGER|ts=1700000000|action=HASTE
    ts := A_NowUTC
    line := "TRIGGER|ts=" ts "|action=" actionId "`n"
    FileAppend(line, EVENTS_LOG, "UTF-8")
}

; =========================
; Ensure dynamic hotkeys are scoped to Tibia
; =========================
; Set HotIf criterion once, then register, then reset.
HotIf(() => WinActive(TARGET_WIN))
RegisterHotkeys()
HotIf()
