#!/bin/bash
# cloud_wa2_matrix.sh — 云端 4090 24G 补全 WA2 边界测试矩阵（81f / 720p）
# 前置：AutoDL 4090 24G 容器（或任意 24G+ CUDA 12.x Linux 机）
# 用法：
#   1. 选镜像：PyTorch 2.8.0 / Python 3.12 / CUDA 12.8（AutoDL 当前可选；2.6/2.8 均兼容，
#      脚本自动检测镜像自带 CUDA torch 并跳过安装）
#   2. 上传本机三个工作流 JSON 与素材到容器 /root/autodl-tmp/wa2/（见 UPLOAD 说明）
#   3. bash cloud_wa2_matrix.sh 2>&1 | tee /root/autodl-tmp/wa2/matrix_run.log
# UPLOAD（本机执行，scp/autodl 面板均可）：
#   D:\ComfyUI\workflows\wa2_api_smoke.json    -> /root/autodl-tmp/wa2/wa2_api_smoke.json
#   D:\ComfyUI\workflows\wa2_anim_int8_81f.json -> /root/autodl-tmp/wa2/wa2_anim_int8_81f.json
#   D:\ComfyUI\workflows\wa2_anim_int8_720p.json -> /root/autodl-tmp/wa2/wa2_anim_int8_720p.json
#   D:\ComfyUI\input\wa2_ref.png               -> /root/autodl-tmp/wa2/wa2_ref.png
#   D:\ComfyUI\input\wa2_drive.mp4              -> /root/autodl-tmp/wa2/wa2_drive.mp4
set -euo pipefail
# AutoDL 学术加速（GitHub/HF 直连慢时取消注释）
# source /etc/network_turbo
ROOT=/root/autodl-tmp/ComfyUI   # 数据盘 50G，系统盘 30G 装不下 24G 权重
WA2=/root/autodl-tmp/wa2

echo "=== [0/5] 磁盘确认"
df -h /root/autodl-tmp | tail -1
# 把所有可能产生大缓存的位置统一指到数据盘（防 pip/HF/triton 默认写 ~/.cache 占 30G 系统盘）
export HF_HOME="$WA2/.cache/huggingface"
export TORCH_HOME="$WA2/.cache/torch"
export TRITON_CACHE_DIR="$WA2/.cache/triton"
export PIP_CACHE_DIR="$WA2/.cache/pip"
export XDG_CACHE_HOME="$WA2/.cache"
mkdir -p "$HF_HOME" "$TORCH_HOME" "$TRITON_CACHE_DIR" "$PIP_CACHE_DIR"

echo "=== [1/5] 环境"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
if [ ! -d "$ROOT" ]; then
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI "$ROOT"
fi
cd "$ROOT"
# 镜像自带 CUDA 版 torch（如 PyTorch 2.8.0/cu128）则直接用，避免无谓降级下载
if python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
  echo "镜像自带 torch $(python -c 'import torch;print(torch.__version__)')，跳过安装"
else
  python -m pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
fi
python -m pip install -q -r requirements.txt || { \
  sed -i 's/comfyui-workflow-templates==[0-9.]*/comfyui-workflow-templates>=0.11.55/' requirements.txt; \
  python -m pip install -q -r requirements.txt; }

echo "=== [2/5] 权重下载（hf-mirror，云带宽直下）"
BASE="https://hf-mirror.com/Comfy-Org/Wan-Animate-2/resolve/main"
mkdir -p models/{diffusion_models,loras,text_encoders,clip_vision,vae} "$WA2" input output
dl() { f="$1"; d="models/$2/$(basename "$f")"; [ -s "$d" ] && { echo "skip $f"; return 0; }
  curl -sS -L -C - --retry 5 -o "$d" "$BASE/$f" && echo "done $f $(stat -c%s "$d") bytes"; }
dl "diffusion_models/wan_animate_2_distill_int8_convrot.safetensors" diffusion_models
dl "loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors" loras
dl "text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" text_encoders
dl "clip_vision/clip_vision_h.safetensors" clip_vision
dl "vae/Wan2_1_VAE_bf16.safetensors" vae

echo "=== [3/5] 素材就位"
cp "$WA2"/wa2_ref.png "$WA2"/wa2_drive.mp4 input/

echo "=== [4/5] 启动服务器（24G 显存无需 --lowvram）"
PYTHONUNBUFFERED=1 python main.py --port 8188 --listen 127.0.0.1 > server.log 2>&1 &
SERVER_PID=$!
for i in $(seq 1 60); do curl -s -m 3 http://127.0.0.1:8188/system_stats >/dev/null 2>&1 && break; sleep 2; done
curl -s http://127.0.0.1:8188/system_stats | head -c 200; echo
nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv,noheader -l 5 > "$WA2/vram_trace.log" 2>&1 &
TRACE_PID=$!

run_one() {  # run_one <名字> <工作流json>
  echo "--- 提交 $1 ($2)"
  local t0=$(date +%s)
  local pid=$(curl -s -X POST -H 'Content-Type: application/json' \
    -d "{\"prompt\": $(cat "$WA2/$2")}" http://127.0.0.1:8188/prompt | python3 -c 'import json,sys;print(json.load(sys.stdin)["prompt_id"])')
  while :; do
    sleep 10
    local st=$(curl -s http://127.0.0.1:8188/history/$pid)
    echo "$st" | python3 -c "import json,sys
h=json.load(sys.stdin); p='$pid'
sys.exit(0 if p in h and h[p]['status'].get('completed') else 1)" && break
    echo "$st" | grep -q '"status_str": *"error"' && { echo "$st" | head -c 800; return 1; }
  done
  echo "$1 耗时 $(( $(date +%s) - t0 ))s"
  curl -s http://127.0.0.1:8188/history/$pid > "$WA2/history_$1.json"
}

echo "=== [5/5] 跑矩阵"
run_one smoke_48f   wa2_api_smoke.json      # 环境验证（应远快于本机 1221s）
run_one boundary_81f wa2_anim_int8_81f.json
run_one boundary_720p wa2_anim_int8_720p.json

kill $TRACE_PID $SERVER_PID 2>/dev/null || true
echo "=== 收尾：取回以下文件回本机归档"
echo "  $WA2/vram_trace.log  $WA2/history_*.json  $ROOT/output/wa2_smoke/*.mp4  matrix_run.log"
echo "=== 显存峰值："
awk -F', ' '{gsub(/ MiB/,"",$2); if($2+0>m) m=$2+0} END{print m" MiB"}' "$WA2/vram_trace.log"
