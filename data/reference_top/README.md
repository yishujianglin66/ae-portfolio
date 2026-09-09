# 顶尖漫剪参照集 (data/reference_top)

个人对标学习用途，仅本地分析、不商用、不外发。
下载工具: yt-dlp + ffmpeg（2026-09-08 扩充至 145 部）。

## 采集口径

- 来源：**B站**（`yt-dlp bilisearch` 29 组关键词）+ **AcFun**（官方搜索 API，含 AKROSS Con 国际赛事作品）
- 筛选：标题须命中 AMV/MAD 域信号；排除教程/素材包/合集/短片；时长 60-400s
- 分层：燃向 burn / 叙事 narrative / 赛事 contest / 顶尖创作者 creator
- 下载：完整视频，优先 1080p（大师级不靠高码率）
- 平台分布：acfun 81, bilibili 64

## 规模（145 部 / 5.2 GB）

- 分层分布：burn 31, handdrawn 23, amv 22, puppet 15, creator_cn 12, seed 12, narrative 12, master_lens 8, contest 5, creator 4, authority 1
- 画质档位：hd1080 90, hd720 42, sd480 7, low 6
  （`low`/`sd480` 为老资源，评估时可用 `quality` 字段筛除，避免拉低对标基线）
- 分辨率：1920x1080 × 88, 1280x720 × 39, 960x540 × 6, 480x360 × 3, 640x360 × 2, 1920x780 × 1, 540x540 × 1, 1080x1080 × 1, 2160x1080 × 1, 1600x908 × 1, 320x240 × 1, 1920x864 × 1
- 帧率：≤30fps × 141, >30fps × 4
- 时长：37s ~ 389s（中位 177s）
- 码率：155 ~ 5726 kbps（中位 1521 kbps）

## 指标分位数（n=145，实测）

由 `scripts/reference_stats.py` 计算，逐部落盘 `reports/reference_stats.json`，
缓存 `reports/ref_metrics_cache.json`（二次运行秒出）。

| 指标 | 均值 | p25 | p50 | p75 | p90 | min | max |
|------|------|-----|-----|-----|-----|-----|-----|
| peak | 0.9083 | 0.9609 | 1.0 | 1.0 | 1.0 | 0.0367 | 1.0 |
| hf_energy | 44.0497 | 14.6 | 32.6 | 63.7 | 100.5 | 0.0 | 245.5 |
| onset_density | 5.0514 | 4.567 | 5.101 | 5.645 | 6.0952 | 1.332 | 7.21 |
| cut_rate | 0.9591 | 0.241 | 0.818 | 1.51 | 2.1552 | 0.0 | 3.654 |
| beat_hit_rate | 0.6876 | 0.6371 | 0.744 | 0.8068 | 0.8618 | 0.0 | 1.0 |
| cut_visibility | 0.8392 | 0.7764 | 0.9248 | 0.995 | 1.0666 | 0.0 | 1.1979 |

**与 run61 最佳候选（master_hr.mp4）对比**：

| 指标 | 本片 | 参照均值 | p75 | 判定 |
|------|------|---------|-----|------|
| peak | 1.0 | 0.9083 | 1.0 | 劣于均值 |
| hf_energy | 54.0 | 44.0497 | 63.7 | 超均值 |
| onset_density | 6.363 | 5.0514 | 5.645 | 超 p90 |
| cut_rate | 3.665 | 0.9591 | 1.51 | 超 p90 |
| beat_hit_rate | 0.8545 | 0.6876 | 0.8068 | 超 p75 |
| cut_visibility | 0.8698 | 0.8392 | 0.995 | 超均值 |

> **证据说明**：原评估报告引用的「参照前三分位 0.8193」在落盘数据中不存在（旧脚本 `score_reference_gap.py` 只算 mean/min/max，未实现分位数）。
以上分位数为 n=145 实测值，可直接复核。

### 按风格分层（均值，跨风格不可直接混算）

| tier | n | beat_hit_rate | cut_visibility | cut_rate | hf_energy |
|------|---|--------------|---------------|---------|-----------|
| burn | 31 | 0.6576 | 0.8851 | 1.1857 | 63.0 |
| handdrawn | 23 | 0.7215 | 0.8001 | 0.3271 | 27.8 |
| amv | 22 | 0.7635 | 0.9485 | 1.3705 | 55.0 |
| puppet | 15 | 0.4156 | 0.4696 | 0.1613 | 24.6 |
| seed | 12 | 0.7559 | 0.9549 | 1.7249 | 50.0 |
| narrative | 12 | 0.7291 | 0.9352 | 1.066 | 42.4 |
| creator_cn | 12 | 0.7286 | 0.8066 | 0.9201 | 55.6 |
| master_lens | 8 | 0.758 | 0.8845 | 1.3385 | 20.6 |
| contest | 5 | 0.6915 | 0.9425 | 0.8252 | 12.9 |
| creator | 4 | 0.7114 | 0.8122 | 0.6915 | 47.2 |
| authority | 1 | 0.76 | 0.5394 | 0.089 | 23.0 |

> 木偶（puppet）与手书（handdrawn）的 cut_visibility / cut_rate 天然远低于
> 燃向漫剪——前者是有限动画/骨骼驱动，切点密度本就稀疏。**对标 run61 这类
> 燃向踩点片时，应只与 burn / amv / seed 层比较**，勿用全体均值。

## 清单

