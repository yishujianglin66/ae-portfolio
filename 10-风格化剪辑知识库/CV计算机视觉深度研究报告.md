---
title: CV计算机视觉深度研究报告
date: 2026-07-05
tags:
  - 计算机视觉
  - CV技术栈
  - 运动估计
  - 色彩分析
  - 构图分析
  - 场景识别
  - 视频处理
  - AE自动化引擎
  - P2片段分析
  - 技术选型
  - 学习路径
---

# CV计算机视觉深度研究报告

> [!abstract] 文档摘要
> 本报告为 AE 自动化引擎的 P2 片段原子分析层提供完整 CV 技术栈选型与学习路径。覆盖运动估计（光流/相机运动/方向统计）、色彩分析（颜色空间/主色板/特征/心理学）、构图分析（三分法/对称/景深/构图法则）、场景识别（传统/深度学习/目标检测/分类体系）、视频处理（场景分割/关键帧/质量评估）全链路，并配套工具库对比、数据集基准、硬件需求、AE 引擎集成方案、12 周学习路径与隐藏缺口识别。所有算法均给出数学公式与 Python 代码示例，可直接落地实现。

> [!tip] 使用指南
> - **架构选型者**：第六、八、九章
> - **算法实现者**：第一至五章（含完整代码）
> - **学习者**：第十章 12 周路径
> - **质检负责人**：第七章数据集 + 第十一章隐藏缺口

---

## 第一章 运动估计深度剖析

### 1.1 光流算法

光流（Optical Flow）是描述相邻帧间像素运动的速度场 $\mathbf{v}(x,y) = (u(x,y), v(x,y))$，是 AE 引擎运动维度的基础信号。

#### 1.1.1 光流约束方程与 Aperture Problem

光流基本约束来自亮度恒定假设：

$$I(x, y, t) = I(x + dx, y + dy, t + dt)$$

Taylor 展开后得到**光流约束方程**：

$$I_x u + I_y v + I_t = 0$$

其中 $I_x, I_y, I_t$ 分别为图像在 $x, y, t$ 方向的偏导。

**Aperture Problem（孔径问题）**：单个像素只能求出沿梯度方向的运动分量，无法求出与梯度正交方向的运动。因此所有稠密光流算法都必须引入额外约束（如平滑性、局部一致性、多项式展开等）才能求解欠定方程。

#### 1.1.2 Horn-Schunck 算法（连续能量最小化）

- **原理**：全局能量最小化，假设光流场整体平滑
- **能量函数**：

$$E = \iint \left( (I_x u + I_y v + I_t)^2 + \alpha^2 (|\nabla u|^2 + |\nabla v|^2) \right) dx\,dy$$

其中 $\alpha$ 为平滑项权重（典型值 1.0~10）。
- **求解**：Euler-Lagrange 方程迭代求解
- **特点**：稠密光流，全局平滑，但边缘模糊，对剧烈运动敏感
- **文献**：Horn & Schunck, "Determining Optical Flow", AI 1981

```python
import cv2
import numpy as np

# Horn-Schunck (OpenCV 未直接实现，需手写或用 scipy)
def horn_schunck(I1, I2, alpha=1.0, num_iter=100):
    I1 = I1.astype(np.float32) / 255.0
    I2 = I2.astype(np.float32) / 255.0
    Ix = 0.25 * (np.roll(I1, -1, 1) - np.roll(I1, 1, 1) +
                 np.roll(I2, -1, 1) - np.roll(I2, 1, 1))
    Iy = 0.25 * (np.roll(I1, -1, 0) - np.roll(I1, 1, 0) +
                 np.roll(I2, -1, 0) - np.roll(I2, 1, 0))
    It = I2 - I1
    u = np.zeros_like(I1)
    v = np.zeros_like(I1)
    kernel = np.array([[1/12, 1/6, 1/12],
                       [1/6,  0,   1/6],
                       [1/12, 1/6, 1/12]], dtype=np.float32)
    for _ in range(num_iter):
        u_avg = cv2.filter2D(u, -1, kernel)
        v_avg = cv2.filter2D(v, -1, kernel)
        denom = alpha**2 + Ix**2 + Iy**2
        u = u_avg - Ix * (Ix*u_avg + Iy*v_avg + It) / denom
        v = v_avg - Iy * (Ix*u_avg + Iy*v_avg + It) / denom
    return u, v
```

#### 1.1.3 Lucas-Kanade 算法（局部窗口假设）

- **原理**：假设局部窗口内光流恒定，求解最小二乘
- **数学推导**：在 $W \times W$ 窗口内，约束方程组：

$$A \mathbf{v} = -b, \quad A = \begin{bmatrix} I_{x1} & I_{y1} \\ \vdots & \vdots \\ I_{xn} & I_{yn} \end{bmatrix}, \quad b = \begin{bmatrix} I_{t1} \\ \vdots \\ I_{tn} \end{bmatrix}$$

最小二乘解：

$$\mathbf{v} = (A^T A)^{-1} A^T (-b)$$

要求 $A^T A$ 可逆（窗口内梯度丰富）。
- **特点**：稀疏光流（特征点处），对大运动不敏感，需金字塔改进
- **应用**：特征点跟踪（KLT tracker）

```python
import cv2
import numpy as np

cap = cv2.VideoCapture("input.mp4")
ret, prev = cap.read()
prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
# Shi-Tomasi 角点
prev_pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=200, qualityLevel=0.01,
                                   minDistance=7, blockSize=7)
lk_params = dict(winSize=(15, 15), maxLevel=2,
                 criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.03))
while True:
    ret, frame = cap.read()
    if not ret: break
    next_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    next_pts, status, err = cv2.calcOpticalFlowPyrLK(prev_gray, next_gray, prev_pts, None, **lk_params)
    good_next = next_pts[status == 1]
    good_prev = prev_pts[status == 1]
    # 可视化
    for i, (p0, p1) in enumerate(zip(good_prev, good_next)):
        x0, y0 = p0.ravel(); x1, y1 = p1.ravel()
        cv2.line(frame, (int(x0), int(y0)), (int(x1), int(y1)), (0, 255, 0), 2)
    cv2.imshow("LK", frame); cv2.waitKey(1)
    prev_gray = next_gray.copy(); prev_pts = good_next.reshape(-1, 1, 2)
```

