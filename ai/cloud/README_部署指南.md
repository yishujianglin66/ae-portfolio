# AutoDL云GPU部署指南 — VLM全量标注加速

## 概述
将VLM标注任务从本地串行API调用迁移到云GPU本地推理，速度提升5-10倍。

## 方案对比

| 方案 | 速度 | 成本 | 复杂度 |
|---|---|---|---|
| 本地串行(T26b) | ~0.01帧/s → 100h | API费~$10 | 零 |
| 本地并发16线程(T26c) | ~0.3帧/s → 60h | API费~$10 | 低 |
| **云GPU RTX 4090(T26d)** | **~2帧/s → 9h** | **¥15-20** | **中** |
| **云GPU A100(T26d)** | **~4帧/s → 4.5h** | **¥30-50** | **中** |

## 部署步骤

### Step 1: 注册AutoDL
1. 访问 https://www.autodl.com
2. 注册账号，充值 ¥50（足够本次任务）

### Step 2: 创建GPU实例
1. 进入"容器实例" → "创建实例"
2. 选择镜像: `PyTorch > 2.1.0 > 3.11(22.04) > 12.1`
3. 选择GPU: **A100 80GB**（推荐）或 **RTX 4090**
4. 数据盘: 50GB（存帧数据约10GB + 模型约16GB）
5. 创建并开机

### Step 3: 配置环境
在AutoDL的JupyterLab终端中运行:
```bash
# 复制setup脚本到实例（从本地）
scp c:\Users\Administrator\Desktop\AE-Knowledge-Vault\ai\cloud\setup_cloud.sh root@CONNECT_HOST:-p CONNECT_PORT:/root/

# SSH到实例后运行
bash /root/setup_cloud.sh
```

### Step 4: 上传数据
```powershell
# 在本地PowerShell运行（替换CONNECT_HOST和CONNECT_PORT）
# 上传帧数据（约10GB，需要10-30分钟）
scp -r -P CONNECT_PORT D:\aot_corpus\frames root@CONNECT_HOST:/root/data/

# 上传伪标签
scp -P CONNECT_PORT D:\aot_corpus\pseudolabels.json root@CONNECT_HOST:/root/data/

# 上传标注脚本
scp -P CONNECT_PORT c:\Users\Administrator\Desktop\AE-Knowledge-Vault\ai\t26d_cloud_gpu_annotate.py root@CONNECT_HOST:/root/
```

### Step 5: 启动标注
```bash
# SSH到实例后
bash /root/run_cloud.sh

# 查看进度
watch -n 30 'wc -l /root/data/vlm_full/results.jsonl; tail -1 /root/data/vlm_full/train.log'
```

### Step 6: 下载结果
标注完成后，下载结果到本地:
```powershell
scp -P CONNECT_PORT root@CONNECT_HOST:/root/data/vlm_full/results.jsonl D:\aot_corpus\vlm_full\
scp -P CONNECT_PORT root@CONNECT_HOST:/root/data/vlm_full/report.json D:\aot_corpus\vlm_full\
```

### Step 7: 释放实例
结果下载完成后，在AutoDL控制台关机/释放实例，停止计费。

## 费用估算

| GPU | 单价 | 预计时间 | 总费用 |
|---|---|---|---|
| RTX 4090 | ¥1.8/h | ~9h | ¥16 |
| A100 80GB | ¥3.5/h | ~4.5h | ¥16 |
| A100 * 2 (并行) | ¥7/h | ~2.5h | ¥18 |

## 注意事项
- AutoDL使用ModelScope下载模型，国内速度快（~5分钟）
- 帧数据约10GB，上传约10-30分钟
- 断点续传已支持，中断后可继续
- 结果文件约100MB，下载很快
- 用完及时释放实例，避免空跑计费
