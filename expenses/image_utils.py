from pathlib import Path
from PIL import Image, ImageOps

def normalize_to_jpeg(src_path: Path, long_edge: int = 2000, quality: int = 85) -> Path:
    """
    任意フォーマット（HEIC/HEIF/WEBP/PNG/JPEGなど）をJPEGに正規化。
    - EXIF回転補正
    - 長辺を long_edge に縮小（アスペクト維持）
    - JPEG品質 quality, optimize=True
    戻り値: 変換後の .jpg パス
    """
    src_path = Path(src_path)
    dst_path = src_path.with_suffix(".jpg")

    with Image.open(src_path) as im:
        im = ImageOps.exif_transpose(im)
        im.thumbnail((long_edge, long_edge))
        im.save(dst_path, format="JPEG", quality=quality, optimize=True)

    return dst_path
