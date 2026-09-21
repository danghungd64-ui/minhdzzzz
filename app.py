"""
Tai Xiu Prediction API v3.0.0
Deploy trên Render: https://minhdzzzz-2.onrender.com
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import hashlib
import time
import random

app = Flask(__name__)
CORS(app)  # Cho phép mọi domain gọi API (cần cho tool HTML)

# ============================================================
# CẤU HÌNH
# ============================================================
VERSION = "3.0.0"
SERVICE_NAME = "Tai Xiu Prediction API"
FEATURES = ["predict", "bridge_forecast", "session_follow"]

# Lưu session tạm thời trong memory
sessions = {}


# ============================================================
# ROOT ENDPOINT - Kiểm tra API online
# ============================================================
@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "status": "online",
        "service": SERVICE_NAME,
        "version": VERSION,
        "features": FEATURES,
        "docs_url": "/docs"
    })


# ============================================================
# HEALTH CHECK
# ============================================================
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": int(time.time()),
        "version": VERSION
    })


# ============================================================
# THUẬT TOÁN DỰ ĐOÁN TÀI XỈU (nâng cao)
# ============================================================
def predict_tai_xiu(md5_hash: str) -> dict:
    """
    Thuật toán dự đoán dựa trên MD5 hashhex.
   dig Kết hợp nhiều vùng dữ liệu để tăng độ phân tán.
    """
    if not md5_hash or len(md5_hash) < 32:
        # Fallback nếu hash không hợp lệ
        md5_hash = hashlib.md5(str(time.time()).encode()).est()

    try:
        # Lấy 3 vùng dữ liệu từ hash
        head = int(md5_hash[0:8], 16)
        mid = int(md5_hash[8:16], 16)
        tail = int(md5_hash[-8:], 16)

        # Kết hợp với hệ số nguyên tố
        combined = (head * 13 + mid * 17 + tail * 31) & 0xFFFFFFFF

        # XOR diffusion (tăng độ ngẫu nhiên)
        combined ^= (combined >> 16)
        combined = (combined * 0x9E3779B9) & 0xFFFFFFFF
        combined ^= (combined >> 13)
        combined = (combined * 0x85EBCA6B) & 0xFFFFFFFF
        combined ^= (combined >> 16)

        # Trích xuất xác suất
        last_byte = combined & 0xFF
        second_byte = (combined >> 8) & 0xFF

        # Tính % Tài (dao động 25% - 75%)
        tai_percent = ((last_byte / 255) * 50) + 25
        tai_percent += ((second_byte / 255) * 10) - 5
        tai_percent = max(25, min(75, tai_percent))

        # Làm tròn
        tai_percent = round(tai_percent, 1)
        xiu_percent = round(100 - tai_percent, 1)

        result = "Tài" if tai_percent >= 50 else "Xỉu"
        confidence = round(max(tai_percent, xiu_percent))

        return {
            "success": True,
            "result": result,
            "prediction": result.lower(),
            "confidence": confidence,
            "tai_percent": tai_percent,
            "xiu_percent": xiu_percent,
            "algorithm": "MD5 Hybrid Diffusion v3",
            "version": VERSION
        }

    except Exception as e:
        # Nếu có lỗi, trả về fallback
        return {
            "success": False,
            "result": "Tài",
            "prediction": "tai",
            "confidence": 50,
            "tai_percent": 50.0,
            "xiu_percent": 50.0,
            "algorithm": "Fallback",
            "error": str(e),
            "version": VERSION
        }


# ============================================================
# ENDPOINT /predict - POST (chính)
# ============================================================
@app.route('/predict', methods=['POST'])
def predict_post():
    data = request.get_json(silent=True) or {}

    # Nhận md5 hoặc hash từ nhiều key khác nhau
    md5_hash = data.get('md5') or data.get('hash') or data.get('input') or ''

    if not md5_hash:
        return jsonify({
            "success": False,
            "error": "Missing 'md5' or 'hash' field",
            "hint": "Send JSON: {\"md5\": \"your_hash_here\"}"
        }), 400

    md5_hash = str(md5_hash).strip()
    result = predict_tai_xiu(md5_hash)

    # Thêm thông tin session
    session_id = hashlib.md5(
        (md5_hash + str(int(time.time() // 60))).encode()
    ).hexdigest()[:12]

    result["session"] = session_id
    result["input_hash"] = md5_hash

    return jsonify(result)


# ============================================================
# ENDPOINT /predict - GET
# ============================================================
@app.route('/predict', methods=['GET'])
def predict_get():
    md5_hash = request.args.get('md5') or request.args.get('hash') or ''

    if not md5_hash:
        return jsonify({
            "success": False,
            "error": "Missing 'md5' query parameter",
            "hint": "Call: /predict?md5=your_hash"
        }), 400

    md5_hash = str(md5_hash).strip()
    result = predict_tai_xiu(md5_hash)

    session_id = hashlib.md5(
        (md5_hash + str(int(time.time() // 60))).encode()
    ).hexdigest()[:12]

    result["session"] = session_id
    result["input_hash"] = md5_hash

    return jsonify(result)


# ============================================================
# ENDPOINT /bridge_forecast - Dự phòng
# ============================================================
@app.route('/bridge_forecast', methods=['POST', 'GET'])
def bridge_forecast():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        md5_hash = data.get('md5') or data.get('hash') or ''
    else:
        md5_hash = request.args.get('md5') or request.args.get('hash') or ''

    if not md5_hash:
        return jsonify({
            "success": False,
            "error": "Missing input hash"
        }), 400

    md5_hash = str(md5_hash).strip()

    # Bridge forecast: kết hợp thêm yếu tố thời gian
    base = predict_tai_xiu(md5_hash)
    time_seed = int(time.time() // 300)  # Đổi mỗi 5 phút
    extra_hash = hashlib.md5(f"{md5_hash}_{time_seed}".encode()).hexdigest()
    extra_val = int(extra_hash[:8], 16) % 20 - 10  # -10 .. +10

    # Điều chỉnh nhẹ
    adjusted_tai = base["tai_percent"] + extra_val * 0.3
    adjusted_tai = max(20, min(80, adjusted_tai))
    adjusted_tai = round(adjusted_tai, 1)

    result = "Tài" if adjusted_tai >= 50 else "Xỉu"

    return jsonify({
        "success": True,
        "result": result,
        "prediction": result.lower(),
        "confidence": round(max(adjusted_tai, 100 - adjusted_tai)),
        "tai_percent": adjusted_tai,
        "xiu_percent": round(100 - adjusted_tai, 1),
        "algorithm": "Bridge Forecast v3",
        "bridge_offset": extra_val,
        "version": VERSION
    })


# ============================================================
# ENDPOINT /session_follow - Theo dõi session
# ============================================================
@app.route('/session_follow', methods=['POST', 'GET'])
def session_follow():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id') or data.get('session') or ''
    else:
        session_id = request.args.get('session_id') or request.args.get('session') or ''

    if not session_id:
        return jsonify({
            "success": False,
            "error": "Missing session_id"
        }), 400

    session_id = str(session_id).strip()

    if session_id not in sessions:
        sessions[session_id] = {
            "created": int(time.time()),
            "predictions": []
        }

    session_data = sessions[session_id]

    # Dự đoán tiếp theo dựa trên lịch sử session
    history_str = ''.join(session_data["predictions"][-10:])
    if history_str:
        follow_hash = hashlib.md5((session_id + history_str).encode()).hexdigest()
    else:
        follow_hash = hashlib.md5(session_id.encode()).hexdigest()

    result = predict_tai_xiu(follow_hash)
    result["session_id"] = session_id
    result["session_length"] = len(session_data["predictions"])

    return jsonify(result)


# ============================================================
# ENDPOINT /docs - Tài liệu API
# ============================================================
@app.route('/docs', methods=['GET'])
def docs():
    return jsonify({
        "service": SERVICE_NAME,
        "version": VERSION,
        "endpoints": {
            "GET /": "Kiểm tra trạng thái API",
            "GET /health": "Health check",
            "POST /predict": "Dự đoán tài xỉu (JSON: {md5})",
            "GET /predict?md5=...": "Dự đoán tài xỉu (query param)",
            "POST /bridge_forecast": "Dự đoán nâng cao",
            "POST /session_follow": "Theo dõi session",
            "GET /docs": "Tài liệu này"
        },
        "examples": {
            "predict": {
                "url": "/predict",
                "method": "POST",
                "body": {"md5": "e10adc3949ba59abbe56e057f20f883e"}
            },
            "response": {
                "success": True,
                "result": "Tài",
                "confidence": 68,
                "tai_percent": 68.5,
                "xiu_percent": 31.5,
                "algorithm": "MD5 Hybrid Diffusion v3",
                "session": "a1b2c3d4e5f6"
            }
        }
    })


# ============================================================
# ERROR HANDLERS
# ============================================================
@app.errorhandler(404)
def not_found(e):
    return jsonify({
        "success": False,
        "error": "Endpoint not found",
        "available": ["/", "/health", "/predict", "/bridge_forecast", "/session_follow", "/docs"]
    }), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({
        "success": False,
        "error": "Internal server error",
        "message": str(e)
    }), 500


# ============================================================
# CHẠY SERVER
# ============================================================
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
