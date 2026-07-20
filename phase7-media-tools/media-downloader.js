/**
 * Phase7 - 媒体下载管理器
 * 
 * 集成 yt-dlp，支持从 1000+ 网站下载视频和音频
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const PathUtils = require('./path-utils');

class MediaDownloader {
    
    /**
     * 检查 yt-dlp 是否可用
     * @returns {Promise<boolean>} yt-dlp 是否可用
     */
    static async checkYtDlpAvailable() {
        return new Promise((resolve) => {
            try {
                const ytDlp = spawn('yt-dlp', ['--version']);
                ytDlp.on('exit', (code) => {
                    resolve(code === 0);
                });
                ytDlp.on('error', () => {
                    resolve(false);
                });
            } catch (e) {
                resolve(false);
            }
        });
    }
    
    /**
     * 从 URL 下载视频
     * @param {string} url - 视频 URL
     * @param {object} options - 下载选项
     * @param {string} options.outputDir - 输出目录
     * @param {string} options.quality - 质量 ('best', '720p', '1080p')
     * @returns {Promise<object>} 下载结果
     */
    static async downloadVideo(url, options = {}) {
        const outputDir = options.outputDir || PathUtils.getDownloadsDir();
        
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }
        
        const outputTemplate = path.join(outputDir, '%(title)s.%(ext)s');
        
        const args = [
            '-o', outputTemplate,
            '--no-playlist',
            '--no-write-comments',
            '--no-write-description',
            '--quiet',
            '--print', 'after_move:filepath',
            url
        ];
        
        if (options.quality && options.quality !== 'best') {
            if (options.quality === '720p') {
                args.push('-S', 'height:720');
            } else if (options.quality === '1080p') {
                args.push('-S', 'height:1080');
            }
        }
        
        return this._spawnYtDlp(args);
    }
    
    /**
     * 从 URL 提取并下载音频
     * @param {string} url - 视频 URL
     * @param {object} options - 下载选项
     * @param {string} options.outputDir - 输出目录
     * @param {string} options.format - 格式 ('mp3', 'm4a', 'wav')
     * @returns {Promise<object>} 下载结果
     */
    static async downloadAudio(url, options = {}) {
        const outputDir = options.outputDir || PathUtils.getDownloadsDir();
        
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }
        
        const format = options.format || 'mp3';
        const outputTemplate = path.join(outputDir, '%(title)s.%(ext)s');
        
        const args = [
            '-x',  // Extract audio only
            '--audio-format', format,
            '--audio-quality', '0', // Best quality
            '-o', outputTemplate,
            '--no-playlist',
            '--quiet',
            '--print', 'after_move:filepath',
            url
        ];
        
        return this._spawnYtDlp(args);
    }
    
    /**
     * 内部方法：执行 yt-dlp 并获取结果
     * @param {string[]} args - yt-dlp 参数
     * @returns {Promise<object>} 结果
     */
    static _spawnYtDlp(args) {
        return new Promise((resolve, reject) => {
            const ytDlp = spawn('yt-dlp', args);
            
            let stdout = '';
            let stderr = '';
            let outputPath = '';
            
            ytDlp.stdout.on('data', (data) => {
                stdout += data.toString();
                const lines = stdout.trim().split('\n');
                if (lines.length > 0) {
                    const lastLine = lines[lines.length - 1].trim();
                    if (lastLine) {
                        outputPath = lastLine;
                    }
                }
            });
            
            ytDlp.stderr.on('data', (data) => {
                stderr += data.toString();
            });
            
            ytDlp.on('exit', (code) => {
                if (code === 0 && outputPath) {
                    resolve({
                        success: true,
                        filePath: outputPath,
                        safePath: PathUtils.toExtendScriptPath(outputPath)
                    });
                } else {
                    reject(new Error(`yt-dlp failed (code ${code}): ${stderr || stdout}`));
                }
            });
            
            ytDlp.on('error', (err) => {
                reject(err);
            });
        });
    }
}

module.exports = MediaDownloader;
