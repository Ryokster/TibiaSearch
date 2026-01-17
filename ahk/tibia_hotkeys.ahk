#Requires AutoHotkey v2.0
#SingleInstance Force
SetTitleMatchMode 2

; =========================================================
; PERSISTENZ
; =========================================================
global CFG_FILE := A_ScriptDir "\tibia_grid.ini"

; =========================================================
; GRID STATE
; Mode: 0=aus, 1=Grid+dezent Markierungen (alle Richtungen), 2=nur Markierung (rot) + nur aktive Richtung
; =========================================================
global Grid := {
    Mode: 0,
    Cell: 70,
    Gui: 0,
    Hwnd: 0,
    OffX: 0,
    OffY: 0,
    OriginX: 0,
    OriginY: 0,
    RangeX: 7,
    RangeY: 5,
    PyrLenX: 4,
    PyrLenY: 4,
    ActiveDir: "U"
}
LoadGridConfig()

; =========================================================
; HUD (GDI+ LAYERED WINDOW) CONFIG
; =========================================================
global HUD_SIZE := 35
global HUD_GAP  := 6
global HUD_X := 100 + 930   ; 1030
global HUD_Y := 100 + 250   ; 350

; Cooldowns (ms) – anpassen falls nötig
global CD3_MS   := 4000     ; Fire Wave
global CD4_MS   := 8000     ; Great Energy Beam
global CD5_MS   := 6000     ; Energy Beam (rechts neben 4)  <-- ggf anpassen
global CD6_MS   := 40000    ; Hell's Core (zwischen 4 und R) <-- ggf anpassen
global CD_R_MS  := 21000    ; Strong Haste

; Icons (PNG bevorzugt, sonst GIF)
global ICON_FIREWAVE_PNG := A_ScriptDir "\Fire_Wave.png"
global ICON_FIREWAVE_GIF := A_ScriptDir "\Fire_Wave.gif"

global ICON_GEB_PNG      := A_ScriptDir "\Great_Energy_Beam.png"
global ICON_GEB_GIF      := A_ScriptDir "\Great_Energy_Beam.gif"

global ICON_EB_PNG       := A_ScriptDir "\Energy_Beam.png"
global ICON_EB_GIF       := A_ScriptDir "\Energy_Beam.gif"        ; du schriebst .gid – bitte als .gif speichern

global ICON_HELL_PNG     := A_ScriptDir "\Hell's_Core.png"
global ICON_HELL_GIF     := A_ScriptDir "\Hell's_Core.gif"

global ICON_HASTE_PNG    := A_ScriptDir "\Strong_Haste.png"
global ICON_HASTE_GIF    := A_ScriptDir "\Strong_Haste.gif"

global HUD := {
    end3: 0, end4: 0, end5: 0, end6: 0, endR: 0,
    timerOn: false,

    gui: 0, hwnd: 0,
    token: 0,
    hdc: 0, hbm: 0, obm: 0,
    g: 0,
    w: 0, h: 0,

    img3: 0, img4: 0, img5: 0, img6: 0, imgR: 0
}

Hud_Init()

; =========================================================
; HOTKEYS – nur wenn Tibia aktiv
; =========================================================
#HotIf WinActive("Tibia - Ryokst")

MButton::Send "{F4}"
!MButton::Send "{F5}"
^MButton::Send "{F6}"
XButton1::Send "{F10}"

; WheelUp / WheelDown -> Trigger + Wheel an Tibia weitergeben (robust)
$WheelUp:: {
    TriggerHaste()
    SendEvent "!r"
}

$WheelDown:: {
    Send "!q"
}

$!WheelUp:: {
  ;  TriggerHaste()
  ;  SendEvent "!{WheelUp}"
}

$!WheelDown:: {
  ;  TriggerHaste()
  ;  SendEvent "!{WheelDown}"
}

;w~WheelUp::TriggerHaste()
;~WheelDown:: Send "!q"
;!WheelUp::Stub_Action("Alt+WheelUp")
;!WheelDown::Stub_Action("Alt+WheelDown")

F12::CycleGridMode()

