# FFmpeg 流媒体协议与实时传输完全指南

> 本指南以实验研究原子级别标准编写，覆盖 FFmpeg 全部主流流媒体协议（RTMP/SRT/RIST/HLS/DASH/WebRTC/RTSP）、低延迟传输方案（LL-HLS/WHIP/WHEP）、多平台直播集成、安全鉴权与运维监控，提供可直接落地的命令、参数表与端到端实战案例。

---

## 一、流媒体协议概述

### 1.1 协议分类与选型

```python
class StreamingProtocolOverview:
    """流媒体协议分类原子模型"""

    PROTOCOL_CATEGORIES = {
        # === 推流协议（Publisher → Server）===
        'push_protocols': {
            'RTMP': {
                'transport': 'TCP 1935',
                'latency': '2-10s',
                'codec_transport': 'FLV 容器',
                'use_case': '直播推流到平台(B站/YouTube/Twitch)',
                'status': '广泛使用(逐渐被 SRT/RIST 替代)',
            },
            'SRT': {
                'transport': 'UDP',
                'latency': '0.1-2s',
                'codec_transport': 'MPEG-TS',
                'use_case': '远距离传输/不稳定网络/低延迟直播',
                'status': '增长中(开源,RFC 草案)',
            },
            'RIST': {
                'transport': 'UDP',
                'latency': '0.1-1s',
                'codec_transport': 'MPEG-TS',
                'use_case': '广播级可靠传输',
                'status': 'VRF 标准,增长中',
            },
            'RTSP': {
                'transport': 'TCP/UDP 554',
                'latency': '0.5-2s',
                'codec_transport': 'RTP',
                'use_case': 'IP 摄像头/监控/安防',
                'status': '稳定(主要用于拉流)',
            },
        },
        # === 拉流协议（Server → Player）===
        'pull_protocols': {
            'HLS': {
                'transport': 'HTTP/HTTPS 80/443',
                'latency': '5-30s (标准), 2-5s (LL-HLS)',
                'codec_transport': 'MPEG-TS/fMP4',
                'use_case': '点播/直播分发/CDN 友好',
                'status': '最广泛(全平台兼容)',
            },
            'DASH': {
                'transport': 'HTTP/HTTPS 80/443',
                'latency': '5-30s',
                'codec_transport': 'fMP4/CMAF',
                'use_case': '点播/直播/自适应码率',
                'status': '增长中(与 HLS 并列)',
            },
            'RTSP': {
                'transport': 'TCP/UDP 554',
                'latency': '0.5-2s',
                'codec_transport': 'RTP',
                'use_case': 'IP 摄像头/监控拉流',
                'status': '稳定',
            },
            'HTTP-FLV': {
                'transport': 'HTTP 80/443',
                'latency': '1-3s',
                'codec_transport': 'FLV',
                'use_case': '低延迟 Web 直播',
                'status': '中国直播平台常用',
            },
        },
        # === 低延迟协议（<1s 延迟）===
        'low_latency_protocols': {
            'WebRTC': {
                'transport': 'UDP (SRTP/DTLS)',
                'latency': '<0.5s (亚秒级)',
                'codec_transport': 'RTP (VP8/VP9/H.264/AV1)',
                'use_case': '实时交互/会议/云游戏',
                'status': '增长中(WHIP/WHEP 标准化)',
            },
            'SRT': {
                'transport': 'UDP',
                'latency': '0.1-2s',
                'codec_transport': 'MPEG-TS',
                'use_case': '低延迟直播/贡献传输',
                'status': '增长中',
            },
            'LL-HLS': {
                'transport': 'HTTP/HTTPS',
                'latency': '2-5s',
                'codec_transport': 'fMP4/CMAF',
                'use_case': '低延迟 HLS 直播',
                'status': '增长中(iOS 15+/Safari 15+)',
            },
            'LL-DASH': {
                'transport': 'HTTP/HTTPS',
                'latency': '2-5s',
                'codec_transport': 'fMP4/CMAF',
                'use_case': '低延迟 DASH 直播',
                'status': '增长中',
            },
        },
    }
```

### 1.2 协议对比矩阵

```python
class ProtocolComparisonMatrix:
    """流媒体协议对比矩阵"""

    COMPARISON_TABLE = {
        'RTMP': {
            'latency': '2-10s',
            'bandwidth_overhead': '低 (TCP)',
            'firewall_compat': '一般 (TCP 1935)',
            'cdn_support': '一般',
            'security': 'TLS 变体 (RTMPS)',
            'adaptive_bitrate': '不支持(原生)',
            'codec_support': 'H.264/AAC (有限)',
            'browser_playback': '需 Flash/HTTP-FLV 转换',
            'complexity': '低',
            'maturity': '高 (2010+)',
        },
        'SRT': {
            'latency': '0.1-2s',
            'bandwidth_overhead': '中 (UDP + ARQ)',
            'firewall_compat': '需开放 UDP 端口',
            'cdn_support': '增长中',
            'security': 'AES-128/256',
            'adaptive_bitrate': '不支持(原生)',
            'codec_support': '全 (MPEG-TS)',
            'browser_playback': '不支持(需网关)',
            'complexity': '中',
            'maturity': '中 (2017+)',
        },
        'HLS': {
            'latency': '5-30s',
            'bandwidth_overhead': '高 (HTTP + 分片)',
            'firewall_compat': '极佳 (HTTP 80/443)',
            'cdn_support': '极佳',
            'security': 'AES-128/DRM',
            'adaptive_bitrate': '原生支持',
            'codec_support': 'H.264/HEVC/AV1/AAC',
            'browser_playback': '全平台',
            'complexity': '中',
            'maturity': '极高 (2009+)',
        },
        'DASH': {
            'latency': '5-30s',
            'bandwidth_overhead': '高 (HTTP + 分片)',
            'firewall_compat': '极佳 (HTTP 80/443)',
            'cdn_support': '极佳',
            'security': 'AES-128/DRM',
            'adaptive_bitrate': '原生支持',
            'codec_support': '全 (fMP4)',
            'browser_playback': 'Chrome/Firefox/Edge',
            'complexity': '高',
            'maturity': '高 (2012+)',
        },
        'WebRTC': {
            'latency': '<0.5s',
            'bandwidth_overhead': '低 (UDP)',
            'firewall_compat': '差 (需 STUN/TURN)',
            'cdn_support': '增长中',
            'security': 'SRTP/DTLS',
            'adaptive_bitrate': '部分(通过 Simulcast)',
            'codec_support': 'VP8/VP9/H.264/AV1/Opus',
            'browser_playback': '全平台(原生)',
            'complexity': '高',
            'maturity': '高 (2017+)',
        },
        'RTSP': {
            'latency': '0.5-2s',
            'bandwidth_overhead': '低',
            'firewall_compat': '差 (需开放多端口)',
            'cdn_support': '差',
            'security': 'SRTP (可选)',
            'adaptive_bitrate': '不支持',
            'codec_support': '全 (RTP)',
            'browser_playback': '不支持(需插件)',
            'complexity': '中',
            'maturity': '极高 (1998+)',
        },
    }

    # 选型决策树
    SELECTION_DECISION_TREE = [
        {'q':'延迟要求?', 'options':{
            '<0.5s': 'WebRTC',
            '0.5-2s': 'SRT / RIST / RTSP',
            '2-5s': 'LL-HLS / HTTP-FLV',
            '5-30s': 'HLS / DASH',
        }},
        {'q':'是否需要 CDN 分发?', 'options':{
            'yes': 'HLS / DASH (HTTP 协议 CDN 友好)',
            'no': 'RTMP / SRT / WebRTC (直连)',
        }},
        {'q':'是否需要浏览器原生播放?', 'options':{
            'yes': 'HLS / DASH / WebRTC / LL-HLS',
            'no': 'RTMP / SRT / RTSP',
        }},
        {'q':'网络稳定性?', 'options':{
            '稳定': 'RTMP / HLS',
            '不稳定': 'SRT / RIST (ARQ 重传)',
        }},
        {'q':'是否需要自适应码率?', 'options':{
            'yes': 'HLS / DASH',
            'no': 'RTMP / SRT / WebRTC',
        }},
    ]
```

---

## 二、RTMP 协议实战

### 2.1 RTMP 推流

