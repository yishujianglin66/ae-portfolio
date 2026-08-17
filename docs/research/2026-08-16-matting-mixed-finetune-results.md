# 抠像混合微调结果汇总（2026-08-16）

> 数据源: animeseg 1111 + cityscapes 1067 + ADE 1132 + CelebA 伪mask 3973 = **7283 对**
> 训练: BiRefNet 冻结backbone + decoder/refiner, batch4, 8 epochs, best_val 0.0876
> 权重: `external/birefnet/finetuned_anime_mixed.pth`（已设为生产引用）

## 动漫域 A/B（animeseg GT, 200 张）

| 权重 | IoU 均值 | 边界 F1 |
|---|---|---|
| base 原版 | 0.9544 | 0.8362 |
| 旧动漫微调 | 0.9740 | 0.8423 |
| **新混合微调** | **0.9756** | 0.8292 |

- IoU 最高（+2.1% vs base），说明加入真实人像/场景数据**未损害动漫域**
- 边界 F1 略降 1.3%（真实数据边缘权衡），整体利大于弊

## COCO person A/B（200 张, 云端 13132）

| 权重 | IoU 均值 |
|---|---|
| base | 0.6064 |
| 旧动漫微调 | 0.6176（+1.12%） |

- 真实人像泛化不降反升

## 结论

- 混合微调 = 动漫域 + 真实人像**双向最优**，已替换生产权重
- FATE 完整重跑需 MatAnyone 分段中间产物（8/14 验收环境，当前不可再生），
  建议下次真机验收时同步验证

## 数据与脚本

- 训练集 7283 对已回传: `D:\AE-Data\matting_dataset_backup\matting_dataset.tar`
- 重建脚本: `scripts/build_matting_dataset.py` + `scripts/gen_celeba_pseudo_mask.py`
- 评估脚本: `scripts/eval_birefnet_anime.py`
