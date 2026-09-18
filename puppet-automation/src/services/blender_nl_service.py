"""Blender NL Service - 自然语言 → Blender 操作服务.

将用户自然语言指令转换为 Blender Python (bpy) 脚本并执行，
包含：中文 Prompt 构建、LLM 网关调用、静态安全审查、
Blender 执行、错误重试五大核心能力。
"""
from __future__ import annotations

import asyncio
import importlib
import importlib.machinery
import importlib.util
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

# ---------------------------------------------------------------------------
# Puppet-Automation shim 导入（与 bridges/blender_ae_bridge.py 保持一致）
# ---------------------------------------------------------------------------

def _ensure_puppet_automation_shim() -> None:
    """注册 puppet_automation 包别名 (目录是 puppet-automation 含连字符)。"""
    if "puppet_automation" in sys.modules and "puppet_automation.src" in sys.modules:
        return
    _project_root = Path(__file__).resolve().parent.parent.parent.parent
    _pa_dir = _project_root / "puppet-automation"
    _src_dir = _pa_dir / "src"
    if "puppet_automation" not in sys.modules:
        _pkg = importlib.util.module_from_spec(
            importlib.machinery.ModuleSpec("puppet_automation", loader=None, is_package=True)
        )
        _pkg.__path__ = [str(_pa_dir)]
        sys.modules["puppet_automation"] = _pkg
    if "puppet_automation.src" not in sys.modules:
        _src_init = _src_dir / "__init__.py"
        if _src_init.exists():
            _spec = importlib.util.spec_from_file_location(
                "puppet_automation.src", _src_init,
                submodule_search_locations=[str(_src_dir)]
            )
        else:
            _spec = importlib.machinery.ModuleSpec(
                "puppet_automation.src", loader=None, is_package=True
            )
            _spec.submodule_search_locations = [str(_src_dir)]
        _src_pkg = importlib.util.module_from_spec(_spec)
        sys.modules["puppet_automation.src"] = _src_pkg
        if _spec.loader is not None:
            _spec.loader.exec_module(_src_pkg)


# ---------------------------------------------------------------------------
# LLM 网关动态加载（core 目录可能不在 sys.path）
# ---------------------------------------------------------------------------

def _load_llm_gateway():
    """动态加载 core.llm_gateway，失败时返回 None。

    返回：(chat_with_routing_func, chat_func, TaskType_enum, llm_gateway_instance) 或 None
    """
    try:
        _project_root = Path(__file__).resolve().parent.parent.parent.parent
        if str(_project_root) not in sys.path:
            sys.path.insert(0, str(_project_root))
    except Exception:
        pass

    try:
        llm_mod = importlib.import_module("core.llm_gateway")
        TaskType = getattr(llm_mod, "TaskType", None)
        llm_gateway = getattr(llm_mod, "llm_gateway", None)
        chat_with_routing = getattr(llm_mod, "chat_with_routing", None)
        chat = getattr(llm_mod, "chat", None)

        # 确保网关已配置（幂等）
        if llm_gateway is not None and hasattr(llm_gateway, "ensure_configured"):
            try:
                llm_gateway.ensure_configured()
            except Exception as e:
                logger.warning(f"LLM 网关 ensure_configured 失败（降级继续）: {e}")

        return {
            "chat_with_routing": chat_with_routing,
            "chat": chat,
            "TaskType": TaskType,
            "gateway": llm_gateway,
        }
    except ImportError as e:
        logger.warning(f"core.llm_gateway 导入失败，LLM 能力将不可用: {e}")
        return None
    except Exception as e:
        logger.warning(f"core.llm_gateway 加载异常: {e}")
        return None


# ---------------------------------------------------------------------------
# Blender Python API 速查 few-shot 片段
# ---------------------------------------------------------------------------