NumpadAdd::AdjustGridCell(+1)
NumpadSub::AdjustGridCell(-1)

Numpad8::MoveGrid(0, -1)
Numpad2::MoveGrid(0,  1)
Numpad4::MoveGrid(-1, 0)
Numpad6::MoveGrid( 1, 0)

+Numpad8::MoveGrid(0, -10)
+Numpad2::MoveGrid(0,  10)
+Numpad4::MoveGrid(-10, 0)
+Numpad6::MoveGrid( 10, 0)

Numpad0::SetOriginToMouse()
Numpad5::ResetGridOffset()

~w::SetActiveDir("U")
~a::SetActiveDir("L")
~s::SetActiveDir("D")
~d::SetActiveDir("R")

; Cooldowns (Tibia bekommt die Taste weiterhin)
~3::TriggerCooldown(3)
~4::TriggerCooldown(4)
~!4::TriggerCooldown(5)     ; Energy Beam (rechts neben 4)
~!2::TriggerCooldown(6)     ; Hell's Core (zwischen 4 und R)

; Strong Haste (Alt+R) – Pass-through
~!r::TriggerHaste()

; HUD debug render (falls du mal neu zeichnen willst)
F11::Hud_Render()

#HotIf

OnExit (*) => Hud_Shutdown()

; =========================================================
; GRID: Mode Toggle + GUI + Controls
; =========================================================
CycleGridMode() {
    global Grid
    if !Grid.Gui
        CreateGridGui()

    Grid.Mode := (Grid.Mode + 1)
    if (Grid.Mode > 2)
        Grid.Mode := 0

    if (Grid.Mode = 0) {
        Grid.Gui.Hide()
        ToolTip "Grid: AUS", 10, 10
        SetTimer () => ToolTip(), -700
        return
    }

    Grid.Gui.Show("x0 y0 w" A_ScreenWidth " h" A_ScreenHeight " NoActivate")
    RedrawGrid()

    msg := (Grid.Mode = 1)
        ? "Grid: MODUS 1 (Grid + dezent, alle Richtungen)"
        : "Grid: MODUS 2 (NUR Markierung, ROT, Richtung: " Grid.ActiveDir ")"

    ToolTip msg, 10, 10
    SetTimer () => ToolTip(), -1100
}

AdjustGridCell(delta) {
    global Grid
    if (Grid.Mode = 0)
        return
    Grid.Cell := Max(8, Min(256, Grid.Cell + delta))
    SaveGridConfig()
    RedrawGrid()
}

MoveGrid(dx, dy) {
    global Grid
    if (Grid.Mode = 0)
        return
    Grid.OffX += dx
    Grid.OffY += dy
    SaveGridConfig()
    RedrawGrid()
}

ResetGridOffset() {
    global Grid
    if (Grid.Mode = 0)
        return
    Grid.OffX := 0
    Grid.OffY := 0
    SaveGridConfig()
    RedrawGrid()
}

SetOriginToMouse() {
    global Grid
    if (Grid.Mode = 0)
        return

    MouseGetPos &mx, &my
    c := Grid.Cell
    ox := Grid.OffX
    oy := Grid.OffY

    phaseX := Mod(ox, c)
    if (phaseX < 0)
        phaseX += c

    phaseY := Mod(oy, c)
    if (phaseY < 0)
        phaseY += c

    cellX := Floor((mx - phaseX) / c) * c + phaseX
    cellY := Floor((my - phaseY) / c) * c + phaseY

    Grid.OriginX := cellX
    Grid.OriginY := cellY
    SaveGridConfig()
    RedrawGrid()

    ToolTip "Origin gesetzt", 10, 10
    SetTimer () => ToolTip(), -700
}

SetActiveDir(dir) {
    global Grid
    Grid.ActiveDir := dir
    if (Grid.Mode = 2)
        RedrawGrid()
}

CreateGridGui() {
    global Grid
    g := Gui("+AlwaysOnTop -Caption +ToolWindow +E0x20 +E0x80000 +LastFound") ; click-through + layered
    g.BackColor := "010101"
    WinSetTransColor "010101", g.Hwnd
    g.Show("Hide x0 y0 w" A_ScreenWidth " h" A_ScreenHeight " NoActivate")

    Grid.Gui := g
    Grid.Hwnd := g.Hwnd
    OnMessage(0x0F, WM_PAINT_Grid)
}

