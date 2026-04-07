#!/usr/bin/env python3
"""
通过飞书 Bot API 发送文件到指定群
（Webhook 不支持文件发送，需要配置飞书自建应用）

用法：
  python3 send-feishu-file.py <file_path> <chat_id> <app_id> <app_secret>

配置方式：
  openclaw config set skills.entries.feishu_news.env.FEISHU_APP_ID      "<app_id>"
  openclaw config set skills.entries.feishu_news.env.FEISHU_APP_SECRET  "<app_secret>"
  openclaw config set skills.entries.summarize.env.FEISHU_MORNING_CHAT_ID "<chat_id>"
"""
import sys, json, os
import urllib.request
import urllib.parse

BASE = "https://open.feishu.cn/open-apis"


def get_token(app_id: str, app_secret: str) -> str:
    url  = f"{BASE}/auth/v3/tenant_access_token/internal"
    body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req  = urllib.request.Request(url, data=body,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)
    if data.get("code") != 0:
        raise RuntimeError(f"获取 token 失败: {data.get('msg')}")
    return data["tenant_access_token"]


def upload_file(token: str, file_path: str) -> str:
    filename = os.path.basename(file_path)
    filesize = os.path.getsize(file_path)

    # multipart/form-data 手动构建
    boundary = "----FeishuNewsBoundary7x24"
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    parts = []
    parts.append(
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file_type"\r\n\r\n'
        f'pdf\r\n'.encode()
    )
    parts.append(
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file_name"\r\n\r\n'
        f'{filename}\r\n'.encode()
    )
    parts.append(
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f'Content-Type: application/pdf\r\n\r\n'.encode() + file_bytes + b'\r\n'
    )
    parts.append(f'--{boundary}--\r\n'.encode())
    body = b"".join(parts)

    url = f"{BASE}/im/v1/files"
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if data.get("code") != 0:
        raise RuntimeError(f"文件上传失败: {data.get('msg')}")
    return data["data"]["file_key"]


def send_file_message(token: str, chat_id: str, file_key: str, caption: str = "") -> None:
    url  = f"{BASE}/im/v1/messages?receive_id_type=chat_id"
    body = json.dumps({
        "receive_id": chat_id,
        "msg_type":   "file",
        "content":    json.dumps({"file_key": file_key}),
    }).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Authorization":  f"Bearer {token}",
            "Content-Type":   "application/json",
        }
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)
    if data.get("code") != 0:
        raise RuntimeError(f"发送消息失败: {data.get('msg')}")

    # 发送说明文字（可选）
    if caption:
        body2 = json.dumps({
            "receive_id": chat_id,
            "msg_type":   "text",
            "content":    json.dumps({"text": caption}),
        }).encode()
        req2 = urllib.request.Request(
            url, data=body2,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
            }
        )
        with urllib.request.urlopen(req2, timeout=10):
            pass


def main():
    if len(sys.argv) < 5:
        print("用法: python3 send-feishu-file.py <file_path> <chat_id> <app_id> <app_secret>")
        sys.exit(1)

    file_path, chat_id, app_id, app_secret = sys.argv[1:5]

    if not os.path.exists(file_path):
        print(f"ERROR: 文件不存在: {file_path}")
        sys.exit(1)

    try:
        token    = get_token(app_id, app_secret)
        file_key = upload_file(token, file_path)
        caption  = f"📰 早报已发送 · {os.path.basename(file_path)}"
        send_file_message(token, chat_id, file_key, caption)
        print(f"SENT:{file_path}")
    except Exception as e:
        print(f"ERROR:{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
