# AE Export Template
# AE导出模板 - 生成AE兼容的输出数据

import json
import os

from fx import *


def export_to_ae(source_path, output_dir, export_type="matte", comp_size=[1920, 1080]):
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    ae_data = {
        "version": "2.0",
        "source": "silhouette",
        "timestamp": datetime.now().isoformat(),
        "aeIntegration": {
            "compName": "Silhouette_Integration",
            "importPath": output_dir.replace("\\", "/") + "/",
            "applyAs": "track_matte" if export_type == "matte" else "tracking_data",
            "targetLayer": "selected",
            "matteMode": "alpha",
        },
    }

    if export_type == "matte":
        matte_path = os.path.join(output_dir, "matte_[####].exr").replace("\\", "/")
        ae_data["roto"] = {
            "matteSequence": matte_path,
            "shapeType": "x-spline",
            "frameRange": [0, 0],
            "resolution": comp_size,
        }

    if export_type == "tracking":
        ae_data["tracking"] = {
            "trackers": [],
            "exportFormat": "ae_keyframes",
            "nullObjectName": "Silhouette_Tracker",
        }

    output_file = os.path.join(output_dir, f"silhouette_export_{export_type}_{int(time.time())}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(ae_data, f, indent=2, ensure_ascii=False)

    print(f"[SILHOUETTE] Exported to AE format: {output_file}")
    return output_file

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        export_to_ae(sys.argv[1], sys.argv[2])
    else:
        print("Usage: ae_export.py <source_path> <output_dir> [matte|tracking]")
