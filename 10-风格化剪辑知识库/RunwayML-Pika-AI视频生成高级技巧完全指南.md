# RunwayML/Pika AI视频生成高级技巧完全指南

---

## 一、提示词工程

### 1.1 提示词结构

```
提示词结构：
[主题描述] + [风格指定] + [技术参数] + [视觉元素] + [情绪氛围]

示例：
"一个赛博朋克风格的未来城市夜景，霓虹灯光闪烁，飞行汽车在空中穿梭，
高楼大厦林立，下雨天气，镜头缓慢移动，8K分辨率，电影质感，
科幻风格，Blade Runner风格，冷色调，高对比度"
```

### 1.2 提示词要素

| 要素类型 | 示例 | 作用 |
|---------|------|------|
| **主体** | "一只猫" | 指定生成主体 |
| **动作** | "正在奔跑" | 指定动作状态 |
| **环境** | "在森林中" | 指定场景 |
| **风格** | "宫崎骏风格" | 指定艺术风格 |
| **构图** | "特写镜头" | 指定镜头角度 |
| **光影** | "金色夕阳" | 指定光线条件 |
| **色彩** | "暖色调" | 指定色彩风格 |
| **画质** | "8K超高清" | 指定画质要求 |

---

## 二、风格化技巧

### 2.1 艺术风格转换

```python
# 使用Runway API进行风格转换
import requests

def style_transfer(image_path, style_prompt, output_path):
    url = "https://api.runwayml.com/v1/generate"
    
    payload = {
        "input": {
            "image": open(image_path, "rb").read(),
            "style": style_prompt
        },
        "model": "style-transfer-v1"
    }
    
    response = requests.post(url, files=payload, headers={
        "Authorization": "Bearer YOUR_API_KEY"
    })
    
    with open(output_path, "wb") as f:
        f.write(response.content)
```

### 2.2 风格关键词库

| 风格类型 | 关键词 | 效果 |
|---------|-------|------|
| **电影风格** | cinematic, film grain, movie quality | 电影质感 |
| **动画风格** | anime, cartoon, studio ghibli | 动漫风格 |
| **油画风格** | oil painting, impressionism | 油画质感 |
| **像素风格** | pixel art, 8-bit, retro game | 像素风 |
| **赛博朋克** | cyberpunk, neon, futuristic | 赛博朋克 |
| **蒸汽朋克** | steampunk, Victorian, gears | 蒸汽朋克 |
| **极简主义** | minimalist, clean, simple | 极简风格 |
| **超现实** | surreal, dreamlike, fantasy | 超现实 |

---

## 三、视频生成参数

### 3.1 Runway参数设置

```python
# Runway Gen-2 API参数
def generate_video(prompt, duration=5, resolution="1080p", fps=24):
    url = "https://api.runwayml.com/v1/generate"
    
    payload = {
        "input": {
            "prompt": prompt,
            "duration": duration,
            "resolution": resolution,
            "fps": fps
        },
        "model": "gen-2",
        "output_format": "mp4"
    }
    
    response = requests.post(url, json=payload, headers={
        "Authorization": "Bearer YOUR_API_KEY"
    })
    
    return response.json()
```

### 3.2 关键参数说明

| 参数 | 选项 | 说明 |
|------|------|------|
| **duration** | 1-10秒 | 视频时长 |
| **resolution** | 720p/1080p/4K | 分辨率 |
| **fps** | 12/24/30 | 帧率 |
| **style** | 预设风格 | 艺术风格 |
| **seed** | 数字 | 随机种子 |
| **cfg_scale** | 1-20 | 提示词权重 |

---

## 四、一致性控制

### 4.1 角色一致性

```python
# 使用参考图保持角色一致性
def generate_consistent_video(prompt, reference_image, duration=5):
    url = "https://api.runwayml.com/v1/generate"
    
    payload = {
        "input": {
            "prompt": prompt,
            "reference_image": open(reference_image, "rb").read(),
            "duration": duration,
            "consistency": "high"
        },
        "model": "gen-2"
    }
    
    response = requests.post(url, files=payload, headers={
        "Authorization": "Bearer YOUR_API_KEY"
    })
    
    return response.json()
```

### 4.2 场景一致性技巧

| 方法 | 说明 | 适用场景 |
|------|------|---------|
| **参考图** | 使用同一参考图 | 角色/物体保持一致 |
| **风格提示词** | 固定风格关键词 | 整体风格统一 |
| **场景描述** | 详细场景描述 | 背景保持一致 |
| **镜头控制** | 固定镜头角度 | 视角保持一致 |

---

## 五、视频编辑功能

### 5.1 视频扩展

```python
# 扩展视频时长
def extend_video(video_path, additional_prompt, additional_duration):
    url = "https://api.runwayml.com/v1/extend"
    
    payload = {
        "input": {
            "video": open(video_path, "rb").read(),
            "prompt": additional_prompt,
            "duration": additional_duration
        },
        "model": "gen-2"
    }
    
    response = requests.post(url, files=payload, headers={
        "Authorization": "Bearer YOUR_API_KEY"
    })
    
    return response.json()
```

### 5.2 视频风格化

```python
# 视频风格转换
def stylize_video(video_path, style_prompt):
    url = "https://api.runwayml.com/v1/stylize"
    
    payload = {
        "input": {
            "video": open(video_path, "rb").read(),
            "style": style_prompt
        },
        "model": "style-transfer-v1"
    }
    
    response = requests.post(url, files=payload, headers={
        "Authorization": "Bearer YOUR_API_KEY"
    })
    
    return response.json()
```

