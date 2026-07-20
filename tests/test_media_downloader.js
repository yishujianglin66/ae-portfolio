/**
 * media-downloader.js 单元测试
 * 覆盖: downloadVideo, downloadAudio 的参数构建逻辑
 *
 * 关注点: quality→args 与 format→args 的映射是下载成功的关键，
 * 错误的参数会导致静默下载失败或错误质量/格式。通过 mock _spawnYtDlp
 * 捕获参数，确保参数构建逻辑正确，不依赖真实 yt-dlp / 网络。
 */

const assert = require('assert');
const path = require('path');
const os = require('os');

const projectRoot = path.dirname(__dirname);
const MediaDownloader = require(path.join(projectRoot, 'phase7-media-tools', 'media-downloader.js'));
const PathUtils = require(path.join(projectRoot, 'phase7-media-tools', 'path-utils.js'));

let passed = 0;
let failed = 0;

async function testAsync(name, fn) {
    try {
        await fn();
        passed++;
        console.log(`  ✓ ${name}`);
    } catch (e) {
        failed++;
        console.log(`  ✗ ${name}: ${e.message}`);
    }
}

// 使用已存在的临时目录，避免触发 mkdirSync
const EXISTING_DIR = os.tmpdir();
const TEST_URL = 'https://www.youtube.com/watch?v=test123';

/**
 * mock _spawnYtDlp，捕获参数并返回可控结果。
 * 返回 { capturedArgs, restore } 用于断言与恢复。
 */
function mockSpawn(resolvedValue) {
    const captured = { args: null, callCount: 0 };
    const original = MediaDownloader._spawnYtDlp;
    MediaDownloader._spawnYtDlp = function (args) {
        captured.args = args;
        captured.callCount++;
        return Promise.resolve(resolvedValue);
    };
    return {
        captured,
        restore: () => { MediaDownloader._spawnYtDlp = original; },
    };
}

(async () => {

// ============================================================================
// 1. downloadVideo - 参数构建
// ============================================================================
console.log('\n=== downloadVideo 参数构建 ===');

await testAsync('默认质量不添加 -S 参数', async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/v.mp4', safePath: '/tmp/v.mp4' });
    try {
        await MediaDownloader.downloadVideo(TEST_URL, { outputDir: EXISTING_DIR });
        assert.strictEqual(m.captured.callCount, 1, '应调用 _spawnYtDlp 一次');
        assert.ok(!m.captured.args.includes('-S'), '默认质量不应含 -S');
    } finally { m.restore(); }
});

await testAsync("quality='best' 不添加 -S 参数", async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/v.mp4', safePath: '/tmp/v.mp4' });
    try {
        await MediaDownloader.downloadVideo(TEST_URL, { outputDir: EXISTING_DIR, quality: 'best' });
        assert.ok(!m.captured.args.includes('-S'), "best 不应含 -S");
    } finally { m.restore(); }
});

await testAsync("quality='720p' 添加 -S height:720", async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/v.mp4', safePath: '/tmp/v.mp4' });
    try {
        await MediaDownloader.downloadVideo(TEST_URL, { outputDir: EXISTING_DIR, quality: '720p' });
        const args = m.captured.args;
        const idx = args.indexOf('-S');
        assert.ok(idx !== -1, '应包含 -S');
        assert.strictEqual(args[idx + 1], 'height:720', '-S 后应为 height:720');
    } finally { m.restore(); }
});

await testAsync("quality='1080p' 添加 -S height:1080", async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/v.mp4', safePath: '/tmp/v.mp4' });
    try {
        await MediaDownloader.downloadVideo(TEST_URL, { outputDir: EXISTING_DIR, quality: '1080p' });
        const args = m.captured.args;
        const idx = args.indexOf('-S');
        assert.ok(idx !== -1, '应包含 -S');
        assert.strictEqual(args[idx + 1], 'height:1080', '-S 后应为 height:1080');
    } finally { m.restore(); }
});

