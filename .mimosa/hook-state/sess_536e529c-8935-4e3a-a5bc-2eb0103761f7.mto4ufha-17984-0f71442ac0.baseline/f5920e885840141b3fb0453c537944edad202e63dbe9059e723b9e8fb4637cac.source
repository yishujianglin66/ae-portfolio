export interface Effect {
  id: string
  name: string
  category: string
  icon: string
  params: { name: string; value: number; min: number; max: number; unit: string }[]
}

export interface StyleTemplate {
  id: string
  name: string
  description: string
  thumbnail: string
  effects: string[]
  intensity: number
}

export interface Project {
  id: string
  name: string
  status: 'draft' | 'processing' | 'completed' | 'failed'
  createdAt: string
  duration: number
  sceneCount: number
}

export interface HistoryItem {
  id: string
  action: string
  timestamp: string
  result: 'success' | 'failure' | 'pending'
  details: string
}

export const mockEffects: Effect[] = [
  {
    id: 'ADBE Glo2',
    name: '发光',
    category: '视觉效果',
    icon: 'Sparkles',
    params: [
      { name: '发光半径', value: 20, min: 0, max: 100, unit: 'px' },
      { name: '发光强度', value: 0.8, min: 0, max: 2, unit: '' },
      { name: '发光颜色', value: 0.5, min: 0, max: 1, unit: '' },
    ],
  },
  {
    id: 'ADBE Blur',
    name: '模糊',
    category: '视觉效果',
    icon: 'Wind',
    params: [
      { name: '模糊量', value: 10, min: 0, max: 50, unit: 'px' },
      { name: '模糊类型', value: 1, min: 0, max: 3, unit: '' },
    ],
  },
  {
    id: 'ADBE Particular',
    name: '粒子',
    category: '特效',
    icon: 'CircleDot',
    params: [
      { name: '粒子数量', value: 100, min: 1, max: 1000, unit: '' },
      { name: '粒子大小', value: 5, min: 1, max: 50, unit: 'px' },
      { name: '发射速率', value: 10, min: 1, max: 100, unit: '/s' },
    ],
  },
  {
    id: 'ADBE Noise',
    name: '噪波',
    category: '视觉效果',
    icon: 'Zap',
    params: [
      { name: '噪波量', value: 20, min: 0, max: 100, unit: '%' },
      { name: '噪波类型', value: 0, min: 0, max: 2, unit: '' },
    ],
  },
  {
    id: 'ADBE Ramp',
    name: '渐变',
    category: '生成效果',
    icon: 'Layers',
    params: [
      { name: '起始颜色', value: 0, min: 0, max: 1, unit: '' },
      { name: '结束颜色', value: 1, min: 0, max: 1, unit: '' },
      { name: '渐变角度', value: 90, min: 0, max: 360, unit: '°' },
    ],
  },
]

export const mockStyleTemplates: StyleTemplate[] = [
  {
    id: 'cinematic',
    name: '电影感',
    description: '深邃的色彩分级和电影质感',
    thumbnail: 'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=cinematic%20dark%20moody%20film%20scene&image_size=square',
    effects: ['发光', '模糊', '渐变'],
    intensity: 0.8,
  },
  {
    id: 'cyberpunk',
    name: '赛博朋克',
    description: '霓虹灯光和未来感视觉效果',
    thumbnail: 'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=cyberpunk%20neon%20city%20night&image_size=square',
    effects: ['发光', '粒子', '渐变'],
    intensity: 1.0,
  },
  {
    id: 'minimal',
    name: '极简',
    description: '干净简洁的视觉风格',
    thumbnail: 'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=minimal%20clean%20white%20design&image_size=square',
    effects: ['模糊'],
    intensity: 0.3,
  },
  {
    id: 'vintage',
    name: '复古',
    description: '怀旧的复古胶片质感',
    thumbnail: 'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=vintage%20retro%20film%20photography&image_size=square',
    effects: ['噪波', '渐变'],
    intensity: 0.7,
  },
  {
    id: 'dreamy',
    name: '梦幻',
    description: '柔和梦幻的视觉效果',
    thumbnail: 'https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=dreamy%20soft%20pastel%20colors&image_size=square',
    effects: ['发光', '模糊'],
    intensity: 0.6,
  },
]

export const mockProjects: Project[] = [
  { id: '1', name: '产品宣传片', status: 'completed', createdAt: '2026-07-09', duration: 180, sceneCount: 5 },
  { id: '2', name: '抖音短视频', status: 'processing', createdAt: '2026-07-09', duration: 15, sceneCount: 3 },
  { id: '3', name: '婚礼集锦', status: 'draft', createdAt: '2026-07-08', duration: 600, sceneCount: 12 },
  { id: '4', name: '品牌广告', status: 'completed', createdAt: '2026-07-08', duration: 90, sceneCount: 4 },
  { id: '5', name: '教程视频', status: 'failed', createdAt: '2026-07-07', duration: 300, sceneCount: 8 },
]

export const mockHistory: HistoryItem[] = [
  { id: '1', action: '添加发光效果', timestamp: '2026-07-09 10:30', result: 'success', details: '图层: layer_001, 参数: 半径20px' },
  { id: '2', action: '应用电影感风格', timestamp: '2026-07-09 10:25', result: 'success', details: '效果: 发光+模糊+渐变' },
  { id: '3', action: '生成节拍动画', timestamp: '2026-07-09 10:20', result: 'pending', details: 'BPM: 120, 图层: layer_001' },
  { id: '4', action: '创建合成', timestamp: '2026-07-09 10:15', result: 'success', details: '尺寸: 1920x1080, 时长: 15s' },
  { id: '5', action: '导入素材', timestamp: '2026-07-09 10:10', result: 'failure', details: '文件不存在: video.mp4' },
]

export const intentTypes = [
  { type: 'ADD_EFFECT', label: '添加效果', icon: 'Plus' },
  { type: 'CREATE_ANIM', label: '创建动画', icon: 'Animation' },
  { type: 'ADJUST_PARAM', label: '调整参数', icon: 'Sliders' },
  { type: 'CREATE_LAYER', label: '创建图层', icon: 'Layers' },
  { type: 'STYLE_COMBO', label: '风格组合', icon: 'Palette' },
  { type: 'REVERSE_ANALYZE', label: '反向分析', icon: 'Search' },
]