```python
class RTMPPush:
    """RTMP 推流原子模型"""

    BASIC_PUSH_COMMANDS = {
        'simple_push': {
            'desc': '基础 RTMP 推流',
            'command': 'ffmpeg -re -i input.mp4 -c:v libx264 -preset medium -b:v 6M '
                       '-c:a aac -b:a 128k -f flv "rtmp://server/live/stream_key"',
            'note': '-re 按原速读取(实时推流必需)',
        },
        'nvenc_push': {
            'desc': 'NVENC 硬件编码推流',
            'command': 'ffmpeg -re -i input.mp4 -c:v h264_nvenc -preset p4 -rc cbr '
                       '-b:v 6M -maxrate 6M -bufsize 12M -g 120 -bf 2 '
                       '-c:a aac -b:a 128k -f flv "rtmp://server/live/stream_key"',
        },
        'live_capture_push': {
            'desc': '摄像头直播推流',
            'command': 'ffmpeg -f dshow -i video="USB Camera":audio="Microphone" '
                       '-c:v h264_nvenc -preset p4 -b:v 4M -c:a aac -b:a 128k '
                       '-f flv "rtmp://server/live/stream_key"',
            'note_linux': '使用 -f v4l2 -i /dev/video0 -f alsa -i hw:0',
            'note_mac': '使用 -f avfoundation -i "0:0"',
        },
        'screen_capture_push': {
            'desc': '屏幕录制直播推流',
            'command': 'ffmpeg -f gdigrab -i desktop -c:v h264_nvenc -preset p4 '
                       '-b:v 8M -r 30 -c:a aac -b:a 128k '
                       '-f flv "rtmp://server/live/stream_key"',
            'note_linux': '使用 -f x11grab -i :0.0',
            'note_mac': '使用 -f avfoundation -i "1"',
        },
    }

    ENCODING_PARAMS = {
        'video': {
            'codec': {'recommended':'h264_nvenc', 'alt':['libx264','h264_qsv','h264_amf']},
            'preset': {'nvenc':'p4', 'libx264':'medium', 'qsv':'fast'},
            'profile': 'high',
            'level': '4.1',
            'bitrate_strategy': 'CBR (直播必须)',
            'gop': '2 × fps (关键帧间隔)',
            'bf': '2 (兼容性优先)',
            'pix_fmt': 'yuv420p (兼容性)',
        },
        'audio': {
            'codec': 'aac',
            'bitrate': '128k (音乐), 64k (语音)',
            'sample_rate': '48000',
            'channels': '2 (立体声)',
        },
        'container': 'flv',
    }

    ADAPTIVE_BITRATE = {
        'desc': '自适应码率推流(多码率输出)',
        'command': '''ffmpeg -re -i input.mp4 \\
  -filter_complex "[0:v]split=3[v1][v2][v3];
    [v1]scale=1920:1080[v1out];
    [v2]scale=1280:720[v2out];
    [v3]scale=854:480[v3out]" \\
  -map "[v1out]" -c:v:0 h264_nvenc -preset p4 -b:v:0 6M -maxrate:0 6M -bufsize:0 12M \\
  -map "[v2out]" -c:v:1 h264_nvenc -preset p4 -b:v:1 3M -maxrate:1 3M -bufsize:1 6M \\
  -map "[v3out]" -c:v:2 h264_nvenc -preset p4 -b:v:2 1.5M -maxrate:2 1.5M -bufsize:2 3M \\
  -map a:0 -c:a:0 aac -b:a:0 128k \\
  -map a:0 -c:a:1 aac -b:a:1 96k \\
  -map a:0 -c:a:2 aac -b:a:2 64k \\
  -f flv "rtmp://server/live/stream_key"''',
    }

    PLATFORM_PUSH = {
        'bilibili': {
            'server': 'rtmp://live-push.bilivideo.com/live-bmc/',
            'params': '-c:v h264_nvenc -preset p4 -b:v 6M -maxrate 6M -bufsize 12M '
                      '-c:a aac -b:a 128k -g 120 -bf 2 -pix_fmt yuv420p -profile:v high -level 4.1',
            'note': '需在 B站直播间获取推流码',
        },
        'youtube': {
            'server': 'rtmp://a.rtmp.youtube.com/live2/',
            'params': '-c:v h264_nvenc -preset p4 -b:v 9M -maxrate 9M -bufsize 18M '
                      '-c:a aac -b:a 128k -g 120 -bf 2 -pix_fmt yuv420p',
            'note': '需在 YouTube Studio 获取直播码',
            'recommended_bitrate': {
                '1080p60': '9-12 Mbps',
                '1080p30': '6-9 Mbps',
                '720p60': '5-7 Mbps',
                '720p30': '3-5 Mbps',
            },
        },
        'twitch': {
            'server': 'rtmp://live.twitch.tv/app/',
            'params': '-c:v h264_nvenc -preset p4 -b:v 6M -maxrate 6M -bufsize 12M '
                      '-c:a aac -b:a 160k -g 120 -bf 2 -pix_fmt yuv420p -keyint_min 120',
            'recommended_bitrate': {
                '1080p60': '6-8 Mbps',
                '720p60': '4-5 Mbps',
                '720p30': '3-4 Mbps',
            },
            'note': 'Twitch 限制 2 B帧, GOP 必须 2s',
        },
        'douyin': {
            'server': 'rtmp://push.douyincdn.com/live/',
            'params': '-c:v h264_nvenc -preset p4 -b:v 4M -maxrate 4M -bufsize 8M '
                      '-c:a aac -b:a 128k -g 120 -bf 2',
            'note': '需在抖音直播伴侣获取推流地址',
        },
        'kuaishou': {
            'server': 'rtmp://push.kuaishouzt.com/live2/',
            'params': '-c:v h264_nvenc -preset p4 -b:v 4M -maxrate 4M -bufsize 8M '
                      '-c:a aac -b:a 128k -g 120 -bf 2',
        },
    }
```

### 2.2 RTMP 拉流与服务器

```python
class RTMPPullServer:
    """RTMP 拉流与服务器搭建"""

    PULL_COMMANDS = {
        'simple_pull': {
            'desc': '基础 RTMP 拉流',
            'command': 'ffmpeg -i "rtmp://server/live/stream_key" -c copy output.mp4',
        },
        'transcode_pull': {
            'desc': '拉流转码',
            'command': 'ffmpeg -i "rtmp://server/live/stream_key" '
                       '-c:v h264_nvenc -preset p5 -b:v 4M -c:a aac -b:a 128k output.mp4',
        },
        'rtmp_to_hls': {
            'desc': 'RTMP 转 HLS 分发',
            'command': 'ffmpeg -i "rtmp://server/live/stream_key" '
                       '-c:v copy -c:a copy -f hls -hls_time 6 -hls_list_size 10 '
                       '-hls_flags delete_segments+append_list output.m3u8',
        },
        'rtmp_to_hls_transcode': {
            'desc': 'RTMP 转码为 HLS',
            'command': 'ffmpeg -i "rtmp://server/live/stream_key" '
                       '-c:v h264_nvenc -preset p4 -b:v 4M -c:a aac -b:a 128k '
                       '-f hls -hls_time 6 -hls_list_size 10 -hls_flags delete_segments '
                       'output.m3u8',
        },
    }

    RTMP_SERVER_OPTIONS = {
        'nginx-rtmp': {
            'desc': 'Nginx RTMP 模块(最常用)',
            'install': '编译 Nginx 时添加 --add-module=nginx-rtmp-module',
            'config': '''
worker_processes auto;
events { worker_connections 1024; }
rtmp {
    server {
        listen 1935;
        chunk_size 4096;
        
        application live {
            live on;
            record off;
            # 推流鉴权
            on_publish http://localhost:8080/auth;
            # HLS 转换
            hls on;
            hls_path /tmp/hls;
            hls_fragment 6;
        }
        
        application vod {
            play /var/videos;
        }
    }
}
http {
    server {
        listen 8080;
        location /hls {
            types { application/vnd.apple.mpegurl m3u8; video/mp2t ts; }
            root /tmp;
            add_header Cache-Control no-cache;
            add_header Access-Control-Allow-Origin *;
        }
    }
}
''',
        },
        'srs': {
            'desc': 'SRS (Simple Realtime Server)',
            'features': ['RTMP/HLS/HTTP-FLV/SRT/WebRTC', '集群', '转码', '录制'],
            'config': '''
listen 1935;
http_server { enabled on; listen 8080; }
vhost __defaultVhost__ {
    hls { enabled on; hls_path ./objs/nginx/html; }
    http_remux { enabled on; mount [vhost]/[app]/[stream].flv; }
    dvr { enabled on; dvr_path ./objs/nginx/html/[app]/[stream].[timestamp].flv; }
    rtc { enabled on; }
}
''',
        },
        'mediasoup': {
            'desc': 'mediasoup (WebRTC 优先)',
            'features': ['WebRTC SFU', '极低延迟', 'Node.js/Rust'],
        },
        'ovenmediaengine': {
            'desc': 'OvenMediaEngine',
            'features': ['WebRTC/LL-HLS', '自适应码率', '录制'],
        },
    }
```

### 2.3 RTMP 故障排查

```python
class RTMPTroubleshoot:
    """RTMP 故障排查"""

    COMMON_ISSUES = {
        'connection_failed': {
            'symptom': 'Connection refused / timeout',
            'causes': ['服务器未启动','防火墙阻挡 1935 端口','推流地址错误'],
            'solutions': [
                '检查服务器 1935 端口: telnet server 1935',
                '检查防火墙规则',
                '验证推流地址格式: rtmp://host:port/app/stream_key',
            ],
        },
        'auth_failed': {
            'symptom': 'RTMP_HandleInvoke: auth failed',
            'causes': ['推流码错误','推流码已过期','鉴权配置错误'],
            'solutions': ['重新获取推流码','检查 on_publish 鉴权脚本'],
        },
        'high_latency': {
            'symptom': '直播延迟 >10s',
            'causes': ['-re 未添加','GOP 过大','B帧过多','缓冲区过大'],
            'solutions': [
                '添加 -re 参数',
                '减小 GOP: -g 60 (2s @ 30fps)',
                '减少 B帧: -bf 0 或 -bf 1',
                '减小缓冲: -bufsize 6M (=b:v)',
            ],
        },
        'stuttering': {
            'symptom': '画面卡顿/丢帧',
            'causes': ['网络带宽不足','编码性能不足','码率过高'],
            'solutions': [
                '降低码率',
                '使用硬件编码器',
                '降低分辨率/帧率',
                '检查网络上行带宽',
            ],
        },
        'audio_video_desync': {
            'symptom': '音画不同步',
            'causes': ['编码延迟差异','时间戳错误'],
            'solutions': [
                '使用 -async 1 -vsync 1',
                '添加 -af aresample=async=1',
                '检查音频采样率匹配',
            ],
        },
        'flv_format_error': {
            'symptom': 'FLV 格式错误/不支持',
            'causes': ['使用不兼容的编码(如 HEVC/AV1)','B帧过多'],
            'solutions': [
                'FLV 不支持 HEVC/AV1, 必须使用 H.264',
                'B帧最多 2 个(FLV 限制)',
                '音频必须 AAC',
            ],
        },
    }
```

---

## 三、HLS 协议实战

### 3.1 HLS 基本架构

```python
class HLSArchitecture:
    """HLS 架构原子模型"""

    HLS_COMPONENTS = {
        'm3u8_playlist': {
            'desc': 'M3U8 播放列表文件',
            'types': {
                'master': '主播放列表(多码率索引)',
                'media': '媒体播放列表(分片索引)',
            },
            'versions': {
                '1': '基础(点播)',
                '3': 'EXT-X-PLAYLIST-TYPE(直播)',
                '4': 'EXT-X-MEDIA(多音轨/字幕)',
                '5': 'EXT-X-SERVER-CONTROL(LL-HLS)',
                '6': 'EXT-X-MAP(fMP4)',
                '7': 'EXT-X-SESSION-DATA',
            },
        },
        'ts_segments': {
            'desc': 'MPEG-TS 分片',
            'duration': '通常 2-10s',
            'format': 'MPEG-TS (传统) / fMP4 (CMAF)',
        },
        'fmp4_segments': {
            'desc': 'fMP4 分片 (CMAF)',
            'advantage': 'HLS/DASH 通用分片,减少存储',
            'init_segment': 'EXT-X-MAP (初始化分片)',
        },
    }

    M3U8_MASTER_EXAMPLE = '''#EXTM3U
#EXT-X-VERSION:6
#EXT-X-STREAM-INF:BANDWIDTH=6000000,RESOLUTION=1920x1080,CODECS="avc1.640028,mp4a.40.2"
stream_1080p.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=3000000,RESOLUTION=1280x720,CODECS="avc1.640020,mp4a.40.2"
stream_720p.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=1500000,RESOLUTION=854x480,CODECS="avc1.64001f,mp4a.40.2"
stream_480p.m3u8'''

    M3U8_MEDIA_LIVE_EXAMPLE = '''#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:6
#EXT-X-MEDIA-SEQUENCE:1234
#EXT-X-PLAYLIST-TYPE:EVENT
#EXTINF:6.000,
seg_01234.ts
#EXTINF:6.000,
seg_01235.ts
#EXTINF:6.000,
seg_01236.ts
#EXT-X-ENDLIST  # 直播不包含此行'''

    M3U8_VOD_EXAMPLE = '''#EXTM3U
#EXT-X-VERSION:4
#EXT-X-TARGETDURATION:10
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-PLAYLIST-TYPE:VOD
#EXTINF:10.000,
seg_000.ts
#EXTINF:10.000,
seg_001.ts
#EXTINF:8.500,
seg_002.ts
#EXT-X-ENDLIST'''
```

