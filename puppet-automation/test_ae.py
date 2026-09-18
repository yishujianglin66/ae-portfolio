import asyncio

from src.config.settings import settings
from src.engines.ae.engine import AEEngine


async def main():
    engine = AEEngine()
    script = '(function(){return JSON.stringify({success:true,projectName:app.project.file.name,numComps:app.project.numItems});})();'
    result = await engine.run_script(script, 'D:/AE-Work/resources/projects/53动漫/25版打开.aep')
    print(f"Success: {result.success}")
    print(f"Metadata: {result.metadata}")
    if result.error:
        print(f"Error: {result.error}")

asyncio.run(main())