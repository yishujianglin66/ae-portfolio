import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

from ae_bridge_base import AEBridgeClient


def _load_dotenv():
    """加载 .env 文件中的环境变量。"""
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
        except Exception:
            pass


_load_dotenv()


def _canonicalize(obj):
    """将对象序列化为规范 JSON 字符串（用于签名）。"""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sign_command(command_data, secret, timestamp=None):
    """为命令数据添加 HMAC-SHA256 签名。"""
    if timestamp is None:
        timestamp = int(time.time())

    data = dict(command_data)
    data["timestamp"] = timestamp

    canonical = _canonicalize(data)
    signature = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    data["signature"] = signature
    data["signature_alg"] = "HMAC-SHA256"
    return data


class MCPBridgeClient(AEBridgeClient):
    """MCP Bridge 客户端（command/script 协议）。

    继承 AEBridgeClient 的文件交换、轮询、清除逻辑，
    保留独立的 _sign_command 签名流程（添加 timestamp + signature_alg）。
    """

    def __init__(self, secret=None):
        documents_dir = Path(os.environ.get('USERPROFILE', '')).joinpath('Documents')
        self.bridge_dir = documents_dir.joinpath('ae-mcp-bridge')
        self.log_file = self.bridge_dir.joinpath('bridge.log')

        resolved_secret = secret or os.environ.get("MCP_BRIDGE_SECRET", "")
        super().__init__(
            command_file=str(self.bridge_dir.joinpath('command.json')),
            result_file=str(self.bridge_dir.joinpath('result.json')),
            timeout=10,
            poll_interval=0.2,
            signature_enabled=bool(resolved_secret),
            secret=resolved_secret,
        )

        self.bridge_dir.mkdir(parents=True, exist_ok=True)

    def _load_secret(self) -> str:
        # secret 已通过构造函数传入，此处返回环境变量值作为 fallback
        return os.environ.get("MCP_BRIDGE_SECRET", "")

    def _is_result_ready(self, result: dict[str, Any]) -> bool:
        """MCP Bridge 协议：status 字段为 success/error/timeout 时结果就绪。"""
        return result.get('status') in ['success', 'error', 'timeout']

    def send_command(self, script_content, timeout=10):
        self.timeout = timeout

        cmd_data = {
            "command": "execute_script",
            "script": script_content,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "status": "pending"
        }

        if self.signature_enabled:
            cmd_data = _sign_command(cmd_data, self.secret)

        self._write_command_file(cmd_data)
        return self._wait_for_result()

    def check_status(self):
        if os.path.exists(self.command_file):
            try:
                with open(self.command_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return {"status": "not_running"}

    def get_logs(self, lines=50):
        if self.log_file.exists():
            with open(self.log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines_list = content.strip().split('\n')
                return '\n'.join(lines_list[-lines:])
        return "No logs available"

def send_test_command():
    client = MCPBridgeClient()

    script = """
    var comp = app.project.items.addComp("Test_MCP_Bridge", 1920, 1080, 1, 10, 30);
    var textLayer = comp.layers.addText("MCP Bridge Test");
    var textProp = textLayer.property("ADBE Text Properties").property("ADBE Text Document");
    var doc = textProp.value;
    doc.fontSize = 48;
    doc.fillColor = [1, 0, 0];
    textProp.setValue(doc);
    textLayer.property("Position").setValue([960, 540]);
    { status: "success", compName: comp.name, layerCount: comp.numLayers }
    """

    print("Sending test command to AE...")
    result = client.send_command(script, timeout=15)
    print("Result:", json.dumps(result, indent=2, ensure_ascii=False))

    return result

if __name__ == "__main__":
    send_test_command()
