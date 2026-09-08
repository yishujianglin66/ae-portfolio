# -*- coding: utf-8 -*-
"""Find all AE-related windows including hidden/minimized ones."""
import win32gui
import win32process

def enum_windows_callback(hwnd, results):
    try:
        title = win32gui.GetWindowText(hwnd)
        if title:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            is_visible = win32gui.IsWindowVisible(hwnd)
            is_minimized = win32gui.IsIconic(hwnd)
            results.append({
                'hwnd': hwnd,
                'title': title,
                'pid': pid,
                'visible': is_visible,
                'minimized': is_minimized
            })
    except Exception as e:
        pass
    return True

windows = []
win32gui.EnumWindows(enum_windows_callback, windows)

# Filter for AE-related windows
ae_keywords = ['after', 'effect', 'adobe', 'aep']
ae_windows = [
    w for w in windows 
    if any(kw in w['title'].lower() for kw in ae_keywords)
]

print(f"Total windows scanned: {len(windows)}")
print(f"Found {len(ae_windows)} AE-related windows:")
for w in ae_windows:
    status = []
    if not w['visible']:
        status.append("HIDDEN")
    if w['minimized']:
        status.append("MINIMIZED")
    status_str = f" [{', '.join(status)}]" if status else ""
    print(f"  HWND={w['hwnd']}, PID={w['pid']}, Title=\"{w['title']}\"{status_str}")

if not ae_windows:
    print("\nNo AE windows found. Checking all AfterFX.exe processes...")
    import subprocess
    result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq AfterFX.exe', '/FO', 'CSV', '/NH'],
        capture_output=True, text=True
    )
    print(result.stdout)
