import io, os, mimetypes
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from flask import current_app

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def drive_upload(local_path: str, filename: str) -> str:
    """
    指定ファイルを Google Drive にアップロードし、
    一般閲覧可能リンク (webContentLink) を返す
    """
    service = get_drive_service()
    file_metadata = {
        "name": filename,
        "parents": [os.getenv("GOOGLE_DRIVE_PARENT_ID")]
    }
    mime_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    media = MediaIoBaseUpload(open(local_path, "rb"), mimetype=mime_type, resumable=True)

    f = service.files().create(body=file_metadata, media_body=media, fields="id, webViewLink, webContentLink").execute()

    # 任意: 公開権限を「リンクを知る全員閲覧可」にする
    service.permissions().create(
        fileId=f["id"],
        body={"role": "reader", "type": "anyone"},
    ).execute()

    return f["webViewLink"]     # ダウンロード直リンクは webContentLink
