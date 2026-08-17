# 动漫 AMV 精确人物抠像专项调研（2026-08-14）

> 触发：FATE 端到端验收用户反馈"大多数时间段抠像粗糙，未跟准人物，精度<70%"。
> 诊断确认：SAM2 链路 mask 面积中位数 57.1%（56% 帧 >50% 画面 = 糊块），根因是 video 传播伪影 + YOLO conf=0.05 兜底假阳性；RVM 面积 11.9% 精确但 33% 盲区。

## 一、候选工具

### P0: MatAnyone（CVPR 2025）⭐
- **性质**：Stable Video Matting with Consistent Memory Propagation——**指定目标的视频抠像**（框选/点选目标 → 记忆传播 → 软 alpha 输出）
- **对症**：SAM2 video 传播会漂移成糊块；MatAnyone 的记忆传播对指定目标保持锚定，且输出软 alpha（边缘质量优于二值 mask）
- **社区标准组合**：SAM2（框选目标）+ MatAnyone（抠像）——[CSDN 部署实操](https://blog.csdn.net/wyj985860/article/details/162814053)
- **仓库**：[pq-yang/MatAnyone](https://github.com/pq-yang/MatAnyone)（[DeepWiki 安装说明](https://deepwiki.com/pq-yang/MatAnyone/2-installation-and-setup)）
- **权重**：[not-lain/matanyone HF 镜像](https://huggingface.co/not-lain/matanyone)（matanyone_hq_sd.pt）
- 待验证：4060 8GB 显存可行性、动漫域精度

### P1: BiRefNet / RMBG-2.5（图像级高精度抠图）
- 逐帧抠图精度高（[BiRefNet Lite Matting](https://model.aibase.com/models/details/1915774916072464386)），但时域一致性需配合本链路已有 warp+MED 资产
- 定位：单帧精修/边缘精修补丁，或 MatAnyone 的盲区帧兜底

### P2: 现有资产调参（零下载，先验证）
- SAM2 **image predictor 逐帧模式**（不用 video 传播——糊块根源）+ YOLO conf 0.05→0.3 + top-1 框 + 面积上限约束
- 链路里 auto_frame 就是这个模式，当前参数太松（conf 0.05 → 假阳性大框）

## 二、推荐路径

1. **先零成本试 P2**：改 conf/top-1/面积约束，50 帧 A/B 验证——若逐帧框选精度达标（mask 面积中位 <25%、无 >50% 糊块），立即可用
2. **P2 不够再上 MatAnyone**：下载权重（~4GB）→ vendoring → 框选目标（YOLO/SAM2 框）→ 记忆传播抠像 → 接现有 MED13 + MOV + AE 链路
3. BiRefNet 作边缘精修补丁（可选）

## 三、验收指标修正（本次教训）

在 J500/非空率/IoU 之外**必须增加精度指标**：
- **糊块率**：mask 面积 >50% 的帧占比（目标 0%；本次 SAM2 链路 56%）
- **面积合理性**：面积中位数区间（动漫人物 720p 参考 10-30%；>40% 即伪影嫌疑）
- **边缘贴合**：EDGE_IoU（需人工 GT，短期用 RVM/SAM2 交叉一致性代理）
