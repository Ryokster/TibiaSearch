#Requires AutoHotkey v2.0
#SingleInstance Force
SetTitleMatchMode 2

; =========================
; HARDCODED TARGET POSITION
; =========================
targetX := 917
targetY := 484

; =========================
; SLEEPS (ms) - adjust if needed
; =========================
S_PRE_MOVE := 150
S_PRE_CLICK := 200
S_AFTER_CLICK := 200
S_BEFORE_PASTE := 150
S_AFTER_PASTE := 150
S_AFTER_ENTER := 150

; =========================
; RUN ON START
; =========================
Sleep 200

MouseMove targetX, targetY, 0
Sleep S_PRE_MOVE
Sleep S_PRE_CLICK

Click
Sleep S_AFTER_CLICK
Sleep S_BEFORE_PASTE

Send "^v"
Sleep S_AFTER_PASTE

Send "{Enter}"
Sleep S_AFTER_ENTER

ExitApp
