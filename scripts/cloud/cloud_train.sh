# BiRefNet 动漫微调 — 云端训练一键部署（AutoDL/矩池云等，PyTorch 2.x + CUDA 镜像）
# 用法（在云实例上）:
#   bash cloud_train.sh
set -e
echo "=== 1. 环境 ==="
pip install -q torch torchvision transformers safetensors opencv-python-headless numpy 2>/dev/null || true

echo "=== 2. 下载数据与权重（需网络）==="
mkdir -p data weights
# 数据集 imgs-masks.zip（173MB）
curl -L -o data/imgs-masks.zip "https://hf-mirror.com/datasets/skytnt/anime-segmentation/resolve/main/data/imgs-masks.zip"
# BiRefNet 权重 + 代码（本地打包上传更稳，见 README）
# curl -L -o weights/model.safetensors "https://hf-mirror.com/ZhengPeng7/BiRefNet/resolve/main/model.safetensors"

echo "=== 3. 解压数据 ==="
python - <<'EOF'
import zipfile
with zipfile.ZipFile('data/imgs-masks.zip') as z:
    z.extractall('data/dataset')
print('解压完成')
EOF

echo "=== 4. 训练（4090 24GB: batch 8）==="
python finetune_birefnet.py --epochs 8 --batch 8 --lr 1e-4

echo "=== 5. 完成，权重在 external/birefnet/finetuned_anime.pth ==="
ls -la external/birefnet/finetuned_anime*.pth 2>/dev/null || ls -la */finetuned_anime*.pth
