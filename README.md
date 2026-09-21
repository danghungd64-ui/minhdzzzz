# 🎲 Tai Xiu Prediction API

API dự đoán Tài Xỉu theo session ID thực tế, tự động chạy cầu từ phiên cuối đến `target_session`.

## 📦 Cài đặt local

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở http://127.0.0.1:8000/docs để test qua Swagger UI.

## 🔌 Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/` | Health check |
| POST | `/predict` | Dự đoán phiên kế tiếp + forecast đến `target_session` |
| POST | `/forecast` | Chỉ mô phỏng chuỗi cầu đến `target_session` |

## 🧪 Test nhanh

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d @test_request.json
```

## 🚀 Deploy Render

1. Push code lên GitHub
2. Vào https://dashboard.render.com → **New +** → **Web Service**
3. Connect repo GitHub
4. Cấu hình:
   - **Runtime**: Python 3
   - **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Region**: Singapore
   - **Plan**: Free
5. Bấm **Create Web Service**

Hoặc dùng `render.yaml` — Render sẽ tự đọc config khi bạn tạo Blueprint.

## ⚠️ Lưu ý

- Free instance sẽ sleep sau 15 phút → request đầu tiên mất ~50s
- Dùng https://uptimerobot.com ping mỗi 5 phút để giữ alive
- `pydantic` phải là 2.10.6 để tránh lỗi build `metadata-generation-failed` trên Python 3.14