RedrawGrid() {
    global Grid
    if !Grid.Gui || (Grid.Mode = 0)
        return
    DllCall("user32\InvalidateRect", "ptr", Grid.Hwnd, "ptr", 0, "int", true)
    DllCall("user32\UpdateWindow", "ptr", Grid.Hwnd)
}

WM_PAINT_Grid(wParam, lParam, msg, hwnd) {
    global Grid
    if (Grid.Mode = 0) || (hwnd != Grid.Hwnd)
        return

    ps := Buffer(72, 0)
    hdc := DllCall("user32\BeginPaint", "ptr", hwnd, "ptr", ps, "ptr")

    w := A_ScreenWidth, h := A_ScreenHeight
    c := Grid.Cell
    ox := Grid.OffX, oy := Grid.OffY

    startX := Mod(ox, c)
    if (startX < 0) startX += c
    startX -= c

    startY := Mod(oy, c)
    if (startY < 0) startY += c
    startY -= c

    baseX := (Grid.OriginX != 0 ? Grid.OriginX : Floor(w/2))
    baseY := (Grid.OriginY != 0 ? Grid.OriginY : Floor(h/2))

    left   := Max(0 - c, baseX - (Grid.RangeX * c))
    right  := Min(w + c, baseX + (Grid.RangeX * c))
    top    := Max(0 - c, baseY - (Grid.RangeY * c))
    bottom := Min(h + c, baseY + (Grid.RangeY * c))

    if (Grid.Mode = 1) {
        PS_DOT := 2
        gridColor := 0x00C8C8C8
        penGrid := DllCall("gdi32\CreatePen", "int", PS_DOT, "int", 1, "uint", gridColor, "ptr")
        oldPen := DllCall("gdi32\SelectObject", "ptr", hdc, "ptr", penGrid, "ptr")

        x := left
        x -= Mod(x - startX, c)
        while (x <= right) {
            DllCall("gdi32\MoveToEx", "ptr", hdc, "int", x, "int", top, "ptr", 0)
            DllCall("gdi32\LineTo",   "ptr", hdc, "int", x, "int", bottom)
            x += c
        }

        y := top
        y -= Mod(y - startY, c)
        while (y <= bottom) {
            DllCall("gdi32\MoveToEx", "ptr", hdc, "int", left, "int", y, "ptr", 0)
            DllCall("gdi32\LineTo",   "ptr", hdc, "int", right, "int", y)
            y += c
        }

        DllCall("gdi32\SelectObject", "ptr", hdc, "ptr", oldPen, "ptr")
        DllCall("gdi32\DeleteObject", "ptr", penGrid)
    }

    DrawPyramidHighlights(hdc, baseX, baseY, c, left, top, right, bottom)

    DllCall("user32\EndPaint", "ptr", hwnd, "ptr", ps)
    return 0
}

