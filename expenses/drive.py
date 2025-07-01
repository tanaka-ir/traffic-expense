from __future__ import annotations
import os, mimetypes
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http      import MediaFileUpload
from google.oauth2             import service_account
from PIL import Image
import pyheif

DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_ID", "xxxxxxxxxxxxxxxxxxxx")

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def _convert_heic_to_jpg(src_path: str) -> tuple[str, str]:
    heif = pyheif.read(src_path)
    img  = Image.frombytes(heif.mode, heif.size, heif.data,
                           "raw", heif.mode, heif.stride)
    dst  = Path(src_path).with_suffix(".jpg")
    img.save(dst, "JPEG", quality=90)
    return str(dst), dst.name

def drive_upload(local_path: str, filename: str) -> str:
    if local_path.lower().endswith(".heic"):
        local_path, filename = _convert_heic_to_jpg(local_path)

    service = get_drive_service()
    meta  = {"name": filename, "parents": [DRIVE_FOLDER_ID]}
    mime  = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    media = MediaFileUpload(local_path, mimetype=mime, resumable=True)

    res = service.files().create(body=meta, media_body=media, fields="id").execute()
    file_id = res["id"]

    service.permissions().create(
        fileId=file_id, body={"role": "reader", "type": "anyone"}
    ).execute()

    return f"https://drive.google.com/uc?export=view&id={file_id}"