### 3.2 HLS 直播

```python
class HLSLiveStreaming:
    """HLS 直播原子模型"""

    HLS_PARAMS = {
        'hls_time': {'desc':'分片时长(秒)','default':'6','range':'1-30','live_recommend':'2-6'},
        'hls_list_size': {'desc':'播放列表保留分片数','default':'5','live_recommend':'6-10'},
        'hls_flags': {
            'values': ['delete_segments','append_list','omit_endlist','round_durations',
                       'discont_start','omit_program_date_time','temp_file','independent_segments'],
            'delete_segments': '删除旧分片(直播)',
            'append_list': '追加模式(事件直播)',
            'omit_endlist': '不写 ENDLIST(直播)',
            'temp_file': '临时文件写入(原子操作)',
            'independent_segments': '每个分片可独立解码',
        },
        'hls_segment_type': {'values':['mpegts','fmp4'],'fmp4':'CMAF 分片'},
        'hls_segment_filename': {'desc':'分片文件名模板','example':'seg_%05d.ts'},
        'hls_playlist_type': {'values':['event','vod'],'event':'事件(可暂停)','vod':'点播'},
        'hls_allow_cache': {'desc':'允许缓存','type':'bool'},
        'hls_base_url': {'desc':'分片基础URL','use':'CDN 域名'},
        'hls_version': {'desc':'HLS 协议版本','default':'3'},
        'method': {'desc':'加密方法','values':['AES-128','SAMPLE-AES','NONE']},
        'hls_key_info_file': {'desc':'密钥信息文件','format':'key_uri\\nkey_file\\niv'},
        'master_pl_name': {'desc':'主播放列表文件名','default':'master.m3u8'},
        'var_stream_map': {'desc':'变体流映射','format':'v:0,a:0 v:1,a:1'},
    }

    LIVE_COMMANDS = {
        'basic_live': {
            'desc': '基础 HLS 直播',
            'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p4 -b:v 4M -maxrate 4M -bufsize 8M \\
  -c:a aac -b:a 128k -g 60 -bf 2 \\
  -f hls -hls_time 6 -hls_list_size 10 -hls_flags delete_segments+temp_file \\
  -hls_segment_filename "seg_%05d.ts" stream.m3u8''',
        },
        'fmp4_live': {
            'desc': 'fMP4/CMAF HLS 直播',
            'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p4 -b:v 4M -c:a aac -b:a 128k -g 60 \\
  -f hls -hls_time 4 -hls_list_size 10 -hls_segment_type fmp4 \\
  -hls_flags delete_segments+independent_segments+temp_file \\
  -hls_init_filename "init.mp4" -hls_segment_filename "seg_%05d.m4s" \\
  stream.m3u8''',
        },
        'multi_bitrate_live': {
            'desc': '多码率 HLS 直播',
            'command': '''ffmpeg -re -i input.mp4 \\
  -filter_complex "[0:v]split=3[v1][v2][v3];
    [v1]scale=1920:1080[v1out];
    [v2]scale=1280:720[v2out];
    [v3]scale=854:480[v3out]" \\
  -map "[v1out]" -c:v:0 h264_nvenc -preset p4 -b:v:0 5M -maxrate:0 5M -bufsize:0 10M -g:0 60 \\
  -map "[v2out]" -c:v:1 h264_nvenc -preset p4 -b:v:1 3M -maxrate:1 3M -bufsize:1 6M -g:1 60 \\
  -map "[v3out]" -c:v:2 h264_nvenc -preset p4 -b:v:2 1.5M -maxrate:2 1.5M -bufsize:2 3M -g:2 60 \\
  -map a:0 -c:a:0 aac -b:a:0 128k \\
  -map a:0 -c:a:1 aac -b:a:1 96k \\
  -map a:0 -c:a:2 aac -b:a:2 64k \\
  -f hls -hls_time 6 -hls_list_size 10 -hls_flags delete_segments+independent_segments \\
  -master_pl_name master.m3u8 \\
  -var_stream_map "v:0,a:0 v:1,a:1 v:2,a:2" \\
  -hls_segment_filename "stream_%v/seg_%05d.ts" stream_%v.m3u8''',
        },
    }

    LL_HLS = {
        'desc': '低延迟 HLS (LL-HLS, HLS v5+)',
        'latency': '2-5s (vs 标准 HLS 10-30s)',
        'requirements': 'iOS 15+ / Safari 15+ / hls.js 1.0+',
        'techniques': ['CMAF fMP4 分片', 'Partial Segments (部分分片)', 'Delta Updates (增量更新)', 'Blocking Playlist Reload'],
        'params': {
            'hls_time': '0.5-1s (极短分片)',
            'hls_segment_type': 'fmp4',
            'hls_flags': 'delete_segments+independent_segments+temp_file+program_date_time',
            'hls_list_size': '6-10',
        },
        'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p4 -tune ll -b:v 4M -maxrate 4M -bufsize 4M \\
  -c:a aac -b:a 128k -g 30 -bf 0 \\
  -f hls -hls_time 1 -hls_list_size 6 -hls_segment_type fmp4 \\
  -hls_flags delete_segments+independent_segments+temp_file+program_date_time \\
  -hls_init_filename "init.mp4" -hls_segment_filename "seg_%05d.m4s" \\
  stream.m3u8''',
        'note': 'LL-HLS 需配合支持的服务器(Nginx/SRS)与播放器(hls.js 1.0+)',
    }
```

### 3.3 HLS 点播

```python
class HLSVOD:
    """HLS 点播原子模型"""

    VOD_COMMANDS = {
        'basic_vod': {
            'desc': '基础 HLS 点播',
            'command': '''ffmpeg -i input.mp4 \\
  -c:v h264_nvenc -preset p7 -rc vbr -b:v 5M -maxrate 8M -bufsize 12M \\
  -c:a aac -b:a 128k -g 240 -bf 3 \\
  -f hls -hls_time 10 -hls_playlist_type vod \\
  -hls_segment_filename "seg_%05d.ts" vod.m3u8''',
        },
        'multi_resolution_vod': {
            'desc': '多分辨率 HLS 点播',
            'command': '''ffmpeg -i input.mp4 \\
  -filter_complex "[0:v]split=3[v1][v2][v3];
    [v1]scale=1920:1080[v1out];
    [v2]scale=1280:720[v2out];
    [v3]scale=854:480[v3out]" \\
  -map "[v1out]" -c:v:0 h264_nvenc -preset p7 -b:v:0 5M -g:0 240 -bf:0 3 \\
  -map "[v2out]" -c:v:1 h264_nvenc -preset p7 -b:v:1 3M -g:1 240 -bf:1 3 \\
  -map "[v3out]" -c:v:2 h264_nvenc -preset p7 -b:v:2 1.5M -g:2 240 -bf:2 3 \\
  -map a:0 -c:a:0 aac -b:a:0 128k \\
  -map a:0 -c:a:1 aac -b:a:1 96k \\
  -f hls -hls_time 10 -hls_playlist_type vod \\
  -master_pl_name master.m3u8 \\
  -var_stream_map "v:0,a:0 v:1,a:1 v:2,a:1" \\
  -hls_segment_filename "stream_%v/seg_%05d.ts" stream_%v.m3u8''',
        },
    }

    ENCRYPTION = {
        'aes_128': {
            'desc': 'AES-128 加密 HLS',
            'steps': [
                '1. 生成 16 字节密钥: openssl rand 16 > enc.key',
                '2. 生成 IV: openssl rand -hex 16',
                '3. 创建 key_info 文件',
                '4. FFmpeg 使用 key_info 加密',
            ],
            'key_info_format': '''# key_info 文件格式:
https://example.com/enc.key  # 密钥 URI(播放器获取密钥的URL)
enc.key                      # 本地密钥文件路径
0123456789abcdef0123456789abcdef  # IV (十六进制)''',
            'command': '''ffmpeg -i input.mp4 \\
  -c:v h264_nvenc -preset p7 -b:v 5M -c:a aac -b:a 128k \\
  -f hls -hls_time 10 -hls_playlist_type vod \\
  -hls_key_info_file key_info \\
  -hls_segment_filename "seg_%05d.ts" encrypted.m3u8''',
        },
        'sample_aes': {
            'desc': 'SAMPLE-AES (FairPlay DRM 前置)',
            'use': 'Apple FairPlay DRM',
            'command': '-hls_enc 1 -hls_enc_url https://example.com/key -hls_enc_key_file key.bin',
        },
    }
```

### 3.4 HLS 与 CDN 集成