DrawPyramidHighlights(hdc, baseX, baseY, c, clipL, clipT, clipR, clipB) {
    global Grid
    spanForStep(step) => Floor(step/2)
    isMode2 := (Grid.Mode = 2)

    HS_FDIAGONAL := 2
    if isMode2 {
        softRed := 0x00E8E8FF
        brush := DllCall("gdi32\CreateHatchBrush", "int", HS_FDIAGONAL, "uint", softRed, "ptr")
        pad := 12
    } else {
        veryLightRed := 0x00FCFCFF
        brush := DllCall("gdi32\CreateHatchBrush", "int", HS_FDIAGONAL, "uint", veryLightRed, "ptr")
        pad := 10
    }

    oldBrush := DllCall("gdi32\SelectObject", "ptr", hdc, "ptr", brush, "ptr")
    nullPen := DllCall("gdi32\GetStockObject", "int", 8, "ptr")
    oldPen := DllCall("gdi32\SelectObject", "ptr", hdc, "ptr", nullPen, "ptr")

    DrawTile(tx, ty) {
        x1 := baseX + tx*c + pad
        y1 := baseY + ty*c + pad
        x2 := baseX + tx*c + c - pad
        y2 := baseY + ty*c + c - pad
        if (x2 < clipL || x1 > clipR || y2 < clipT || y1 > clipB)
            return
        DllCall("gdi32\Rectangle", "ptr", hdc, "int", x1, "int", y1, "int", x2, "int", y2)
    }

    dir := Grid.ActiveDir
    drawU := (!isMode2) || (dir = "U")
    drawD := (!isMode2) || (dir = "D")
    drawL := (!isMode2) || (dir = "L")
    drawR := (!isMode2) || (dir = "R")

    if drawU {
        Loop Grid.PyrLenY {
            s := A_Index, y := -s, span := spanForStep(s)
            dx := -span
            while (dx <= span) {
                DrawTile(dx, y), dx += 1
            }
        }
    }
    if drawD {
        Loop Grid.PyrLenY {
            s := A_Index, y := s, span := spanForStep(s)
            dx := -span
            while (dx <= span) {
                DrawTile(dx, y), dx += 1
            }
        }
    }
    if drawR {
        Loop Grid.PyrLenX {
            s := A_Index, x := s, span := spanForStep(s)
            dy := -span
            while (dy <= span) {
                DrawTile(x, dy), dy += 1
            }
        }
    }
    if drawL {
        Loop Grid.PyrLenX {
            s := A_Index, x := -s, span := spanForStep(s)
            dy := -span
            while (dy <= span) {
                DrawTile(x, dy), dy += 1
            }
        }
    }

    DllCall("gdi32\SelectObject", "ptr", hdc, "ptr", oldPen, "ptr")
    DllCall("gdi32\SelectObject", "ptr", hdc, "ptr", oldBrush, "ptr")
    DllCall("gdi32\DeleteObject", "ptr", brush)
}

; =========================================================
; HUD LOGIC (timers)
; =========================================================
TriggerCooldown(which) {
    global HUD, CD3_MS, CD4_MS, CD5_MS, CD6_MS
    now := A_TickCount

    switch which {
        case 3: HUD.end3 := now + CD3_MS
        case 4: HUD.end4 := now + CD4_MS
        case 5: HUD.end5 := now + CD5_MS
        case 6: HUD.end6 := now + CD6_MS
        default: return
    }

    if !HUD.timerOn {
        HUD.timerOn := true
        SetTimer UpdateCooldownHud, 33
    }
    UpdateCooldownHud()
}

TriggerHaste() {
    global HUD, CD_R_MS
    HUD.endR := A_TickCount + CD_R_MS

    if !HUD.timerOn {
        HUD.timerOn := true
        SetTimer UpdateCooldownHud, 33
    }
    UpdateCooldownHud()
}

UpdateCooldownHud() {
    global HUD
    now := A_TickCount

    Hud_Render()

    if (HUD.end3 <= now && HUD.end4 <= now && HUD.end5 <= now && HUD.end6 <= now && HUD.endR <= now) {
        HUD.end3 := 0, HUD.end4 := 0, HUD.end5 := 0, HUD.end6 := 0, HUD.endR := 0
        SetTimer UpdateCooldownHud, 0
        HUD.timerOn := false
        Hud_Render()
    }
}

