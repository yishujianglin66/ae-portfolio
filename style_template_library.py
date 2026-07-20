STYLE_TEMPLATES = {
    "cinematic": {
        "name": "cinematic",
        "display_name": "电影感",
        "category": "电影风格",
        "description": "经典电影调色风格，高对比度、适度饱和度、暖色调倾向，营造胶片质感",
        "keywords": ["电影", "胶片", "高对比", "暖调", "质感"],
        "intensity_range": [0.2, 1.5],
        "effects": [
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {
                    "Brightness": 5.0,
                    "Contrast": 25.0,
                    "Use Legacy": False
                },
                "intensity_param": "Contrast",
                "intensity_factor": 40.0
            },
            {
                "effectName": "ADBE Color Balance",
                "settings": {
                    "Red Shadow Level": 5.0,
                    "Green Shadow Level": 2.0,
                    "Blue Shadow Level": -3.0,
                    "Red Midtone Level": 8.0,
                    "Green Midtone Level": 4.0,
                    "Blue Midtone Level": -5.0,
                    "Red Highlight Level": 3.0,
                    "Green Highlight Level": 2.0,
                    "Blue Highlight Level": -2.0,
                    "Preserve Luminosity": True
                },
                "intensity_param": "Red Midtone Level",
                "intensity_factor": 15.0
            },
            {
                "effectName": "ADBE Glo2",
                "settings": {
                    "Glow Threshold": 70.0,
                    "Glow Radius": 15.0,
                    "Glow Intensity": 0.8,
                    "Composite Original": "On Top",
                    "Glow Colors": "A & B Colors",
                    "Color Looping": "Sawtooth B>A",
                    "Color A": [1.0, 0.8, 0.5, 1.0],
                    "Color B": [1.0, 0.6, 0.3, 1.0]
                },
                "intensity_param": "Glow Intensity",
                "intensity_factor": 1.5
            }
        ]
    },
    "cyberpunk": {
        "name": "cyberpunk",
        "display_name": "赛博朋克",
        "category": "科幻风格",
        "description": "霓虹色彩、高对比度、蓝紫色调，未来科技感十足",
        "keywords": ["赛博朋克", "霓虹", "科幻", "蓝紫", "未来"],
        "intensity_range": [0.3, 2.0],
        "effects": [
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {
                    "Channel Control": "Master",
                    "Saturation": 25.0,
                    "Lightness": 0.0,
                    "Master Hue": -10.0
                },
                "intensity_param": "Saturation",
                "intensity_factor": 50.0
            },
            {
                "effectName": "ADBE Color Balance",
                "settings": {
                    "Red Shadow Level": -8.0,
                    "Green Shadow Level": 3.0,
                    "Blue Shadow Level": 15.0,
                    "Red Midtone Level": -12.0,
                    "Green Midtone Level": 5.0,
                    "Blue Midtone Level": 20.0,
                    "Red Highlight Level": -5.0,
                    "Green Highlight Level": 2.0,
                    "Blue Highlight Level": 10.0,
                    "Preserve Luminosity": True
                },
                "intensity_param": "Blue Midtone Level",
                "intensity_factor": 30.0
            },
            {
                "effectName": "ADBE Glo2",
                "settings": {
                    "Glow Threshold": 50.0,
                    "Glow Radius": 25.0,
                    "Glow Intensity": 1.2,
                    "Composite Original": "On Top",
                    "Glow Colors": "A & B Colors",
                    "Color Looping": "Triangle A>B",
                    "Color A": [0.3, 0.2, 1.0, 1.0],
                    "Color B": [1.0, 0.2, 0.8, 1.0]
                },
                "intensity_param": "Glow Intensity",
                "intensity_factor": 2.5
            }
        ]
    },
    "dreamy": {
        "name": "dreamy",
        "display_name": "梦幻",
        "category": "氛围风格",
        "description": "柔焦效果、低对比度、柔和色彩，营造梦幻朦胧的氛围",
        "keywords": ["梦幻", "朦胧", "柔焦", "柔和", "浪漫"],
        "intensity_range": [0.3, 1.8],
        "effects": [
            {
                "effectName": "ADBE Gaussian Blur 2",
                "settings": {
                    "Blurriness": 5.0,
                    "Blur Dimensions": "Horizontal and Vertical",
                    "Repeat Edge Pixels": True
                },
                "intensity_param": "Blurriness",
                "intensity_factor": 12.0
            },
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {
                    "Brightness": 10.0,
                    "Contrast": -15.0,
                    "Use Legacy": False
                },
                "intensity_param": "Brightness",
                "intensity_factor": 20.0
            },
            {
                "effectName": "ADBE Glo2",
                "settings": {
                    "Glow Threshold": 40.0,
                    "Glow Radius": 40.0,
                    "Glow Intensity": 0.6,
                    "Composite Original": "On Top",
                    "Glow Colors": "A & B Colors",
                    "Color Looping": "Sawtooth B>A",
                    "Color A": [1.0, 0.9, 0.95, 1.0],
                    "Color B": [0.9, 0.95, 1.0, 1.0]
                },
                "intensity_param": "Glow Intensity",
                "intensity_factor": 1.2
            }
        ]
    },
    "horror": {
        "name": "horror",
        "display_name": "恐怖",
        "category": "情绪风格",
        "description": "低饱和度、高对比度、暗调处理，营造惊悚压抑的氛围",
        "keywords": ["恐怖", "惊悚", "暗调", "压抑", "低饱和"],
        "intensity_range": [0.4, 2.0],
        "effects": [
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {
                    "Brightness": -15.0,
                    "Contrast": 30.0,
                    "Use Legacy": False
                },
                "intensity_param": "Contrast",
                "intensity_factor": 50.0
            },
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {
                    "Channel Control": "Master",
                    "Saturation": -30.0,
                    "Lightness": -10.0,
                    "Master Hue": 0.0
                },
                "intensity_param": "Saturation",
                "intensity_factor": -50.0
            },
            {
                "effectName": "ADBE Fractal Noise",
                "settings": {
                    "Fractal Type": "Cloudy",
                    "Noise Type": "Soft Linear",
                    "Contrast": 50.0,
                    "Brightness": -20.0,
                    "Overflow": "Clip",
                    "Transform Rotation": 0.0,
                    "Uniform Scaling": True,
                    "Scale": 200.0,
                    "Complexity": 5,
                    "Evolution": 0.0,
                    "Blending Mode": "Overlay"
                },
                "intensity_param": "Contrast",
                "intensity_factor": 80.0
            }
        ]
    },
    "vintage": {
        "name": "vintage",
        "display_name": "复古",
        "category": "怀旧风格",
        "description": "暖黄色调、颗粒质感、低对比度，模拟老电影胶片效果",
        "keywords": ["复古", "怀旧", "暖黄", "胶片", "颗粒"],
        "intensity_range": [0.3, 1.8],
        "effects": [
            {
                "effectName": "ADBE Color Balance",
                "settings": {
                    "Red Shadow Level": 10.0,
                    "Green Shadow Level": 5.0,
                    "Blue Shadow Level": -8.0,
                    "Red Midtone Level": 15.0,
                    "Green Midtone Level": 8.0,
                    "Blue Midtone Level": -12.0,
                    "Red Highlight Level": 8.0,
                    "Green Highlight Level": 5.0,
                    "Blue Highlight Level": -6.0,
                    "Preserve Luminosity": True
                },
                "intensity_param": "Red Midtone Level",
                "intensity_factor": 25.0
            },
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {
                    "Brightness": 5.0,
                    "Contrast": -10.0,
                    "Use Legacy": False
                },
                "intensity_param": "Contrast",
                "intensity_factor": -20.0
            },
            {
                "effectName": "ADBE Fractal Noise",
                "settings": {
                    "Fractal Type": "Turbulent Basic",
                    "Noise Type": "Spline",
                    "Contrast": 30.0,
                    "Brightness": -10.0,
                    "Overflow": "Clip",
                    "Transform Rotation": 0.0,
                    "Uniform Scaling": True,
                    "Scale": 300.0,
                    "Complexity": 3,
                    "Evolution": 0.0,
                    "Blending Mode": "Soft Light"
                },
                "intensity_param": "Contrast",
                "intensity_factor": 50.0
            }
        ]
    },
    "neon": {
        "name": "neon",
        "display_name": "霓虹",
        "category": "光效风格",
        "description": "强烈发光效果、高饱和度、霓虹色彩，营造赛博朋克的光感",
        "keywords": ["霓虹", "发光", "高饱和", "光效", "炫彩"],
        "intensity_range": [0.4, 2.5],
        "effects": [
            {
                "effectName": "ADBE Glo2",
                "settings": {
                    "Glow Threshold": 30.0,
                    "Glow Radius": 30.0,
                    "Glow Intensity": 1.5,
                    "Composite Original": "On Top",
                    "Glow Colors": "A & B Colors",
                    "Color Looping": "Triangle A>B",
                    "Color A": [0.0, 1.0, 1.0, 1.0],
                    "Color B": [1.0, 0.0, 1.0, 1.0]
                },
                "intensity_param": "Glow Intensity",
                "intensity_factor": 3.0
            },
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {
                    "Channel Control": "Master",
                    "Saturation": 30.0,
                    "Lightness": 5.0,
                    "Master Hue": 0.0
                },
                "intensity_param": "Saturation",
                "intensity_factor": 60.0
            }
        ]
    },
    "minimal": {
        "name": "minimal",
        "display_name": "极简",
        "category": "简约风格",
        "description": "低饱和度、柔和色调、干净简洁，追求极简主义美学",
        "keywords": ["极简", "简约", "干净", "低饱和", "柔和"],
        "intensity_range": [0.2, 1.2],
        "effects": [
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {
                    "Channel Control": "Master",
                    "Saturation": -20.0,
                    "Lightness": 5.0,
                    "Master Hue": 0.0
                },
                "intensity_param": "Saturation",
                "intensity_factor": -35.0
            },
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {
                    "Brightness": 8.0,
                    "Contrast": -5.0,
                    "Use Legacy": False
                },
                "intensity_param": "Brightness",
                "intensity_factor": 15.0
            }
        ]
    },
    "drama": {
        "name": "drama",
        "display_name": "戏剧性",
        "category": "情绪风格",
        "description": "高对比度、深阴影、强反差，营造戏剧性张力",
        "keywords": ["戏剧", "高对比", "阴影", "张力", "强烈"],
        "intensity_range": [0.4, 2.0],
        "effects": [
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {
                    "Brightness": -5.0,
                    "Contrast": 40.0,
                    "Use Legacy": False
                },
                "intensity_param": "Contrast",
                "intensity_factor": 60.0
            },
            {
                "effectName": "ADBE Color Balance",
                "settings": {
                    "Red Shadow Level": -3.0,
                    "Green Shadow Level": -5.0,
                    "Blue Shadow Level": -8.0,
                    "Red Midtone Level": 3.0,
                    "Green Midtone Level": 0.0,
                    "Blue Midtone Level": -5.0,
                    "Red Highlight Level": 5.0,
                    "Green Highlight Level": 3.0,
                    "Blue Highlight Level": 0.0,
                    "Preserve Luminosity": True
                },
                "intensity_param": "Red Highlight Level",
                "intensity_factor": 10.0
            }
        ]
    },
    "warm": {
        "name": "warm",
        "display_name": "暖色调",
        "category": "色彩风格",
        "description": "橙红暖调、温馨舒适，营造温暖治愈的视觉感受",
        "keywords": ["暖色", "橙红", "温馨", "治愈", "阳光"],
        "intensity_range": [0.3, 1.8],
        "effects": [
            {
                "effectName": "ADBE Color Balance",
                "settings": {
                    "Red Shadow Level": 8.0,
                    "Green Shadow Level": 4.0,
                    "Blue Shadow Level": -6.0,
                    "Red Midtone Level": 12.0,
                    "Green Midtone Level": 6.0,
                    "Blue Midtone Level": -10.0,
                    "Red Highlight Level": 6.0,
                    "Green Highlight Level": 4.0,
                    "Blue Highlight Level": -4.0,
                    "Preserve Luminosity": True
                },
                "intensity_param": "Red Midtone Level",
                "intensity_factor": 20.0
            },
            {
                "effectName": "ADBE Glo2",
                "settings": {
                    "Glow Threshold": 60.0,
                    "Glow Radius": 20.0,
                    "Glow Intensity": 0.5,
                    "Composite Original": "On Top",
                    "Glow Colors": "A & B Colors",
                    "Color Looping": "Sawtooth B>A",
                    "Color A": [1.0, 0.85, 0.6, 1.0],
                    "Color B": [1.0, 0.7, 0.4, 1.0]
                },
                "intensity_param": "Glow Intensity",
                "intensity_factor": 1.0
            }
        ]
    },
    "cool": {
        "name": "cool",
        "display_name": "冷色调",
        "category": "色彩风格",
        "description": "蓝青冷调、清冷干净，营造冷静理性的视觉感受",
        "keywords": ["冷色", "蓝青", "清冷", "冷静", "干净"],
        "intensity_range": [0.3, 1.8],
        "effects": [
            {
                "effectName": "ADBE Color Balance",
                "settings": {
                    "Red Shadow Level": -8.0,
                    "Green Shadow Level": 2.0,
                    "Blue Shadow Level": 10.0,
                    "Red Midtone Level": -10.0,
                    "Green Midtone Level": 3.0,
                    "Blue Midtone Level": 15.0,
                    "Red Highlight Level": -5.0,
                    "Green Highlight Level": 2.0,
                    "Blue Highlight Level": 8.0,
                    "Preserve Luminosity": True
                },
                "intensity_param": "Blue Midtone Level",
                "intensity_factor": 25.0
            },
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {
                    "Brightness": 3.0,
                    "Contrast": 10.0,
                    "Use Legacy": False
                },
                "intensity_param": "Contrast",
                "intensity_factor": 20.0
            }
        ]
    },
    "grunge": {
        "name": "grunge",
        "display_name": "脏污油渍",
        "category": "质感风格",
        "description": "高对比度、杂色颗粒、低饱和度，营造粗糙破旧的质感",
        "keywords": ["脏污", "油渍", "颗粒", "粗糙", "破旧"],
        "intensity_range": [0.4, 2.0],
        "effects": [
            {
                "effectName": "ADBE Fractal Noise",
                "settings": {
                    "Fractal Type": "Turbulent Sharp",
                    "Noise Type": "Soft Linear",
                    "Contrast": 60.0,
                    "Brightness": -30.0,
                    "Overflow": "Clip",
                    "Transform Rotation": 0.0,
                    "Uniform Scaling": True,
                    "Scale": 150.0,
                    "Complexity": 6,
                    "Evolution": 0.0,
                    "Blending Mode": "Overlay"
                },
                "intensity_param": "Contrast",
                "intensity_factor": 90.0
            },
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {
                    "Brightness": -10.0,
                    "Contrast": 35.0,
                    "Use Legacy": False
                },
                "intensity_param": "Contrast",
                "intensity_factor": 55.0
            },
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {
                    "Channel Control": "Master",
                    "Saturation": -25.0,
                    "Lightness": -5.0,
                    "Master Hue": 0.0
                },
                "intensity_param": "Saturation",
                "intensity_factor": -45.0
            }
        ]
    },
    "soft_glow": {
        "name": "soft_glow",
        "display_name": "柔光",
        "category": "光效风格",
        "description": "柔和发光、暖调倾向、朦胧美感，营造温柔梦幻的氛围",
        "keywords": ["柔光", "发光", "温柔", "梦幻", "暖调"],
        "intensity_range": [0.3, 2.0],
        "effects": [
            {
                "effectName": "ADBE Glo2",
                "settings": {
                    "Glow Threshold": 45.0,
                    "Glow Radius": 35.0,
                    "Glow Intensity": 0.9,
                    "Composite Original": "On Top",
                    "Glow Colors": "A & B Colors",
                    "Color Looping": "Sawtooth B>A",
                    "Color A": [1.0, 0.95, 0.85, 1.0],
                    "Color B": [1.0, 0.85, 0.7, 1.0]
                },
                "intensity_param": "Glow Intensity",
                "intensity_factor": 1.8
            },
            {
                "effectName": "ADBE Gaussian Blur 2",
                "settings": {
                    "Blurriness": 3.0,
                    "Blur Dimensions": "Horizontal and Vertical",
                    "Repeat Edge Pixels": True
                },
                "intensity_param": "Blurriness",
                "intensity_factor": 8.0
            },
            {
                "effectName": "ADBE Color Balance",
                "settings": {
                    "Red Shadow Level": 5.0,
                    "Green Shadow Level": 3.0,
                    "Blue Shadow Level": -2.0,
                    "Red Midtone Level": 8.0,
                    "Green Midtone Level": 5.0,
                    "Blue Midtone Level": -4.0,
                    "Red Highlight Level": 4.0,
                    "Green Highlight Level": 3.0,
                    "Blue Highlight Level": -2.0,
                    "Preserve Luminosity": True
                },
                "intensity_param": "Red Midtone Level",
                "intensity_factor": 12.0
            }
        ]
    },
    "high_energy": {
        "name": "high_energy",
        "display_name": "高能",
        "category": "情绪风格",
        "description": "高饱和度、高对比度、强烈色彩冲击，充满活力与能量",
        "keywords": ["高能", "活力", "高饱和", "强烈", "冲击"],
        "intensity_range": [0.4, 2.5],
        "effects": [
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {
                    "Channel Control": "Master",
                    "Saturation": 35.0,
                    "Lightness": 5.0,
                    "Master Hue": 0.0
                },
                "intensity_param": "Saturation",
                "intensity_factor": 70.0
            },
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {
                    "Brightness": 5.0,
                    "Contrast": 30.0,
                    "Use Legacy": False
                },
                "intensity_param": "Contrast",
                "intensity_factor": 50.0
            },
            {
                "effectName": "ADBE Glo2",
                "settings": {
                    "Glow Threshold": 55.0,
                    "Glow Radius": 20.0,
                    "Glow Intensity": 1.0,
                    "Composite Original": "On Top",
                    "Glow Colors": "A & B Colors",
                    "Color Looping": "Triangle A>B",
                    "Color A": [1.0, 0.5, 0.2, 1.0],
                    "Color B": [0.2, 0.7, 1.0, 1.0]
                },
                "intensity_param": "Glow Intensity",
                "intensity_factor": 2.0
            }
        ]
    },
    "noir": {
        "name": "noir",
        "display_name": "黑色电影",
        "category": "电影风格",
        "description": "黑白效果、高对比度、硬阴影，经典黑色电影风格",
        "keywords": ["黑色电影", "黑白", "硬阴影", "经典", "悬疑"],
        "intensity_range": [0.4, 2.0],
        "effects": [
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {
                    "Channel Control": "Master",
                    "Saturation": -100.0,
                    "Lightness": 0.0,
                    "Master Hue": 0.0
                },
                "intensity_param": "Saturation",
                "intensity_factor": -100.0
            },
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {
                    "Brightness": -8.0,
                    "Contrast": 45.0,
                    "Use Legacy": False
                },
                "intensity_param": "Contrast",
                "intensity_factor": 70.0
            },
            {
                "effectName": "ADBE Fractal Noise",
                "settings": {
                    "Fractal Type": "Cloudy",
                    "Noise Type": "Soft Linear",
                    "Contrast": 20.0,
                    "Brightness": -15.0,
                    "Overflow": "Clip",
                    "Transform Rotation": 0.0,
                    "Uniform Scaling": True,
                    "Scale": 250.0,
                    "Complexity": 4,
                    "Evolution": 0.0,
                    "Blending Mode": "Soft Light"
                },
                "intensity_param": "Contrast",
                "intensity_factor": 40.0
            }
        ]
    },
    "pastel": {
        "name": "pastel",
        "display_name": "马卡龙",
        "category": "色彩风格",
        "description": "低饱和度、柔和粉彩色、明亮清新，甜美可爱的视觉风格",
        "keywords": ["马卡龙", "粉彩", "甜美", "清新", "柔和"],
        "intensity_range": [0.3, 1.5],
        "effects": [
            {
                "effectName": "ADBE HUE SATURATION",
                "settings": {
                    "Channel Control": "Master",
                    "Saturation": -15.0,
                    "Lightness": 15.0,
                    "Master Hue": 0.0
                },
                "intensity_param": "Lightness",
                "intensity_factor": 25.0
            },
            {
                "effectName": "ADBE Brightness & Contrast 2",
                "settings": {
                    "Brightness": 12.0,
                    "Contrast": -15.0,
                    "Use Legacy": False
                },
                "intensity_param": "Brightness",
                "intensity_factor": 20.0
            },
            {
                "effectName": "ADBE Glo2",
                "settings": {
                    "Glow Threshold": 50.0,
                    "Glow Radius": 25.0,
                    "Glow Intensity": 0.4,
                    "Composite Original": "On Top",
                    "Glow Colors": "A & B Colors",
                    "Color Looping": "Sawtooth B>A",
                    "Color A": [1.0, 0.9, 0.95, 1.0],
                    "Color B": [0.95, 0.9, 1.0, 1.0]
                },
                "intensity_param": "Glow Intensity",
                "intensity_factor": 0.8
            }
        ]
    }
}
