#!/bin/bash
# AutoDL云GPU标注启动脚本
# 在AutoDL实例的terminal中运行

set -e

echo "=== T26d: 云GPU VLM标注启动 ==="
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader)"
echo "VRAM: $(nvidia-smi --query-gpu=memory.total --format=csv,noheader)"

# 环境变量
export VLM_MODEL="Qwen/Qwen3-VL-8B-Instruct"
export FRAMES_DIR="/root/data/frames"
export PSEUDO_LABELS="/root/data/pseudolabels.json"
export OUTPUT_DIR="/root/data/vlm_full"

# 根据GPU选择batch_size
GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | tr -d ' ')
if [ "$GPU_MEM" -gt 40000 ]; then
    export BATCH_SIZE=8  # A100 80GB
    echo "A100检测, BATCH_SIZE=8"
elif [ "$GPU_MEM" -gt 20000 ]; then
    export BATCH_SIZE=4  # RTX 4090
    echo "4090检测, BATCH_SIZE=4"
else
    export BATCH_SIZE=2
    echo "小显存GPU, BATCH_SIZE=2"
fi

# 检查数据
if [ ! -d "$FRAMES_DIR" ] || [ -z "$(ls -A $FRAMES_DIR 2>/dev/null)" ]; then
    echo "ERROR: 帧数据目录为空或不存在: $FRAMES_DIR"
    echo "请先上传帧数据到 $FRAMES_DIR"
    exit 1
fi

FRAME_COUNT=$(find $FRAMES_DIR -name "*.jpg" | wc -l)
echo "帧数据: $FRAME_COUNT 张"

if [ ! -f "$PSEUDO_LABELS" ]; then
    echo "WARNING: 伪标签文件不存在: $PSEUDO_LABELS"
fi

# 启动标注
echo "开始标注..."
nohup python /root/t26d_cloud_gpu_annotate.py > /root/data/vlm_full/train.log 2>&1 &
PID=$!
echo "标注进程PID: $PID"
echo "查看日志: tail -f /root/data/vlm_full/train.log"
echo ""
echo "监控命令: watch -n 30 'wc -l /root/data/vlm_full/results.jsonl; tail -1 /root/data/vlm_full/train.log'"
