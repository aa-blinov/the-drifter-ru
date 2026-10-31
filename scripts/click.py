#!/usr/bin/env python
"""Клик в игре.

Игра работает как point-and-click, и её меню проходятся мышью. Клик
задаётся точкой в окне игры, поэтому место не зависит от того, где окно
стоит на экране.

    python3 scripts/click.py --at 960,515
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as w
import subprocess
import time

user32 = ctypes.windll.user32


def game_pid(name: str = "TheDrifter.exe"):
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq %s" % name, "/FO", "CSV", "/NH"],
        capture_output=True)
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        parts = [p.strip('" ') for p in line.split('","')]
        if len(parts) > 1 and parts[0].lower() == name.lower():
            return int(parts[1])
    return 0


def game_window(pid: int):
    found = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)

    def callback(hwnd, _lparam):
        owner = w.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if buf.value == "The Drifter":
                    found.append(hwnd)
        return True

    user32.EnumWindows(enum_proc(callback), 0)
    return found[0] if found else 0


MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def click(x: int, y: int) -> None:
    """Один клик в точке экрана."""
    user32.SetCursorPos(x, y)
    time.sleep(0.1)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.06)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", required=True, help="точка в окне: x,y")
    args = parser.parse_args()

    pid = game_pid()
    if not pid:
        raise SystemExit("игра не запущена")
    hwnd = game_window(pid)
    if not hwnd:
        raise SystemExit("окно игры не найдено")

    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)

    rect = w.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    x, y = (int(v) for v in args.at.split(","))
    click(rect.left + x, rect.top + y)
    print("клик в окне: %d,%d" % (x, y))


if __name__ == "__main__":
    main()
