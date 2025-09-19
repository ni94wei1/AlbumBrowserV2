import subprocess
import sys
from pathlib import Path

photo_path = Path(r"E:\测试目录\1\653A7189.jpg")

def get_rating(file_path: Path) -> int:
    result = subprocess.run(
        ["exiftool", "-Rating", "-s3", str(file_path)],
        capture_output=True, text=True, encoding="mbcs", errors="ignore"  # ← 修改
    )
    if result.returncode != 0:
        raise RuntimeError(f"读取评级失败: {result.stderr.strip()}")
    rating_str = result.stdout.strip()
    return int(rating_str) if rating_str.isdigit() else 0

def set_rating(file_path: Path, stars: int):
    if stars < 0 or stars > 5:
        raise ValueError("星级必须是 0-5 之间的整数")
    result = subprocess.run(
        ["exiftool", f"-Rating={stars}", "-overwrite_original", str(file_path)],
        capture_output=True, text=True, encoding="mbcs", errors="ignore"  # ← 修改
    )
    if result.returncode != 0:
        raise RuntimeError(f"写入评级失败: {result.stderr.strip()}")

if __name__ == "__main__":
    current = get_rating(photo_path)
    print(f"当前评级: {current}⭐")

    if len(sys.argv) > 1:
        new_rating = int(sys.argv[1])
        set_rating(photo_path, new_rating)
        print(f"已将评级设置为 {new_rating}⭐")