await testAsync('URL 作为最后一个参数', async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/v.mp4', safePath: '/tmp/v.mp4' });
    try {
        await MediaDownloader.downloadVideo(TEST_URL, { outputDir: EXISTING_DIR });
        const args = m.captured.args;
        assert.strictEqual(args[args.length - 1], TEST_URL, 'URL 应在参数末尾');
    } finally { m.restore(); }
});

await testAsync('包含 --no-playlist 参数', async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/v.mp4', safePath: '/tmp/v.mp4' });
    try {
        await MediaDownloader.downloadVideo(TEST_URL, { outputDir: EXISTING_DIR });
        assert.ok(m.captured.args.includes('--no-playlist'), '应含 --no-playlist');
    } finally { m.restore(); }
});

await testAsync('包含 -o 输出模板参数', async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/v.mp4', safePath: '/tmp/v.mp4' });
    try {
        await MediaDownloader.downloadVideo(TEST_URL, { outputDir: EXISTING_DIR });
        const idx = m.captured.args.indexOf('-o');
        assert.ok(idx !== -1, '应含 -o');
        assert.ok(m.captured.args[idx + 1].includes('%(title)s.%(ext)s'), '应含标题模板');
    } finally { m.restore(); }
});

await testAsync('自定义 outputDir 被使用', async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/v.mp4', safePath: '/tmp/v.mp4' });
    try {
        await MediaDownloader.downloadVideo(TEST_URL, { outputDir: EXISTING_DIR });
        const idx = m.captured.args.indexOf('-o');
        assert.ok(m.captured.args[idx + 1].startsWith(EXISTING_DIR), '输出模板应基于自定义目录');
    } finally { m.restore(); }
});

await testAsync('透传 _spawnYtDlp 返回结果', async () => {
    const expected = { success: true, filePath: 'C:\\tmp\\video.mp4', safePath: 'C:/tmp/video.mp4' };
    const m = mockSpawn(expected);
    try {
        const result = await MediaDownloader.downloadVideo(TEST_URL, { outputDir: EXISTING_DIR });
        assert.deepStrictEqual(result, expected, '应原样返回 _spawnYtDlp 结果');
    } finally { m.restore(); }
});

// ============================================================================
// 2. downloadAudio - 参数构建
// ============================================================================
console.log('\n=== downloadAudio 参数构建 ===');

await testAsync('默认格式为 mp3', async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/a.mp3', safePath: '/tmp/a.mp3' });
    try {
        await MediaDownloader.downloadAudio(TEST_URL, { outputDir: EXISTING_DIR });
        const idx = m.captured.args.indexOf('--audio-format');
        assert.ok(idx !== -1, '应含 --audio-format');
        assert.strictEqual(m.captured.args[idx + 1], 'mp3', '默认格式应为 mp3');
    } finally { m.restore(); }
});

await testAsync("format='m4a' 传递正确格式", async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/a.m4a', safePath: '/tmp/a.m4a' });
    try {
        await MediaDownloader.downloadAudio(TEST_URL, { outputDir: EXISTING_DIR, format: 'm4a' });
        const idx = m.captured.args.indexOf('--audio-format');
        assert.strictEqual(m.captured.args[idx + 1], 'm4a', '格式应为 m4a');
    } finally { m.restore(); }
});

await testAsync("format='wav' 传递正确格式", async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/a.wav', safePath: '/tmp/a.wav' });
    try {
        await MediaDownloader.downloadAudio(TEST_URL, { outputDir: EXISTING_DIR, format: 'wav' });
        const idx = m.captured.args.indexOf('--audio-format');
        assert.strictEqual(m.captured.args[idx + 1], 'wav', '格式应为 wav');
    } finally { m.restore(); }
});

await testAsync('包含 -x 音频提取标志', async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/a.mp3', safePath: '/tmp/a.mp3' });
    try {
        await MediaDownloader.downloadAudio(TEST_URL, { outputDir: EXISTING_DIR });
        assert.ok(m.captured.args.includes('-x'), '应含 -x 提取音频');
    } finally { m.restore(); }
});