; =========================================================
; HUD (GDI+ Layered Window) - INIT/RENDER
; Layout:
;   Row1: [3]
;   Row2: [4] [5-right]
;   Row3: [6]
;   Row4: [R] (only when active)
; =========================================================
Hud_Init() {
    global HUD, HUD_X, HUD_Y, HUD_SIZE, HUD_GAP
    global ICON_FIREWAVE_PNG, ICON_FIREWAVE_GIF, ICON_GEB_PNG, ICON_GEB_GIF
    global ICON_EB_PNG, ICON_EB_GIF, ICON_HELL_PNG, ICON_HELL_GIF, ICON_HASTE_PNG, ICON_HASTE_GIF

    ; 2 Spalten wegen Button rechts neben dem mittleren
    HUD.w := HUD_SIZE*2 + HUD_GAP
    ; 4 Reihen reserviert (R bleibt leer/transparent, wenn nicht aktiv)
    HUD.h := HUD_SIZE*4 + HUD_GAP*3

    ; WICHTIG: WS_EX_LAYERED (E0x80000), sonst "weißer Streifen"
    g := Gui("+AlwaysOnTop -Caption +ToolWindow +E0x20 +E0x80000 +LastFound")
    g.Show("x" HUD_X " y" HUD_Y " w" HUD.w " h" HUD.h " NoActivate")
    HUD.gui := g
    HUD.hwnd := g.Hwnd

    HUD.token := Gdip_Startup()

    HUD.hdc := DllCall("gdi32\CreateCompatibleDC", "ptr", 0, "ptr")
    HUD.hbm := CreateDIBSection(HUD.w, HUD.h)
    HUD.obm := DllCall("gdi32\SelectObject", "ptr", HUD.hdc, "ptr", HUD.hbm, "ptr")
    HUD.g := Gdip_GraphicsFromHDC(HUD.hdc)
    Gdip_SetSmoothingMode(HUD.g, 4)
    Gdip_SetInterpolationMode(HUD.g, 7)

    HUD.img3 := Hud_LoadBitmap(ICON_FIREWAVE_PNG, ICON_FIREWAVE_GIF)
    HUD.img4 := Hud_LoadBitmap(ICON_GEB_PNG,      ICON_GEB_GIF)
    HUD.img5 := Hud_LoadBitmap(ICON_EB_PNG,       ICON_EB_GIF)
    HUD.img6 := Hud_LoadBitmap(ICON_HELL_PNG,     ICON_HELL_GIF)
    HUD.imgR := Hud_LoadBitmap(ICON_HASTE_PNG,    ICON_HASTE_GIF)

    Hud_Render()
}

Hud_LoadBitmap(pngPath, gifPath) {
    if FileExist(pngPath) {
        p := Gdip_CreateBitmapFromFile(pngPath)
        if p
            return p
    }
    if FileExist(gifPath) {
        p := Gdip_CreateBitmapFromFile(gifPath)
        if p
            return p
    }
    return 0
}

Hud_Render() {
    global HUD, HUD_SIZE, HUD_GAP, CD3_MS, CD4_MS, CD5_MS, CD6_MS, CD_R_MS
    if !HUD.g
        return

    now := A_TickCount

    ; Clear transparent
    Gdip_GraphicsClear(HUD.g, 0x00000000)

    ; Layout coords
    xL := 0
    xR := HUD_SIZE + HUD_GAP

    y1 := 0
    y2 := HUD_SIZE + HUD_GAP
    y3 := (HUD_SIZE + HUD_GAP) * 2
    y4 := (HUD_SIZE + HUD_GAP) * 3

    ; Draw tiles + borders
    Hud_DrawTile(HUD.g, HUD.img3, "3", xL, y1, HUD_SIZE, HUD_SIZE)
    Hud_DrawCooldownOverlay(HUD.g, HUD.end3, now, CD3_MS, xL, y1, HUD_SIZE, HUD_SIZE)

    Hud_DrawTile(HUD.g, HUD.img4, "4", xL, y2, HUD_SIZE, HUD_SIZE)
    Hud_DrawCooldownOverlay(HUD.g, HUD.end4, now, CD4_MS, xL, y2, HUD_SIZE, HUD_SIZE)

    ; Right of middle: Energy Beam (5)
    Hud_DrawTile(HUD.g, HUD.img5, "5", xR, y2, HUD_SIZE, HUD_SIZE)
    Hud_DrawCooldownOverlay(HUD.g, HUD.end5, now, CD5_MS, xR, y2, HUD_SIZE, HUD_SIZE)

    ; Between middle and lower: Hell's Core (6)
    Hud_DrawTile(HUD.g, HUD.img6, "6", xL, y3, HUD_SIZE, HUD_SIZE)
    Hud_DrawCooldownOverlay(HUD.g, HUD.end6, now, CD6_MS, xL, y3, HUD_SIZE, HUD_SIZE)

    ; Bottom: Strong Haste (R) only when active
    if (HUD.endR > now) {
        Hud_DrawTile(HUD.g, HUD.imgR, "R", xL, y4, HUD_SIZE, HUD_SIZE)
        Hud_DrawCooldownOverlay(HUD.g, HUD.endR, now, CD_R_MS, xL, y4, HUD_SIZE, HUD_SIZE)
    }

    UpdateLayeredWindow(HUD.hwnd, HUD.hdc, HUD.w, HUD.h)
}