#### 1.1.4 Farneback 算法（多项式展开，AE 引擎推荐使用）

- **原理**：将每帧近似为二次多项式：

$$f(\mathbf{x}) = \mathbf{x}^T A \mathbf{x} + \mathbf{b}^T \mathbf{x} + c$$

通过对比两帧的多项式系数，求出位移场 $\mathbf{d}$，使新多项式与原多项式在位移后匹配
- **特点**：稠密光流，精度高，速度中等，对噪声鲁棒
- **AE 引擎推荐原因**：精度-速度均衡好，OpenCV 原生支持，输出稠密场可直接做运动统计
- **论文**：Farnebäck, "Two-Frame Motion Estimation Based on Polynomial Expansion", SCIA 2003

```python
import cv2
import numpy as np

def farneback_flow(prev_gray, next_gray):
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray, next_gray, None,
        pyr_scale=0.5, levels=5, winsize=15,
        iterations=3, poly_n=5, poly_sigma=1.2,
        flags=cv2.OPTFLOW_FARNEBACK_GAUSSIAN
    )
    # flow shape: (H, W, 2), 通道0=u(水平), 通道1=v(垂直)
    return flow

def flow_to_visualization(flow):
    h, w = flow.shape[:2]
    hsv = np.zeros((h, w, 3), dtype=np.uint8)
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    hsv[..., 0] = ang * 180 / np.pi / 2
    hsv[..., 1] = 255
    hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
```

#### 1.1.5 DeepFlow（深度学习）

- **原理**：将匹配代价卷积与变分优化结合，使用深度结构（cv::optflow::DenseOpticalFlow）
- **论文**：Weinzaepfel et al., "DeepFlow: Large displacement optical flow with deep matching", ICCV 2013, arXiv:1512.01255
- **特点**：对大位移运动表现好，但参数多

#### 1.1.6 RAFT（Recurrent All-Pairs Field Transforms，SOTA）

- **原理**：构建所有像素对的 4D cost volume，通过 GRU 循环更新光流
- **论文**：Teed & Deng, "RAFT: Recurrent All-Pairs Field Transforms for Optical Flow", ECCV 2020, arXiv:2003.12039
- **代码**：https://github.com/princeton-vl/RAFT
- **特点**：SOTA 精度（KITTI/Sintel 数据集），需要 GPU
- **AE 引擎应用建议**：用于离线高精度分析；实时分析用 Farneback

```python
# RAFT 推理（torchvision 实现）
import torch
import torchvision.transforms as T
from torchvision.models.optical_flow import raft_large, Raft_Large_Weights

device = "cuda" if torch.cuda.is_available() else "cpu"
model = raft_large(weights=Raft_Large_Weights.DEFAULT).to(device).eval()
transform = Raft_Large_Weights.DEFAULT.transforms()
img1 = T.ToTensor()(cv2.cvtColor(prev, cv2.COLOR_BGR2RGB)).to(device)
img2 = T.ToTensor()(cv2.cvtColor(next_, cv2.COLOR_BGR2RGB)).to(device)
img1_t, img2_t = transform(img1, img2)
with torch.no_grad():
    flow_list = model(img1_t.unsqueeze(0), img2_t.unsqueeze(0))
flow = flow_list[-1][0].cpu().numpy().transpose(1, 2, 0)  # (H, W, 2)
```

#### 1.1.7 算法对比表

| 算法 | 类型 | 精度 | 速度 | 内存 | GPU需求 | 推荐场景 |
|------|------|------|------|------|--------|---------|
| Horn-Schunck | 全局稠密 | 中 | 慢 | 中 | 否 | 教学演示 |
| Lucas-Kanade | 稀疏特征 | 中 | 快 | 低 | 否 | 特征点跟踪 |
| Farneback | 稠密多项式 | 中高 | 中 | 中 | 可选 | **AE 引擎首选** |
| DeepFlow | 深度+变分 | 高 | 慢 | 高 | 否 | 大位移场景 |
| RAFT | 深度学习 | 极高 | GPU快/CPU慢 | 高 | 强烈推荐 | 离线高精度 |
| FlowNet2 | 深度学习 | 高 | 中 | 高 | 推荐 | 备选 |
| PWC-Net | 深度学习 | 高 | 快 | 中 | 推荐 | 实时稠密 |

---

### 1.2 相机运动分类

#### 1.2.1 全局运动估计

通过 RANSAC 拟合两帧间的变换模型：

- **仿射变换（6 参数）**：适合远景平面运动
$$\begin{bmatrix} x' \\ y' \end{bmatrix} = \begin{bmatrix} a & b \\ c & d \end{bmatrix} \begin{bmatrix} x \\ y \end{bmatrix} + \begin{bmatrix} e \\ f \end{bmatrix}$$
- **透视变换（8 参数 homography）**：适合任意平面/相机旋转

```python
# 使用 ORB 特征 + RANSAC 估计全局仿射
orb = cv2.ORB_create(1000)
kp1, des1 = orb.detectAndCompute(prev_gray, None)
kp2, des2 = orb.detectAndCompute(next_gray, None)
bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
matches = bf.match(des1, des2)
src = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
dst = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
M, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3)
# M = [[cos θ * s, -sin θ * s, tx], [sin θ * s, cos θ * s, ty]]
```

#### 1.2.2 缩放/平移/旋转判别

对估计的 2×3 仿射矩阵 $M$ 分解：

