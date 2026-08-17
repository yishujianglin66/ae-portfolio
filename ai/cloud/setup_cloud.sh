#!/bin/bash
# AutoDL云GPU环境一键配置脚本
# 用法: 在AutoDL实例的terminal中运行 bash setup_cloud.sh

set -e
echo "=== T26d: AutoDL云GPU环境配置 ==="

# 1. 检查GPU
echo "[1/5] 检查GPU..."
nvidia-smi --query-gpu=name,memory.total --format=csv

# 2. 安装依赖
echo "[2/5] 安装Python依赖..."
pip install -q transformers>=4.45.0 accelerate pillow qwen-vl-utils modelscope

# 3. 下载模型（从ModelScope，国内快）
echo "[3/5] 下载Qwen3-VL-8B模型..."
MODEL_DIR="/root/models/Qwen3-VL-8B-Instruct"
if [ ! -d "$MODEL_DIR" ]; then
    python -c "
from modelscope import snapshot_download
snapshot_download('Qwen/Qwen3-VL-8B-Instruct', local_dir='$MODEL_DIR')
"
    echo "  模型下载完成"
else
    echo "  模型已存在，跳过下载"
fi

# 4. 创建数据目录
echo "[4/5] 创建数据目录..."
mkdir -p /root/data/frames /root/data/vlm_full

# 5. 验证
echo "[5/5] 验证环境..."
python -c "
import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
print(f'PyTorch: {torch.__version__}')
print(f'CUDA: {torch.cuda.is_available()}')
print(f'GPU: {torch.cuda.get_device_name(0)}')
print(f'VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB')
print('环境验证通过!')
"

echo ""
echo "=== 环境配置完成 ==="
echo "下一步:"
echo "  1. 上传帧数据: scp -r D:\\aot_corpus\\frames root@connect.xxx.autodl.me:/root/data/"
echo "  2. 上传伪标签: scp D:\\aot_corpus\\pseudolabels.json root@connect.xxx.autodl.me:/root/data/"
echo "  3. 复制脚本:   scp t26d_cloud_gpu_annotate.py root@connect.xxx.autodl.me:/root/"
echo "  4. 启动标注:   在AutoDL terminal中运行 bash run_cloud.sh"