Hud_DrawTile(g, pBitmap, label, x, y, w, h) {
    if (pBitmap)
        Gdip_DrawImageRectI(g, pBitmap, x, y, w, h)
    else
        Hud_DrawFallbackTile(g, label, x, y, w, h)

    ; White border (2px)
    pen := Gdip_CreatePen(0xFFFFFFFF, 2)
    ; inset 1px so stroke stays within bounds
    Gdip_DrawRectangle(g, pen, x+1, y+1, w-2, h-2)
    Gdip_DeletePen(pen)
}

Hud_DrawFallbackTile(g, label, x, y, w, h) {
    br := Gdip_BrushCreateSolid(0xAA202020)
    Gdip_FillRectangle(g, br, x, y, w, h)
    Gdip_DeleteBrush(br)
    Hud_DrawTextShadow(g, label, x, y, w, h, 18)
}

Hud_DrawCooldownOverlay(g, endTick, now, cdMS, x, y, w, h) {
    if (endTick <= now || cdMS <= 0)
        return

    rem := endTick - now
    pct := Round((rem / cdMS) * 100)
    pct := Max(0, Min(100, pct))

    ; Red bar (more visible)
    barH := 7
    barY := y + h - barH
    bw := Round(w * (pct / 100))

    ; background bar (dark)
    brBg := Gdip_BrushCreateSolid(0xAA101010)
    Gdip_FillRectangle(g, brBg, x, barY, w, barH)
    Gdip_DeleteBrush(brBg)

    ; foreground bar (RED)
    if (bw > 0) {
        brFill := Gdip_BrushCreateSolid(0xCCFF0000)
        Gdip_FillRectangle(g, brFill, x, barY, bw, barH)
        Gdip_DeleteBrush(brFill)
    }

    sec := Ceil(rem / 1000)
    Hud_DrawTextShadow(g, sec, x, y, w, h, 18)
}

Hud_DrawTextShadow(g, text, x, y, w, h, size) {
    Hud_DrawText(g, text, x+1, y+1, w, h, size, 0xCC000000)
    Hud_DrawText(g, text, x,   y,   w, h, size, 0xEEFFFFFF)
}

Hud_DrawText(g, text, x, y, w, h, size, argb) {
    pBrush := Gdip_BrushCreateSolid(argb)
    hFamily := Gdip_FontFamilyCreate("Segoe UI")
    hFont := Gdip_FontCreate(hFamily, size, 1)
    fmt := Gdip_StringFormatCreate(0x0000)
    Gdip_SetStringFormatAlign(fmt, 1)
    Gdip_SetStringFormatLineAlign(fmt, 1)
    rc := Buffer(16, 0)
    NumPut("float", x, rc, 0), NumPut("float", y, rc, 4), NumPut("float", w, rc, 8), NumPut("float", h, rc, 12)
    Gdip_DrawString(g, text, hFont, fmt, pBrush, rc)
    Gdip_DeleteStringFormat(fmt)
    Gdip_DeleteFont(hFont)
    Gdip_DeleteFontFamily(hFamily)
    Gdip_DeleteBrush(pBrush)
}

Hud_Shutdown() {
    global HUD
    try {
        for _, p in [HUD.img3, HUD.img4, HUD.img5, HUD.img6, HUD.imgR]
            if p
                Gdip_DisposeImage(p)

        if HUD.g
            Gdip_DeleteGraphics(HUD.g)

        if HUD.obm
            DllCall("gdi32\SelectObject", "ptr", HUD.hdc, "ptr", HUD.obm)

        if HUD.hbm
            DllCall("gdi32\DeleteObject", "ptr", HUD.hbm)

        if HUD.hdc
            DllCall("gdi32\DeleteDC", "ptr", HUD.hdc)

        if HUD.token
            Gdip_Shutdown(HUD.token)
    }
}