```python
def classify_camera_motion(M):
    # M = [[a, b, tx], [c, d, ty]]
    a, b = M[0, 0], M[0, 1]
    c, d = M[1, 0], M[1, 1]
    tx, ty = M[0, 2], M[1, 2]
    scale = np.sqrt(a*a + c*c)
    theta = np.degrees(np.arctan2(c, a))  # 旋转角度
    return {
        "scale": float(scale),         # >1 推镜头, <1 拉镜头
        "translation": float(np.hypot(tx, ty)),  # 平移幅度
        "rotation": float(theta),      # 旋转角度
        "is_zoom": abs(scale - 1.0) > 0.02 and abs(theta) < 1.0,
        "is_pan":  abs(tx) > 5 and abs(scale - 1.0) < 0.02,
        "is_tilt": abs(ty) > 5 and abs(scale - 1.0) < 0.02,
        "is_rotate": abs(theta) > 2.0,
    }
```

#### 1.3.3 相机抖动检测

- 计算多帧间仿射参数序列 $\{tx_t, ty_t, \theta_t\}$
- 计算其一阶差分的高频能量（FFT 高频分量占比）
- 高频能量 > 阈值 → 抖动

#### 1.3.4 手持 vs 稳定器区分

- **手持**：抖动高频能量大，呈现 5~10Hz 周期性抖动
- **稳定器**：运动平滑，低频主导，无周期性
- 判别指标：高频能量比 $R = \frac{\sum_{f>5Hz} |F(\theta)|^2}{\sum |F(\theta)|^2}$，$R > 0.3$ 判为手持

---

### 1.3 运动方向统计

#### 1.3.1 8 方向直方图

将每个像素的 $(u, v)$ 向量按角度量化到 8 个方向（每 45° 一个 bin），统计加权幅值：

```python
def motion_direction_histogram(flow, bins=8):
    mag = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
    ang = np.arctan2(flow[..., 1], flow[..., 0])  # -π~π
    hist, _ = np.histogram(ang, bins=bins, range=(-np.pi, np.pi), weights=mag)
    hist = hist / (hist.sum() + 1e-8)
    return hist  # 长度8的概率分布
```

#### 1.3.2 主方向提取

- 取直方图最大 bin 对应方向作为主方向
- 主方向强度 = max_bin_ratio，> 0.4 视为强主方向，< 0.2 视为复杂运动

#### 1.3.3 复杂运动分解

- 若主方向不显著（max_bin_ratio < 0.2），采用 PCA 分解前 2 个主成分
- 输出 `motion_complexity` = 主成分方差贡献比

---

## 第二章 色彩分析深度剖析

### 2.1 颜色空间

#### 2.1.1 RGB（不推荐直接用）

- 设备相关，通道间强相关（亮度与色度耦合），不适合直接做色彩统计

#### 2.1.2 HSL/HSV（直觉但非感知均匀）

- **H（色相 0~360°）/ S（饱和度 0~1）/ L 或 V（亮度 0~1）**
- 转换公式（RGB→HSV）：

$$V = \max(R, G, B)$$
$$S = \begin{cases} \frac{V - \min(R,G,B)}{V} & V \neq 0 \\ 0 & V = 0 \end{cases}$$
$$H = \begin{cases} 60 \cdot \frac{G-B}{\Delta} & V=R \\ 120 + 60 \cdot \frac{B-R}{\Delta} & V=G \\ 240 + 60 \cdot \frac{R-G}{\Delta} & V=B \end{cases}$$

- **优点**：与人类直觉一致，适合按色相分桶
- **缺点**：感知不均匀（同样的 ΔH 在不同区域看起来差距不同）

#### 2.1.3 Lab（感知均匀，推荐）

- **L**（亮度 0~100）/ **a**（红绿轴 -128~128）/ **b**（黄蓝轴 -128~128）
- 转换：RGB → XYZ → Lab
- 色差 $\Delta E_{76}$：

$$\Delta E_{76} = \sqrt{(L_1-L_2)^2 + (a_1-a_2)^2 + (b_1-b_2)^2}$$

- **推荐原因**：感知均匀，色差与人类视觉一致，适合主色聚类与相似度判断

#### 2.1.4 YCbCr（视频编码标准）

- **Y（亮度）/ Cb（蓝色差）/ Cr（红色差）**
- 用于 H.264/H.265 等编码内部表示
- 转换（BT.601）：

$$Y = 0.299 R + 0.587 G + 0.114 B$$
$$Cb = 128 - 0.168736 R - 0.331264 G + 0.5 B$$
$$Cr = 128 + 0.5 R - 0.418688 G - 0.081312 B$$

#### 2.1.5 颜色空间转换代码

```python
import cv2
img_bgr = cv2.imread("frame.jpg")
img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
img_lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
img_ycbcr = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2YCrCb)
```

---

### 2.2 主色板提取

#### 2.2.1 K-Means 聚类（最常用）

- **K 选择方法**：
  - 肘部法则（Elbow）：绘制 inertia vs K 曲线，找拐点
  - 轮廓系数（Silhouette Score）
  - 经验值：电影帧建议 K=5~8

```python
import cv2
import numpy as np
from sklearn.cluster import KMeans

def extract_palette_kmeans(img_bgr, k=6):
    img_lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    pixels = img_lab.reshape(-1, 3).astype(np.float32)
    # 随机采样加速
    if len(pixels) > 10000:
        idx = np.random.choice(len(pixels), 10000, replace=False)
        pixels = pixels[idx]
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(pixels)
    centers = km.cluster_centers_
    labels = km.labels_
    counts = np.bincount(labels)
    ratios = counts / counts.sum()
    # 按比例降序
    order = np.argsort(-ratios)
    palette = [(centers[i].astype(int), float(ratios[i])) for i in order]
    return palette  # [(Lab色, 占比), ...]
```

#### 2.2.2 Mean Shift

- 优点：无需指定 K，自动发现模态
- 缺点：带宽选择困难，速度慢

