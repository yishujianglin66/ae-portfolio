import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from douyin_downloader_pro import DouyinDownloaderPro

async def test():
    downloader = DouyinDownloaderPro()
    
    print("Cookie validation:")
    result = downloader.validate_cookie()
    print(result)
    
    print("\nGetting video info:")
    info = await downloader.get_video_info("7515063317476527397")
    print(info)
    
    print("\nDownloading video:")
    result = await downloader.download_video("7515063317476527397")
    print(result)

if __name__ == "__main__":
    asyncio.run(test())