; =========================================================
; INI LOAD/SAVE
; =========================================================
LoadGridConfig() {
    global Grid, CFG_FILE
    if !FileExist(CFG_FILE)
        return
    Grid.Cell := IniRead(CFG_FILE, "Grid", "Cell", Grid.Cell)
    Grid.OffX := IniRead(CFG_FILE, "Grid", "OffX", Grid.OffX)
    Grid.OffY := IniRead(CFG_FILE, "Grid", "OffY", Grid.OffY)
    Grid.OriginX := IniRead(CFG_FILE, "Grid", "OriginX", Grid.OriginX)
    Grid.OriginY := IniRead(CFG_FILE, "Grid", "OriginY", Grid.OriginY)
}

SaveGridConfig() {
    global Grid, CFG_FILE
    IniWrite(Grid.Cell, CFG_FILE, "Grid", "Cell")
    IniWrite(Grid.OffX, CFG_FILE, "Grid", "OffX")
    IniWrite(Grid.OffY, CFG_FILE, "Grid", "OffY")
    IniWrite(Grid.OriginX, CFG_FILE, "Grid", "OriginX")
    IniWrite(Grid.OriginY, CFG_FILE, "Grid", "OriginY")
}

; =========================================================
; GDI+ MINIMAL WRAPPER (v2, self-contained)
; =========================================================
Gdip_Startup() {
    if !DllCall("GetModuleHandle", "str", "gdiplus", "ptr")
        DllCall("LoadLibrary", "str", "gdiplus", "ptr")

    si := Buffer(A_PtrSize=8 ? 24 : 16, 0)
    NumPut("UInt", 1, si, 0)
    token := 0
    DllCall("gdiplus\GdiplusStartup", "ptr*", &token, "ptr", si, "ptr", 0)
    return token
}
Gdip_Shutdown(token) => DllCall("gdiplus\GdiplusShutdown", "ptr", token)

Gdip_CreateBitmapFromFile(sFile) {
    pBitmap := 0
    DllCall("gdiplus\GdipCreateBitmapFromFile", "wstr", sFile, "ptr*", &pBitmap)
    return pBitmap
}
Gdip_DisposeImage(pBitmap) => DllCall("gdiplus\GdipDisposeImage", "ptr", pBitmap)

Gdip_GraphicsFromHDC(hdc) {
    pGraphics := 0
    DllCall("gdiplus\GdipCreateFromHDC", "ptr", hdc, "ptr*", &pGraphics)
    return pGraphics
}
Gdip_DeleteGraphics(pGraphics) => DllCall("gdiplus\GdipDeleteGraphics", "ptr", pGraphics)

Gdip_SetSmoothingMode(pGraphics, mode) => DllCall("gdiplus\GdipSetSmoothingMode", "ptr", pGraphics, "int", mode)
Gdip_SetInterpolationMode(pGraphics, mode) => DllCall("gdiplus\GdipSetInterpolationMode", "ptr", pGraphics, "int", mode)

Gdip_GraphicsClear(pGraphics, argb) => DllCall("gdiplus\GdipGraphicsClear", "ptr", pGraphics, "UInt", argb)
Gdip_DrawImageRectI(pGraphics, pBitmap, x, y, w, h) => DllCall("gdiplus\GdipDrawImageRectI", "ptr", pGraphics, "ptr", pBitmap, "int", x, "int", y, "int", w, "int", h)

Gdip_BrushCreateSolid(argb) {
    pBrush := 0
    DllCall("gdiplus\GdipCreateSolidFill", "UInt", argb, "ptr*", &pBrush)
    return pBrush
}
Gdip_DeleteBrush(pBrush) => DllCall("gdiplus\GdipDeleteBrush", "ptr", pBrush)
Gdip_FillRectangle(pGraphics, pBrush, x, y, w, h) => DllCall("gdiplus\GdipFillRectangle", "ptr", pGraphics, "ptr", pBrush, "float", x, "float", y, "float", w, "float", h)

