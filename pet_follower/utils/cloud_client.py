# pet_follower/cloud_client.py
import io
import requests
import cv2

SERVER_IP = "192.168.1.246"  # 换成你电脑的 IP
SERVER_URL = f"http://{SERVER_IP}:5000/api/upload-image"

def send_frame_bgr(frame):
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        print("[cloud_client] encode failed")
        return

    img_bytes = io.BytesIO(buf.tobytes())
    files = {"image": ("frame_from_pi.jpg", img_bytes, "image/jpeg")}

    try:
        resp = requests.post(SERVER_URL, files=files, timeout=10)
        print("[cloud_client] status:", resp.status_code)
        try:
            print("[cloud_client] json:", resp.json())
        except Exception:
            print("[cloud_client] text:", resp.text)
    except Exception as e:
        print("[cloud_client] error:", e)