BLENDER_API_FEW_SHOT = r"""
# ============================================================
# Blender Python API 速查参考（请据此生成正确的 bpy 脚本）
# ============================================================

## 1. 对象操作
import bpy
# 全选/取消
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.select_all(action='DESELECT')
# 删除物体
bpy.ops.object.delete(use_global=False)
# 添加物体
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0, 0, 0))
bpy.ops.object.light_add(type='AREA', location=(0, 0, 5))
bpy.ops.object.camera_add(location=(0, -5, 2))
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
# 重命名
obj = bpy.context.active_object
obj.name = "MyObject"
# 设置位置/旋转/缩放
obj.location = (1.0, 2.0, 3.0)
obj.rotation_euler = (0.0, 0.0, 1.5708)
obj.scale = (2.0, 2.0, 2.0)

## 2. 材质与节点
mat = bpy.data.materials.new(name="NewMaterial")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs['Base Color'].default_value = (0.8, 0.2, 0.2, 1.0)  # RGBA
bsdf.inputs['Roughness'].default_value = 0.5
if obj.data.materials:
    obj.data.materials[0] = mat
else:
    obj.data.materials.append(mat)

## 3. 场景与渲染
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = 'PNG'
scene.frame_start = 1
scene.frame_end = 60
scene.camera = obj  # 设置相机
bpy.context.scene.camera = bpy.data.objects["Main_Camera"]
bpy.ops.render.render(write_still=True)

## 4. 动画与关键帧
obj.location = (0, 0, 0)
obj.keyframe_insert(data_path="location", frame=1)
obj.location = (5, 0, 0)
obj.keyframe_insert(data_path="location", frame=60)

## 5. 导入导出
bpy.ops.import_scene.fbx(filepath=r"C:\path\to\model.fbx")
bpy.ops.export_scene.fbx(filepath=r"C:\out\model.fbx", use_selection=False)
bpy.ops.wm.save_mainfile(filepath=r"C:\out\scene.blend")
bpy.ops.wm.open_mainfile(filepath=r"C:\in\scene.blend")

## 6. bpy.data 数据访问（不依赖 bpy.ops，更安全）
# 获取物体
cube = bpy.data.objects.get("Cube")
if cube:
    cube.location.x += 1.0
# 创建网格
mesh = bpy.data.meshes.new("MyMesh")
mesh_obj = bpy.data.objects.new("MyMeshObj", mesh)
bpy.context.collection.objects.link(mesh_obj)
# 创建集合
new_col = bpy.data.collections.new("MyCollection")
bpy.context.scene.collection.children.link(new_col)
"""


# ---------------------------------------------------------------------------
# Prompt 模板
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """你是专业的 Blender Python (bpy) 自动化脚本工程师。
你的任务是将用户的中文自然语言指令转换为可以直接在 Blender 中执行的纯 bpy Python 脚本。

## 输出要求（严格遵守）
1. 只输出 Python 代码，不要任何解释、Markdown 标记、前置后置说明。
2. 代码必须以 `import bpy` 开头。
3. 所有注释使用中文（# 注释）。
4. 只使用 Blender Python API（bpy.*），禁止调用任何系统级 API。
5. 代码独立可运行：假设在 blender --background --python <script.py> 模式下执行。
6. 禁止使用：exec、eval、subprocess、os.system、__import__、globals、locals、compile。
7. 文件操作（open）仅限 bpy 原生需要的场景，且必须使用二进制模式（'rb'/'wb'）。
8. 如果指令不够明确，请根据常见场景做合理假设，并在注释中标明。

## Blender 背景模式注意事项
- 部分 bpy.ops 依赖 3D 视图上下文，背景模式下可能失败。
- 优先使用 bpy.data.* 直接操作数据，而不是 bpy.ops.*。
- 不要依赖 bpy.context.active_object，而是通过 bpy.data.objects.get("Name") 获取。
- 如果必须使用 bpy.ops.object.mode_set 等操作，确保先选中并激活正确的对象。

## API 速查参考
{api_few_shot}

## 场景上下文（如果有）
{scene_context}

## 用户指令
{user_command}

{error_feedback}

## 现在请生成完整的 bpy Python 脚本（以 import bpy 开头）：
"""

ERROR_FEEDBACK_TEMPLATE = """
## 上一次执行错误（请根据错误修复脚本）
上次生成的代码：
```python
{previous_code}
```

错误 Traceback：
```
{error_traceback}
```

请根据以上错误信息修正代码，重新生成完整的 bpy 脚本。
"""


# ---------------------------------------------------------------------------
# 安全审查
# ---------------------------------------------------------------------------

