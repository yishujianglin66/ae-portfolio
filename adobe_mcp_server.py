#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adobe_mcp_server.py — Adobe MCP Stdio Server
=============================================

作为 MCP Server 运行，通过 stdin/stdout 与 MCP 客户端通信。
每个 Adobe 软件一个 server 实例。

用法:
    python adobe_mcp_server.py --app photoshop
    python adobe_mcp_server.py --app premiere
    python adobe_mcp_server.py --app media_encoder
    python adobe_mcp_server.py --app after_effects
"""

import sys
import json
import argparse
from pathlib import Path

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).parent))

from adobe_mcp_manager import AdobeMCPServer


def main():
    parser = argparse.ArgumentParser(description="Adobe MCP Stdio Server")
    parser.add_argument("--app", required=True, 
                       choices=["photoshop", "premiere", "media_encoder", "after_effects"],
                       help="Target Adobe app")
    parser.add_argument("--jsx", type=str, help="JSX listener path (info only)")
    args = parser.parse_args()
    
    server = AdobeMCPServer(args.app)
    
    # Log startup
    log_path = Path(__file__).parent / f".{args.app}-mcp-bridge" / "mcp_server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    import time
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] MCP Server started for {args.app}\n")
    
    server.run_stdio()


if __name__ == "__main__":
    main()