await testAsync('包含 --audio-quality 0（最佳质量）', async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/a.mp3', safePath: '/tmp/a.mp3' });
    try {
        await MediaDownloader.downloadAudio(TEST_URL, { outputDir: EXISTING_DIR });
        const idx = m.captured.args.indexOf('--audio-quality');
        assert.ok(idx !== -1, '应含 --audio-quality');
        assert.strictEqual(m.captured.args[idx + 1], '0', '应为 0（最佳）');
    } finally { m.restore(); }
});

await testAsync('URL 作为最后一个参数', async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/a.mp3', safePath: '/tmp/a.mp3' });
    try {
        await MediaDownloader.downloadAudio(TEST_URL, { outputDir: EXISTING_DIR });
        const args = m.captured.args;
        assert.strictEqual(args[args.length - 1], TEST_URL, 'URL 应在参数末尾');
    } finally { m.restore(); }
});

await testAsync('包含 --no-playlist 参数', async () => {
    const m = mockSpawn({ success: true, filePath: '/tmp/a.mp3', safePath: '/tmp/a.mp3' });
    try {
        await MediaDownloader.downloadAudio(TEST_URL, { outputDir: EXISTING_DIR });
        assert.ok(m.captured.args.includes('--no-playlist'), '应含 --no-playlist');
    } finally { m.restore(); }
});

await testAsync('透传 _spawnYtDlp 返回结果', async () => {
    const expected = { success: true, filePath: 'C:\\tmp\\audio.mp3', safePath: 'C:/tmp/audio.mp3' };
    const m = mockSpawn(expected);
    try {
        const result = await MediaDownloader.downloadAudio(TEST_URL, { outputDir: EXISTING_DIR });
        assert.deepStrictEqual(result, expected, '应原样返回结果');
    } finally { m.restore(); }
});

// ============================================================================
// 3. _spawnYtDlp 结果结构（验证 safePath 转换契约）
// ============================================================================
console.log('\n=== _spawnYtDlp 结果契约 ===');

await testAsync('mock 返回值结构包含 success/filePath/safePath', async () => {
    const m = mockSpawn({ success: true, filePath: '/x/a.mp4', safePath: '/x/a.mp4' });
    try {
        const r = await MediaDownloader.downloadVideo(TEST_URL, { outputDir: EXISTING_DIR });
        assert.ok('success' in r, '应有 success');
        assert.ok('filePath' in r, '应有 filePath');
        assert.ok('safePath' in r, '应有 safePath');
    } finally { m.restore(); }
});

// ============================================================================
// 4. downloadVideo 与 downloadAudio 参数差异
// ============================================================================
console.log('\n=== 视频/音频参数差异 ===');

await testAsync('downloadVideo 不含 -x，downloadAudio 含 -x', async () => {
    const mv = mockSpawn({ success: true, filePath: '/v.mp4', safePath: '/v.mp4' });
    await MediaDownloader.downloadVideo(TEST_URL, { outputDir: EXISTING_DIR });
    const videoArgs = mv.captured.args.slice();
    mv.restore();

    const ma = mockSpawn({ success: true, filePath: '/a.mp3', safePath: '/a.mp3' });
    await MediaDownloader.downloadAudio(TEST_URL, { outputDir: EXISTING_DIR });
    const audioArgs = ma.captured.args.slice();
    ma.restore();

    assert.ok(!videoArgs.includes('-x'), '视频下载不应含 -x');
    assert.ok(audioArgs.includes('-x'), '音频下载应含 -x');
    assert.ok(!videoArgs.includes('--audio-format'), '视频下载不应含 --audio-format');
    assert.ok(audioArgs.includes('--audio-format'), '音频下载应含 --audio-format');
});

// ============================================================================
console.log(`\n========================================`);
console.log(` media-downloader 单元测试: ${passed} 通过 / ${failed} 失败`);
console.log(`========================================`);

if (failed > 0) process.exit(1);

})();
