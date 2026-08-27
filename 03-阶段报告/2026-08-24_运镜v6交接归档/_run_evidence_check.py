from pathlib import Path
import collections, json

files = [
    r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\cloud_labels\vlm_labels_v2new.jsonl',
    r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\cloud_labels\v5_6_labels_washed.jsonl',
    r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\cloud_labels\suspect_review.jsonl',
    r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\recheck_suspects.py',
    r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\cloud_labels\suspect_rechecked.jsonl',
    r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\cloud_labels\suspect_errors.jsonl',
    r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\cloud_labels\v5_6_labels_final.jsonl',
    r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\cloud_labels\v6_meta_4class.jsonl',
    r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\_F1_meta_4class.py',
    r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\scripts\train_anime_camera_v5.py',
]

out_lines = []
out_lines.append('===== EVIDENCE GATE 1: EXISTENCE CHECK (2026-08-24 09:12 session) =====')
all_ok = True
for f in files:
    p = Path(f)
    if p.exists():
        size = p.stat().st_size
        lines = ''
        if f.endswith('.jsonl'):
            try:
                with open(p, 'r', encoding='utf-8') as fh:
                    n = sum(1 for _ in fh)
                lines = f' {n} lines'
            except:
                pass
        out_lines.append(f'OK   {size:>11d} bytes{lines}   {p.name}')
    else:
        out_lines.append(f'MISS                                       {p.name}')
        all_ok = False
out_lines.append('')

cnt = None
fields_example = None
first_line = None
p4 = Path(r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\cloud_labels\v6_meta_4class.jsonl')
if p4.exists():
    cnt = collections.Counter()
    with open(p4, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if first_line is None:
                first_line = line[:400]
            try:
                r = json.loads(line)
                if fields_example is None:
                    fields_example = list(r.keys())
                lb = r.get('label') or r.get('meta_label') or r.get('movement_label')
                cnt[lb] += 1
            except:
                pass
    out_lines.append('===== EVIDENCE GATE 2: FIRST-LINE + DISTRIBUTION (v6_meta_4class.jsonl, READY) =====')
    out_lines.append(f'Total rows: {sum(cnt.values())}')
    out_lines.append(f'字段清单: {fields_example}')
    out_lines.append(f'首行样本 (真实JSON, 字段核验): {first_line}')
    out_lines.append('4 元类真实分布 (Counter实测):')
    total = sum(cnt.values())
    for k, v in cnt.most_common():
        out_lines.append(f'  {k:24s}: {v:5d}  {v/total*100:5.2f}%')
    gini = 1 - sum((v/total) ** 2 for v in cnt.values())
    out_lines.append(
        f'Gini 系数 (越小越均匀): {gini:.4f}  [v5_6 6类 Gini=0.7123, arrow-down '
        f'{(0.7123 - gini) / 0.7123 * 100:.1f}%]'
    )
out_lines.append('')

EXP_4 = {'meta-static', 'meta-pan', 'meta-tilt-orbit', 'meta-zoom'}
out_lines.append('===== EVIDENCE GATE 3: 任务签名三对齐 (模型签名 x 数据签名 x 类名清单) =====')
if cnt is not None:
    got = set(cnt.keys())
    out_lines.append(f'预期类名清单 (Trainer num_classes=4): {sorted(EXP_4)}')
    out_lines.append(f'实际 JSONL label 值 (Counter 键):    {sorted(got)}')
    out_lines.append(f'交集: {sorted(EXP_4 & got)}')
    if EXP_4 == got:
        status = 'CHECK 三签名完全一致 (可启动训练)'
    else:
        status = 'CROSS 类名不匹配，请修正映射'
    out_lines.append(f'对齐状态: {status}')
else:
    out_lines.append('SKIP v6_meta_4class.jsonl 不存在，无法核验三对齐')
out_lines.append('')

if all_ok:
    global_status = 'CHECK 全部 READY 文件存在'
else:
    global_status = 'CROSS 存在 MISS，先补文件'
out_lines.append(f'===== 闸门1 全局: {global_status} =====')

out = '\n'.join(out_lines)
print(out)
with open(
    r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\evidence_report_20260824.txt',
    'w',
    encoding='utf-8',
) as f:
    f.write(out + '\n')