```python
class HLSCDNIntegration:
    """HLS CDN 集成"""

    CDN_CONFIG = {
        'cache_strategy': {
            'm3u8': {'cache':'短 (5-10s 直播, 1h 点播)','headers':['Cache-Control: max-age=5']},
            'ts_segments': {'cache':'长 (24h+)','headers':['Cache-Control: max-age=86400']},
            'fmp4_init': {'cache':'永久','headers':['Cache-Control: max-age=31536000']},
            'fmp4_segments': {'cache':'长 (24h+)','headers':['Cache-Control: max-age=86400']},
        },
        'cors': {
            'header': 'Access-Control-Allow-Origin: *',
            'methods': 'GET, HEAD, OPTIONS',
            'credentials': 'false (HLS 通常不需要凭证)',
        },
        'preloading': {
            'desc': 'CDN 预热(直播开始前预加载)',
            'method': '主动推送分片到 CDN 边缘节点',
        },
        'origin_shield': {
            'desc': '源站保护(减少回源)',
            'recommendation': '大型直播必须配置',
        },
    }

    NGINX_HLS_CONFIG = '''
server {
    listen 80;
    server_name hls.example.com;
    
    location /hls {
        types {
            application/vnd.apple.mpegurl m3u8;
            video/mp2t ts;
            video/mp4 mp4;
            application/octet-stream m4s;
        }
        root /var/www/hls;
        
        # CORS
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods 'GET, HEAD, OPTIONS';
        
        # 缓存策略
        location ~ \\.m3u8$ {
            add_header Cache-Control "no-cache";
            add_header Pragma "no-cache";
        }
        location ~ \\.ts$|\\.m4s$ {
            add_header Cache-Control "max-age=86400";
        }
        location ~ \\.mp4$ {
            add_header Cache-Control "max-age=31536000, immutable";
        }
        
        # 直播分片自动清理
        location ~ \\.ts$ {
            try_files $uri @cleanup;
        }
    }
}
'''
```

---

## 四、DASH 协议实战

### 4.1 DASH 架构

```python
class DASHArchitecture:
    """DASH 架构原子模型"""

    DASH_COMPONENTS = {
        'mpd_manifest': {
            'desc': 'MPD (Media Presentation Description) 清单',
            'format': 'XML',
            'structure': ['Period','AdaptationSet','Representation','SegmentList'],
        },
        'segments': {
            'desc': '分片',
            'types': {
                'init': '初始化分片(fMP4 moov box)',
                'media': '媒体分片(fMP4 moof+mdat)',
            },
            'format': 'fMP4/CMAF',
        },
        'segment_addressing': {
            'template': 'SegmentTemplate (模板化URL)',
            'timeline': 'SegmentTimeline (时间线)',
            'list': 'SegmentList (显式列表)',
        },
    }

    MPD_EXAMPLE = '''<?xml version="1.0" encoding="UTF-8"?>
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" 
     type="static" 
     mediaPresentationDuration="PT600S" 
     minBufferTime="PT2S">
  <Period>
    <AdaptationSet mimeType="video/mp4" codecs="avc1.640028">
      <Representation id="v0" bandwidth="5000000" width="1920" height="1080">
        <SegmentTemplate media="video_v0_$Number$.m4s" 
                         initialization="video_v0_init.mp4"
                         startNumber="1" 
                         duration="6000" 
                         timescale="1000"/>
      </Representation>
      <Representation id="v1" bandwidth="3000000" width="1280" height="720">
        <SegmentTemplate media="video_v1_$Number$.m4s" 
                         initialization="video_v1_init.mp4"
                         startNumber="1" 
                         duration="6000" 
                         timescale="1000"/>
      </Representation>
    </AdaptationSet>
    <AdaptationSet mimeType="audio/mp4" codecs="mp4a.40.2">
      <Representation id="a0" bandwidth="128000">
        <SegmentTemplate media="audio_a0_$Number$.m4s" 
                         initialization="audio_a0_init.mp4"
                         startNumber="1" 
                         duration="6000" 
                         timescale="1000"/>
      </Representation>
    </AdaptationSet>
  </Period>
</MPD>'''

    DASH_PARAMS = {
        'use_template': {'desc':'使用 SegmentTemplate','type':'bool','default':'1'},
        'use_timeline': {'desc':'使用 SegmentTimeline','type':'bool','default':'1'},
        'segment_duration': {'desc':'分片时长(秒)','default':'5'},
        'adaptation_sets': {'desc':'自适应集定义','format':'id=0,streams=v:0,v:1 id=1,streams=a:0'},
        'init_seg_name': {'desc':'初始化分片文件名','default':'init-stream$RepresentationID$.m4s'},
        'media_seg_name': {'desc':'媒体分片文件名','default':'chunk-stream$RepresentationID$-$Number%05d$.m4s'},
        'window_size': {'desc':'直播窗口大小(分片数)','default':'5'},
        'extra_window_size': {'desc':'额外窗口大小','default':'5'},
        'remove_at_exit': {'desc':'退出时删除分片','type':'bool'},
        'lhls': {'desc':'低延迟 HLS (实验性)','type':'bool'},
    }
```

### 4.2 DASH 直播与点播

```python
class DASHLiveVOD:
    """DASH 直播与点播"""

    VOD_COMMANDS = {
        'basic_vod': {
            'desc': '基础 DASH 点播',
            'command': '''ffmpeg -i input.mp4 \\
  -c:v libx264 -preset medium -b:v 5M -c:a aac -b:a 128k \\
  -use_template 1 -use_timeline 1 \\
  -adaptation_sets "id=0,streams=v:0 id=1,streams=a:0" \\
  -f dash manifest.mpd''',
        },
        'nvenc_vod': {
            'desc': 'NVENC DASH 点播',
            'command': '''ffmpeg -i input.mp4 \\
  -c:v h264_nvenc -preset p7 -b:v 5M -c:a aac -b:a 128k -g 240 -bf 3 \\
  -use_template 1 -use_timeline 1 \\
  -adaptation_sets "id=0,streams=v:0 id=1,streams=a:0" \\
  -f dash manifest.mpd''',
        },
        'multi_resolution': {
            'desc': '多分辨率 DASH',
            'command': '''ffmpeg -i input.mp4 \\
  -filter_complex "[0:v]split=3[v1][v2][v3];
    [v1]scale=1920:1080[v1out];
    [v2]scale=1280:720[v2out];
    [v3]scale=854:480[v3out]" \\
  -map "[v1out]" -c:v:0 h264_nvenc -preset p7 -b:v:0 5M -g:0 240 \\
  -map "[v2out]" -c:v:1 h264_nvenc -preset p7 -b:v:1 3M -g:1 240 \\
  -map "[v3out]" -c:v:2 h264_nvenc -preset p7 -b:v:2 1.5M -g:2 240 \\
  -map a:0 -c:a:0 aac -b:a:0 128k \\
  -use_template 1 -use_timeline 1 \\
  -adaptation_sets "id=0,streams=v:0,v:1,v:2 id=1,streams=a:0" \\
  -f dash manifest.mpd''',
        },
    }

    LIVE_COMMANDS = {
        'basic_live': {
            'desc': '基础 DASH 直播',
            'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p4 -b:v 4M -c:a aac -b:a 128k -g 60 \\
  -use_template 1 -use_timeline 0 \\
  -window_size 10 -extra_window_size 5 \\
  -adaptation_sets "id=0,streams=v:0 id=1,streams=a:0" \\
  -f dash manifest.mpd''',
        },
    }

    DASH_VS_HLS = {
        'latency': {'HLS':'5-30s','DASH':'5-30s','LL-HLS':'2-5s','LL-DASH':'2-5s'},
        'codec_support': {'HLS':'H.264/HEVC/AV1','DASH':'全(含 VP9/AV1)'},
        'browser_support': {
            'HLS':'Safari 原生,其他需 hls.js',
            'DASH':'Chrome/Firefox/Edge 原生(部分),其他需 dash.js',
        },
        'drm_support': {
            'HLS':'FairPlay (Apple), Widevine, PlayReady',
            'DASH':'Widevine, PlayReady (更广泛)',
        },
        'ad_insertion': {
            'HLS':'HLS Interstitial (新), SCTE-35',
            'DASH':'SCTE-35, DASH Interstitial',
        },
        'cdn_caching': {
            'HLS':'极佳 (m3u8/ts)',
            'DASH':'极佳 (mpd/m4s)',
        },
        'segment_format': {
            'HLS':'MPEG-TS (传统), fMP4 (CMAF)',
            'DASH':'fMP4 (CMAF)',
            'common':'CMAF fMP4 可同时用于 HLS 和 DASH',
        },
    }
```

---

## 五、SRT 协议实战

### 5.1 SRT 原理与参数

```python
class SRTProtocol:
    """SRT (Secure Reliable Transport) 协议原子模型"""

    SRT_PRINCIPLES = {
        'reliability': '基于 UDP + ARQ (自动重传请求)',
        'congestion_control': '拥塞控制(类似 TCP)',
        'encryption': 'AES-128/256 端到端加密',
        'firewall_traversal': 'UDP 打洞(Listener/Caller/Rendezvous 模式)',
        'bandwidth_estimation': '实时带宽估算',
        'latency_control': '可配置延迟(buffer + latency)',
    }

    SRT_MODES = {
        'caller': {
            'desc': 'Caller 模式(主动连接)',
            'use': '推流端 / 客户端主动连接服务器',
            'command': 'srt://server:port?mode=caller',
            'note': '默认模式',
        },
        'listener': {
            'desc': 'Listener 模式(监听)',
            'use': '服务器端监听等待连接',
            'command': 'srt://:port?mode=listener',
        },
        'rendezvous': {
            'desc': 'Rendezvous 模式(对等)',
            'use': '双方同时连接(防火墙穿透)',
            'command': 'srt://peer:port?mode=rendezvous',
        },
    }

    SRT_PARAMS = {
        'latency': {'desc':'延迟缓冲(毫秒)','default':'120','range':'20-10000','live_recommend':'120-500'},
        'peer_latency': {'desc':'对端延迟(毫秒)','default':'120'},
        'recvlatency': {'desc':'接收延迟(毫秒)','default':'120'},
        'connect_timeout': {'desc':'连接超时(毫秒)','default':'3000'},
        'mode': {'values':['caller','listener','rendezvous']},
        'payload_size': {'desc':'有效载荷大小(字节)','default':'1316','max':'1456'},
        'mss': {'desc':'最大分段大小','default':'1500'},
        'passphrase': {'desc':'加密密码(10-79字符)','enable':'AES-256'},
        'pbkeylen': {'values':['16','24','32'],'desc':'密钥长度(bytes)','32':'AES-256'},
        'stream_id': {'desc':'流ID(多路复用)','use':'SRT 多路复用'},
        'tsbpdmode': {'desc':'时间戳基于分组传递模式','default':'1','values':['0','1']},
        'congestion': {'desc':'拥塞控制算法','default':'live','values':['live','file']},
        'inputbw': {'desc':'输入带宽(bps)','use':'file 模式'},
        'oheadbw': {'desc':'开销百分比(%)','default':'25'},
        'maxbw': {'desc':'最大带宽(bps)','use':'限速'},
        'smoother': {'values':['live','file'],'live':'实时(默认)','file':'文件传输'},
        ' adaptation_period': {'desc':'适配周期(毫秒)'},
        'enforced_encryption': {'values':['0','1'],'1':'强制加密(无密码拒绝)'},
        'passphrase': {'desc':'加密密码','length':'10-79 字符'},
    }

    PERFORMANCE_TUNING = {
        'latency_optimization': {
            'low_latency': {'latency':'20-50','use':'局域网/稳定网络'},
            'standard': {'latency':'120-250','use':'公网直播'},
            'high_latency': {'latency':'500-2000','use':'跨国/不稳定网络'},
        },
        'bandwidth_optimization': {
            'overhead': {'default':'25%','range':'10-50%','note':'重传所需额外带宽'},
            'maxbw_setting': '设为略高于编码码率(如 8M 码率设 10M maxbw)',
        },
    }
```

