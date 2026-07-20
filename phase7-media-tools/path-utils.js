/**
 * Phase7 - 路径处理工具类
 * 
 * 解决 Windows 路径转义、反斜杠转换等问题
 * 确保 ExtendScript (AE) 正确读取路径
 */

const os = require('os');
const path = require('path');
const fs = require('fs');

// B07 修复：统一配置读取，与 Python 侧 media-config.json 保持一致
const CONFIG_PATH = path.join(__dirname, '..', 'config', 'media-config.json');
let _config = null;

function _loadConfig() {
    if (_config) return _config;
    try {
        if (fs.existsSync(CONFIG_PATH)) {
            const raw = fs.readFileSync(CONFIG_PATH, 'utf-8');
            _config = JSON.parse(raw);
            // 解析相对路径（基于项目根目录）
            const projectRoot = path.resolve(__dirname, '..');
            if (_config.directories) {
                for (const key of Object.keys(_config.directories)) {
                    const val = _config.directories[key];
                    if (typeof val === 'string' && (val.startsWith('./') || val.startsWith('.\\'))) {
                        _config.directories[key] = path.resolve(projectRoot, val.substring(2));
                    }
                }
            }
            return _config;
        }
    } catch (e) {
        // 配置加载失败时回退到默认值
    }
    _config = {};
    return _config;
}

class PathUtils {
    
    /**
     * 将 Windows 路径转换为 ExtendScript 安全的路径
     * 使用正斜杠，避免转义问题
     * @param {string} winPath - Windows 路径（可能有反斜杠）
     * @returns {string} ExtendScript 安全路径
     */
    static toExtendScriptPath(winPath) {
        if (!winPath) return '';
        
        // 先规范化路径
        let normalized = path.normalize(winPath);
        
        // 所有反斜杠替换为正斜杠
        normalized = normalized.replace(/\\/g, '/');
        
        return normalized;
    }
    
    /**
     * 获取项目根目录下的素材目录
     * @param {string} subDir - 子目录名（可选）
     * @returns {string} 素材目录的完整路径
     */
    static getMediaDir(subDir = null) {
        const config = _loadConfig();
        const projectRoot = path.resolve(__dirname, '..');
        let mediaDir;
        
        // 优先使用 media-config.json 中的配置
        if (config.directories && config.directories.video_library) {
            mediaDir = config.directories.video_library;
        } else {
            // 回退：使用项目根目录下的默认路径
            mediaDir = path.join(projectRoot, '05-测试套件', 'test_resources');
        }
        
        if (subDir) {
            mediaDir = path.join(mediaDir, subDir);
        }
        
        // 确保目录存在
        if (!fs.existsSync(mediaDir)) {
            fs.mkdirSync(mediaDir, { recursive: true });
        }
        
        return PathUtils.toExtendScriptPath(mediaDir);
    }
    
    /**
     * 获取用户下载目录
     * @returns {string} 用户下载目录路径
     */
    static getDownloadsDir() {
        const config = _loadConfig();
        let downloadsDir;
        
        // 优先使用 media-config.json 中的配置
        if (config.directories && config.directories.download_temp) {
            downloadsDir = config.directories.download_temp;
        } else {
            // 回退：使用用户下载目录
            downloadsDir = path.join(os.homedir(), 'Downloads');
        }
        
        return PathUtils.toExtendScriptPath(downloadsDir);
    }
    
    /**
     * 生成带时间戳的安全文件名
     * @param {string} prefix - 文件名前缀
     * @param {string} extension - 文件扩展名（含点，如 .mp4）
     * @returns {string} 安全文件名
     */
    static generateSafeFilename(prefix, extension) {
        const timestamp = new Date().toISOString()
            .replace(/[:.]/g, '-')
            .replace(/T/, '_')
            .substring(0, 19);
        
        return `${prefix}_${timestamp}${extension}`;
    }
    
    /**
     * 检查文件是否存在（跨平台安全）
     * @param {string} filePath - 文件路径
     * @returns {boolean} 文件是否存在
     */
    static fileExists(filePath) {
        const fs = require('fs');
        return fs.existsSync(filePath);
    }
}

module.exports = PathUtils;