# 高危调用黑名单（正则，匹配单词边界，避免误伤 bpy 正常代码）
_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"\bexec\s*\(", "禁止使用 exec() 动态执行代码"),
    (r"\beval\s*\(", "禁止使用 eval() 动态求值"),
    (r"\bcompile\s*\(", "禁止使用 compile() 编译代码"),
    (r"\bsubprocess\b", "禁止导入或调用 subprocess 模块"),
    (r"\bos\.system\s*\(", "禁止使用 os.system() 执行系统命令"),
    (r"\bos\.popen\s*\(", "禁止使用 os.popen()"),
    (r"\bos\.execl\b", "禁止使用 os.execl* 系列函数"),
    (r"\b__import__\s*\(", "禁止使用 __import__() 动态导入"),
    (r"\bglobals\s*\(\)", "禁止访问 globals()"),
    (r"\blocals\s*\(\)", "禁止访问 locals()"),
    (r"\bgetattr\s*\(\s*__builtins__", "禁止通过 __builtins__ 获取危险函数"),
    (r"\bimport\s+ctypes\b", "禁止导入 ctypes"),
    (r"\bimport\s+socket\b", "禁止导入 socket"),
    (r"\bimport\s+requests\b", "禁止导入 requests（网络请求）"),
    (r"\bimport\s+urllib\b", "禁止导入 urllib（网络请求）"),
    (r"\bimport\s+httplib\b", "禁止导入 httplib（网络请求）"),
    (r"\bimport\s+shutil\b", "禁止导入 shutil（文件操作高危）"),
]

# open() 调用需要额外检查：只允许二进制模式（rb/wb/ab/r+b/w+b/a+b）
_OPEN_PATTERN = re.compile(
    r"\bopen\s*\(\s*[^)]*?,\s*['\"]([^'\"]*)['\"]",
    re.DOTALL,
)


@dataclass
class SafetyCheckResult:
    """安全审查结果。"""
    passed: bool
    violations: list[str] = field(default_factory=list)

    @property
    def error_message(self) -> str:
        if self.passed:
            return ""
        return "脚本安全审查未通过，检测到以下高危调用：\n" + "\n".join(
            f"  - {v}" for v in self.violations
        )


def _safety_check(generated_code: str) -> SafetyCheckResult:
    """静态代码安全审查：拦截高危调用。

    Args:
        generated_code: LLM 生成的 bpy 脚本

    Returns:
        SafetyCheckResult(passed, violations)
    """
    violations: list[str] = []

    if not generated_code or not generated_code.strip():
        violations.append("生成的代码为空")
        return SafetyCheckResult(passed=False, violations=violations)

    # 1. 正则黑名单匹配
    for pattern, reason in _DANGEROUS_PATTERNS:
        if re.search(pattern, generated_code):
            violations.append(reason)

    # 2. open() 模式检查
    for match in _OPEN_PATTERN.finditer(generated_code):
        mode = match.group(1).lower()
        # 只允许：rb, wb, ab, r+b, w+b, a+b 及其排列变体（必须包含 'b' 二进制标记）
        if "b" not in mode:
            violations.append(
                f"open() 调用检测到非二进制模式 '{mode}'，仅限二进制模式（rb/wb/ab 等）"
            )

    return SafetyCheckResult(passed=len(violations) == 0, violations=violations)


# ---------------------------------------------------------------------------
# 执行结果
# ---------------------------------------------------------------------------

@dataclass
class BlenderNLResult:
    """自然语言 → Blender 执行结果。"""
    status: str  # "success" | "safety_violation" | "llm_unavailable" | "execution_failed" | "max_attempts_exceeded"
    generated_code: str = ""
    attempt_count: int = 0
    stdout: str = ""
    stderr: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_code": self.generated_code,
            "attempt_count": self.attempt_count,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# BlenderNLService 核心类
# ---------------------------------------------------------------------------