### 5.2 SRT 推流与拉流

```python
class SRTStreamOperations:
    """SRT 推流拉流实战"""

    PUSH_COMMANDS = {
        'srt_push_basic': {
            'desc': '基础 SRT 推流',
            'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p4 -b:v 4M -c:a aac -b:a 128k \\
  -f mpegts "srt://server:9000?stream_id=live/stream1"''',
        },
        'srt_push_encrypted': {
            'desc': '加密 SRT 推流',
            'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p4 -b:v 4M -c:a aac -b:a 128k \\
  -f mpegts "srt://server:9000?stream_id=live/stream1&passphrase=MySecurePass123&pbkeylen=32"''',
        },
        'srt_push_low_latency': {
            'desc': '低延迟 SRT 推流',
            'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p4 -tune ll -b:v 4M -maxrate 4M -bufsize 4M \\
  -c:a aac -b:a 128k -g 30 -bf 0 \\
  -f mpegts "srt://server:9000?stream_id=live/stream1&latency=50000&peer_latency=50000"''',
            'note': 'latency=50000 表示 50ms 延迟(极低)',
        },
        'srt_push_high_latency': {
            'desc': '高延迟稳定 SRT 推流(不稳定网络)',
            'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p4 -b:v 4M -c:a aac -b:a 128k \\
  -f mpegts "srt://server:9000?stream_id=live/stream1&latency=3000000&peer_latency=3000000"''',
            'note': 'latency=3000000 表示 3s 延迟(容忍丢包)',
        },
    }

    PULL_COMMANDS = {
        'srt_pull_basic': {
            'desc': '基础 SRT 拉流',
            'command': '''ffmpeg -i "srt://server:9000?stream_id=live/stream1&mode=caller" \\
  -c copy output.ts''',
        },
        'srt_pull_to_hls': {
            'desc': 'SRT 拉流转 HLS 分发',
            'command': '''ffmpeg -i "srt://server:9000?stream_id=live/stream1" \\
  -c:v copy -c:a copy -f hls -hls_time 6 -hls_list_size 10 \\
  -hls_flags delete_segments output.m3u8''',
        },
        'srt_pull_transcode': {
            'desc': 'SRT 拉流转码',
            'command': '''ffmpeg -i "srt://server:9000?stream_id=live/stream1" \\
  -c:v h264_nvenc -preset p5 -b:v 3M -c:a aac -b:a 128k \\
  -f flv "rtmp://cdn/live/stream1"''',
        },
    }

    SRT_SERVER_CONFIG = {
        'srs_srt': {
            'desc': 'SRS 服务器 SRT 配置',
            'config': '''
srt_server {
    enabled on;
    listen 10080;
    maxbw 1000000000;
    connect_timeout 4000;
    peer_latency 300000;
    recvlatency 300000;
    latency 300000;
    tlpktdrop on;
    tsbpdmode on;
}
vhost __defaultVhost__ {
    srt {
        enabled on;
        srt_to_rtmp on;
    }
}
''',
        },
        'srt_live_server': {
            'desc': 'SRT Live Server (SLS)',
            'features': ['开源 SRT 服务器', '多路复用', '负载均衡'],
        },
    }
```

### 5.3 SRT 安全传输

```python
class SRTSecurity:
    """SRT 安全传输"""

    ENCRYPTION = {
        'aes_128': {'pbkeylen':16, 'passphrase_length':'10-79', 'note':'AES-128-CBC'},
        'aes_192': {'pbkeylen':24, 'passphrase_length':'10-79', 'note':'AES-192-CBC'},
        'aes_256': {'pbkeylen':32, 'passphrase_length':'10-79', 'note':'AES-256-CBC (推荐)'},
    }

    AUTHENTICATION = {
        'stream_id': {
            'desc': '基于 Stream ID 的鉴权',
            'format': '#!::h=host,r=stream,m=request,u=user,s=token',
            'fields': {
                'h': '主机名',
                'r': '资源(流名)',
                'm': '请求模式(publish/request)',
                'u': '用户名',
                's': '签名/Token',
            },
            'example': 'srt://server:9000?stream_id=#!::h=example.com,r=live/stream1,m=publish,u=admin,s=abc123token',
        },
    }

    SECURITY_PRACTICES = {
        'tls': 'SRT 内置 AES 加密,无需额外 TLS',
        'firewall': '仅开放 UDP 端口,配置 IP 白名单',
        'token': 'Stream ID 中携带动态 Token,服务器验证',
        'key_rotation': '定期更换 passphrase',
        'enforced_encryption': 'enforced_encryption=1 拒绝无密码连接',
    }
```

---

## 六、WebRTC 低延迟传输

### 6.1 WebRTC 架构

```python
class WebRTCArchitecture:
    """WebRTC 架构原子模型"""

    WEBRTC_COMPONENTS = {
        'media': {
            'video_codecs': ['VP8','VP9','H.264','AV1','H.265(部分)'],
            'audio_codecs': ['Opus','G.711','G.722'],
            'container': 'RTP (Real-time Transport Protocol)',
        },
        'transport': {
            'signaling': 'WebSocket / HTTP (SDP 交换)',
            'media_transport': 'SRTP over UDP',
            'nat_traversal': ['STUN','TURN','ICE'],
        },
        'security': {
            'dtls': 'DTLS (Datagram TLS) 密钥协商',
            'srtp': 'SRTP (Secure RTP) 媒体加密',
        },
        'topology': {
            'p2p': '点对点(1对1)',
            'sfu': '选择性转发单元(1对多,推荐)',
            'mcu': '多点控制单元(混流,开销大)',
        },
    }

    LATENCY_BREAKDOWN = {
        'capture': '5-20ms',
        'encode': '5-50ms (取决于编码器)',
        'network': '10-100ms (取决于距离)',
        'decode': '5-30ms',
        'render': '5-15ms',
        'total': '30-200ms (亚秒级)',
    }

    SIGNALING_PROTOCOL = {
        'sdp': {
            'desc': 'Session Description Protocol (会话描述)',
            'offer': '呼叫方创建 Offer',
            'answer': '被叫方创建 Answer',
            'ice_candidates': 'ICE 候选地址交换',
        },
        'transport': {
            'websocket': '最常用(实时双向)',
            'http': '轮询(不推荐)',
            'sse': '单向(配合 HTTP POST)',
        },
    }
```

### 6.2 FFmpeg 与 WebRTC 桥接

```python
class FFmpegWebRTCBridge:
    """FFmpeg 与 WebRTC 桥接方案"""

    BRIDGE_OPTIONS = {
        'mediamtx': {
            'desc': 'MediaMTX (原 rtsp-simple-server)',
            'features': ['RTSP/RTMP/SRT → WebRTC', '轻量', 'Go 实现'],
            'command': 'ffmpeg -re -i input.mp4 -c copy -f rtsp rtsp://localhost:8554/stream',
            'webrtc_url': 'http://localhost:8889/stream',
        },
        'ovenmediaengine': {
            'desc': 'OvenMediaEngine',
            'features': ['WebRTC/LL-HLS', '自适应码率', '录制'],
            'command': 'ffmpeg -re -i input.mp4 -c copy -f mpegts srt://ome:9999/stream',
            'webrtc_url': 'wss://ome:3333/stream',
        },
        'janus': {
            'desc': 'Janus Gateway',
            'features': ['WebRTC SFU', '插件架构', 'C 实现'],
        },
        'srs_webrtc': {
            'desc': 'SRS WebRTC',
            'features': ['RTMP/SRT → WebRTC', 'WHIP/WHEP'],
            'config': 'rtc { enabled on; listen 1985; }',
            'command': 'ffmpeg -re -i input.mp4 -c copy -f flv rtmp://srs/live/stream',
            'webrtc_url': 'webrtc://srs/live/stream',
        },
        'whip_whep': {
            'desc': 'WHIP/WHEP 标准协议',
            'whip': 'WebRTC HTTP Ingestion Protocol (推流)',
            'whep': 'WebRTC HTTP Egress Protocol (拉流)',
            'command': 'ffmpeg -re -i input.mp4 -c:v libx264 -c:a libopus -f webrtc whep://server/stream',
            'note': 'FFmpeg 6.0+ 实验性支持',
        },
    }
```

### 6.3 WHIP/WHEP 协议

```python
class WHIPWHEPProtocol:
    """WHIP/WHEP 协议原子模型"""

    WHIP_SPEC = {
        'desc': 'WebRTC HTTP Ingestion Protocol (推流标准)',
        'rfc': 'draft-ietf-wish-whip',
        'transport': 'HTTP POST (SDP 交换)',
        'media_transport': 'WebRTC (SRTP/DTLS)',
        'latency': '<500ms',
        'use_case': '浏览器/FFmpeg → WebRTC 服务器推流',
    }

    WHEP_SPEC = {
        'desc': 'WebRTC HTTP Egress Protocol (拉流标准)',
        'rfc': 'draft-ietf-wish-whep',
        'transport': 'HTTP POST (SDP 交换)',
        'media_transport': 'WebRTC (SRTP/DTLS)',
        'latency': '<500ms',
        'use_case': 'WebRTC 服务器 → 浏览器/FFmpeg 拉流',
    }

    FFMPEG_WHIP_COMMANDS = {
        'whip_push': {
            'desc': 'FFmpeg WHIP 推流',
            'command': '''ffmpeg -re -i input.mp4 \\
  -c:v libx264 -preset fast -tune zerolatency -b:v 2M -maxrate 2M \\
  -c:a libopus -b:a 128k -ar 48000 -ac 2 \\
  -f webrtc "http://whip-server/whip/endpoint"''',
            'note': 'FFmpeg 6.0+ 实验性支持,需编译 --enable-webrtc',
        },
        'whep_pull': {
            'desc': 'FFmpeg WHEP 拉流',
            'command': '''ffmpeg -f webrtc -i "http://whep-server/whep/endpoint" \\
  -c copy output.mp4''',
        },
    }

    QUALITY_OPTIMIZATION = {
        'codec': {
            'video': {'recommended':'VP8', 'alt':['H.264','VP9','AV1']},
            'audio': {'recommended':'Opus', 'alt':['G.711']},
        },
        'bitrate': {
            'video_1080p': '2-4 Mbps',
            'video_720p': '1-2 Mbps',
            'video_480p': '0.5-1 Mbps',
            'audio': '64-128 kbps (Opus)',
        },
        'latency_optimization': [
            '使用 -tune zerolatency (libx264)',
            '减小 GOP: -g 30 (1s @ 30fps)',
            '禁用 B帧: -bf 0',
            '减小缓冲: -bufsize 1M',
            '使用硬件编码器减少编码延迟',
        ],
        'simulcast': {
            'desc': '联播(多分辨率同时推流)',
            'benefit': '客户端按带宽选择层',
            'layers': ['高(1080p)','中(720p)','低(360p)'],
        },
    }
```