Gdip_FontFamilyCreate(name) {
    pFamily := 0
    DllCall("gdiplus\GdipCreateFontFamilyFromName", "wstr", name, "ptr", 0, "ptr*", &pFamily)
    return pFamily
}
Gdip_DeleteFontFamily(pFamily) => DllCall("gdiplus\GdipDeleteFontFamily", "ptr", pFamily)

Gdip_FontCreate(pFamily, emSize, style:=0) {
    pFont := 0
    DllCall("gdiplus\GdipCreateFont", "ptr", pFamily, "float", emSize, "int", style, "int", 0, "ptr*", &pFont)
    return pFont
}
Gdip_DeleteFont(pFont) => DllCall("gdiplus\GdipDeleteFont", "ptr", pFont)

Gdip_StringFormatCreate(flags:=0) {
    pFormat := 0
    DllCall("gdiplus\GdipCreateStringFormat", "int", flags, "int", 0, "ptr*", &pFormat)
    return pFormat
}
Gdip_DeleteStringFormat(pFormat) => DllCall("gdiplus\GdipDeleteStringFormat", "ptr", pFormat)
Gdip_SetStringFormatAlign(pFormat, align) => DllCall("gdiplus\GdipSetStringFormatAlign", "ptr", pFormat, "int", align)
Gdip_SetStringFormatLineAlign(pFormat, align) => DllCall("gdiplus\GdipSetStringFormatLineAlign", "ptr", pFormat, "int", align)
Gdip_DrawString(pGraphics, sString, pFont, pFormat, pBrush, pRectF) => DllCall("gdiplus\GdipDrawString", "ptr", pGraphics, "wstr", sString, "int", -1, "ptr", pFont, "ptr", pRectF, "ptr", pFormat, "ptr", pBrush)

; ---- Pen / Rectangle (für weißen Rahmen) ----
Gdip_CreatePen(argb, width) {
    pPen := 0
    DllCall("gdiplus\GdipCreatePen1", "UInt", argb, "float", width, "int", 2, "ptr*", &pPen) ; UnitPixel=2
    return pPen
}
Gdip_DeletePen(pPen) => DllCall("gdiplus\GdipDeletePen", "ptr", pPen)
Gdip_DrawRectangle(pGraphics, pPen, x, y, w, h) => DllCall("gdiplus\GdipDrawRectangle", "ptr", pGraphics, "ptr", pPen, "float", x, "float", y, "float", w, "float", h)

; ---- Layered Window Backbuffer helpers ----
CreateDIBSection(w, h) {
    bi := Buffer(40, 0)
    NumPut("UInt", 40, bi, 0)
    NumPut("Int",  w,  bi, 4)
    NumPut("Int", -h,  bi, 8)     ; top-down
    NumPut("UShort", 1, bi, 12)
    NumPut("UShort", 32, bi, 14)  ; 32 bpp
    NumPut("UInt", 0, bi, 16)     ; BI_RGB

    ppvBits := 0
    return DllCall("gdi32\CreateDIBSection", "ptr", 0, "ptr", bi, "uint", 0, "ptr*", &ppvBits, "ptr", 0, "uint", 0, "ptr")
}

UpdateLayeredWindow(hwnd, hdc, w, h) {
    sz := Buffer(8, 0)
    NumPut("Int", w, sz, 0)
    NumPut("Int", h, sz, 4)

    ptSrc := Buffer(8, 0)
    NumPut("Int", 0, ptSrc, 0)
    NumPut("Int", 0, ptSrc, 4)

    blend := Buffer(4, 0)
    NumPut("UChar", 0x00, blend, 0) ; AC_SRC_OVER
    NumPut("UChar", 0x00, blend, 1)
    NumPut("UChar", 0xFF, blend, 2)
    NumPut("UChar", 0x01, blend, 3) ; AC_SRC_ALPHA

    DllCall("user32\UpdateLayeredWindow"
        , "ptr", hwnd
        , "ptr", 0
        , "ptr", 0
        , "ptr", sz
        , "ptr", hdc
        , "ptr", ptSrc
        , "uint", 0
        , "ptr", blend
        , "uint", 0x02
    )
}