```python
from sklearn.cluster import MeanShift, estimate_bandwidth
def extract_palette_meanshift(img_bgr):
    img_lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    bw = estimate_bandwidth(img_lab, quantile=0.2, n_samples=5000)
    ms = MeanShift(bandwidth=bw, bin_seeding=True).fit(img_lab)
    return ms.cluster_centers_.astype(int), len(ms.cluster_centers_)
```

#### 2.2.3 DBSCAN

- 优点：可发现噪声与任意形状簇
- 缺点：对密度不均的数据表现差

#### 2.2.4 Median Cut（经典量化）

- 经典图像量化算法，递归地将颜色空间按最长轴切分
- 速度快，但精度不如 K-Means

#### 2.2.5 颜色距离度量

- **Euclidean（Lab 空间）**：$\Delta E_{76}$，简单但有误差
- **CIEDE2000**：感知最准确，公式复杂，包含 $S_L, S_C, S_H$ 权重

$$\Delta E_{00} = \sqrt{\left(\frac{\Delta L'}{k_L S_L}\right)^2 + \left(\frac{\Delta C'}{k_C S_C}\right)^2 + \left(\frac{\Delta H'}{k_H S_H}\right)^2 + R_T \cdot \frac{\Delta C'}{k_C S_C} \cdot \frac{\Delta H'}{k_H S_H}}$$

```python
from colormath.color_objects import LabColor
from colormath.color_diff import delta_e_cie2000
def color_distance_ciede2000(lab1, lab2):
    c1 = LabColor(lab_l=lab1[0], lab_a=lab1[1], lab_b=lab1[2])
    c2 = LabColor(lab_l=lab2[0], lab_a=lab2[1], lab_b=lab2[2])
    return delta_e_cie2000(c1, c2)
```

---

### 2.3 色彩特征

#### 2.3.1 颜色直方图（HSL 3 通道）

```python
def hsl_histogram(img_bgr, bins=(12, 8, 8)):
    img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    hist = [cv2.calcHist([img_hsv], [i], None, [bins[i]], [0, 180 if i==0 else 256]).flatten()
            for i in range(3)]
    hist = [h / (h.sum() + 1e-8) for h in hist]
    return hist
```

#### 2.3.2 颜色矩（mean/std/skewness）

```python
def color_moments(img_bgr):
    img_lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    means = img_lab.mean(axis=(0,1))
    stds  = img_lab.std(axis=(0,1))
    skew  = ((img_lab - means) ** 3).mean(axis=(0,1)) ** (1/3)
    return np.concatenate([means, stds, skew])  # 9 维
```

#### 2.3.3 颜色一致性向量（CCV）

- 颜色直方图的改进：区分"大块同色区域"与"零散同色像素"
- 对每个颜色 bin 分：coherent（属于大连通域）+ incoherent（孤立点）

#### 2.3.4 主色 vs 主导色差异

- **主色（Dominant）**：聚类后占比最大的颜色（视觉上最突出）
- **平均色（Average）**：所有像素 Lab 均值（可能根本不出现）
- **AE 引擎建议同时输出两者**：dominant_color + average_color

#### 2.3.5 颜色命名

- CSS 色名：140 个（如 "tomato", "steelblue"）
- 中文色名：参考《中国传统色》426 色谱，或 ISCC-NBS 系统

```python
def name_color_cn(lab):
    # 简化示例：基于 H 判大类
    rgb = cv2.cvtColor(np.uint8([[lab]]), cv2.COLOR_LAB2RGB)[0,0]
    r, g, b = rgb
    if r > 200 and g < 80 and b < 80: return "红色"
    if r > 200 and g > 200 and b < 80: return "黄色"
    if r < 80 and g > 150 and b < 80: return "绿色"
    if r < 80 and g < 80 and b > 200: return "蓝色"
    return "中性色"
```

---

### 2.4 色彩心理学

#### 2.4.1 暖色/冷色判别

- 暖色：R 通道均值 > B 通道均值
- 冷色：B > R
- 阈值：$|R - B| > 10$ 判定，否则中性

#### 2.4.2 季节感映射

| 季节 | 主色组合 | H 范围 |
|------|---------|--------|
| 春 | 粉、嫩绿 | H ∈ [60°, 160°] ∪ [300°, 360°] |
| 夏 | 蓝、明黄 | H ∈ [180°, 260°] ∪ [40°, 60°] |
| 秋 | 橙、红、棕 | H ∈ [10°, 50°] |
| 冬 | 白、灰、冷蓝 | 低 S + 高 L |

#### 2.4.3 情感映射表

| 颜色 | 正向情感 | 负向情感 | 典型应用 |
|------|---------|---------|---------|
| 红 | 热情、爱、力量 | 危险、警告、愤怒 | 婚礼/警示 |
| 橙 | 活力、温暖、欢快 | 焦躁 | 食品/运动 |
| 黄 | 希望、智慧、明亮 | 不安、背叛 | 儿童/警示 |
| 绿 | 自然、健康、和平 | 嫉妒、霉变 | 环保/医疗 |
| 蓝 | 冷静、科技、信任 | 忧郁、冷漠 | 科技/金融 |
| 紫 | 神秘、高贵、浪漫 | 哀伤、迷信 | 奢侈品 |
| 黑 | 高级、力量、稳重 | 死亡、压抑 | 时尚 |
| 白 | 纯洁、神圣、简约 | 虚无、空旷 | 极简 |

---

## 第三章 构图分析深度剖析

### 3.1 三分法

#### 3.1.1 显著性检测（Saliency Detection）

识别画面中视觉注意力集中的区域，是三分法评分的基础。

#### 3.1.2 显著图算法

- **Spectral Residual (SR)**：在频谱域减去残差得到显著图
  - 论文：Hou & Zhang, CVPR 2007
- **FT (Frequency Tuned)**：高斯低通+颜色对比
  - 论文：Achanta et al., CVPR 2009
- **LC (Luminance Contrast)**：基于全局亮度对比
- **HC (Histogram Contrast)**：基于颜色直方图对比

```python
import cv2
img = cv2.imread("frame.jpg")
saliency = cv2.saliency.StaticSaliencySpectralResidual_create()
(success, sal_map) = saliency.computeSaliency(img)
sal_map = (sal_map * 255).astype(np.uint8)
# FT
ft = cv2.saliency.StaticSaliencyFineGrained_create()
_, ft_map = ft.computeSaliency(img)
```

#### 3.1.3 主体位置检测

- 二值化显著图 → 找最大连通域 → 计算质心 $(cx, cy)$

#### 3.1.4 三分法评分函数

将画面分 9 宫格，主体应落在 4 个交叉点附近：

```python
def rule_of_thirds_score(sal_map):
    h, w = sal_map.shape
    cy, cx = sal_map.shape[0] / 2, sal_map.shape[1] / 2
    # 计算显著图质心
    M = cv2.moments(sal_map)
    if M["m00"] == 0: return 0.0
    px = M["m10"] / M["m00"]
    py = M["m01"] / M["m00"]
    # 三分点
    pts = [(w/3, h/3), (2*w/3, h/3), (w/3, 2*h/3), (2*w/3, 2*h/3)]
    dists = [np.hypot(px - p[0], py - p[1]) for p in pts]
    min_d = min(dists)
    # 归一化：距离越近，分数越高
    diag = np.hypot(w, h)
    score = max(0.0, 1.0 - min_d / (diag * 0.15))
    return float(score)
```

---

### 3.2 对称性

#### 3.2.1 水平/垂直/对角对称

- 计算原图与镜像翻转图的逐像素差
- 对称性分数 = $1 - \frac{\|I - I_{flip}\|}{\|I\|}$

```python
def symmetry_score(img_gray):
    h, w = img_gray.shape
    # 水平镜像（左右对称）
    flip_v = cv2.flip(img_gray, 1)
    diff_v = np.abs(img_gray.astype(np.float32) - flip_v.astype(np.float32))
    score_v = 1.0 - diff_v.mean() / 255.0
    # 垂直镜像
    flip_h = cv2.flip(img_gray, 0)
    diff_h = np.abs(img_gray.astype(np.float32) - flip_h.astype(np.float32))
    score_h = 1.0 - diff_h.mean() / 255.0
    return {"vertical": float(score_v), "horizontal": float(score_h)}
```

---

### 3.3 景深判断

#### 3.3.1 Laplacian Variance（清晰度）

$$\text{Sharpness} = \frac{1}{HW} \sum_{x,y} \left( \nabla^2 I \right)^2$$

```python
def laplacian_variance(img_gray):
    return float(cv2.Laplacian(img_gray, cv2.CV_64F).var())
```

#### 3.3.2 中心 vs 边缘清晰度对比

- 将图像分中心区域（中间 1/3）与边缘区域
- 计算 Laplacian variance 比
- 中心高、边缘低 → 浅景深（Bokeh）；接近 → 大景深

```python
def depth_of_field_score(img_gray):
    h, w = img_gray.shape
    center = img_gray[h//3:2*h//3, w//3:2*w//3]
    edge = np.concatenate([
        img_gray[:h//3].ravel(),
        img_gray[2*h//3:].ravel(),
        img_gray[h//3:2*h//3, :w//3].ravel(),
        img_gray[h//3:2*h//3, 2*w//3:].ravel(),
    ]).reshape(-1, w//3 if False else 1)  # 简化
    c_var = cv2.Laplacian(center, cv2.CV_64F).var()
    # 边缘四块
    edges = [
        img_gray[:h//3, :], img_gray[2*h//3:, :],
        img_gray[h//3:2*h//3, :w//3], img_gray[h//3:2*h//3, 2*w//3:]
    ]
    e_var = np.mean([cv2.Laplacian(e, cv2.CV_64F).var() for e in edges])
    return float(c_var / (e_var + 1e-6))
```

#### 3.3.3 Bokeh 检测

- 边缘区域的高频成分少 + 高光圆形模糊斑 → Bokeh 强

---

### 3.4 构图法则

| 法则 | 描述 | 评分要点 |
|------|------|---------|
| 黄金分割 | 主体位于 0.618 处 | 类似三分法但偏移更内 |
| 三分法 | 主体位于三分线交叉点 | 见 3.1.4 |
| 中心构图 | 主体位于画面中心 | 质心距中心 < 阈值 |
| 对角线构图 | 主要边缘沿对角线 | Hough 直线主方向 45°/135° |
| 引导线 | 场景中线条引导至主体 | 检测直线汇聚点 |
| 框架构图 | 前景形成边框 | 边缘检测暗色环 |

---

## 第四章 场景识别深度剖析

### 4.1 传统方法

#### 4.1.1 SIFT/SURF/ORB 特征

- **SIFT**：尺度不变特征，专利已过期，OpenCV 可用
- **SURF**：SIFT 加速版，曾受专利限制
- **ORB**：免费快速，AE 引擎推荐
- 论文：Rublee et al., "ORB: an efficient alternative to SIFT or SURF", ICCV 2011

#### 4.1.2 BoVW（Bag of Visual Words）

1. 提取所有训练图像的 ORB 特征
2. K-Means 聚类得到视觉词典（K=1000~5000）
3. 每张图量化为词频直方图
4. 用 SVM 分类

#### 4.1.3 SVM 分类

```python
from sklearn.svm import LinearSVC
clf = LinearSVC(C=1.0)
clf.fit(X_train_bow, y_train)
```

---

### 4.2 深度学习方法

#### 4.2.1 ResNet50/101（推荐）

- 残差连接，深网络易训练
- 论文：He et al., "Deep Residual Learning", CVPR 2016, arXiv:1512.03385
- ImageNet Top-5：ResNet50 ~92.9%, ResNet101 ~94.0%
- **AE 引擎推荐**：精度-速度均衡，生态成熟

#### 4.2.2 VGG16/19

- 结构简单但参数量大（VGG16 ~138M）
- 论文：Simonyan & Zisserman, arXiv:1409.1556

#### 4.2.3 EfficientNet（SOTA 效率）

- 复合缩放（depth/width/resolution 同时缩放）
- 论文：Tan & Le, "EfficientNet", ICML 2019, arXiv:1905.11946
- EfficientNet-B7：Top-1 84.4%，参数 66M

#### 4.2.4 ViT（Vision Transformer）

- 将图像切 patch 喂入 Transformer
- 论文：Dosovitskiy et al., "An Image is Worth 16x16 Words", ICLR 2021, arXiv:2010.11929
- 大数据下表现优异，小数据集需 ViT-Large 以上

#### 4.2.5 CLIP（多模态）

- 图文对比学习，零样本分类能力强
- 论文：Radford et al., "Learning Transferable Visual Models", ICML 2021, arXiv:2103.00020
- 代码：https://github.com/openai/CLIP
- **AE 引擎应用**：用 CLIP 给画面打语义标签（"夕阳海景"、"城市夜景"），无需训练自定义分类器

```python
import torch, clip
from PIL import Image
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device)
image = preprocess(Image.open("frame.jpg")).unsqueeze(0).to(device)
texts = ["城市夜景", "自然风光", "人像特写", "动作场面", "抽象艺术"]
text_tokens = clip.tokenize(texts).to(device)
with torch.no_grad():
    logits = model(image, text_tokens).logits_per_image.softmax(-1)
for t, p in zip(texts, logits[0]):
    print(f"{t}: {p:.3f}")
```

#### 4.2.6 预训练模型选择策略

| 数据量 | 任务 | 推荐模型 |
|--------|------|---------|
| < 1k 张 | 通用分类 | CLIP 零样本 |
| 1k~10k | 自定义 | ResNet50 微调 |
| > 10k | 高精度 | EfficientNet / ViT |
| 实时需求 | 边缘部署 | MobileNetV3 |

---

### 4.3 目标检测

#### 4.3.1 YOLOv8/v10（实时）

- 论文/代码：https://github.com/ultralytics/ultralytics
- YOLOv8 在 COCO 上 mAP 53.9，速度 280 FPS（A100）
- YOLOv10（2024）端到端无 NMS

```python
from ultralytics import YOLO
model = YOLO("yolov8n.pt")
results = model("frame.jpg")
for r in results:
    boxes = r.boxes
    for b in boxes:
        cls = model.names[int(b.cls)]
        conf = float(b.conf)
        xyxy = b.xyxy[0].cpu().numpy()
```

#### 4.3.2 Faster R-CNN（高精度）

- 两阶段检测：RPN + ROI Pooling
- 论文：Ren et al., NeurIPS 2015, arXiv:1506.01497
- mAP 高但速度慢

#### 4.3.3 DETR（Transformer）

- 论文：Carion et al., "End-to-End Object Detection with Transformers", ECCV 2020, arXiv:2005.12872
- 无 NMS、无 anchor，端到端

---

### 4.4 场景类型分类体系

#### 4.4.1 Places365（365 类场景）

- 数据集 800 万张图，覆盖 365 个场景类（"海滩"、"卧室"、"火车站"）
- 论文：Zhou et al., "Places: A 10 Million Image Database for Scene Recognition", IEEE TPAMI 2017
- 主页：http://places2.csail.mit.edu/
- 预训练模型：ResNet50 在 Places365 上的权重可直接下载

#### 4.4.2 ImageNet（1000 类）

- 通用物体分类基准
- 主页：https://www.image-net.org/

#### 4.4.3 自定义分类体系（AE 引擎推荐）

针对 AE 剪辑场景，建议使用精简的 5~8 类体系：

```yaml
scene_taxonomy:
  - cityscape       # 城市景观
  - nature          # 自然风光
  - portrait        # 人像特写
  - action          # 动作场面
  - abstract        # 抽象/动画
  - interior        # 室内场景
  - food            # 食物
  - text_overlay    # 字幕/图文
```

---

## 第五章 视频处理深度剖析

### 5.1 场景分割

#### 5.1.1 PySceneDetect（基于直方图差异）

- 代码：https://github.com/Breakthrough/PySceneDetect
- 算法：相邻帧 HSV 直方图卡方距离 + 自适应阈值

```python
from scenedetect import detect, ContentDetector
scene_list = detect("video.mp4", ContentDetector(threshold=27.0, min_scene_len=15))
for s in scene_list:
    print(s)  # (start, end)
```

#### 5.1.2 TransNetV2（深度学习，SOTA）

- 论文：Súkeník et al., "TransNetV2: An effective deep network architecture for shot boundary detection", 2022, arXiv:2103.17218
- 代码：https://github.com/soCzechia/TransNetV2
- 精度优于传统方法，可检测渐变转场（fade、dissolve）

```python
import tensorflow as tf
from transnetv2 import TransNetV2
model = TransNetV2()
predictions = model.predict_video(video_path="video.mp4")
scenes = model.predictions_to_scenes(predictions)
```

#### 5.1.3 镜头边界检测（cut/gradual transition）

- **硬切（cut）**：帧间差异陡变，幅值大
- **渐变（gradual）**：dissolve/fade，连续多帧中等差异

---

### 5.2 关键帧提取

#### 5.2.1 帧差分法

```python
def keyframes_diff(cap, threshold=0.5):
    prev = None
    keyframes = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret: break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev is not None:
            diff = np.mean(np.abs(gray.astype(np.float32) - prev.astype(np.float32)))
            if diff > threshold:
                keyframes.append((idx, frame))
        prev = gray
        idx += 1
    return keyframes
```

#### 5.2.2 聚类法

- 对全片采样帧做 K-Means，每类取最接近中心的帧

#### 5.2.3 显著性法

- 选显著图能量最大的若干帧

---

### 5.3 视频质量评估

#### 5.3.1 BRISQUE（无参考）

- 使用场景统计特征 + SVR 训练
- 论文：Mittal et al., "No-Reference Image Quality Assessment in the Spatial Domain", 2012
- OpenCV 内置：`cv2.quality.QualityBRISQUE_create()`

#### 5.3.2 NIQE

- 与 BRISQUE 类似但不需训练（基于自然场景统计 MA 模型）

#### 5.3.3 PIQE

- Perception-based Image Quality Evaluator

```python
import cv2
brisque = cv2.quality.QualityBRISQUE_create("brisque_model_live.yml", "brisque_range_live.yml")
score = brisque.compute(img)
```

---

## 第六章 工具库深度对比

| 库 | 版本(2024) | 许可证 | 活跃度 | 主要依赖 | 性能 | 社区 |
|----|-----------|--------|--------|---------|------|------|
| OpenCV | 4.9 | Apache 2.0 | 高 | numpy, ffmpeg | 极快(C++) | ★★★★★ |
| scikit-image | 0.22 | BSD | 中高 | numpy, scipy | 中(Python) | ★★★★ |
| Pillow (PIL) | 10.2 | MIT | 高 | - | 中 | ★★★★★ |
| imageio | 2.34 | BSD | 高 | numpy | 中 | ★★★★ |
| av (PyAV) | 12.0 | BSD | 中 | ffmpeg | 快(直接C API) | ★★★ |
| decord | 0.6 | Apache2 | 中 | ffmpeg | 极快(GPU可) | ★★★ |
| mmcv (OpenMMLab) | 2.1 | Apache 2.0 | 高 | torch | 中 | ★★★★ |
| torch/torchvision | 2.2 | BSD | 高 | - | 极快(GPU) | ★★★★★ |
| ultralytics (YOLO) | 8.1 | AGPL | 高 | torch | 极快 | ★★★★★ |

**AE 引擎推荐组合**：OpenCV（基础） + PyAV/decord（视频解码） + torch/CLIP（语义） + ultralytics（目标检测） + PySceneDetect（场景分割）

---

## 第七章 数据集和评估基准

### 7.1 主要数据集

| 数据集 | 类别数 | 数据量 | 任务 | 链接 |
|--------|--------|--------|------|------|
| ImageNet | 1000 | 1.4M | 通用分类 | image-net.org |
| Places365 | 365 | 8M | 场景识别 | places2.csail.mit.edu |
| COCO | 80 | 330K图 | 目标检测 | cocodataset.org |
| DUTS | - | 10K | 显著性分割 | cvlab.ust.hk |
| Hollywood2 | 12 | 20h | 动作识别 | di.ens.fr |
| KITTI Flow | - | 400帧 | 光流 | cvlibs.net |
| Sintel | - | 1041帧 | 光流 | MPI Sintel |
| FlyingChairs | - | 22872对 | 光流 | MPI |

### 7.2 评估指标

- **分类**：Top-1/Top-5 Accuracy
- **目标检测**：mAP@0.5, mAP@0.5:0.95
- **分割**：IoU, F1, Dice
- **光流**：EPE（End-Point-Error）

---

## 第八章 硬件需求

### 8.1 CPU 计算时间基准（1080p 单帧）

| 任务 | i5-12400 | i7-13700 | 备注 |
|------|---------|---------|------|
| Farneback 光流 | 80 ms | 35 ms | OpenCV |
| K-Means 主色 | 25 ms | 12 ms | 采样后 |
| 三分法评分 | 5 ms | 2 ms | |
| ResNet50 分类 | 300 ms | 120 ms | ONNX CPU |
| YOLOv8n 检测 | 200 ms | 80 ms | CPU |

### 8.2 GPU 加速场景

- 光流：CUDA OpticalFlow（cuOF）提速 5~10×
- 分类/检测：GPU 提速 10~50×
- **强烈建议**：CUDA 11+ / cuDNN 8+，4GB 以上显存

### 8.3 内存需求

- 1080p 单帧 BGR：~6MB
- 缓存 30 帧用于光流分析：~200MB
- 加载 ResNet50：~600MB 显存
- 加载 YOLOv8n：~500MB 显存

### 8.4 视频流式处理

- **关键**：不要一次性读全片，按需 seek
- decord 支持 RandomAccessReader，可任意 seek 且快
- 每 N 帧采样 1 帧用于分析（N=5~10）

---

## 第九章 与 AE 引擎集成

### 9.1 Python 调用模式

- AE ExtendScript 通过 `system.callSystem()` 调 Python，传 JSON
- 或用 Node.js 子进程 + Python child_process
- AE 2024+ 支持 ExtendScript → Python 桥接

```javascript
// ExtendScript 调用 Python
var cmd = 'python analyze_clip.py "' + footagePath + '"';
var result = system.callSystem(cmd);
var data = JSON.parse(result);
// data.motion_intensity, data.dominant_color, ...
```

### 9.2 性能优化

- **帧采样率**：24/30fps 视频按 5fps 采样，60fps 按 10fps 采样
- **并行处理**：光流/色彩/构图/场景识别四通道并行（multiprocessing.Pool）
- **缓存中间结果**：每帧的 HSV/Lab/灰度图只计算一次
- **降级机制**：GPU 不可用时自动切到 CPU 模型（YOLOv8n → ResNet50 → CLIP 零样本）

### 9.3 错误处理和降级

```python
try:
    flow = run_raft(prev_gray, next_gray)
except Exception as e:
    logger.warning(f"RAFT 失败，降级到 Farneback: {e}")
    flow = cv2.calcOpticalFlowFarneback(...)
```

---

## 第十章 12 周学习路径细化（仅 CV 部分）

### 第 1 周：基础与 OpenCV 入门
- 教材：《OpenCV 4 计算机视觉项目实战》第 1-3 章
- 论文：Horn & Schunck 1981（光流奠基）
- 实战：用 OpenCV 读取视频，计算 HSV 直方图
- 验收：能输出每帧的均值颜色

### 第 2 周：光流算法（传统）
- 教材：Szeliski《Computer Vision: Algorithms and Applications》第 8 章
- 论文：Lucas & Kanade 1981、Farnebäck 2003
- 实战：实现 LK 与 Farneback，对比可视化
- 验收：输出运动方向直方图

### 第 3 周：光流算法（深度学习）
- 论文：RAFT (arXiv:2003.12039)、FlowNet2
- 视频：第一行代码 RAFT 复现
- 实战：在 Sintel 数据集上跑 RAFT
- 验收：EPE < 5px

### 第 4 周：色彩分析
- 教材：《Color: An Introduction to Practice and Principles》
- 论文：CIEDE2000 色差公式
- 实战：实现 K-Means 主色提取
- 验收：给定电影帧输出 6 色板

### 第 5 周：构图分析
- 教材：《摄影构图学》
- 论文：Spectral Residual Saliency (CVPR 2007)
- 实战：实现三分法评分
- 验收：对 100 张摄影作品评分，与人工评分相关 > 0.6

### 第 6 周：场景识别（传统）
- 教材：《视觉词袋模型综述》
- 实战：实现 BoVW + SVM 分类
- 验收：在 5 类场景上 mAP > 0.7

### 第 7 周：场景识别（深度学习）
- 论文：ResNet (arXiv:1512.03385)
- 实战：用 torchvision 加载 ResNet50，迁移学习
- 验收：自定义 8 类场景 Top-1 > 0.8

### 第 8 周：CLIP 与多模态
- 论文：CLIP (arXiv:2103.00020)
- 实战：用 CLIP 给电影帧打语义标签
- 验收：能输出"夕阳海边"这类描述性标签

### 第 9 周：目标检测
- 论文：YOLOv8 文档、Faster R-CNN、DETR
- 实战：用 YOLOv8 检测视频中人物
- 验收：能输出每帧人物框

### 第 10 周：视频场景分割
- 论文：TransNetV2 (arXiv:2103.17218)
- 实战：用 PySceneDetect + TransNetV2 双方案对比
- 验收：能输出视频镜头列表

### 第 11 周：视频质量评估
- 论文：BRISQUE (Mittal 2012)
- 实战：实现 BRISQUE/NIQE
- 验收：能输出每个镜头的质量分数

### 第 12 周：综合实战与 AE 集成
- 实战：将以上模块封装为 `analyze_clip.py`，输出 ClipAtom YAML
- 验收：对一段 3 分钟视频，2 分钟内完成全部分析

---

## 第十一章 隐藏缺口识别

### 11.1 视频编码多样性

- **H.264**：最常见，OpenCV/decord 兼容好
- **H.265/HEVC**：需 ffmpeg 支持，部分库解码慢
- **ProRes**：Apple 专业格式，需 ffmpeg with --enable-gpl
- **AV1**：开源新格式，解码 CPU 开销大，建议硬件解码
- **AE 引擎建议**：统一转码为 H.264 中间格式再分析

### 11.2 帧率不统一

- 24/25/30/60/120fps 共存
- 解决：分析前统一重采样到 30fps，或按时间戳采样

### 11.3 隔行扫描 vs 逐行扫描

- 隔行扫描（1080i）需先去隔行
- 用 `cv2.deinterlace()` 或 ffmpeg `yadif` 滤镜

### 11.4 HDR 视频

- HDR10/HDR10+/Dolby Vision
- 8-bit SDR 算法直接失效，需 PQ/HLG → SDR 色调映射
- cv2 不直接支持 HDR 解码，需 ffmpeg 提取

### 11.5 RAW 视频

- CinemaDNG / RED R3D / ProRes RAW
- 厂商 SDK 才能解码，AE 引擎建议拒绝或转码

### 11.6 极端情况

- **极暗**：噪声大，光流易失败，需先降噪（BM3D / DnCNN）
- **极亮**：过曝，细节丢失，需检测过曝区域
- **单色**：主色聚类退化（所有像素同色），需检测并输出 "monochrome"
- **闪烁**：flicker，亮度周期性变化，需检测后做 deflicker

### 11.7 中文环境特殊场景

- **古风**：低饱和、暖黄基调，主色集中
- **水墨**：黑白灰阶，需独立黑白分类器
- **书法**：黑底白字或白底黑字，需 OCR 配合
- **AE 引擎建议**：训练专用 LoRA 微调 CLIP 中文分类头

---

## 参考资源汇总

### 论文与 arXiv 编号
- Horn & Schunck 1981 AI 17:185-203
- Lucas & Kanade 1981 IJCAI
- Farnebäck 2003 SCIA
- DeepFlow arXiv:1512.01255
- RAFT arXiv:2003.12039
- ResNet arXiv:1512.03385
- VGG arXiv:1409.1556
- EfficientNet arXiv:1905.11946
- ViT arXiv:2010.11929
- CLIP arXiv:2103.00020
- YOLOv8 ultralytics.com
- Faster R-CNN arXiv:1506.01497
- DETR arXiv:2005.12872
- TransNetV2 arXiv:2103.17218
- BRISQUE (Mittal 2012)
- CIEDE2000 (Sharma 2005)

### GitHub 仓库
- OpenCV: https://github.com/opencv/opencv
- scikit-image: https://github.com/scikit-image/scikit-image
- RAFT: https://github.com/princeton-vl/RAFT
- CLIP: https://github.com/openai/CLIP
- ultralytics: https://github.com/ultralytics/ultralytics
- PySceneDetect: https://github.com/Breakthrough/PySceneDetect
- TransNetV2: https://github.com/soCzechia/TransNetV2
- decord: https://github.com/dmlc/decord

### 官方文档
- OpenCV: https://docs.opencv.org/4.x/
- PyTorch: https://pytorch.org/docs/
- torchvision: https://pytorch.org/vision/
- Places365: http://places2.csail.mit.edu/
- ImageNet: https://www.image-net.org/
- COCO: https://cocodataset.org/

---

## 关联文档

- [[片段元数据与视觉能量图谱]]
- [[音画匹配推演系统总览]]
