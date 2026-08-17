#!/usr/bin/env python3
"""AEP (After Effects Project) 二进制结构解析器

离线解析 AEP 文件的块状二进制结构，提取：
- 项目头部信息（签名、字节序、版本号、时间基准）
- 合成（composition）列表（分辨率、时长、帧率候选）
- 图层（layer）列表
- 效果引用（通过 matchName 标识，存储在 "mn" 子块中）
- 素材文件路径

AEP 文件格式要点：
- 文件开头为 "RIFX"（大端字节序）或 "FORM"（小端字节序）签名
- 随后 4 字节为文件大小，再 4 字节为 form type（"Egg!"）
- 之后为嵌套的块结构：4 字节 type + 4 字节 length + data
- RIFF 风格 LIST 容器块：`LIST <length> <list_type 4 bytes> <sub-chunks>`
  递归子块前必须跳过 4 字节 list_type
- 关键 LIST list_type：
  - `Item`：项目项（含 CIFO/CIF2/CIF3 子块的是合成，否则是素材/文件夹）
  - `Fold`：文件夹
  - `Layr`/`SLay`/`CLay`/`DLay`/`SecL`：图层变体
  - `CIFO`/`CIF2`/`CIF3`：合成信息（含 CpS2/CapS/CPTm/CROI/CcCt）
  - `tdgp`：图层组（含属性/效果/matchName）
  - `Gide`/`Ewst`：导轨/状态
- 关键叶块：
  - `idta`：合成/素材数据（含维度候选、时长候选）
  - `ldta`：图层数据（含图层 ID、时长候选、名称）
  - `Utf8`：UTF-8 字符串（项目/合成/图层名称）
  - `mn`/`mn  `：matchName（效果标识，通常以 "ADBE" 前缀）
  - `CPTm`：合成时间
  - `CROI`：合成 ROI
  - `fnme`/`Fnme`：文件名

仅使用 Python 标准库，采用流式顺序读取以支持大文件（100MB+）。
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path
from typing import Any, BinaryIO

# ---------------------------------------------------------------------------
# 常量定义
# ---------------------------------------------------------------------------

# LIST 容器的 list_type 集合（识别容器类型）
LIST_ITEM: str = 'Item'           # 项目项（合成/素材/文件夹）
LIST_FOLDER: str = 'Fold'         # 文件夹
LIST_LAYER_TYPES: set[str] = {    # 图层变体
    'Layr', 'SLay', 'CLay', 'DLay', 'SecL',
}
LIST_COMP_INFO_TYPES: set[str] = {  # 合成信息
    'CIFO', 'CIF2', 'CIF3',
}
LIST_COMP_PARAM_TYPES: set[str] = {  # 合成参数
    'CpS2', 'CapS',
}
LIST_GROUP_TYPES: set[str] = {    # 图层组/属性组
    'tdgp', 'adgm', 'gmPt',
}
LIST_OTHER_CONTAINER_TYPES: set[str] = {  # 其他容器
    'Gide', 'Ewst', 'list', 'Ordl', 'Stds', 'StC2',
}

# matchName 块类型（效果的 matchName 存于此）
MATCH_NAME_TYPES: set[bytes] = {b'mn  ', b'mn', b'mnM ', b'mnNm', b'mn\x00\x00'}

# 字符串型块类型
STRING_TYPES: set[bytes] = {
    b'Utf8', b'utf8', b'Utf1', b'Utf0', b'utf1', b'utf0',
    b'ASC ', b'asc ', b'str ', b'Str ', b'name', b'Name',
    b'fnme', b'Fnme', b'opti', b'nmpt',
}

# 素材/源 ID 块类型
SOURCE_ID_TYPES: set[bytes] = {b'ssid', b'ssig', b'sfid', b'src '}

# 文件扩展名集合（用于路径二次确认）
FILE_EXTS: set[str] = {
    'aep', 'aet', 'mp4', 'mov', 'avi', 'm4v', 'mkv', 'wmv', 'flv', 'webm',
    'mpg', 'mpeg', 'm2ts', 'mts', 'png', 'jpg', 'jpeg', 'psd', 'ai', 'tif',
    'tiff', 'tga', 'exr', 'gif', 'bmp', 'svg', 'webp', 'hdr', 'cr2', 'nef',
    'dng', 'wav', 'mp3', 'aac', 'm4a', 'aiff', 'aif', 'flac', 'ogg', 'wma',
    'opus', 'pdf', 'txt', 'csv', 'obj', 'fbx', 'glb', 'gltf',
}

# 文件路径匹配正则
PATH_RE = re.compile(
    r'(?:'
    r'[A-Za-z]:[\\/][^\x00-\x1f<>|"?*\r\n]+'
    r'|\\\\[^\x00-\x1f<>|"?*\r\n]+'
    r'|/[^\x00-\x1f<>|"?*\r\n]+'
    r'|(?<![A-Za-z0-9_])[^\x00-\x1f<>|"?*\r\n\s/\\][^\x00-\x1f<>|"?*\r\n]*'
    r'\.(?:aep|aet|mp4|mov|avi|m4v|mkv|wmv|flv|webm|mpg|mpeg|m2ts|mts|'
    r'png|jpg|jpeg|psd|ai|tif|tiff|tga|exr|gif|bmp|svg|webp|hdr|cr2|nef|dng|'
    r'wav|mp3|aac|m4a|aiff|aif|flac|ogg|wma|opus|pdf|obj|fbx|glb|gltf)'
    r')',
    re.IGNORECASE,
)

# matchName 前缀模式（用于全局补充扫描）
MATCH_NAME_PREFIX_RE = re.compile(rb'ADBE[\x20-\x7e]{2,80}')

MAX_RECURSION_DEPTH: int = 80
STREAM_SCAN_THRESHOLD: int = 4 * 1024 * 1024
SCAN_BLOCK: int = 1024 * 1024
MAX_LEAF_READ: int = 16 * 1024 * 1024


# ---------------------------------------------------------------------------
# 解析器
# ---------------------------------------------------------------------------


class AEPParser:
    """AEP 文件二进制解析器。

    使用流式顺序读取解析 RIFX/FORM 容器内的嵌套块结构。
    正确处理 RIFF 风格 LIST 块：递归子块前跳过 4 字节 list_type。
    """

    def __init__(self, file_path: str | Path) -> None:
        self.file_path: Path = Path(file_path)
        self.endian: str = '>'
        self.file_size: int = 0

        # 解析结果
        self.file_info: dict[str, Any] = {}
        self.header: dict[str, Any] = {}
        self.compositions: list[dict[str, Any]] = []
        self.layers: list[dict[str, Any]] = []
        self.footage_items: list[dict[str, Any]] = []
        self.folders: list[dict[str, Any]] = []
        self.match_names: list[dict[str, Any]] = []
        self.file_paths: list[dict[str, Any]] = []
        self.raw_strings: list[dict[str, Any]] = []
        self.chunk_stats: dict[str, int] = {}

        # 上下文栈（list_type 路径）
        self._context_stack: list[str] = []
        self._comp_index: int = -1
        self._layer_index: int = -1
        self._folder_depth: int = 0

        # 去重集合
        self._seen_match: set[tuple[str, str]] = set()
        self._seen_paths: set[str] = set()
        self._seen_strings: set[str] = set()

        # 统计
        self._chunk_count: int = 0
        self._max_depth: int = 0

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def parse(self) -> dict[str, Any]:
        """解析 AEP 文件并返回结构化结果字典。"""
        self.file_size = self.file_path.stat().st_size
        with open(self.file_path, 'rb') as f:
            self._parse_root(f)
        self._global_supplement_scan()
        self._finalize()
        return self._build_result()

    # ------------------------------------------------------------------
    # 根容器解析
    # ------------------------------------------------------------------

    def _parse_root(self, f: BinaryIO) -> None:
        signature = f.read(4)
        if len(signature) < 4:
            raise ValueError("文件过短，无法读取签名")

        if signature == b'RIFX':
            self.endian = '>'
        elif signature in (b'FORM', b'RIFF'):
            self.endian = '<'
        else:
            raise ValueError(f"未知的 AEP 签名: {signature!r}")

        size_bytes = f.read(4)
        if len(size_bytes) < 4:
            raise ValueError("文件过短，无法读取大小字段")
        form_type = f.read(4)

        if signature in (b'FORM', b'RIFF'):
            be_size = struct.unpack('>I', size_bytes)[0]
            le_size = struct.unpack('<I', size_bytes)[0]
            target = self.file_size - 8
            self.endian = '>' if abs(be_size - target) <= abs(le_size - target) else '<'

        declared_size = struct.unpack(self.endian + 'I', size_bytes)[0]

        self.file_info = {
            'file_name': self.file_path.name,
            'file_path': str(self.file_path),
            'file_size': self.file_size,
            'signature': signature.decode('ascii', errors='replace'),
            'byte_order': 'big-endian' if self.endian == '>' else 'little-endian',
            'form_type': form_type.decode('ascii', errors='replace'),
            'declared_size': declared_size,
        }

        content_end = f.tell() + max(declared_size - 4, 0)
        end = min(content_end, self.file_size)
        self._parse_chunks(f, end, depth=0)

    # ------------------------------------------------------------------
    # 块遍历（核心：正确处理 LIST 块）
    # ------------------------------------------------------------------

    def _parse_chunks(self, f: BinaryIO, end: int, depth: int) -> None:
        """顺序解析从当前位置到 end 之间的所有块。

        对 LIST 块特殊处理：读取 4 字节 list_type，递归子块时跳过 list_type。
        """
        if depth > MAX_RECURSION_DEPTH:
            return
        self._max_depth = max(self._max_depth, depth)

        while f.tell() + 8 <= end:
            pos = f.tell()
            header = f.read(8)
            if len(header) < 8:
                break
            chunk_type = header[:4]
            chunk_length = struct.unpack(self.endian + 'I', header[4:8])[0]
            data_start = f.tell()

            self._chunk_count += 1
            type_str = chunk_type.decode('ascii', errors='replace')
            self.chunk_stats[type_str] = self.chunk_stats.get(type_str, 0) + 1

            # 读取 LIST 的 list_type（4 字节，紧跟在 length 之后）
            list_type: str | None = None
            if chunk_type == b'LIST' and chunk_length >= 4:
                lt_bytes = f.read(4)
                list_type = lt_bytes.decode('ascii', errors='replace')

            self._process_chunk(
                f, chunk_type, type_str, list_type,
                chunk_length, data_start, depth, pos,
            )

            # 跳到块末尾（奇数长度有 1 字节填充）
            next_pos = data_start + chunk_length
            if chunk_length % 2 == 1:
                next_pos += 1
            if next_pos <= pos:
                break
            if next_pos > end + 1:
                f.seek(min(next_pos, self.file_size))
                break
            f.seek(next_pos)

    def _process_chunk(
        self,
        f: BinaryIO,
        chunk_type: bytes,
        type_str: str,
        list_type: str | None,
        length: int,
        data_start: int,
        depth: int,
        pos: int,
    ) -> None:
        """处理单个块。LIST 块递归子块（跳过 list_type），叶块直接处理。"""
        # 构建上下文键
        if list_type:
            context_key = f'LIST/{list_type}'
        else:
            context_key = type_str
        self._context_stack.append(context_key)
        context = '/'.join(self._context_stack)

        is_list = (chunk_type == b'LIST' and list_type is not None
                   and 0 < length and depth < MAX_RECURSION_DEPTH)

        if is_list:
            # 进入 LIST 容器
            self._on_list_enter(list_type, context, pos, length, depth, f, data_start)
            # 递归子块：从 data_start + 4（跳过 list_type）到 data_start + length
            child_start = data_start + 4
            child_end = data_start + length
            f.seek(child_start)
            self._parse_chunks(f, child_end, depth + 1)
            self._on_list_exit(list_type, context, pos, length, depth)
        else:
            self._process_leaf(
                f, chunk_type, type_str, length, data_start, context, pos, depth,
            )

        self._context_stack.pop()

    # ------------------------------------------------------------------
    # LIST 容器进出
    # ------------------------------------------------------------------

    def _on_list_enter(
        self, list_type: str, context: str, pos: int, length: int,
        depth: int, f: BinaryIO, data_start: int,
    ) -> None:
        """进入 LIST 容器时触发。根据 list_type 识别容器类型。"""
        if list_type == LIST_ITEM:
            # 判断是合成还是素材：扫描子块是否含 CIFO/CIF2/CIF3
            is_comp = self._item_has_comp_info(f, data_start + 4, data_start + length)
            if is_comp:
                self._comp_index = len(self.compositions)
                self.compositions.append({
                    'index': self._comp_index,
                    'offset': pos,
                    'name': None,
                    'width': None,
                    'height': None,
                    'frame_rate': None,
                    'duration_frames': None,
                    'duration_seconds': None,
                    'pixel_aspect': None,
                    'layer_count': 0,
                    'effects': [],
                    'idta_fields': {},
                    'context': context,
                })
            else:
                # 素材或文件夹，先记录为 footage，后续根据子块修正
                self.footage_items.append({
                    'offset': pos,
                    'name': None,
                    'file_path': None,
                    'width': None,
                    'height': None,
                    'context': context,
                })
        elif list_type in LIST_LAYER_TYPES:
            self._layer_index = len(self.layers)
            comp_idx = self._comp_index if self._comp_index >= 0 else None
            layer_type = list_type  # Layr/SLay/CLay/DLay/SecL
            self.layers.append({
                'index': self._layer_index,
                'offset': pos,
                'name': None,
                'layer_type': layer_type,
                'composition_index': comp_idx,
                'duration_frames': None,
                'effects': [],
                'ldta_fields': {},
                'context': context,
            })
            if comp_idx is not None and comp_idx < len(self.compositions):
                self.compositions[comp_idx]['layer_count'] += 1
        elif list_type == LIST_FOLDER:
            self._folder_depth += 1
            self.folders.append({
                'offset': pos,
                'name': None,
                'context': context,
            })

    def _on_list_exit(
        self, list_type: str, context: str, pos: int, length: int, depth: int,
    ) -> None:
        """离开 LIST 容器时触发。"""
        if list_type == LIST_ITEM:
            self._comp_index = -1
        elif list_type in LIST_LAYER_TYPES:
            self._layer_index = -1
        elif list_type == LIST_FOLDER:
            self._folder_depth -= 1

    def _item_has_comp_info(self, f: BinaryIO, start: int, end: int) -> bool:
        """扫描 LIST/Item 的子块，判断是否含 CIFO/CIF2/CIF3（即是否为合成）。"""
        try:
            f.seek(start)
            while f.tell() + 8 <= end:
                ct = f.read(4)
                ln = struct.unpack(self.endian + 'I', f.read(4))[0]
                ds = f.tell()
                if ct == b'LIST' and ln >= 4:
                    lt = f.read(4).decode('ascii', errors='replace')
                    if lt in LIST_COMP_INFO_TYPES:
                        f.seek(start)
                        return True
                next_pos = ds + ln + (ln % 2)
                if next_pos <= ds:
                    break
                f.seek(next_pos)
            f.seek(start)
            return False
        except Exception:
            f.seek(start)
            return False

    # ------------------------------------------------------------------
    # 叶块处理
    # ------------------------------------------------------------------

    def _process_leaf(
        self,
        f: BinaryIO,
        chunk_type: bytes,
        type_str: str,
        length: int,
        data_start: int,
        context: str,
        pos: int,
        depth: int,
    ) -> None:
        if length <= 0:
            return

        # 版本块 svap
        if type_str == 'svap':
            data = self._read_limited(f, data_start, min(length, 8))
            if data:
                self.header['svap_raw_hex'] = data.hex()
                if len(data) >= 2:
                    major = struct.unpack('>H', data[:2])[0]
                    self.header['svap_version_major'] = major
            return

        # matchName 块（mn / mn  ）
        if chunk_type in MATCH_NAME_TYPES or type_str.strip().startswith('mn'):
            data = self._read_limited(f, data_start, min(length, 512))
            if data:
                name = self._decode_string(data)
                if name:
                    self._add_match_name(name, context, pos, type_str)
            return

        # 字符串块（可能含素材路径 / 名称）
        if chunk_type in STRING_TYPES:
            data = self._read_limited(f, data_start, min(length, 4096))
            if data:
                s = self._decode_string(data)
                if s:
                    self._add_string(s, context, pos, type_str)
            return

        # idta 块（合成/素材数据）
        if type_str == 'idta':
            self._process_idta(f, data_start, length, context)
            return

        # ldta 块（图层数据）
        if type_str == 'ldta':
            self._process_ldta(f, data_start, length, context)
            return

        # CPTm 块（合成时间）
        if type_str == 'CPTm':
            data = self._read_limited(f, data_start, min(length, 16))
            if data and len(data) >= 8:
                self.header.setdefault('CPTm_samples', []).append({
                    'offset': pos, 'hex': data.hex(),
                    'u32_hi': struct.unpack('>I', data[:4])[0],
                    'u32_lo': struct.unpack('>I', data[4:8])[0],
                })
            return

        # CROI 块（合成 ROI）
        if type_str == 'CROI':
            data = self._read_limited(f, data_start, min(length, 16))
            if data and len(data) >= 8:
                self.header.setdefault('CROI_samples', []).append({
                    'offset': pos, 'hex': data.hex(),
                })
            return

        # 素材 ID 块
        if chunk_type in SOURCE_ID_TYPES:
            return

        # 大叶块流式扫描
        if length > STREAM_SCAN_THRESHOLD:
            self._stream_scan_chunk(f, data_start, length, context)
        else:
            data = self._read_limited(f, data_start, min(length, MAX_LEAF_READ))
            if data:
                self._scan_data_for_paths(data, context, pos)
                if 'name' in type_str.lower() or type_str in ('nmpt',):
                    s = self._decode_string(data)
                    if s:
                        self._apply_name(s)

    def _process_idta(
        self, f: BinaryIO, data_start: int, length: int, context: str,
    ) -> None:
        """处理 idta 块（合成/素材数据）。

        根据 AEP 格式观察：
        - @0x00 u16: item type（4 = comp）
        - @0x10 u32: 候选 ID（非分辨率）
        - @0x14 u32: 常见值 32（可能是 flag）
        - @0x38 u32: 常见值 3840（可能是时长帧数候选）
        - @0x50 u32: 时间戳
        """
        data = self._read_limited(f, data_start, min(length, 128))
        if not data or len(data) < 4:
            return

        fields: dict[str, Any] = {'offset': data_start, 'length': length}
        if len(data) >= 2:
            fields['item_type_u16'] = struct.unpack('>H', data[:2])[0]
        # 提取所有 4 字节对齐的 u32 字段
        for off in range(0, min(len(data) - 3, 84), 4):
            val = struct.unpack('>I', data[off:off + 4])[0]
            if val != 0:
                fields[f'u32@0x{off:02x}'] = val

        # 应用到当前合成
        if self._comp_index >= 0 and self._comp_index < len(self.compositions):
            comp = self.compositions[self._comp_index]
            comp['idta_fields'] = fields
            # @0x38 u32=3840 可能是时长帧数
            val38 = fields.get('u32@0x38')
            if val38 is not None and comp['duration_frames'] is None:
                if 1 <= val38 <= 10_000_000:
                    comp['duration_frames'] = val38

    def _process_ldta(
        self, f: BinaryIO, data_start: int, length: int, context: str,
    ) -> None:
        """处理 ldta 块（图层数据）。

        根据 AEP 格式观察：
        - @0x00 u32: layer ID
        - @0x10 u32: 常见值 600（可能是图层时长帧数）
        - @0x18 u32: 时间码候选
        - @0x40+: GBK 编码的图层名（备选，优先用 Utf8 块）
        """
        data = self._read_limited(f, data_start, min(length, 256))
        if not data or len(data) < 4:
            return

        fields: dict[str, Any] = {'offset': data_start, 'length': length}
        for off in range(0, min(len(data) - 3, 84), 4):
            val = struct.unpack('>I', data[off:off + 4])[0]
            if val != 0:
                fields[f'u32@0x{off:02x}'] = val

        # 尝试从 @0x40 提取 GBK 名称（备选）
        if len(data) >= 0x50:
            try:
                gbk_name = data[0x40:0x40 + 32].split(b'\x00')[0].decode('gbk', errors='ignore').strip()
                if gbk_name and self._is_mostly_printable(gbk_name):
                    fields['gbk_name_candidate'] = gbk_name
            except Exception:
                pass

        # 应用到当前图层
        if self._layer_index >= 0 and self._layer_index < len(self.layers):
            layer = self.layers[self._layer_index]
            layer['ldta_fields'] = fields
            # @0x10 u32=600 可能是时长帧数
            val10 = fields.get('u32@0x10')
            if val10 is not None and layer['duration_frames'] is None:
                if 1 <= val10 <= 10_000_000:
                    layer['duration_frames'] = val10
            # 应用 GBK 名称（仅在 Utf8 名称未设置时）
            gbk_name = fields.get('gbk_name_candidate')
            if gbk_name and layer['name'] is None:
                layer['name'] = gbk_name

    # ------------------------------------------------------------------
    # 数据读取与解码
    # ------------------------------------------------------------------

    def _read_limited(self, f: BinaryIO, start: int, size: int) -> bytes:
        f.seek(start)
        return f.read(size)

    def _decode_string(self, data: bytes) -> str:
        """从字节数据解码字符串，依次尝试 UTF-16-BE/LE、UTF-8、ASCII。"""
        if not data:
            return ''
        candidates: list[bytes] = [data]
        if len(data) >= 2:
            candidates.append(data[2:])
        if len(data) >= 4:
            candidates.append(data[4:])

        best = ''
        for cand in candidates:
            if len(cand) >= 2 and cand[1] == 0:
                try:
                    s = cand.decode('utf-16-be', errors='ignore').rstrip('\x00')
                    s = s.strip('\ufffd')
                    if s and self._is_mostly_printable(s):
                        return s
                except UnicodeDecodeError:
                    pass
            if len(cand) >= 2 and cand[0] == 0:
                try:
                    s = cand.decode('utf-16-le', errors='ignore').rstrip('\x00')
                    s = s.strip('\ufffd')
                    if s and self._is_mostly_printable(s):
                        return s
                except UnicodeDecodeError:
                    pass
            try:
                s = cand.decode('utf-8', errors='ignore').rstrip('\x00')
                if s and self._is_mostly_printable(s):
                    if not best or len(s) > len(best):
                        best = s
            except UnicodeDecodeError:
                pass

        if not best:
            s = data.decode('ascii', errors='ignore').rstrip('\x00')
            s = ''.join(c if 32 <= ord(c) < 127 else ' ' for c in s).strip()
            if self._is_mostly_printable(s):
                best = s
        return best

    @staticmethod
    def _is_mostly_printable(s: str) -> bool:
        if not s:
            return False
        printable = sum(1 for c in s if c.isprintable() or c in '\t')
        return printable / len(s) >= 0.6

    # ------------------------------------------------------------------
    # 结果收集
    # ------------------------------------------------------------------

    def _add_match_name(self, name: str, context: str, pos: int, type_str: str) -> None:
        name = name.strip()
        if not name or len(name) < 2:
            return
        key = (name, context)
        if key in self._seen_match:
            return
        self._seen_match.add(key)
        entry = {
            'matchName': name,
            'context': context,
            'offset': pos,
            'chunk_type': type_str,
            'composition_index': self._comp_index if self._comp_index >= 0 else None,
            'layer_index': self._layer_index if self._layer_index >= 0 else None,
        }
        self.match_names.append(entry)
        if self._comp_index >= 0 and self._comp_index < len(self.compositions):
            self.compositions[self._comp_index]['effects'].append(name)
        if self._layer_index >= 0 and self._layer_index < len(self.layers):
            self.layers[self._layer_index]['effects'].append(name)

    def _add_string(self, s: str, context: str, pos: int, type_str: str) -> None:
        s = s.strip()
        if not s or len(s) < 2:
            return
        if self._extract_paths_from_text(s, context, pos):
            pass
        if s not in self._seen_strings:
            self._seen_strings.add(s)
            self.raw_strings.append({
                'value': s,
                'context': context,
                'offset': pos,
                'chunk_type': type_str,
            })
        self._apply_name(s)

    def _apply_name(self, s: str) -> None:
        s = s.strip()
        if not s or len(s) > 256:
            return
        if PATH_RE.search(s):
            return
        if self._comp_index >= 0 and self._comp_index < len(self.compositions):
            comp = self.compositions[self._comp_index]
            if comp['name'] is None and self._looks_like_name(s):
                comp['name'] = s
        if self._layer_index >= 0 and self._layer_index < len(self.layers):
            layer = self.layers[self._layer_index]
            if layer['name'] is None and self._looks_like_name(s):
                layer['name'] = s

    @staticmethod
    def _looks_like_name(s: str) -> bool:
        if not s or len(s) > 128:
            return False
        if any(c in s for c in ('\\', '/', ':')) and len(s) > 4:
            if re.match(r'^[A-Za-z]:', s):
                return False
        printable = sum(1 for c in s if c.isprintable())
        return printable / max(len(s), 1) >= 0.8

    def _extract_paths_from_text(self, text: str, context: str, pos: int) -> bool:
        found = False
        for m in PATH_RE.finditer(text):
            path = m.group(0).strip().strip('"').strip("'")
            if self._is_valid_path(path):
                self._add_file_path(path, context, pos)
                found = True
        return found

    def _is_valid_path(self, path: str) -> bool:
        if not path or len(path) < 3:
            return False
        lower = path.lower()
        has_ext = any(lower.endswith('.' + ext) for ext in FILE_EXTS)
        is_abs = bool(re.match(r'^[A-Za-z]:[\\/]', path) or path.startswith('\\\\') or path.startswith('/'))
        return has_ext or is_abs

    def _add_file_path(self, path: str, context: str, pos: int) -> None:
        path = path.strip()
        if not path:
            return
        key = path.lower()
        if key in self._seen_paths:
            return
        self._seen_paths.add(key)
        self.file_paths.append({
            'path': path,
            'context': context,
            'offset': pos,
            'extension': Path(path).suffix.lstrip('.').lower() if '.' in path else '',
        })

    def _scan_data_for_paths(self, data: bytes, context: str, pos: int) -> None:
        """扫描字节数据中的路径字符串（ASCII 与 UTF-16）。"""
        try:
            text = data.decode('utf-8', errors='ignore')
            self._extract_paths_from_text(text, context, pos)
            for m in MATCH_NAME_PREFIX_RE.finditer(data):
                name = m.group(0).decode('ascii', errors='ignore').strip()
                if name and (name, context) not in self._seen_match:
                    self._add_match_name(name, context, pos, 'scan')
        except Exception:
            pass
        try:
            text16 = data.decode('utf-16-be', errors='ignore')
            if self._is_mostly_printable(text16):
                self._extract_paths_from_text(text16, context, pos)
        except Exception:
            pass

    def _stream_scan_chunk(
        self, f: BinaryIO, start: int, length: int, context: str,
    ) -> None:
        """流式扫描大块，分块读取以提取路径与 matchName。"""
        f.seek(start)
        remaining = length
        prev_tail = b''
        offset = start
        while remaining > 0:
            block = f.read(min(SCAN_BLOCK, remaining))
            if not block:
                break
            remaining -= len(block)
            buf = prev_tail + block
            self._scan_data_for_paths(buf, context, offset)
            prev_tail = buf[-512:] if len(buf) > 512 else b''
            offset += len(block)

    # ------------------------------------------------------------------
    # 全局补充扫描
    # ------------------------------------------------------------------

    def _global_supplement_scan(self) -> None:
        """对整个文件做一次流式扫描，补充块解析可能遗漏的路径与 matchName。"""
        try:
            with open(self.file_path, 'rb') as gf:
                prev_tail = b''
                while True:
                    block = gf.read(SCAN_BLOCK)
                    if not block:
                        break
                    buf = prev_tail + block
                    self._scan_data_for_paths(buf, 'global', 0)
                    prev_tail = buf[-1024:] if len(buf) > 1024 else b''
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 收尾
    # ------------------------------------------------------------------

    def _finalize(self) -> None:
        for comp in self.compositions:
            frames = comp.get('duration_frames')
            rate = comp.get('frame_rate')
            if frames is not None and rate and rate > 0:
                comp['duration_seconds'] = round(frames / rate, 3)
        self.header['chunk_count'] = self._chunk_count
        self.header['max_depth'] = self._max_depth
        self.header['chunk_type_counts'] = dict(
            sorted(self.chunk_stats.items(), key=lambda x: -x[1])
        )
        self.file_info['match_name_count'] = len(self.match_names)
        self.file_info['file_path_count'] = len(self.file_paths)
        self.file_info['composition_count'] = len(self.compositions)
        self.file_info['layer_count'] = len(self.layers)
        self.file_info['footage_count'] = len(self.footage_items)
        self.file_info['folder_count'] = len(self.folders)

    def _build_result(self) -> dict[str, Any]:
        return {
            'file_info': self.file_info,
            'header': self.header,
            'compositions': self.compositions,
            'layers': self.layers,
            'footage_items': self.footage_items[:500],
            'folders': self.folders,
            'match_names': self.match_names,
            'file_paths': self.file_paths,
            'raw_strings': self.raw_strings[:200],
            'summary': {
                'compositions': len(self.compositions),
                'layers': len(self.layers),
                'footage_items': len(self.footage_items),
                'folders': len(self.folders),
                'match_names': len(self.match_names),
                'file_paths': len(self.file_paths),
                'unique_match_names': len({m['matchName'] for m in self.match_names}),
                'unique_file_paths': len({p['path'] for p in self.file_paths}),
            },
        }


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = Path(
    r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_director'
    r'\ae_project_analysis\binary_parse_results'
)

DEFAULT_TEST_FILES = [
    r'D:\BaiduNetdiskDownload\AE新手10套\do you mean（简单）\9.23.aep',
    r'D:\BaiduNetdiskDownload\53动漫\25版打开.aep',
]


def parse_one(aep_path: str | Path, output_dir: Path) -> dict[str, Any]:
    """解析单个 AEP 文件并写出 JSON 结果。"""
    aep_path = Path(aep_path)
    if not aep_path.exists():
        print(f"  [跳过] 文件不存在: {aep_path}")
        return {'error': 'file not found', 'path': str(aep_path)}

    output_dir.mkdir(parents=True, exist_ok=True)
    out_name = aep_path.stem + '_binary_parse.json'
    out_path = output_dir / out_name

    print(f"  解析中: {aep_path.name} ({aep_path.stat().st_size / 1024 / 1024:.2f} MB)")
    parser = AEPParser(aep_path)
    result = parser.parse()

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    s = result['summary']
    print(
        f"  -> {out_path.name} | "
        f"合成={s['compositions']} 图层={s['layers']} "
        f"素材={s['footage_items']} 文件夹={s['folders']} "
        f"matchName={s['match_names']}(去重{s['unique_match_names']}) "
        f"素材路径={s['file_paths']}(去重{s['unique_file_paths']})"
    )
    return result


def main(argv: list[str]) -> int:
    print("=" * 72)
    print("AEP 二进制结构解析器")
    print("=" * 72)

    files: list[str] = []
    output_dir = DEFAULT_OUTPUT_DIR
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg in ('-o', '--output'):
            output_dir = Path(argv[i + 1])
            i += 2
        elif arg in ('-h', '--help'):
            print("用法: python aep_binary_parser.py [file1.aep file2.aep ...] [-o OUTPUT_DIR]")
            print("未提供文件时使用默认测试文件。")
            return 0
        else:
            files.append(arg)
            i += 1

    if not files:
        print("未指定输入文件，使用默认测试文件：")
        files = DEFAULT_TEST_FILES

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"输出目录: {output_dir}")
    print(f"待解析文件数: {len(files)}")
    print("-" * 72)

    all_results: list[dict[str, Any]] = []
    for fp in files:
        try:
            res = parse_one(fp, output_dir)
            all_results.append({'input': fp, 'result': res})
        except Exception as e:
            print(f"  [错误] 解析失败 {fp}: {e}")
            all_results.append({'input': fp, 'error': str(e)})

    print("-" * 72)
    print("解析完成。")

    summary_path = output_dir / '_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"汇总: {summary_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