| # | 标题 | 平台 | 分层 | 画质 | 时长 | 分辨率 | 帧率 | 大小 | 来源 |
|---|------|------|------|------|------|--------|------|------|------|
| 1 | 《原神》万叶手书「可叹叶飘零，归期未有期」 | bilibili | creator_cn | hd1080 | 232s | 1920x1080 | 30 | 22.4MB | [BV17M4y1M7Lv](https://www.bilibili.com/video/BV17M4y1M7Lv) |
| 2 | 泛式 剧情MAD 原来你是我最想留住的幸运 「春物完结篇」 | bilibili | creator_cn | hd1080 | 298s | 1920x1080 | 30 | 12.6MB | [BV18Z4y1V7ZJ](https://www.bilibili.com/video/BV18Z4y1V7ZJ) |
| 3 | 挑战B站最强踩点！108部动画超燃混剪！！！ | bilibili | burn | hd1080 | 150s | 1920x1080 | 23.98 | 49.8MB | [BV1nV411a7jr](https://www.bilibili.com/video/BV1nV411a7jr) |
| 4 | 【海贼王 极致踩点 燃爆】点燃你的腺上激素，爽就完事了！！！ | bilibili | burn | hd1080 | 180s | 1920x1080 | 23.98 | 23.0MB | [BV1D4411k7UE](https://www.bilibili.com/video/BV1D4411k7UE) |
| 5 | 泛式 单集MAD 海贼王 顶上战争篇 这个时代的名字叫白胡子！ | bilibili | creator_cn | hd720 | 255s | 1280x720 | 24 | 66.2MB | [BV1qW411j7TR](https://www.bilibili.com/video/BV1qW411j7TR) |
| 6 | 【兵长A爆！踩点】1 22秒让你沉陷于兵长的魅力中！ | bilibili | burn | hd720 | 83s | 1280x720 | 23.98 | 12.5MB | [BV1uE411Z79z](https://www.bilibili.com/video/BV1uE411Z79z) |
| 7 | 《原神》流浪者手书「彷徨在那无可奈何的夜」 | bilibili | creator | hd1080 | 163s | 1920x1080 | 30 | 15.9MB | [BV1TP4y1Q72x](https://www.bilibili.com/video/BV1TP4y1Q72x) |
| 8 | 【AMV-柯南】全员高燃混剪，你准备好了吗 | bilibili | burn | hd1080 | 232s | 1920x1080 | 25 | 45.0MB | [BV13Q4y1N734](https://www.bilibili.com/video/BV13Q4y1N734) |
| 9 | [前方高燃预警]全员恶人，各自为营 | bilibili | burn | hd1080 | 135s | 1920x1080 | 30 | 20.5MB | [BV1VY4y1o79P](https://www.bilibili.com/video/BV1VY4y1o79P) |
| 10 | 【fate saber 全程高燃】这就是吾王的巅峰打戏 | bilibili | burn | hd720 | 213s | 1280x720 | 30 | 14.2MB | [BV1MB84eoEtP](https://www.bilibili.com/video/BV1MB84eoEtP) |
| 11 | 这才是男生眼中的花子君！全程踩点燃向！ | bilibili | burn | hd1080 | 77s | 1920x1080 | 30 | 9.1MB | [BV17a4y1x77M](https://www.bilibili.com/video/BV17a4y1x77M) |
| 12 | “前方高燃！！！”—《Alibi》 | bilibili | burn | hd1080 | 220s | 1920x1080 | 30 | 20.2MB | [BV19C411z7Nr](https://www.bilibili.com/video/BV19C411z7Nr) |
| 13 | 『索隆超燃混剪』25秒后准备好硬币 这才是海贼王副手的实力！ | bilibili | burn | hd1080 | 226s | 1920x1080 | 30 | 26.9MB | [BV1re411g7M9](https://www.bilibili.com/video/BV1re411g7M9) |
| 14 | 【阴阳师 踩点 燃向】毁灭，才是反派的浪漫~~ | bilibili | burn | hd1080 | 195s | 1920x1080 | 30 | 30.0MB | [BV19t41157E6](https://www.bilibili.com/video/BV19t41157E6) |
| 15 | ⚠️史诗级高燃！战力天花板的觉醒时刻 | bilibili | burn | hd1080 | 181s | 1920x1080 | 30 | 23.5MB | [BV1NQcLe7EjC](https://www.bilibili.com/video/BV1NQcLe7EjC) |
| 16 | 【魔道祖师 踩点向】To make it in this world（踩点 燃向 | bilibili | burn | hd1080 | 111s | 1920x1080 | 25 | 11.1MB | [BV1t4411F7tG](https://www.bilibili.com/video/BV1t4411F7tG) |
| 17 | ⚡「凹凸世界-全员就位」⚡【全员 踩点 4k 高燃】 | bilibili | burn | hd1080 | 178s | 1920x1080 | 24 | 40.3MB | [BV12T411u7sU](https://www.bilibili.com/video/BV12T411u7sU) |
| 18 | 【AMV 狂赌之渊】Beggars『踩点 燃向』 | bilibili | burn | hd720 | 71s | 1280x720 | 24 | 9.0MB | [BV14b411t7fg](https://www.bilibili.com/video/BV14b411t7fg) |
| 19 | 泛式 单集MAD 一拳超人 深海王篇 不屈的正义 | acfun | creator_cn | hd720 | 221s | 1280x720 | 23.98 | 50.9MB | [ac2503567](https://www.acfun.cn/v/ac2503567) |
| 20 | 【一念永恒 4k】：⚡年度超燃混剪⚡ | bilibili | burn | hd1080 | 92s | 1920x1080 | 30 | 12.8MB | [BV1Zg4y1c7KU](https://www.bilibili.com/video/BV1Zg4y1c7KU) |
| 21 | 一拳超人 AMV 击杀咏叹调 Murder Melody | acfun | master_lens | sd480 | 254s | 960x540 | 30 | 31.6MB | [ac2346223](https://www.acfun.cn/v/ac2346223) |
| 22 | 【首席高燃】“看好了，魔刀是这样用的” | bilibili | burn | hd1080 | 205s | 1920x1080 | 25 | 21.0MB | [BV1Za4y1571t](https://www.bilibili.com/video/BV1Za4y1571t) |
| 23 | 【4K】这可能是你看过最帅的蜘蛛侠混剪 | bilibili | burn | hd1080 | 155s | 1920x1080 | 30 | 38.0MB | [BV1Az4y1V7Yb](https://www.bilibili.com/video/BV1Az4y1V7Yb) |
| 24 | [一拳超人超燃AMV] JUST ONE PUNCH！ | acfun | creator_cn | hd720 | 110s | 1280x720 | 30 | 22.1MB | [ac2349288](https://www.acfun.cn/v/ac2349288) |
| 25 | 炮姐战歌，记录高燃时刻！ | bilibili | burn | hd1080 | 256s | 1920x1080 | 25 | 44.7MB | [BV144411B77s](https://www.bilibili.com/video/BV144411B77s) |
| 26 | 𝙀𝙫𝙚𝙧𝙮𝙩𝙝𝙞𝙣𝙜 𝙗𝙡𝙖𝙘𝙠【高燃 踩点 暗影大人MAD】 | bilibili | burn | hd1080 | 238s | 1920x1080 | 29.97 | 21.2MB | [BV1qc411j7Ge](https://www.bilibili.com/video/BV1qc411j7Ge) |
| 27 | 【静止画MAD】 introductory chapter 【路人女主】 | bilibili | narrative | hd1080 | 264s | 1920x1080 | 30 | 66.4MB | [BV1ws411S7tm](https://www.bilibili.com/video/BV1ws411S7tm) |
| 28 | ⚡️前方惊艳无限！来感受米游的踩点盛宴吧！ | bilibili | burn | hd1080 | 351s | 1920x1080 | 25 | 81.3MB | [BV1jLAJeLEYV](https://www.bilibili.com/video/BV1jLAJeLEYV) |
| 29 | ⚠️弹丸论破，但是高燃踩点！⚠️ | bilibili | burn | hd1080 | 172s | 1920x1080 | 27.58 | 18.8MB | [BV1LG4y1v7hz](https://www.bilibili.com/video/BV1LG4y1v7hz) |
| 30 | 【高燃 踩点】用高燃的方式打开约定的梦幻岛 | bilibili | burn | hd1080 | 179s | 1920x1080 | 30 | 26.1MB | [BV1Qb411g7ac](https://www.bilibili.com/video/BV1Qb411g7ac) |
| 31 | AMV 略鬼畜 一拳超人，太强的话，会很寂寞的 | acfun | amv | hd720 | 177s | 1280x720 | 30 | 22.9MB | [ac2337076](https://www.acfun.cn/v/ac2337076) |
| 32 | 【不死者之王 混剪 1080P】前方高能，吾乃侍奉无上至尊之人！ | bilibili | burn | hd720 | 232s | 1280x720 | 25 | 62.1MB | [BV1Mb411M7yL](https://www.bilibili.com/video/BV1Mb411M7yL) |
| 33 | 【猫之茗X混剪】给圈外人一点小小的茗圈震撼 | bilibili | burn | hd1080 | 143s | 1920x1080 | 30 | 13.4MB | [BV1hW6FYZE5V](https://www.bilibili.com/video/BV1hW6FYZE5V) |
| 34 | 猫【Mad 大赛 2016】 | bilibili | creator | hd720 | 144s | 1280x720 | 29.97 | 7.0MB | [BV1Xs411C7Tx](https://www.bilibili.com/video/BV1Xs411C7Tx) |
| 35 | 【甜蜜家园 Sweet Home】燃向 全员疯狂踩点 | bilibili | burn | hd1080 | 148s | 1920x1080 | 25 | 18.0MB | [BV1qf4y1e7Ne](https://www.bilibili.com/video/BV1qf4y1e7Ne) |
| 36 | 【七大罪 高燃AMV】我曾为了你放弃称王，现在我要为了你重回王座！ | bilibili | burn | hd1080 | 199s | 1920x1080 | 30 | 71.8MB | [BV1Et411z7Ao](https://www.bilibili.com/video/BV1Et411z7Ao) |
| 37 | 各种晒妹子!! 各种吻!!! Amv 初吻 | acfun | amv | hd720 | 246s | 1280x720 | 23.98 | 48.6MB | [ac3016322](https://www.acfun.cn/v/ac3016322) |
| 38 | 【绝望合集】“所以生命啊，它苦涩如歌。” 催泪向 | bilibili | narrative | hd1080 | 196s | 1920x1080 | 30 | 13.4MB | [BV1rj411U7jc](https://www.bilibili.com/video/BV1rj411U7jc) |
| 39 | 【国漫 全程高燃 一人之下】高燃混剪！ | bilibili | burn | hd1080 | 126s | 1920x1080 | 29.97 | 51.1MB | [BV1S7411d7Hy](https://www.bilibili.com/video/BV1S7411d7Hy) |
| 40 | Hands in my hand 动态歌词排版 燃向踩点 混剪 | bilibili | burn | hd1080 | 176s | 1920x1080 | 30 | 29.7MB | [BV19V4y1x7Aj](https://www.bilibili.com/video/BV19V4y1x7Aj) |
| 41 | AMV HERO S COME BACK AKROSS Con 2015 | acfun | master_lens | hd720 | 96s | 1280x720 | 30 | 18.4MB | [ac2433831](https://www.acfun.cn/v/ac2433831) |
| 42 | AMV 分开这么久了，你有想过我吗 | acfun | amv | sd480 | 268s | 960x540 | 30 | 29.8MB | [ac2319337](https://www.acfun.cn/v/ac2319337) |
| 43 | 一拳超人 AMV 超燃 佩戴耳机效果更佳 | acfun | amv | hd1080 | 230s | 1920x1080 | 30 | 87.4MB | [ac3955423](https://www.acfun.cn/v/ac3955423) |
| 44 | 你的名字 AMV 从梦中找寻你の名字 | acfun | amv | hd1080 | 173s | 1920x1080 | 30 | 55.7MB | [ac3412438](https://www.acfun.cn/v/ac3412438) |
| 45 | 博人传 AMV | acfun | amv | hd1080 | 242s | 1920x1080 | 30 | 75.0MB | [ac2551109](https://www.acfun.cn/v/ac2551109) |
| 46 | 超闪衔接AMV 战斗不停，燃息不止 | acfun | amv | hd720 | 286s | 1280x720 | 23.98 | 68.4MB | [ac2694782](https://www.acfun.cn/v/ac2694782) |
| 47 | 【魔圆 踩点 高燃】𝑩𝒆 𝑻𝒉𝒆 𝑹𝒆𝒏𝒆𝒈𝒂𝒅𝒆𝒔 | bilibili | burn | hd1080 | 91s | 1920x1080 | 25 | 18.0MB | [BV1FS4y1t76A](https://www.bilibili.com/video/BV1FS4y1t76A) |
| 48 | 【静止画MAD】【龙王的工作！】银空 | bilibili | narrative | hd720 | 92s | 1280x720 | 25 | 16.0MB | [BV1nW411g74U](https://www.bilibili.com/video/BV1nW411g74U) |
| 49 | 【K 高燃 混剪 全员美男】NO BLOOD！NO BONE！NO ASH！ | bilibili | burn | hd1080 | 76s | 1920x1080 | 30 | 11.0MB | [BV1Nx4y1Z76T](https://www.bilibili.com/video/BV1Nx4y1Z76T) |
| 50 | 欢乐节奏向 AMV 这是我最好的咸鱼了~！ | acfun | amv | hd720 | 130s | 1280x720 | 30 | 25.4MB | [ac2702228](https://www.acfun.cn/v/ac2702228) |
| 51 | 【Lycoris Recoil 踩点 高燃 Light That Fire】千攻 | bilibili | burn | hd1080 | 122s | 1920x1080 | 30 | 17.7MB | [BV1VN4y1K72e](https://www.bilibili.com/video/BV1VN4y1K72e) |
| 52 | 【静止画MAD】人造人・沙鲁篇【龙珠Z】 | bilibili | narrative | hd1080 | 150s | 1920x1080 | 24 | 32.3MB | [BV1NYtKeXEPu](https://www.bilibili.com/video/BV1NYtKeXEPu) |
| 53 | AMV-龙珠Z 孙悟饭 英雄传奇 | acfun | amv | hd720 | 342s | 1280x720 | 30 | 63.0MB | [ac2537523](https://www.acfun.cn/v/ac2537523) |
| 54 | AMV 玉子的甜蜜爱恋 | acfun | amv | hd720 | 108s | 1280x720 | 30 | 18.5MB | [ac2397038](https://www.acfun.cn/v/ac2397038) |
| 55 | 庆年AMV 这次就给你们来一场节奏盛宴 | acfun | amv | sd480 | 314s | 960x540 | 30 | 35.4MB | [ac2504503](https://www.acfun.cn/v/ac2504503) |
| 56 | 夏日蕉易战A队 AVUP的虚度日常（描改手书） A站独家 | acfun | handdrawn | hd1080 | 110s | 1920x1080 | 23.98 | 15.2MB | [ac17697429](https://www.acfun.cn/v/ac17697429) |
| 57 | AMV 燃烧的电音。多动漫衔切剪辑 | acfun | amv | hd720 | 139s | 1280x720 | 30 | 26.3MB | [ac1836108](https://www.acfun.cn/v/ac1836108) |
| 58 | 盛唐幻夜X逍遥诀手游 归去来兮-夜幕CP虐心手书MAD | acfun | handdrawn | hd1080 | 55s | 1920x1080 | 30 | 17.0MB | [ac4769608](https://www.acfun.cn/v/ac4769608) |
| 59 | 站娘有文化 手书-AC娘被玩坏了 | acfun | handdrawn | hd1080 | 300s | 1920x1080 | 25 | 83.1MB | [ac13336718](https://www.acfun.cn/v/ac13336718) |
| 60 | 富豪刑事 手书 神加 king | acfun | handdrawn | hd1080 | 135s | 1920x1080 | 30 | 36.7MB | [ac17523107](https://www.acfun.cn/v/ac17523107) |
| 61 | 【静止画MAD】亚人 | bilibili | narrative | hd720 | 96s | 1280x720 | 29.97 | 24.8MB | [BV1E7411n7nz](https://www.bilibili.com/video/BV1E7411n7nz) |
| 62 | 这就是我们用青春守护的 玉 ！ 火影忍者疾风传 青鸟AMV | acfun | amv | hd1080 | 213s | 1920x1080 | 30 | 67.5MB | [ac12957609](https://www.acfun.cn/v/ac12957609) |
| 63 | 综漫 AMV 多素材 燃系 战斗是为了未来与未来！！！ | acfun | amv | hd1080 | 216s | 1920x1080 | 30 | 83.7MB | [ac2465497](https://www.acfun.cn/v/ac2465497) |
| 64 | 富豪刑事 手书 神加的villain | acfun | handdrawn | hd720 | 199s | 1600x908 | 30 | 27.3MB | [ac17100707](https://www.acfun.cn/v/ac17100707) |
| 65 | JOJO AMV 人类的赞歌 | acfun | amv | sd480 | 313s | 960x540 | 30 | 38.4MB | [ac2566265](https://www.acfun.cn/v/ac2566265) |
| 66 | 【命运石之门0 静止画MAD】他与她的选择 | bilibili | narrative | hd1080 | 225s | 1920x1080 | 30 | 54.1MB | [BV1Z7411P78B](https://www.bilibili.com/video/BV1Z7411P78B) |
| 67 | “人类是无法互相理解的”【高达 MAD】致我们心中永远的高达 | bilibili | narrative | hd1080 | 224s | 1920x1080 | 30 | 46.9MB | [BV1xB8Q6PExX](https://www.bilibili.com/video/BV1xB8Q6PExX) |
| 68 | 误解系AMV 千反田X阿虚 不离不弃 | acfun | amv | hd720 | 226s | 1280x720 | 30 | 36.3MB | [ac1764791](https://www.acfun.cn/v/ac1764791) |
| 69 | AMV Mermaid 我是否住进你的心房了呢 | acfun | amv | hd1080 | 312s | 1920x1080 | 30 | 73.9MB | [ac2554801](https://www.acfun.cn/v/ac2554801) |
| 70 | 综漫 新人向 AMV 爆燃出你的热血 | acfun | amv | hd720 | 269s | 1280x720 | 30 | 54.9MB | [ac2541402](https://www.acfun.cn/v/ac2541402) |
| 71 | [综漫AMV] 平凡的世界 平凡的旅程 | acfun | amv | hd720 | 308s | 1280x720 | 30 | 56.8MB | [ac1890221](https://www.acfun.cn/v/ac1890221) |
| 72 | 【水星的魔女 剧情向 狸米MAD】我与你的故事 | bilibili | narrative | hd1080 | 246s | 1920x1080 | 30 | 19.6MB | [BV1n84y1h74x](https://www.bilibili.com/video/BV1n84y1h74x) |
| 73 | 少年骇客 高燃混剪AMV 英雄登 哦！小破表别挂啊！！！ | acfun | amv | hd720 | 270s | 1280x720 | 30 | 48.1MB | [ac16299856](https://www.acfun.cn/v/ac16299856) |
| 74 | 泛式 排球AMV 乌野VS青城 近年来最精彩的一场比赛 | acfun | creator_cn | hd720 | 236s | 1280x720 | 30 | 38.3MB | [ac3215351](https://www.acfun.cn/v/ac3215351) |
| 75 | 治愈 合作 AMV 再一次听见了你的声音 | acfun | amv | hd720 | 312s | 1280x720 | 30 | 44.2MB | [ac1919207](https://www.acfun.cn/v/ac1919207) |
| 76 | 听说A站的人超好，所以我就投了一个一拳超人的视频 | acfun | amv | hd1080 | 92s | 1920x1080 | 30 | 35.2MB | [ac10368003](https://www.acfun.cn/v/ac10368003) |
| 77 | AKross2016 NanaMi 孤独者的荣光 | acfun | creator_cn | hd1080 | 245s | 1920x1080 | 30 | 60.4MB | [ac3302540](https://www.acfun.cn/v/ac3302540) |
| 78 | 描改手书 那什么AcFun | acfun | handdrawn | hd1080 | 155s | 1920x1080 | 60 | 57.0MB | [ac41919817](https://www.acfun.cn/v/ac41919817) |
| 79 | 周年整婵 逐渐加快（像素风手书） | acfun | handdrawn | hd1080 | 139s | 1920x1080 | 25 | 40.4MB | [ac19506259](https://www.acfun.cn/v/ac19506259) |
| 80 | 全彩神手绘 海盗高达OP风动画 | acfun | handdrawn | low | 354s | 640x360 | 30 | 15.3MB | [ac656404](https://www.acfun.cn/v/ac656404) |
| 81 | 小马两周年 小马的偶像宣言 私、アイドル宣言 手书PV | acfun | handdrawn | hd1080 | 267s | 1920x1080 | 30 | 100.8MB | [ac35634575](https://www.acfun.cn/v/ac35634575) |
| 82 | 泛式 单集MAD 3分钟看完落第骑士第4集 唯一神的陨落 | acfun | creator_cn | hd720 | 214s | 1280x720 | 30 | 35.4MB | [ac2418354](https://www.acfun.cn/v/ac2418354) |
| 83 | 【杨志刚 黑桃Q 轻踩点】“按级别，你应该叫我长官” | bilibili | creator | hd1080 | 138s | 2160x1080 | 30 | 46.6MB | [BV1aK411D77z](https://www.bilibili.com/video/BV1aK411D77z) |
| 84 | 【MAD】爱上他人，便是孤独的开始 | bilibili | narrative | hd1080 | 283s | 1920x1080 | 24 | 65.3MB | [BV1Fb411Y7JJ](https://www.bilibili.com/video/BV1Fb411Y7JJ) |
| 85 | 朝阳 正道之光朝阳阳与千岛酱不得不说的小故事（生草手书向） | acfun | handdrawn | hd1080 | 169s | 1920x1080 | 29.97 | 26.1MB | [ac15129225](https://www.acfun.cn/v/ac15129225) |
| 86 | 【冰海战记mad 燃向】“成长的痛苦是不可避免的邪恶” | bilibili | narrative | hd1080 | 300s | 1920x1080 | 24 | 26.2MB | [BV1XoYjeyEnV](https://www.bilibili.com/video/BV1XoYjeyEnV) |
| 87 | 原创曲 想成为你的光 晴心Haruko 手书PV付 | acfun | handdrawn | hd1080 | 234s | 1920x1080 | 30 | 43.9MB | [ac28221887](https://www.acfun.cn/v/ac28221887) |
| 88 | 原神手书 这个仇我报定了！屑哥哥的最大危机 | acfun | handdrawn | hd1080 | 78s | 1920x1080 | 23.98 | 22.1MB | [ac34793635](https://www.acfun.cn/v/ac34793635) |
| 89 | 描改手书 猴山的扫除时间 | acfun | handdrawn | hd1080 | 146s | 1920x1080 | 59.94 | 34.0MB | [ac35435921](https://www.acfun.cn/v/ac35435921) |
| 90 | A站独家 谁都好、请夸夸我啦！ 手书PV | acfun | handdrawn | hd720 | 68s | 1280x720 | 25 | 7.9MB | [ac20109221](https://www.acfun.cn/v/ac20109221) |
| 91 | 【静止系 家庭教师】未来へ | bilibili | narrative | hd1080 | 275s | 1920x1080 | 25 | 64.9MB | [BV1jt4y1k7mq](https://www.bilibili.com/video/BV1jt4y1k7mq) |
| 92 | 【静止画MAD】灌篮高手全国大赛静止画~~全展示 | bilibili | narrative | hd720 | 251s | 1280x720 | 30 | 21.2MB | [BV19P411M7bd](https://www.bilibili.com/video/BV19P411M7bd) |
| 93 | 初音ミク 現充都去爆炸吧！ 手書PV字幕附 | acfun | handdrawn | low | 91s | 480x360 | 30 | 2.9MB | [ac747562](https://www.acfun.cn/v/ac747562) |
| 94 | 毒 小光子郎Caipirinha 手书MAD | acfun | handdrawn | low | 61s | 320x240 | 30 | 2.8MB | [ac2351822](https://www.acfun.cn/v/ac2351822) |
| 95 | AMV LOVE THEORY AKROSS Con 2015 | acfun | master_lens | hd720 | 193s | 1280x720 | 30 | 31.6MB | [ac2512702](https://www.acfun.cn/v/ac2512702) |
| 96 | 柯南手书MAD [昴志 秀志]KISS唾 | acfun | handdrawn | low | 71s | 480x360 | 30 | 1.4MB | [ac2614044](https://www.acfun.cn/v/ac2614044) |
| 97 | 不是很懂你们日语rap 紫雨UNITEDまさかのアリス突撃編 手書きPV | acfun | handdrawn | low | 254s | 480x360 | 30 | 14.8MB | [ac2714854](https://www.acfun.cn/v/ac2714854) |
| 98 | 描改手书 阿潘只是在摇快乐水而已 | acfun | handdrawn | hd1080 | 47s | 1920x1080 | 25 | 9.4MB | [ac33048446](https://www.acfun.cn/v/ac33048446) |
| 99 | 描改手书 延误歌名 | acfun | handdrawn | hd1080 | 170s | 1920x1080 | 60 | 35.3MB | [ac41402922](https://www.acfun.cn/v/ac41402922) |
| 100 | 东方手书PV 献给哭泣少女的七重奏 | acfun | handdrawn | low | 179s | 640x360 | 30 | 5.1MB | [ac2568422](https://www.acfun.cn/v/ac2568422) |
| 101 | AMV YEARNING DECEPTION AKROSS Con 2015 | acfun | master_lens | hd720 | 191s | 1280x720 | 30 | 29.5MB | [ac2335851](https://www.acfun.cn/v/ac2335851) |
| 102 | 颗粒苍 多人合作向手书MAD 颗粒儿生快 オーダーメイド | acfun | handdrawn | sd480 | 389s | 960x540 | 30 | 16.5MB | [ac2548178](https://www.acfun.cn/v/ac2548178) |
| 103 | 原神手书 以后这儿归我们提瓦特管了！ | acfun | handdrawn | hd1080 | 111s | 1920x1080 | 25 | 30.5MB | [ac34600275](https://www.acfun.cn/v/ac34600275) |
| 104 | AMV FATE S END AKROSS Con 2015 | acfun | master_lens | hd1080 | 149s | 1920x1080 | 30 | 60.4MB | [ac2356133](https://www.acfun.cn/v/ac2356133) |
| 105 | AMV AGAINST FATE AKROSS Con 2015 | acfun | creator_cn | hd1080 | 164s | 1920x1080 | 30 | 58.2MB | [ac2439236](https://www.acfun.cn/v/ac2439236) |
| 106 | AMV Moon Powder AKROSS Con 2014 | acfun | contest | hd720 | 211s | 1280x720 | 30 | 28.8MB | [ac1971395](https://www.acfun.cn/v/ac1971395) |
| 107 | AMV MARY MARY ACTION AKROSS Con 2015 | acfun | master_lens | hd720 | 206s | 1280x720 | 30 | 40.0MB | [ac2464669](https://www.acfun.cn/v/ac2464669) |
| 108 | AMV I LL BE HERE AKROSS Con 2015 | acfun | contest | hd1080 | 179s | 1920x1080 | 30 | 61.8MB | [ac2441173](https://www.acfun.cn/v/ac2441173) |
| 109 | AMV MY MEDICAL LIFE AKROSS Con 2015 | acfun | contest | hd720 | 280s | 1280x720 | 30 | 45.3MB | [ac2350070](https://www.acfun.cn/v/ac2350070) |
| 110 | AMV SILENCE IS GOLDEN AKROSS Con 2015 | acfun | contest | hd720 | 251s | 1280x720 | 30 | 47.7MB | [ac2512680](https://www.acfun.cn/v/ac2512680) |
| 111 | AMV FORSAKEN AKROSS Con 2015 | acfun | contest | hd720 | 247s | 1280x720 | 30 | 65.6MB | [ac2441067](https://www.acfun.cn/v/ac2441067) |
| 112 | 「暗表」手书 《祝福》——yoasobi | bilibili | creator | hd1080 | 92s | 1920x1080 | 17.75 | 33.1MB | [BV1X84y1z7S1](https://www.bilibili.com/video/BV1X84y1z7S1) |
| 113 | 黑桃Q 不要眨眼，100部二次元手游高然大混剪 | acfun | creator_cn | hd720 | 235s | 1280x720 | 29.97 | 47.7MB | [ac11272030](https://www.acfun.cn/v/ac11272030) |
| 114 | 心跳暴击！纸片人46版的「欅坂46 - 不協和音」 | acfun | puppet | hd1080 | 248s | 1920x1080 | 29.97 | 158.5MB | [ac33355485](https://www.acfun.cn/v/ac33355485) |
| 115 | 东方MMD 最近的Twitte动画总结 | acfun | puppet | hd720 | 231s | 1280x720 | 30 | 30.8MB | [ac16768404](https://www.acfun.cn/v/ac16768404) |
| 116 | [AMV 4K] 5 Years by Donya | bilibili | master_lens | hd1080 | 99s | 1920x1080 | 23.98 | 32.8MB | [BV1au4m1F7Hd](https://www.bilibili.com/video/BV1au4m1F7Hd) |
| 117 | [AMV] exhausted by Donya | bilibili | master_lens | hd720 | 90s | 1920x780 | 23.98 | 15.6MB | [BV1ZUY4zgEwV](https://www.bilibili.com/video/BV1ZUY4zgEwV) |
| 118 | LOL纸片人动画第四弹 | acfun | puppet | sd480 | 134s | 540x540 | 25 | 15.2MB | [ac11481099](https://www.acfun.cn/v/ac11481099) |
| 119 | 黑桃Q 翻到一张十年前光盘里的铃芽户缔MAD | acfun | creator_cn | hd1080 | 174s | 1920x1080 | 23.98 | 78.5MB | [ac41006908](https://www.acfun.cn/v/ac41006908) |
| 120 | mmd动画 金手环薇薇安，way back home | acfun | puppet | hd1080 | 66s | 1920x1080 | 30 | 19.7MB | [ac10868331](https://www.acfun.cn/v/ac10868331) |
| 121 | 东方MMD 美食动画 | acfun | puppet | hd1080 | 51s | 1920x1080 | 30 | 36.6MB | [ac19109991](https://www.acfun.cn/v/ac19109991) |
| 122 | 莫甘娜潘森---LOL纸片人动画 | acfun | puppet | hd1080 | 86s | 1920x1080 | 30 | 26.1MB | [ac11071665](https://www.acfun.cn/v/ac11071665) |
| 123 | School Days MAD - あなたが いない(당신이... 없어) In | acfun | authority | hd720 | 285s | 1280x720 | 26.5 | 26.1MB | [ac37390762](https://www.acfun.cn/v/ac37390762) |
| 124 | WASU_ART 2022年纸片人动画作品总结 | acfun | puppet | hd1080 | 120s | 1080x1080 | 30 | 39.6MB | [ac40955911](https://www.acfun.cn/v/ac40955911) |
| 125 | 水母妹妹画的纸片人真活了过来，为什么纸片人消失时她悲痛万分 | acfun | puppet | hd1080 | 130s | 1920x1080 | 60 | 91.7MB | [ac47155485](https://www.acfun.cn/v/ac47155485) |
| 126 | 转载 可动纸片人 请问，要和我一起画画嘛？ | acfun | puppet | hd720 | 47s | 1280x720 | 30 | 9.5MB | [ac34756526](https://www.acfun.cn/v/ac34756526) |
| 127 | mmd动画 新科娘和迪达拉，舞蹈Happy Halloween | acfun | puppet | hd1080 | 37s | 1920x1080 | 30 | 13.7MB | [ac11531930](https://www.acfun.cn/v/ac11531930) |
| 128 | mmd动画 新科娘和木糖纯，舞蹈白金disco | acfun | puppet | hd1080 | 88s | 1920x1080 | 30 | 34.7MB | [ac12205198](https://www.acfun.cn/v/ac12205198) |
| 129 | 转载 可动纸片人 旗袍Eyi | acfun | puppet | hd720 | 74s | 1280x720 | 30 | 11.1MB | [ac34756430](https://www.acfun.cn/v/ac34756430) |
| 130 | mmd动画 新科娘，学习春丽的功夫 | acfun | puppet | hd1080 | 80s | 1920x1080 | 30 | 22.5MB | [ac11839049](https://www.acfun.cn/v/ac11839049) |
| 131 | mmd动画 新科娘，panama | acfun | puppet | hd1080 | 130s | 1920x1080 | 30 | 50.3MB | [ac11363195](https://www.acfun.cn/v/ac11363195) |
| 132 | mmd动画 新科娘，lemon | acfun | puppet | hd1080 | 164s | 1920x1080 | 30 | 51.2MB | [ac11488141](https://www.acfun.cn/v/ac11488141) |
| 133 | mad 夏日幽灵 泛式 剪不断的回忆，那些我们未曾说出口的遗憾 | acfun | creator_cn | sd480 | 192s | 960x540 | 30 | 20.3MB | [ac46261490](https://www.acfun.cn/v/ac46261490) |
| 134 | Cyberpunk 2077 - Edgerunners - Lucy ⧸ Ne | bilibili | seed | hd1080 | 96s | 1920x1080 | 23.98 | 32.9MB | [BV188411b7W5](https://www.bilibili.com/video/BV188411b7W5) |
| 135 | My War x Levitating __ Attack on Titan「A | bilibili | seed | hd1080 | 180s | 1920x1080 | 25 | 51.4MB | [BV1bo4y1f7m4](https://www.bilibili.com/video/BV1bo4y1f7m4) |
| 136 | “在所有的道别里 我最喜欢「明天见」” | bilibili | seed | hd1080 | 99s | 1920x1080 | 25 | 13.4MB | [BV1MTyeBQE4T](https://www.bilibili.com/video/BV1MTyeBQE4T) |
| 137 | ⚠️好家伙！请别眨眼！感受极致踩点带来的天花板盛宴吧！！ | bilibili | seed | hd1080 | 142s | 1920x1080 | 23.98 | 31.0MB | [BV14EdpYsEbB](https://www.bilibili.com/video/BV14EdpYsEbB) |
| 138 | 『世界灿烂盛大，欢迎回家』 | bilibili | seed | hd1080 | 267s | 1920x1080 | 25 | 25.1MB | [BV1n34y1z7Ut](https://www.bilibili.com/video/BV1n34y1z7Ut) |
| 139 | 【火影忍者】高燃混剪战斗踩点无缝衔接4k | bilibili | seed | hd1080 | 190s | 1920x1080 | 30 | 70.2MB | [BV1bK4y1N7yn](https://www.bilibili.com/video/BV1bK4y1N7yn) |
| 140 | 【经典动画】热血燃向⧸高燃｜火影忍者鸣人vs佐助神级AMV，燃到头皮发麻 | bilibili | seed | hd1080 | 146s | 1920x1080 | 30 | 15.0MB | [BV1GMTc6GEfP](https://www.bilibili.com/video/BV1GMTc6GEfP) |
| 141 | 【𝗘𝗩𝗔⧸𝟲𝟬帧】“这就是我的人生，明日香！” | bilibili | seed | hd1080 | 118s | 1920x1080 | 30 | 13.3MB | [BV1qC4y1E7oU](https://www.bilibili.com/video/BV1qC4y1E7oU) |
| 142 | 别眨眼！这应该是你今年看过最爽视频之一！！ | bilibili | seed | hd1080 | 133s | 1920x1080 | 23.98 | 42.2MB | [BV1mL411x7HB](https://www.bilibili.com/video/BV1mL411x7HB) |
| 143 | 带好耳机！开始拔刀！超燃卡点！视觉盛宴！来袭！ #超然混剪 #动漫混剪 #动漫卡 | bilibili | seed | hd1080 | 152s | 1920x1080 | 30 | 57.0MB | [BV1pP42znEBU](https://www.bilibili.com/video/BV1pP42znEBU) |
| 144 | 混剪⧸动漫⧸高燃⧸踩点】超100部动漫超燃混剪！极致踩点！ | bilibili | seed | hd720 | 101s | 1920x864 | 30 | 11.9MB | [BV1LhMqzKE9h](https://www.bilibili.com/video/BV1LhMqzKE9h) |
| 145 | 𝙒𝙚 𝘼𝙧𝙚 众 神 归 位｜⚠️ 这才是世界的巅峰战力！！ | bilibili | seed | hd1080 | 176s | 1920x1080 | 30 | 39.9MB | [BV1Aq7EzQELW](https://www.bilibili.com/video/BV1Aq7EzQELW) |

## 复现

```bash
# 1a. 建 B站候选池（检索，只取元数据）
python scripts/collect_reference_candidates.py --per-query 20
# 1b. 建 AcFun 候选池（含 AKROSS Con 赛事作品）
python scripts/collect_acfun_candidates.py --per-query 30
# 2a. 下载 B站（分层抽样，含 412 风控退避重试）
python scripts/download_reference_set.py --target 60 --min-views 3000
# 2b. 下载 AcFun（赛事层优先）
python scripts/download_acfun_reference.py --target 20
# 3. 重建清单与本表
python scripts/build_reference_manifest.py
# 4. 逐部指标 + 分位数（并行，带缓存）
python scripts/reference_stats.py --refs data/reference_top \
    --mine output/unified_run61/polish/master_hr.mp4 --workers 6
```

## 已知限制

- 平台覆盖 B站 + AcFun 两家（YouTube/Niconico/Vimeo 无代理不可达，已实测）。
- 播放量为下载时快照，非持续追踪。
- 分层偏重燃向（burn 占比最高）；技术流层为空——B站/AcFun 该关键词域均为教程，
  需改用大师名定向搜索或人工投稿补齐。
- 逐部指标（beat_hit_rate / cut_visibility 等）由 `scripts/reference_stats.py` 计算，
  与旧 `score_reference_gap.py` 同源函数，但后者不输出分位数。
