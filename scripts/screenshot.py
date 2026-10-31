#!/usr/bin/env python
"""Снимок экрана запущенной игры.

Игра рисует текст шрифтами из своих собственных ассетов, и единственный
способ узнать, помещается ли русский текст, стоит ли он на базовой линии и
читается ли так же, как английский, это посмотреть на игру.

Окно игры находится по процессу игры, а снимок окна снимается напрямую,
поэтому то, что его закрывает, в кадр не попадает.

    python3 scripts/screenshot.py --out work/shots/scene.png
    python3 scripts/screenshot.py --out work/shots/scene.png --full
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as w
import os
import subprocess
import sys
import time

POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

CAPTURE = r"""
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Shot {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
$handle = [IntPtr]::new([int64]$env:SHOT_HWND)
$r = New-Object Shot+RECT
[void][Shot]::GetWindowRect($handle, [ref]$r)
$w = $r.Right - $r.Left
$h = $r.Bottom - $r.Top
if ($w -le 0 -or $h -le 0) { exit 3 }
$bitmap = New-Object System.Drawing.Bitmap $w, $h
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$dc = $graphics.GetHdc()
[void][Shot]::PrintWindow($handle, $dc, 2)
$graphics.ReleaseHdc($dc)
$graphics.Dispose()
$bitmap.Save($env:SHOT_PATH, [System.Drawing.Imaging.ImageFormat]::Png)
$bitmap.Dispose()
"""


def game_pid(name: str = "TheDrifter.exe"):
    """Процесс запущенной игры."""
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq %s" % name, "/FO", "CSV", "/NH"],
        capture_output=True)
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        parts = [p.strip('" ') for p in line.split('","')]
        if len(parts) > 1 and parts[0].lower() == name.lower():
            return int(parts[1])
    return None


def game_window(pid: int):
    """Окно игры по процессу, которому оно принадлежит."""
    user32 = ctypes.windll.user32
    found = []

    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)

    def callback(hwnd, _lparam):
        owner = w.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid or not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            rect = w.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            if rect.right - rect.left > 200 and rect.bottom - rect.top > 200:
                found.append((hwnd, rect.left, rect.top))
        return True

    user32.EnumWindows(enum_proc(callback), 0)
    return found[0][0] if found else None


def capture_window(hwnd: int, path: str) -> str:
    """Один снимок одного окна."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    env = dict(os.environ, SHOT_PATH=os.path.abspath(path),
               SHOT_HWND=str(hwnd))
    result = subprocess.run([POWERSHELL, "-NoProfile", "-Command", CAPTURE],
                            env=env, capture_output=True)
    if not os.path.exists(path):
        raise SystemExit("снимок не записан: %s"
                         % result.stderr.decode("utf-8", "replace")[:300])
    return path


def capture_screen(path: str) -> str:
    """Один снимок всего экрана."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    script = r"""
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bitmap.Save($env:SHOT_PATH, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
"""
    env = dict(os.environ, SHOT_PATH=os.path.abspath(path))
    subprocess.run([POWERSHELL, "-NoProfile", "-Command", script], env=env, check=True)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="work/shots/screen.png")
    parser.add_argument("--full", action="store_true",
                        help="весь экран, а не окно игры")
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--focus", action="store_true",
                        help="вывести окно игры на передний план")
    args = parser.parse_args()

    if args.delay:
        time.sleep(args.delay)

    if args.full:
        print(capture_screen(args.out))
        return

    pid = game_pid()
    if not pid:
        raise SystemExit("игра не запущена")
    hwnd = game_window(pid)
    if not hwnd:
        raise SystemExit("окно игры не найдено")
    if args.focus:
        # Игра стартует свёрнутой, когда её запускают из командной строки, а у
        # свёрнутого окна нет картинки, которую можно снять.
        ctypes.windll.user32.ShowWindow(hwnd, 9)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        time.sleep(0.8)
    print(capture_window(hwnd, args.out))


if __name__ == "__main__":
    main()