---

## 七、多平台直播方案

### 7.1 多平台同时推流

```python
class MultiPlatformStreaming:
    """多平台同时推流"""

    MULTI_PUSH_COMMANDS = {
        'tee_muxer': {
            'desc': '使用 tee muxer 同时推流到多平台',
            'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p4 -b:v 6M -maxrate 6M -bufsize 12M \\
  -c:a aac -b:a 128k -g 120 -bf 2 -pix_fmt yuv420p \\
  -f tee "[f=flv]rtmp://live-push.bilivideo.com/live-bmc/your_bili_key|
           [f=flv]rtmp://a.rtmp.youtube.com/live2/your_yt_key|
           [f=flv]rtmp://live.twitch.tv/app/your_twitch_key"''',
            'note': '编码一次,复制到多个输出,节省编码资源',
        },
        'multi_output': {
            'desc': '多输出分别编码(不同码率)',
            'command': '''ffmpeg -re -i input.mp4 \\
  -filter_complex "[0:v]split=2[v1][v2]" \\
  -map "[v1]" -c:v:0 h264_nvenc -preset p4 -b:v:0 6M -maxrate:0 6M -bufsize:0 12M \\
  -map "[v2]" -c:v:1 h264_nvenc -preset p4 -b:v:1 4M -maxrate:1 4M -bufsize:1 8M \\
  -map a:0 -c:a:0 aac -b:a:0 128k \\
  -map a:0 -c:a:1 aac -b:a:1 128k \\
  -f flv "rtmp://bilivideo.com/live-bmc/bili_key" \\
  -f flv "rtmp://youtube.com/live2/yt_key"''',
        },
    }

    TRANSCODE_REMUX = {
        'transcode': {
            'desc': '转码(改变编码/码率)',
            'use': '目标平台要求不同编码/码率',
            'overhead': '高(需要重新编码)',
        },
        'remux': {
            'desc': '转封装(改变容器,不改变编码)',
            'use': 'RTMP → HLS, SRT → RTMP 等',
            'overhead': '低(仅重新封装)',
            'command': 'ffmpeg -i rtmp://source -c copy -f hls output.m3u8',
        },
        'copy': {
            'desc': '直接复制流',
            'use': '相同编码/格式直接转发',
            'overhead': '最低',
        },
    }

    RECORD_AND_LIVE = {
        'desc': '录制与直播并行',
        'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p4 -b:v 6M -c:a aac -b:a 128k \\
  -map 0 -f flv "rtmp://server/live/stream" \\
  -map 0 -c copy recording.mp4''',
        'note': '同时输出直播流和本地录制文件',
    }
```

### 7.2 备份与故障切换

```python
class BackupFailover:
    """备份与故障切换"""

    STRATEGIES = {
        'dual_push': {
            'desc': '双路推流(主备)',
            'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p4 -b:v 6M -c:a aac -b:a 128k \\
  -f tee "[f=flv]rtmp://primary-server/live/stream|
           [f=flv]rtmp://backup-server/live/stream"''',
            'note': '同时推流到主备服务器,播放器自动切换',
        },
        'srt_redundancy': {
            'desc': 'SRT 冗余路径',
            'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p4 -b:v 4M -c:a aac -b:a 128k \\
  -f mpegts "srt://primary:9000?stream_id=stream&latency=500000" \\
  -f mpegts "srt://backup:9000?stream_id=stream&latency=500000"''',
        },
        'health_check': {
            'desc': '健康检查与自动切换',
            'method': '监控推流状态,失败时切换到备用',
            'script': '''# PowerShell 健康检查脚本
$primaryOK = Test-NetConnection -ComputerName primary-server -Port 1935 -InformationLevel Quiet
$backupOK = Test-NetConnection -ComputerName backup-server -Port 1935 -InformationLevel Quiet

if ($primaryOK) {
    $server = "primary-server"
} elseif ($backupOK) {
    $server = "backup-server"
} else {
    Write-Error "所有服务器不可用"
    exit 1
}

ffmpeg -re -i input.mp4 -c:v h264_nvenc -preset p4 -b:v 6M `
    -c:a aac -b:a 128k -f flv "rtmp://$server/live/stream"''',
        },
    }
```

---

## 八、与 AE/Premiere 集成

### 8.1 AE 渲染后直接推流

```python
class AEStreamingIntegration:
    """AE 渲染推流集成"""

    AE_DIRECT_STREAM = {
        'workflow': [
            '1. AE 完成合成并渲染到无损/低压缩格式(ProRes/DNxHR)',
            '2. FFmpeg 读取渲染输出文件并实时推流',
            '3. 配合 AE 的 aerender 命令行渲染实现自动化',
        ],
        'command': '''ffmpeg -re -i ae_output.mov \\
  -c:v h264_nvenc -preset p4 -b:v 8M -maxrate 8M -bufsize 16M \\
  -c:a aac -b:a 128k -g 120 -bf 2 -pix_fmt yuv420p \\
  -f flv "rtmp://server/live/stream_key"''',
    }

    AE_RENDER_STREAM_SCRIPT = {
        'desc': 'AE 命令行渲染 + 推流一体化脚本',
        'script': '''# PowerShell 脚本
$aerender = "C:\\Program Files\\Adobe\\Adobe After Effects 2024\\Support Files\\aerender.exe"
$project = "D:\\projects\\live_graphics.aep"
$comp = "Main Comp"
$output = "D:\\output\\frame_%05d.png"

# 1. AE 渲染 PNG 序列
& $aerender -project $project -comp $comp -output $output -RStemplate "Best Settings" -OMtemplate "PNG"

# 2. FFmpeg 读取序列并推流
ffmpeg -re -framerate 30 -i "D:\\output\\frame_%05d.png" \\
  -c:v h264_nvenc -preset p4 -b:v 8M -maxrate 8M -bufsize 16M \\
  -g 120 -bf 2 -pix_fmt yuv420p -f flv "rtmp://server/live/stream"

# 或直接读取 AE 输出的 ProRes
# ffmpeg -re -i ae_prores.mov -c:v h264_nvenc -preset p4 -b:v 8M -f flv "rtmp://server/live/stream"''',
    }

    PREMIERE_DYNAMIC_LINK = {
        'desc': 'Premiere 动态链接直播',
        'workflow': [
            '1. Premiere 序列完成编辑',
            '2. 使用 Media Encoder 或 FFmpeg 导出',
            '3. FFmpeg 推流',
        ],
        'command': '''# Premiere 导出 ProRes → FFmpeg 推流
ffmpeg -re -i premiere_export.mov \\
  -c:v h264_nvenc -preset p4 -b:v 8M -c:a aac -b:a 128k \\
  -f flv "rtmp://server/live/stream"''',
    }

    VIRTUAL_STUDIO = {
        'desc': '虚拟演播室方案',
        'components': {
            'ae': '实时图形/字幕/动画',
            'obs': '场景合成/切换',
            'ffmpeg': '推流/转码',
            'ndi': '局域网低延迟传输',
        },
        'workflow': [
            '1. AE 输出图形到 NDI',
            '2. OBS 接收 NDI 并合成',
            '3. OBS 内置推流(或 FFmpeg)',
            '4. 多平台分发',
        ],
        'ndi_command': '''# FFmpeg 通过 NDI 接收
ffmpeg -f libndi_newtek -i "NDI_SOURCE" \\
  -c:v h264_nvenc -preset p4 -b:v 8M -c:a aac -b:a 128k \\
  -f flv "rtmp://server/live/stream"''',
    }
```

---

## 九、监控与运维

### 9.1 流媒体健康检查

```python
class StreamHealthMonitor:
    """流媒体健康检查"""

    MONITORING_COMMANDS = {
        'ffprobe_check': {
            'desc': '使用 ffprobe 检查流状态',
            'command': '''ffprobe -v quiet -print_format json -show_streams -show_format \\
  "rtmp://server/live/stream"''',
            'check_items': ['codec','resolution','bitrate','fps','duration'],
        },
        'continuous_monitor': {
            'desc': '持续监控流质量',
            'command': '''while true; do
  ffprobe -v quiet -print_format json -show_streams "rtmp://server/live/stream" | \\
    python3 -c "
import json, sys
data = json.load(sys.stdin)
for s in data.get('streams', []):
    if s['codec_type'] == 'video':
        print(f'[{s.get(\"codec_name\")}] {s.get(\"width\")}x{s.get(\"height\")} @ {eval(s.get(\"r_frame_rate\",\"0/1\"))}fps bitrate={s.get(\"bit_rate\",\"N/A\")}')
    elif s['codec_type'] == 'audio':
        print(f'[audio:{s.get(\"codec_name\")}] {s.get(\"sample_rate\")}Hz {s.get(\"channels\")}ch bitrate={s.get(\"bit_rate\",\"N/A\")}')
"
  sleep 5
done''',
        },
        'frame_drop_detect': {
            'desc': '丢帧检测',
            'command': 'ffmpeg -i stream -vf "fps=fps=30" -f null - 2>&1 | grep "drop"',
        },
    }

    HEALTH_METRICS = {
        'video': {
            'fps': {'target':'=源fps','warn':'<源fps 90%','critical':'<源fps 80%'},
            'bitrate': {'target':'=设定码率','warn':'±20%','critical':'±40%'},
            'resolution': {'target':'=设定分辨率','critical':'不匹配'},
            'keyframe_interval': {'target':'=设定GOP','warn':'GOP异常'},
        },
        'audio': {
            'sample_rate': {'target':'48000','critical':'不匹配'},
            'channels': {'target':'2(立体声)','critical':'不匹配'},
            'bitrate': {'target':'=设定码率','warn':'±20%'},
            'audio_level': {'target':'-20 to -6 dB','warn':'< -40 或 > -3 dB','critical':'削波'},
        },
        'network': {
            'latency': {'target':'<2s (直播)','warn':'>5s','critical':'>10s'},
            'packet_loss': {'target':'0%','warn':'>0.1%','critical':'>1%'},
            'jitter': {'target':'<50ms','warn':'>100ms','critical':'>200ms'},
        },
    }
