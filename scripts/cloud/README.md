# 云端 BiRefNet 动漫微调 — 部署说明

> 目标：把本地共享 GPU 拖慢到 18 小时的训练，搬到云 GPU（4090 24GB）30 分钟完成。

## 需要上传的文件（打包后 ~600MB）

| 文件 | 大小 | 说明 |
|---|---|---|
| `scripts/finetune_birefnet.py` | 12KB | 训练脚本（已适配云端路径：--data 参数可改） |
| `scripts/cloud/cloud_train.sh` | 1KB | 一键训练 |
| `external/animeseg/dataset/`（imgs+masks 1111对） | 173MB | 训练数据 |
| `external/birefnet/`（config.json + BiRefNet_config.py + birefnet.py + model.safetensors） | 424MB | 模型 |

## 操作步骤（AutoDL 示例）

1. **开实例**：AutoDL/矩池云 → RTX 4090（24GB）→ 镜像选 `PyTorch 2.1+`（含 CUDA 12）→ 按量计费约 2 元/小时
2. **上传**（本地 PowerShell，替换成你的实例 SSH 信息）：
   ```powershell
   # 打包
   tar -cf cloud_birefnet.tar scripts/finetune_birefnet.py scripts/cloud/cloud_train.sh external/animeseg/dataset external/birefnet
   # 上传（AutoDL 控制台有"上传文件"或 scp）
   scp -P <端口> cloud_birefnet.tar root@<实例IP>:/root/autodl-tmp/
   ```
3. **云端执行**：
   ```bash
   cd /root/autodl-tmp && tar -xf cloud_birefnet.tar
   # 训练脚本的数据/模型路径常量需按云端目录调整（或直接用 cloud_train.sh 内的下载方式）
   bash scripts/cloud/cloud_train.sh
   ```
4. **回传权重**：
   ```powershell
   scp -P <端口> root@<实例IP>:/root/autodl-tmp/external/birefnet/finetuned_anime.pth external/birefnet/
   ```
5. **释放实例**（重要，按量计费）

## 或者：你开好实例把 SSH 命令发我，我全程远程操作

如果你愿意提供实例的 SSH 登录信息（AutoDL 控制台的"SSH 登录指令"），我可以：
- 远程上传 → 训练 → 监控 → 回传权重 → 本地验证 v15，全程自动化。

> 安全提示：SSH 凭据只在你的实例有效且用完即销毁；如不便提供，按上面步骤自己操作也可。
