#!/usr/bin/env python
"""Отправка клавиш в запущенную игру.

Игра работает как point-and-click, и экран это единственный способ проверить
перевод. Скрипт отправляет нажатия, которые проводят игру до места, где
перевод надо смотреть.

    python3 scripts/send_keys.py --keys "{ENTER}" --wait 2
    python3 scripts/send_keys.py --keys "{DOWN 3}{ENTER}"
"""
from __future__ import annotations

import argparse
import subprocess
import time

POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

SCRIPT = r"""
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Keys {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, IntPtr e);
  [DllImport("user32.dll")] public static extern short VkKeyScan(char c);
  public delegate bool EnumProc(IntPtr h, IntPtr p);
  public const uint KEYUP = 2;
}
"@
$script:found = [IntPtr]::Zero
$target = 0
if ($env:WINDOW_PID -ne "") { $target = [uint32]$env:WINDOW_PID }
$cb = [Keys+EnumProc]{
  param($h, $p)
  if ($target -ne 0) {
    $owner = 0
    [void][Keys]::GetWindowThreadProcessId($h, [ref]$owner)
    if ($owner -eq $target) {
      $sb = New-Object System.Text.StringBuilder 512
      [void][Keys]::GetWindowText($h, $sb, 512)
      if ($sb.ToString() -eq $env:WINDOW_TITLE) { $script:found = $h; return $false }
    }
    return $true
  }
  if ([Keys]::IsWindowVisible($h)) {
    $sb = New-Object System.Text.StringBuilder 512
    [void][Keys]::GetWindowText($h, $sb, 512)
    if ($sb.ToString() -eq $env:WINDOW_TITLE) { $script:found = $h; return $false }
  }
  return $true
}
[void][Keys]::EnumWindows($cb, [IntPtr]::Zero)
$h = $script:found
if ($h -eq [IntPtr]::Zero) { exit 2 }
[void][Keys]::ShowWindow($h, 9)
[void][Keys]::SetForegroundWindow($h)
Start-Sleep -Milliseconds 250
$spec = $env:KEY_SPEC
$i = 0
while ($i -lt $spec.Length) {
  $c = $spec[$i]
  if ($c -eq '{') {
    $j = $spec.IndexOf('}', $i)
    $token = $spec.Substring($i + 1, $j - $i - 1)
    $parts = $token -split ' '
    $vk = switch ($parts[0]) {
      'ENTER' { 0x0D } 'TAB' { 0x09 } 'ESC' { 0x1B } 'SPACE' { 0x20 }
      'BACK' { 0x08 } 'LEFT' { 0x25 } 'UP' { 0x26 } 'RIGHT' { 0x27 } 'DOWN' { 0x28 }
      'F1' { 0x70 } 'F2' { 0x71 } 'F3' { 0x72 } 'F4' { 0x73 }
      'PAGEUP' { 0x21 } 'PAGEDOWN' { 0x22 } 'HOME' { 0x24 } 'END' { 0x23 }
      default { 0 }
    }
    $count = 1
    if ($parts.Count -gt 1) { $count = [int]$parts[1] }
    if ($vk -ne 0) {
      for ($k = 0; $k -lt $count; $k++) {
        [Keys]::keybd_event([byte]$vk, 0, 0, [IntPtr]::Zero)
        [Keys]::keybd_event([byte]$vk, 0, [Keys]::KEYUP, [IntPtr]::Zero)
        Start-Sleep -Milliseconds 90
      }
    }
    $i = $j + 1
  } else {
    $vk = [Keys]::VkKeyScan($c)
    if ($vk -ne -1) {
      $code = [byte]($vk -band 0xFF)
      $shift = ($vk -shr 8) -band 1
      if ($shift -eq 1) {
        [Keys]::keybd_event(0x10, 0, 0, [IntPtr]::Zero)
        [Keys]::keybd_event($code, 0, 0, [IntPtr]::Zero)
        [Keys]::keybd_event($code, 0, [Keys]::KEYUP, [IntPtr]::Zero)
        [Keys]::keybd_event(0x10, 0, [Keys]::KEYUP, [IntPtr]::Zero)
      } else {
        [Keys]::keybd_event($code, 0, 0, [IntPtr]::Zero)
        [Keys]::keybd_event($code, 0, [Keys]::KEYUP, [IntPtr]::Zero)
      }
    }
    $i++
  }
  Start-Sleep -Milliseconds 90
}
"""


def game_pid(name: str = "TheDrifter.exe"):
    """Процесс запущенной игры."""
    import subprocess
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq %s" % name, "/FO", "CSV", "/NH"],
        capture_output=True)
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        parts = [p.strip('" ') for p in line.split('","')]
        if len(parts) > 1 and parts[0].lower() == name.lower():
            return parts[1]
    return ""


def send(keys: str, window_title: str = "The Drifter", pid: str = ""):
    env = dict(__import__("os").environ, KEY_SPEC=keys, WINDOW_TITLE=window_title,
               WINDOW_PID=pid or game_pid())
    result = subprocess.run([POWERSHELL, "-NoProfile", "-Command", SCRIPT],
                            env=env, capture_output=True)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keys", required=True,
                        help="клавиши: {ENTER}, {DOWN 3}, {ESC} и буквы")
    parser.add_argument("--window", default="The Drifter")
    parser.add_argument("--wait", type=float, default=0.0)
    args = parser.parse_args()

    if args.wait:
        time.sleep(args.wait)
    code = send(args.keys, args.window)
    print("отправлено %r (код %d)" % (args.keys, code))


if __name__ == "__main__":
    main()
