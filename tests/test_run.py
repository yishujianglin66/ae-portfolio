# 最简单的测试 - 只写入文件，不使用任何 fx API

import os
import time

output_path = os.path.join(os.path.expanduser("~"), "Documents", "ae-mcp-bridge", "test_run.txt")

# 写入时间戳，确认执行
with open(output_path, "w", encoding="utf-8") as f:
    f.write(f"Script executed at: {time.ctime()}\n")
    f.write(f"Python version: {os.sys.version}\n")
    f.write("SUCCESS\n")

# 再追加一行
with open(output_path, "a", encoding="utf-8") as f:
    f.write("Done writing.\n")
