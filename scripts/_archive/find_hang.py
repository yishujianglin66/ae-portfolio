"""用 faulthandler 定位 pytest 挂起文件"""
import faulthandler
import sys
import os

os.chdir(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, ".")

dump_file = open("hang_dump2.txt", "w", encoding="utf-8")
faulthandler.dump_traceback_later(180, exit=True, file=dump_file)

import pytest
r = pytest.main(["tests/", "-q", "--tb=line", "--no-header"])

faulthandler.cancel_dump_traceback_later()
dump_file.close()
with open("test_results.txt", "w", encoding="utf-8") as out:
    out.write(f"exit_code={r}\n")
print(f"\nDone: exit={r}")