```

### 9.2 延迟优化

```python
class LatencyOptimization:
    """延迟优化策略"""

    LATENCY_SOURCES = {
        'capture': {'latency':'5-20ms','optimization':'使用硬件采集卡'},
        'encode': {'latency':'5-50ms','optimization':'硬件编码器 + zerolatency'},
        'muxer_buffer': {'latency':'100-500ms','optimization':'减小缓冲,使用 -flush_packets 1'},
        'network': {'latency':'10-200ms','optimization':'选择低延迟协议(SRT/WebRTC)'},
        'demuxer_buffer': {'latency':'100-500ms','optimization':'服务器端减小缓冲'},
        'player_buffer': {'latency':'500-3000ms','optimization':'播放器设置低延迟模式'},
        'total': {'range':'0.7-4s','target':'<1s (WebRTC), <2s (SRT), <5s (LL-HLS)'},
    }

    OPTIMIZATION_TECHNIQUES = {
        'encoding': {
            'tune': '-tune zerolatency (libx264) / -tune ll (NVENC)',
            'gop': '-g 30 (1s GOP @ 30fps)',
            'bframes': '-bf 0 (禁用B帧)',
            'buffer': '-bufsize 1M (最小缓冲)',
            'rc': '-rc cbr (稳定码率)',
        },
        'muxer': {
            'flush': '-flush_packets 1 (立即刷新)',
            'flvflags': '+no_duration_filesize',
        },
        'protocol': {
            'rtmp': '-rtmp_live live',
            'hls': '-hls_time 1 -hls_list_size 6 (短分片)',
            'srt': 'latency=50000 (50ms)',
            'webrtc': '原生低延迟',
        },
        'player': {
            'buffer': '低延迟模式(1-2s缓冲)',
            'sync': '同步到音频(避免音画漂移)',
        },
    }

    LOW_LATENCY_CONFIG = {
        'rtmp_sub_second': {
            'desc': '亚秒级 RTMP 直播',
            'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p1 -tune ll -rc cbr -b:v 6M -maxrate 6M -bufsize 1M \\
  -g 30 -bf 0 -c:a aac -b:a 128k -ar 48000 \\
  -flush_packets 1 -f flv "rtmp://server/live/stream"''',
        },
        'srt_ultra_low': {
            'desc': '超低延迟 SRT',
            'command': '''ffmpeg -re -i input.mp4 \\
  -c:v h264_nvenc -preset p1 -tune ll -b:v 6M -bufsize 1M -g 30 -bf 0 \\
  -c:a aac -b:a 128k -f mpegts \\
  "srt://server:9000?stream_id=stream&latency=20000&peer_latency=20000"''',
        },
    }
```

### 9.3 带宽管理

```python
class BandwidthManagement:
    """带宽管理"""

    BANDWIDTH_CALCULATION = {
        'formula': '总带宽 = 视频码率 + 音频码率 + 协议开销(10-30%)',
        'examples': {
            '1080p_h264_6m': {'video':'6 Mbps','audio':'128 kbps','overhead':'10%','total':'6.75 Mbps'},
            '720p_h264_3m':  {'video':'3 Mbps','audio':'128 kbps','overhead':'10%','total':'3.45 Mbps'},
            '480p_h264_1.5m':{'video':'1.5 Mbps','audio':'64 kbps','overhead':'15%','total':'1.80 Mbps'},
        },
    }

    BANDWIDTH_OPTIMIZATION = {
        'codec_selection': {
            'h264': '基线(兼容性)',
            'hevc': '节省 30-50% 带宽',
            'av1': '节省 40-60% 带宽(vs H.264)',
        },
        'resolution_scaling': {
            '1080p': '5-8 Mbps (H.264)',
            '720p': '3-5 Mbps (H.264)',
            '480p': '1-2 Mbps (H.264)',
        },
        'adaptive_bitrate': {
            'desc': '自适应码率(ABR)',
            'method': '多码率输出 + 客户端按带宽选择',
            'hls': 'master.m3u8 多码率列表',
            'dash': 'MPD 多 Representation',
        },
        'rate_control': {
            'vbr': '可变码率(节省带宽,动态场景可能超限)',
            'cbr': '恒定码率(带宽可预测,推荐直播)',
            'constrained_vbr': '受限VBR(maxrate 约束)',
        },
    }
```

### 9.4 日志分析

```python
class LogAnalysis:
    """日志分析"""

    FFMPEG_LOG_LEVELS = {
        'quiet':   '-v quiet   # 无输出',
        'panic':   '-v panic   # 仅致命错误',
        'fatal':   '-v fatal   # 致命错误',
        'error':   '-v error   # 错误',
        'warning': '-v warning # 警告(推荐)',
        'info':    '-v info    # 信息(默认)',
        'verbose': '-v verbose # 详细',
        'debug':   '-v debug   # 调试',
        'trace':   '-v trace   # 跟踪(最详细)',
    }

    LOG_ANALYSIS_PATTERNS = {
        'drop_frames': {
            'pattern': 'drop=\\d+',
            'meaning': '丢帧数',
            'action': '检查编码性能/带宽',
        },
        'dup_frames': {
            'pattern': 'dup=\\d+',
            'meaning': '重复帧数',
            'action': '检查帧率设置',
        },
        'bitrate_warning': {
            'pattern': 'bitrate tolerance',
            'meaning': '码率超出容差',
            'action': '调整 maxrate/bufsize',
        },
        'rtmp_error': {
            'pattern': 'RTMP_HandleInvoke|RTMP_Connect',
            'meaning': 'RTMP 连接/调用错误',
            'action': '检查服务器地址/推流码',
        },
        'encoding_error': {
            'pattern': 'Error while opening encoder|Invalid argument',
            'meaning': '编码器打开失败',
            'action': '检查编码器参数',
        },
        'network_timeout': {
            'pattern': 'Connection refused|timeout',
            'meaning': '网络连接失败',
            'action': '检查网络/防火墙',
        },
    }

    PROGRESS_MONITORING = {
        'desc': '进度监控',
        'command': 'ffmpeg -i input -c copy output -progress pipe:1 2>/dev/null',
        'output_format': 'frame=1234 fps=30.0 stream_size=12345678 out_time_ms=41000000 bitrate=6000000 speed=1.0x',
        'parse_script': '''import sys
for line in sys.stdin:
    line = line.strip()
    if line.startswith('frame='):
        print(f"帧: {line.split('=')[1]}")
    elif line.startswith('fps='):
        print(f"FPS: {line.split('=')[1]}")
    elif line.startswith('bitrate='):
        print(f"码率: {int(line.split('=')[1])/1000:.0f} kbps")
    elif line.startswith('speed='):
        print(f"速度: {line.split('=')[1]}")
    elif line == 'progress=end':
        print("完成")
        break''',
    }
```

---

## 十、安全与鉴权

### 10.1 推流鉴权

```python
class PushAuthentication:
    """推流鉴权原子模型"""

    AUTH_METHODS = {
        'token_based': {
            'desc': 'Token 鉴权(最常用)',
            'method': '推流URL携带动态Token,服务器验证',
            'url_format': 'rtmp://server/live/stream?token=abc123&expire=1234567890',
            'token_generation': 'MD5(stream_key + secret + timestamp)',
            'srs_config': 'on_publish http://localhost:8080/auth;',
            'auth_script': '''# SRS on_publish 鉴权脚本 (Python Flask)
from flask import Flask, request, abort
import hashlib

app = Flask(__name__)
SECRET = "your_secret_key"

@app.route('/auth', methods=['POST'])
def auth():
    stream_key = request.form.get('name', '')
    token = request.args.get('token', '')
    expire = request.args.get('expire', '0')
    
    expected = hashlib.md5(f"{stream_key}{SECRET}{expire}".encode()).hexdigest()
    
    if token == expected:
        return "OK", 200
    else:
        abort(403)
''',
        },
        'signature_based': {
            'desc': '签名鉴权',
            'method': '基于 HMAC-SHA256 的签名',
            'url_format': 'rtmp://server/live/stream?sign=<hmac>&ts=<timestamp>',
            'sign_generation': 'HMAC-SHA256(secret, stream_id + timestamp)',
        },
        'ip_whitelist': {
            'desc': 'IP 白名单',
            'method': '限制推流IP',
            'config': 'nginx-rtmp: allow publish 192.168.1.0/24; deny publish all;',
        },
        'rtmps': {
            'desc': 'RTMP over TLS',
            'method': 'RTMP + TLS 加密',
            'port': '443 (通常)',
            'command': 'ffmpeg -i input -c copy -f flv "rtmps://server:443/live/stream"',
        },
        'srt_passphrase': {
            'desc': 'SRT 加密',
            'method': 'AES-128/192/256',
            'params': 'passphrase=MyPassword&pbkeylen=32',
        },
    }
```

### 10.2 播放鉴权与防盗链

```python
class PlaybackSecurity:
    """播放鉴权与防盗链"""

    PLAYBACK_AUTH = {
        'signed_url': {
            'desc': '签名URL(限时播放)',
            'method': '生成带过期时间的签名URL',
            'cdn_example': 'https://cdn.com/stream.m3u8?sign=abc123&expire=1234567890',
            'generation': 'MD5(path + secret + expire_time)',
        },
        'referer_check': {
            'desc': 'Referer 检查',
            'method': '检查 HTTP Referer 头',
            'nginx_config': '''
valid_referers none blocked example.com *.example.com;
if ($invalid_referer) {
    return 403;
}''',
        },
        'ip_restriction': {
            'desc': 'IP 限制',
            'method': '基于 IP 的访问控制',
            'config': 'allow 192.168.1.0/24; deny all;',
        },
        'geo_restriction': {
            'desc': '地域限制',
            'method': '基于 GeoIP 的地域控制',
            'nginx_config': '''
geoip_country /usr/share/GeoIP/GeoIP.dat;
map $geoip_country_code $allowed_country {
    default no;
    CN yes;
    US yes;
}
if ($allowed_country = no) {
    return 403;
}''',
        },
    }

    DRM_INTEGRATION = {
        'apple_fairplay': {
            'desc': 'Apple FairPlay DRM (HLS)',
            'method': 'SAMPLE-AES + FPS密钥服务器',
            'use': 'iOS/macOS 设备',
            'hls_config': 'EXT-X-KEY:METHOD=SAMPLE-AES,URI=skd://key-server,KEYFORMAT=...,...',
        },
        'google_widevine': {
            'desc': 'Google Widevine DRM (DASH/HLS)',
            'method': 'CENC (Common Encryption)',
            'use': 'Chrome/Android/Firefox',
            'dash_config': 'ContentProtection schemeIdUri="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"',
        },
        'microsoft_playready': {
            'desc': 'Microsoft PlayReady DRM (DASH/HLS)',
            'method': 'CENC',
            'use': 'Edge/Windows/Xbox',
            'dash_config': 'ContentProtection schemeIdUri="urn:uuid:9a04f079-9840-4286-ab92-e65be0885f95"',
        },
        'multi_drm': {
            'desc': '多DRM(CENC)',
            'method': 'Common Encryption 一次加密,多DRM解密',
            'use': '跨平台(同时支持 FairPlay/Widevine/PlayReady)',
        },
    }
```

---

## 附录

### 附录 A: 流媒体命令速查表

```bash
# === RTMP ===
# 推流
ffmpeg -re -i input.mp4 -c:v h264_nvenc -preset p4 -b:v 6M -c:a aac -b:a 128k -f flv "rtmp://server/live/key"

# 拉流录制
ffmpeg -i "rtmp://server/live/key" -c copy output.mp4

# RTMP 转 HLS
ffmpeg -i "rtmp://server/live/key" -c copy -f hls -hls_time 6 -hls_list_size 10 output.m3u8

# === HLS ===
# 直播
ffmpeg -re -i input.mp4 -c:v h264_nvenc -preset p4 -b:v 4M -c:a aac -b:a 128k -f hls -hls_time 6 -hls_list_size 10 -hls_flags delete_segments stream.m3u8

# 点播
ffmpeg -i input.mp4 -c:v h264_nvenc -preset p7 -b:v 5M -c:a aac -b:a 128k -f hls -hls_time 10 -hls_playlist_type vod vod.m3u8

# 多码率
ffmpeg -re -i input.mp4 -filter_complex "[0:v]split=3[v1][v2][v3];[v1]scale=1920:1080[v1out];[v2]scale=1280:720[v2out];[v3]scale=854:480[v3out]" -map "[v1out]" -c:v:0 h264_nvenc -b:v:0 5M -map "[v2out]" -c:v:1 h264_nvenc -b:v:1 3M -map "[v3out]" -c:v:2 h264_nvenc -b:v:2 1.5M -map a:0 -c:a:0 aac -f hls -master_pl_name master.m3u8 -var_stream_map "v:0,a:0 v:1,a:0 v:2,a:0" stream_%v.m3u8

# 加密
ffmpeg -i input.mp4 -c:v h264_nvenc -b:v 5M -f hls -hls_key_info_file key_info encrypted.m3u8

# === DASH ===
ffmpeg -i input.mp4 -c:v h264_nvenc -preset p7 -b:v 5M -c:a aac -b:a 128k -use_template 1 -use_timeline 1 -adaptation_sets "id=0,streams=v:0 id=1,streams=a:0" -f dash manifest.mpd

# === SRT ===
# 推流
ffmpeg -re -i input.mp4 -c:v h264_nvenc -b:v 4M -c:a aac -b:a 128k -f mpegts "srt://server:9000?stream_id=live/stream"

# 加密推流
ffmpeg -re -i input.mp4 -c:v h264_nvenc -b:v 4M -c:a aac -f mpegts "srt://server:9000?stream_id=live/stream&passphrase=MyPass123&pbkeylen=32"

# 拉流
ffmpeg -i "srt://server:9000?stream_id=live/stream&mode=caller" -c copy output.ts

# === WebRTC (WHIP/WHEP) ===
ffmpeg -re -i input.mp4 -c:v libx264 -tune zerolatency -b:v 2M -c:a libopus -f webrtc "http://whip-server/whip/endpoint"

# === 多平台同时推流 ===
ffmpeg -re -i input.mp4 -c:v h264_nvenc -preset p4 -b:v 6M -c:a aac -b:a 128k -f tee "[f=flv]rtmp://bili/live/key|[f=flv]rtmp://yt/live/key|[f=flv]rtmp://twitch/live/key"

# === 录制 + 直播 ===
ffmpeg -re -i input.mp4 -c:v h264_nvenc -preset p4 -b:v 6M -c:a aac -b:a 128k -map 0 -f flv "rtmp://server/live/key" -map 0 -c copy recording.mp4

# === 健康检查 ===
ffprobe -v quiet -print_format json -show_streams "rtmp://server/live/key"
```

### 附录 B: 协议参数对比表

| 协议 | 传输层 | 端口 | 典型延迟 | 加密 | 自适应码率 | CDN友好 | 浏览器原生 |
|------|--------|------|----------|------|-----------|---------|-----------|
| RTMP | TCP | 1935 | 2-10s | RTMPS(TLS) | 否 | 一般 | 否 |
| RTSP | TCP/UDP | 554 | 0.5-2s | SRTP | 否 | 差 | 否 |
| HLS | HTTP | 80/443 | 5-30s | AES-128/DRM | 是 | 极佳 | Safari |
| LL-HLS | HTTP | 80/443 | 2-5s | AES-128/DRM | 是 | 极佳 | iOS15+/Safari15+ |
| DASH | HTTP | 80/443 | 5-30s | AES-128/DRM | 是 | 极佳 | Chrome/Edge/Firefox |
| SRT | UDP | 自定义 | 0.1-2s | AES-128/256 | 否 | 一般 | 否 |
| RIST | UDP | 自定义 | 0.1-1s | AES-128 | 否 | 一般 | 否 |
| WebRTC | UDP | 自定义 | <0.5s | SRTP/DTLS | 部分(Simulcast) | 增长中 | 全平台 |
| HTTP-FLV | HTTP | 80/443 | 1-3s | HTTPS | 否 | 极佳 | 需flv.js |

### 附录 C: 常见平台推流参数

| 平台 | 协议 | 推荐编码器 | 1080p码率 | 720p码率 | 最大帧率 | GOP | B帧 |
|------|------|-----------|----------|---------|---------|-----|-----|
| B站 | RTMP | H.264 | 6-10 Mbps | 3-5 Mbps | 60 | 120 | 2 |
| YouTube | RTMP | H.264 | 9-12 Mbps | 5-7 Mbps | 60 | 120 | 2 |
| Twitch | RTMP | H.264 | 6-8 Mbps | 4-5 Mbps | 60 | 120 | 2 |
| 抖音 | RTMP | H.264 | 4-6 Mbps | 2-4 Mbps | 60 | 120 | 2 |
| 快手 | RTMP | H.264 | 4-6 Mbps | 2-4 Mbps | 60 | 120 | 2 |
| 微信视频号 | RTMP | H.264 | 4-6 Mbps | 2-4 Mbps | 30 | 60 | 2 |
| 小红书 | RTMP | H.264 | 4-6 Mbps | 2-4 Mbps | 30 | 60 | 2 |
| Facebook | RTMP | H.264 | 6 Mbps | 3-4 Mbps | 60 | 120 | 2 |

### 附录 D: 故障排查流程图

```python
class TroubleshootingFlowchart:
    """故障排查流程"""

    FLOWCHART = {
        'step_1': {
            'q': '推流是否成功?',
            'yes': 'goto step_2',
            'no': 'goto step_5',
        },
        'step_2': {
            'q': '播放器是否可以拉流?',
            'yes': 'goto step_3',
            'no': '检查: 1.服务器配置 2.防火墙 3.播放地址',
        },
        'step_3': {
            'q': '画面是否正常?',
            'yes': 'goto step_4',
            'no': '检查: 1.编码参数 2.像素格式 3.分辨率 4.色彩空间',
        },
        'step_4': {
            'q': '延迟是否可接受?',
            'yes': '完成',
            'no': '优化: 1.GOP 2.B帧 3.缓冲 4.协议 5.播放器缓冲',
        },
        'step_5': {
            'q': '错误信息?',
            'options': {
                'Connection refused': '检查服务器/端口/防火墙',
                'Auth failed': '检查推流码/鉴权',
                'Encoder not found': '检查FFmpeg编译选项',
                'Format error': '检查容器格式(FLV仅支持H.264+AAC)',
                'Permission denied': '检查文件/目录权限',
                'Network timeout': '检查网络连接/带宽',
            },
        },
    }

    QUICK_FIX = {
        '卡顿': [
            '降低码率',
            '降低分辨率',
            '使用硬件编码器',
            '检查上行带宽',
            '减小缓冲',
        ],
        '延迟高': [
            '减小GOP',
            '禁用B帧(-bf 0)',
            '使用 -tune zerolatency / -tune ll',
            '减小缓冲(-bufsize)',
            '使用低延迟协议(SRT/WebRTC)',
            '添加 -flush_packets 1',
        ],
        '音画不同步': [
            '使用 -async 1 -vsync 1',
            '检查音频采样率',
            '添加 -af aresample=async=1',
        ],
        '花屏': [
            '检查网络丢包',
            '增加缓冲',
            '降低码率',
            '检查编码参数',
        ],
        '黑屏': [
            '检查视频源',
            '检查编码器是否支持输入格式',
            '检查像素格式',
        ],
        '无声音': [
            '检查音频源',
            '检查音频编码器',
            '检查音频流映射(-map)',
        ],
    }
```

---

> **版本**: 2026.07 | **标准**: 实验研究原子级别 | **适用**: FFmpeg 6.0+ / 7.0+
> **覆盖协议**: RTMP / SRT / RIST / HLS / LL-HLS / DASH / WebRTC / WHIP / WHEP / RTSP
> **更新日志**: 2026.07 初版，覆盖全主流流媒体协议与低延迟传输方案