---

## 六、Pika生成技巧

### 6.1 Pika提示词优化

```
Pika提示词特点：
- 更偏向简洁
- 强调动作和动态
- 支持中文提示词

示例：
"一只小猫在草地上追逐蝴蝶，阳光明媚，春天，温馨治愈"
```

### 6.2 Pika风格参数

| 参数 | 选项 | 效果 |
|------|------|------|
| **style** | cinematic | 电影质感 |
| **style** | anime | 动漫风格 |
| **style** | 3d | 3D风格 |
| **style** | pixel | 像素风格 |
| **style** | watercolor | 水彩风格 |
| **style** | oil | 油画风格 |

---

## 七、工作流集成

### 7.1 AE工作流集成

```python
# AE + Runway工作流
def ae_runway_workflow(project_path, prompt):
    # 1. 生成AI视频
    video_path = generate_video(prompt)
    
    # 2. 导入AE
    import_after_effects(video_path, project_path)
    
    # 3. 添加效果
    apply_effects(project_path)
    
    # 4. 渲染输出
    render_project(project_path)
```

### 7.2 Premiere工作流集成

```python
# Premiere + Runway工作流
def premiere_runway_workflow(project_path, prompts):
    # 1. 批量生成视频
    video_paths = [generate_video(p) for p in prompts]
    
    # 2. 导入Premiere
    import_premiere(video_paths, project_path)
    
    # 3. 剪辑拼接
    edit_timeline(project_path)
    
    # 4. 添加音频
    add_audio(project_path)
    
    # 5. 导出
    export_video(project_path)
```

---

## 八、提示词模板库

### 8.1 场景模板

```python
# 场景模板库
SCENE_TEMPLATES = {
    "cyberpunk_city": {
        "prompt": "赛博朋克风格的未来城市夜景，霓虹灯光，飞行汽车，高楼大厦，下雨，8K",
        "duration": 5,
        "style": "cinematic"
    },
    "fantasy_forest": {
        "prompt": "魔幻风格的森林，发光的植物，小精灵，阳光透过树叶，梦幻氛围，4K",
        "duration": 5,
        "style": "anime"
    },
    "space_exploration": {
        "prompt": "太空探索场景，宇航员在星球表面，星空背景，科幻风格，8K",
        "duration": 5,
        "style": "cinematic"
    }
}
```

### 8.2 角色模板

```python
# 角色模板库
CHARACTER_TEMPLATES = {
    "cute_cat": {
        "prompt": "一只可爱的橘猫，毛茸茸的，大眼睛，温馨背景，治愈风格",
        "style": "anime"
    },
    "robot": {
        "prompt": "未来感机器人，金属质感，发光眼睛，高科技背景，科幻风格",
        "style": "3d"
    },
    "warrior": {
        "prompt": "中世纪骑士，盔甲，宝剑，城堡背景，史诗风格",
        "style": "cinematic"
    }
}
```

---

## 九、批量生成与管理

### 9.1 批量生成

```python
# 批量生成脚本
def batch_generate(prompts, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    
    for i, prompt in enumerate(prompts):
        result = generate_video(prompt)
        video_path = os.path.join(output_folder, f"video_{i+1}.mp4")
        
        with open(video_path, "wb") as f:
            f.write(result.content)
```

### 9.2 生成结果管理

```python
# 生成结果管理类
class GenerationManager:
    def __init__(self, output_folder="generations"):
        self.output_folder = output_folder
        os.makedirs(output_folder, exist_ok=True)
    
    def generate(self, prompt, name=None):
        result = generate_video(prompt)
        
        if name:
            filename = f"{name}.mp4"
        else:
            filename = f"{int(time.time())}.mp4"
        
        filepath = os.path.join(self.output_folder, filename)
        
        with open(filepath, "wb") as f:
            f.write(result.content)
        
        return filepath
    
    def list_generations(self):
        return os.listdir(self.output_folder)
    
    def get_generation(self, filename):
        return os.path.join(self.output_folder, filename)
```

---

## 十、高级技巧

### 10.1 提示词迭代优化

```python
# 提示词迭代优化
def optimize_prompt(initial_prompt, feedback):
    improvements = {
        "more details": "添加详细描述",
        "better quality": "添加8K/超高清关键词",
        "different style": "更换风格关键词",
        "faster": "缩短时长",
        "slower": "增加时长"
    }
    
    optimized_prompt = initial_prompt
    
    for key, value in feedback.items():
        if key in improvements:
            optimized_prompt += f", {improvements[key]}"
    
    return optimized_prompt
```

### 10.2 多模态输入

```python
# 多模态输入生成
def multimodal_generate(image_path, audio_path, text_prompt):
    url = "https://api.runwayml.com/v1/generate"
    
    payload = {
        "input": {
            "image": open(image_path, "rb").read(),
            "audio": open(audio_path, "rb").read(),
            "prompt": text_prompt
        },
        "model": "gen-2"
    }
    
    response = requests.post(url, files=payload, headers={
        "Authorization": "Bearer YOUR_API_KEY"
    })
    
    return response.json()
```

---

> **关联文档**：
> - [[RunwayML-Pika-核心功能完全指南]]
> - [[RunwayML-Pika-企业级集成指南]]
> - [[Phase3-风格化合成全链路技术详解]]