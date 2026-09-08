# -*- coding: utf-8 -*-
"""Find all dialog windows."""
import win32gui

def enum_windows_callback(hwnd, results):
    try:
        title = win32gui.GetWindowText(hwnd)
        if title:
            results.append((hwnd, title))
    except Exception:
        pass
    return True

windows = []
win32gui.EnumWindows(enum_windows_callback, windows)

# Filter for dialog windows
dialog_keywords = ['dialog', 'open', 'file', 'browse', 'select', 'choose']
dialogs = [
    (h, t) for h, t in windows 
    if any(kw in t.lower() for kw in dialog_keywords)
]

print(f"Total windows scanned: {len(windows)}")
print(f"Found {len(dialogs)} dialog windows:")
for h, t in dialogs:
    print(f"  HWND={h}, Title=\"{t}\"")
