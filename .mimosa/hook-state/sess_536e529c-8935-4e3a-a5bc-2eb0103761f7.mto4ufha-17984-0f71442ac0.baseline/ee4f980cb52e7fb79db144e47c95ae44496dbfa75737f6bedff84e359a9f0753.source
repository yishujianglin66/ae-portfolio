import os, sys
sys.stdout.reconfigure(encoding='utf-8')

clip_base = "D:/AE-Work/视频素材库/冰海战记新素材/"

# List all files with their exact bytes
print("=== Exact filenames in clip directory ===")
for f in sorted(os.listdir(clip_base)):
    if f.endswith('.mp4'):
        # Show the special characters
        print(f"File: {f}")
        # Find special chars
        for i, c in enumerate(f):
            if ord(c) > 127 and c not in '冰海战记收藏季全合集冰海战记第一季最后的封神场面授权转载第二季最精彩的打戏托尔芬蛇【】':
                print(f"  pos {i}: U+{ord(c):04X} = '{c}'")
        print()

# The JSX SOURCES dict constructs paths like:
# CLIP_PATH + SOURCES["MUKANJYO"]
# Let's verify each constructed path
sources_jsx = {
    "MUKANJYO":  "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p01 S1OP1-MUKANJYO.f30077.mp4",
    "TORCHES":   "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p02 S1ED1-Torches.f30080.mp4",
    "DarkCrow":  "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p03 S1OP2-Dark Crow.f30077.mp4",
    "RIVER":     "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p05 S2OP1-River.f30077.mp4",
    "PARADOX":   "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p07 S2OP2-Paradox.f30080.mp4",
    "EPIC_S1":   "vinland_2_冰海战记第一季：最后的封神场面.f30080.mp4",
    "FIGHT_S2":  "vinland_3_【授权转载】冰海战记第二季最精彩的打戏 托尔芬VS蛇.f30077.mp4",
    "MAD_4K":    "vinland_4_4K_MAD.f30077.mp4",
    "MAD_REV":   "vinland_5_【MAD⧸冰海战记】There's a revolution coming!.f30080.mp4"
}

print("\n=== Path verification (Python os.path.exists) ===")
for name, fname in sources_jsx.items():
    full = os.path.join(clip_base, fname)
    exists = os.path.exists(full)
    print(f"  {name}: {'EXISTS' if exists else 'MISSING'}")
    if not exists:
        # Try to find similar
        for actual in os.listdir(clip_base):
            if fname[:20] in actual:
                print(f"    Similar: {actual}")
                # Show char differences
                for j in range(min(len(fname), len(actual))):
                    if j < len(fname) and j < len(actual) and fname[j] != actual[j]:
                        print(f"    Diff at pos {j}: JSX=U+{ord(fname[j]):04X}('{fname[j]}') vs Actual=U+{ord(actual[j]):04X}('{actual[j]}')")
                break
