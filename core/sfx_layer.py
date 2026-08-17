def _load_index(): return []
def plan_sfx(beats, seed=0, pools_override=None): return []
def mix_sfx(src, dst, sfx):
    import shutil
    try: shutil.copy2(src,dst); return True
    except OSError: return False
