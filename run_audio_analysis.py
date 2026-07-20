import sys
sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

# 导入模块（文件名带连字符）
import importlib.util
spec = importlib.util.spec_from_file_location("audio_analyzer", "audio-analyzer.py")
audio_analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio_analyzer)

# 分析BGM
analyzer = audio_analyzer.AudioAnalyzer()
result = analyzer.analyze_audio(r"D:\AE-Work\音频素材库\BGM\抖音_BGM_世上无难事.mp3")

import json
print(json.dumps(result, indent=2, ensure_ascii=False))