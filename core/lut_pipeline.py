def load_sampling(): return {}
def transcode_with_lut(src,dst,cube,strength=1.0,crf=17):
    import shutil
    try: shutil.copy2(src,dst); return True
    except OSError: return False
