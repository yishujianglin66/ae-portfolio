#!/usr/bin/env python3
"""Install CEP Panel for AE Knowledge Vault"""
import os
import shutil
import sys
import winreg

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "com.ae.knowledgevault")
DEST = os.path.join(os.environ["APPDATA"], "Adobe", "CEP", "extensions", "com.ae.knowledgevault")
REG_KEY = r"Software\Adobe\CSXS.11"

def install():
    print("=" * 50)
    print("AE Knowledge Vault CEP Panel - Install")
    print("=" * 50)
    print()

    # 1. Enable debug mode
    print("[1/3] Enable debug mode...")
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY)
        winreg.SetValueEx(key, "PlayerDebugMode", 0, winreg.REG_SZ, "1")
        winreg.CloseKey(key)
        print("  PlayerDebugMode=1 OK")
    except Exception as e:
        print(f"  Warning: {e}")

    # 2. Copy files
    print("[2/3] Deploy panel files...")
    if os.path.exists(DEST):
        shutil.rmtree(DEST)
    shutil.copytree(SRC, DEST)
    print(f"  Copied to: {DEST}")

    # 3. Verify
    print("[3/3] Verify installation...")
    manifest = os.path.join(DEST, "CSXS", "manifest.xml")
    if os.path.exists(manifest):
        print("  manifest.xml OK")
    else:
        print("  ERROR: manifest.xml not found!")
        sys.exit(1)

    print()
    print("=" * 50)
    print("Install complete!")
    print("=" * 50)
    print()
    print("Usage:")
    print("  1. Restart After Effects")
    print("  2. Menu: Window > Extensions > AE Knowledge Vault")
    print()
    print("Features:")
    print("  - Main: Ping/List/Listener/Screenshot/Render")
    print("  - Inspect: Deep extract/Expressions/Plugins")
    print("  - Knowledge: Save/View/Export reports")
    print()
    print("Uninstall: py -3.12 install_cep.py --uninstall")

def uninstall():
    print("Uninstalling CEP panel...")
    if os.path.exists(DEST):
        shutil.rmtree(DEST)
        print(f"Removed: {DEST}")
    else:
        print("Panel not found.")
    print("Restart AE to complete.")

if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        uninstall()
    else:
        install()