class BlenderNLService:
    """自然语言 → Blender 操作服务。

    流程：
        1. 构建中文 Prompt（含用户指令 + 上下文 + API 速查 few-shot）
        2. 通过 LLM 网关生成 bpy 脚本（TaskType 优先 code_generation / RENDER_AUTOMATION）
        3. 静态安全审查（拦截 exec/eval/subprocess 等高危调用）
        4. 通过 BlenderEngine --python <tmp> 模式执行
        5. 失败时将 traceback 附入 Prompt，最多重试 2 次
    """

    def __init__(
        self,
        blender_engine: Any | None = None,
        llm_gateway_bundle: dict[str, Any] | None = None,
        knowledge_api_dir: Path | str | None = None,
    ) -> None:
        """初始化服务。

        Args:
            blender_engine: BlenderEngine 实例（可选，None 时延迟创建）
            llm_gateway_bundle: _load_llm_gateway() 返回的 bundle（可选，None 时自动加载）
            knowledge_api_dir: Blender Python API 参考目录（可选，用于动态加载 few-shot）
        """
        self._blender_engine = blender_engine
        self._llm_bundle = llm_gateway_bundle
        self._knowledge_api_dir = Path(knowledge_api_dir) if knowledge_api_dir else None
        self._api_few_shot_cached: str | None = None
        logger.info("BlenderNLService initialized")

    # ------------------------------------------------------------------
    # 延迟属性
    # ------------------------------------------------------------------

    @property
    def blender_engine(self):
        """延迟获取 BlenderEngine。"""
        if self._blender_engine is None:
            _ensure_puppet_automation_shim()
            try:
                from puppet_automation.src.engines.blender import BlenderEngine
                self._blender_engine = BlenderEngine()
            except Exception as e:
                logger.warning(f"BlenderEngine 创建失败（将使用 CLI 模式兜底）: {e}")
                self._blender_engine = False  # 标记为不可用，避免重复尝试
        return self._blender_engine

    @property
    def llm_bundle(self) -> dict[str, Any] | None:
        """延迟获取 LLM 网关 bundle。"""
        if self._llm_bundle is None:
            self._llm_bundle = _load_llm_gateway()
            if self._llm_bundle is None:
                self._llm_bundle = False  # 标记为不可用
        return self._llm_bundle if self._llm_bundle is not False else None

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def _load_api_few_shot(self) -> str:
        """从知识库目录动态加载 Blender Python API 速查 few-shot。"""
        if self._api_few_shot_cached is not None:
            return self._api_few_shot_cached

        content_parts = [BLENDER_API_FEW_SHOT]

        if self._knowledge_api_dir and self._knowledge_api_dir.exists():
            try:
                md_files = sorted(self._knowledge_api_dir.glob("*.md"))[:6]
                extra = []
                for md in md_files:
                    try:
                        text = md.read_text(encoding="utf-8", errors="ignore")
                        # 提取代码块
                        code_blocks = re.findall(r"```python\n(.*?)```", text, re.DOTALL)
                        if code_blocks:
                            extra.append(f"### 摘自 {md.name}:")
                            for block in code_blocks[:2]:
                                extra.append(block.strip()[:500])
                    except Exception:
                        continue
                if extra:
                    content_parts.append("\n\n## 知识库补充示例\n" + "\n\n".join(extra))
            except Exception as e:
                logger.debug(f"知识库 API 目录加载失败（使用默认 few-shot）: {e}")

        self._api_few_shot_cached = "\n".join(content_parts)
        return self._api_few_shot_cached

    def _build_prompt(
        self,
        command: str,
        scene_context: str | None,
        previous_code: str | None = None,
        previous_error: str | None = None,
    ) -> tuple[str, str]:
        """构建 system prompt 与用户消息。

        Returns:
            (system_prompt, user_message)
        """
        api_few_shot = self._load_api_few_shot()

        error_feedback = ""
        if previous_code and previous_error:
            error_feedback = ERROR_FEEDBACK_TEMPLATE.format(
                previous_code=previous_code,
                error_traceback=previous_error,
            )

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            api_few_shot=api_few_shot,
            scene_context=scene_context or "（无）",
            user_command=command,
            error_feedback=error_feedback,
        )
        user_message = f"请根据以下指令生成 Blender Python 脚本：\n指令：{command}"
        return system_prompt, user_message

    # ------------------------------------------------------------------
    # LLM 调用
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        system_prompt: str,
        user_message: str,
    ) -> tuple[bool, str]:
        """调用 LLM 网关生成代码。

        Returns:
            (success: bool, content_or_error: str)
        """
        bundle = self.llm_bundle
        if bundle is None:
            return False, "LLM 网关不可用（core.llm_gateway 加载失败或未配置 API Key）"

        TaskType = bundle.get("TaskType")
        chat_with_routing = bundle.get("chat_with_routing")
        chat = bundle.get("chat")

        # 选择 TaskType：优先用代码生成相关的路由
        task_type = None
        if TaskType is not None:
            # TaskType 中没有 code_generation 时，依次尝试相近类型
            for candidate_name in ["RENDER_AUTOMATION", "ADOBE_AUTOMATION", "SCENE_GENERATION_3D", "GENERAL"]:
                candidate = getattr(TaskType, candidate_name, None)
                if candidate is not None:
                    task_type = candidate
                    break

        try:
            # 路径 1：chat_with_routing（智能路由，优先）
            if chat_with_routing is not None and task_type is not None:
                logger.debug(f"调用 LLM chat_with_routing (task_type={task_type.name})")
                resp = await chat_with_routing(
                    message=user_message,
                    task_type=task_type,
                    system_prompt=system_prompt,
                    temperature=0.2,
                    max_tokens=4096,
                )
                if getattr(resp, "success", False):
                    return True, self._clean_code_block(getattr(resp, "content", ""))
                else:
                    logger.warning(f"chat_with_routing 失败: {getattr(resp, 'error', 'unknown')}")

            # 路径 2：fallback 到 chat()
            if chat is not None:
                logger.debug("调用 LLM chat (fallback)")
                resp = await chat(
                    message=user_message,
                    system_prompt=system_prompt,
                    temperature=0.2,
                    max_tokens=4096,
                )
                if getattr(resp, "success", False):
                    return True, self._clean_code_block(getattr(resp, "content", ""))
                else:
                    return False, f"LLM 调用失败: {getattr(resp, 'error', 'unknown error')}"

            return False, "LLM 网关无可用调用接口（chat_with_routing/chat 均未找到）"
        except Exception as e:
            logger.exception(f"LLM 调用异常: {e}")
            return False, f"LLM 调用异常: {e}"

    @staticmethod
    def _clean_code_block(raw: str) -> str:
        """从 LLM 响应中提取纯代码（去除 Markdown ``` 围栏）。"""
        if not raw:
            return ""
        text = raw.strip()
        # 去除 ```python ... ``` 或 ``` ... ``` 围栏
        fenced = re.match(r"^```(?:python)?\s*\n([\s\S]*?)\n```\s*$", text)
        if fenced:
            return fenced.group(1).strip()
        # 若响应以 ``` 开头但未闭合，则去除首行
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        # 去掉末尾 ```
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    # ------------------------------------------------------------------
    # Blender 脚本执行
    # ------------------------------------------------------------------

    async def _execute_blender_script(
        self,
        script_content: str,
    ) -> tuple[bool, str, str]:
        """执行 Blender Python 脚本。

        优先使用 BlenderEngine.run_script()，不可用时回退到 CLI 子进程模式。

        Returns:
            (success, stdout, stderr)
        """
        engine = self.blender_engine

        # 路径 1：BlenderEngine.run_script
        if engine and engine is not False:
            try:
                run_script = getattr(engine, "run_script", None)
                if run_script is not None:
                    result = await run_script(script_content)
                    success = bool(getattr(result, "success", False))
                    metadata = getattr(result, "metadata", {}) or {}
                    stdout = str(metadata.get("stdout_tail", ""))
                    stderr = str(getattr(result, "error", "") or "")
                    return success, stdout, stderr
            except Exception as e:
                logger.warning(f"BlenderEngine.run_script 异常，回退 CLI 模式: {e}")

        # 路径 2：CLI --python <tmp> 兜底
        return await self._execute_blender_cli(script_content)

    async def _execute_blender_cli(
        self,
        script_content: str,
    ) -> tuple[bool, str, str]:
        """通过 blender --background --python <tmp> 子进程执行脚本。"""
        import subprocess

        # 写入临时脚本
        script_file = Path(tempfile.gettempdir()) / f"bl_nl_{id(self)}_{asyncio.get_event_loop().time():.0f}.py"
        try:
            script_file.write_text(script_content, encoding="utf-8")

            # 尝试从 settings 或环境变量获取 blender 路径
            blender_exe: str | None = None
            try:
                _ensure_puppet_automation_shim()
                from puppet_automation.src.config import settings
                blender_exe = str(getattr(settings, "blender_path", "")) or None
            except Exception:
                blender_exe = None

            if not blender_exe:
                import shutil
                blender_exe = shutil.which("blender")

            if not blender_exe:
                return False, "", "无法找到 Blender 可执行文件，请设置 settings.blender_path 或将 blender 加入 PATH"

            cmd = [blender_exe, "--background", "--python", str(script_file)]

            def _run():
                try:
                    proc = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=14400,
                    )
                    return proc.returncode == 0, proc.stdout or "", proc.stderr or ""
                except subprocess.TimeoutExpired:
                    return False, "", "Blender 执行超时（>4小时）"
                except FileNotFoundError:
                    return False, "", f"Blender 可执行文件未找到: {blender_exe}"
                except Exception as e:
                    return False, "", f"执行异常: {e}"

            return await asyncio.to_thread(_run)
        finally:
            script_file.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    async def execute(
        self,
        command: str,
        scene_context: str | None = None,
        max_attempts: int = 2,
    ) -> BlenderNLResult:
        """自然语言 → Blender 执行主流程。

        Args:
            command: 用户自然语言指令（中文）
            scene_context: 场景上下文描述（可选，如"当前场景有一个名为'Cube'的立方体"）
            max_attempts: 最大尝试次数（默认 2，含首次，即最多重试 1 次自修复）

        Returns:
            BlenderNLResult
        """
        if not command or not command.strip():
            return BlenderNLResult(
                status="execution_failed",
                error="指令不能为空",
            )

        max_attempts = max(1, min(max_attempts, 5))  # 限制 1~5 次
        previous_code: str | None = None
        previous_error: str | None = None

        for attempt in range(1, max_attempts + 1):
            logger.info(f"[BlenderNLService] 第 {attempt}/{max_attempts} 次尝试")

            # Step 1: 构建 Prompt
            system_prompt, user_message = self._build_prompt(
                command=command,
                scene_context=scene_context,
                previous_code=previous_code,
                previous_error=previous_error,
            )

            # Step 2: 调用 LLM 生成代码
            llm_ok, llm_content = await self._call_llm(system_prompt, user_message)
            if not llm_ok:
                if attempt == max_attempts:
                    return BlenderNLResult(
                        status="llm_unavailable",
                        generated_code="",
                        attempt_count=attempt,
                        error=llm_content,
                    )
                previous_error = f"LLM 调用失败: {llm_content}"
                continue

            generated_code = llm_content
            if not generated_code.strip():
                if attempt == max_attempts:
                    return BlenderNLResult(
                        status="execution_failed",
                        generated_code="",
                        attempt_count=attempt,
                        error="LLM 生成的代码为空",
                    )
                previous_error = "LLM 返回空代码"
                continue

            # Step 3: 静态安全审查
            safety = _safety_check(generated_code)
            if not safety.passed:
                logger.warning(f"[BlenderNLService] 安全审查未通过: {safety.violations}")
                return BlenderNLResult(
                    status="safety_violation",
                    generated_code=generated_code,
                    attempt_count=attempt,
                    error=safety.error_message,
                )

            # Step 4: 执行脚本
            exec_ok, stdout, stderr = await self._execute_blender_script(generated_code)
            if exec_ok:
                logger.info(f"[BlenderNLService] 第 {attempt} 次执行成功")
                return BlenderNLResult(
                    status="success",
                    generated_code=generated_code,
                    attempt_count=attempt,
                    stdout=stdout,
                    stderr=stderr,
                    error="",
                )

            # 失败：记录并准备重试
            previous_code = generated_code
            previous_error = (stderr or stdout or "未知执行错误")[-2000:]
            logger.warning(
                f"[BlenderNLService] 第 {attempt} 次执行失败，"
                f"{'准备重试' if attempt < max_attempts else '已达最大次数'}"
            )

        # 达到最大尝试次数
        return BlenderNLResult(
            status="max_attempts_exceeded",
            generated_code=previous_code or "",
            attempt_count=max_attempts,
            stdout="",
            stderr=previous_error or "",
            error=f"执行失败，已达最大尝试次数 {max_attempts}。最后一次错误：{previous_error or '未知'}",
        )


# ---------------------------------------------------------------------------
# 模块级便捷函数
# ---------------------------------------------------------------------------

_default_service: BlenderNLService | None = None


def get_default_service() -> BlenderNLService:
    """获取（懒加载）默认服务单例。"""
    global _default_service
    if _default_service is None:
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        api_ref_dir = project_root / "15-3D模型与骨骼动画知识库" / "07-Blender Python API参考"
        _default_service = BlenderNLService(
            knowledge_api_dir=api_ref_dir if api_ref_dir.exists() else None,
        )
    return _default_service


async def nl_execute(
    command: str,
    scene_context: str | None = None,
    max_attempts: int = 2,
) -> BlenderNLResult:
    """便捷函数：调用默认服务执行自然语言指令。"""
    service = get_default_service()
    return await service.execute(
        command=command,
        scene_context=scene_context,
        max_attempts=max_attempts,
    )
