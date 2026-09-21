from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
import hashlib
import time

app = FastAPI(
    title="Tai Xiu Prediction API - LEMINH",
    description="API dự đoán Tài Xỉu có cache theo phiên + cooldown 30s.",
    version="5.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# CACHE + COOLDOWN
# ---------------------------------------------------------
# Lưu kết quả dự đoán theo session để tránh đổi linh tinh
PREDICTION_CACHE = {}   # {session: response_dict}

# Cooldown theo session — chỉ cho dự đoán 1 lần / 30s / session
LAST_PREDICT_TIME = {}  # {session: timestamp}
COOLDOWN_SECONDS = 30

# ---------------------------------------------------------
# Models
# ---------------------------------------------------------
class SessionData(BaseModel):
    session: int
    dice: Optional[List[int]] = None
    total: Optional[int] = None
    result: Optional[str] = None

class PredictRequest(BaseModel):
    history: List[SessionData]
    target_session: Optional[int] = None

class PredictResponse(BaseModel):
    target_session: int
    prediction: str
    confidence: float
    confidence_tai: float
    confidence_xiu: float
    detected_bridge: str
    analysis: dict
    gap: Optional[int] = 1
    cached: Optional[bool] = False

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def preprocess_history(history: List[SessionData]) -> List[dict]:
    processed = []
    for item in history:
        total = item.total if item.total is not None else (
            sum(item.dice) if item.dice else None
        )
        if total is None:
            continue
        res = item.result.lower() if item.result else ("tai" if total >= 11 else "xiu")
        processed.append({
            "session": item.session,
            "total": total,
            "result": res
        })
    return processed


def detect_streak(results: List[str]) -> int:
    if not results:
        return 0
    last = results[-1]
    streak = 1
    for i in range(len(results) - 2, -1, -1):
        if results[i] == last:
            streak += 1
        else:
            break
    return streak


def detect_alternating(results: List[str]) -> int:
    if len(results) < 2:
        return 0
    count = 1
    for i in range(len(results) - 2, -1, -1):
        if results[i] != results[i + 1]:
            count += 1
        else:
            break
    return count


def detect_2_2(results: List[str]) -> Optional[str]:
    if len(results) < 4:
        return None
    last4 = results[-4:]
    if last4 == ["tai", "tai", "xiu", "xiu"]:
        return "tai"
    if last4 == ["xiu", "xiu", "tai", "tai"]:
        return "xiu"
    return None


def detect_3_3(results: List[str]) -> Optional[str]:
    if len(results) < 6:
        return None
    last6 = results[-6:]
    if last6 == ["tai", "tai", "tai", "xiu", "xiu", "xiu"]:
        return "tai"
    if last6 == ["xiu", "xiu", "xiu", "tai", "tai", "tai"]:
        return "xiu"
    return None


def analyze_bridge_pattern(results: List[str], totals: List[int]) -> tuple:
    n = len(results)
    if n == 0:
        return "tai", "Chưa đủ dữ liệu", 0.50, "Cần tối thiểu 1 phiên."

    last_res = results[-1]
    opposite = "xiu" if last_res == "tai" else "tai"
    last_total = totals[-1]

    streak = detect_streak(results)
    alt = detect_alternating(results)

    p3 = detect_3_3(results)
    if p3:
        return p3, "Cầu 3-3", 0.74, f"Mẫu 3-3 hoàn tất, dự đoán {p3.upper()}."

    p2 = detect_2_2(results)
    if p2:
        return p2, "Cầu 2-2", 0.70, f"Mẫu 2-2 hoàn tất, dự đoán {p2.upper()}."

    if streak >= 5:
        return last_res, "Cầu Bệt Mạnh", 0.80, f"Bệt {last_res.upper()} {streak} phiên."
    if streak >= 4:
        return last_res, "Cầu Bệt", 0.74, f"Bệt {last_res.upper()} {streak} phiên."
    if streak >= 3:
        return last_res, "Cầu Bệt Nhẹ", 0.66, f"Bệt {last_res.upper()} {streak} phiên."

    if alt >= 5:
        return opposite, "Cầu 1-1 Mạnh", 0.76, f"Đan xen {alt} phiên, đổi {opposite.upper()}."
    if alt >= 3:
        return opposite, "Cầu 1-1", 0.68, f"Đan xen {alt} phiên, đổi {opposite.upper()}."

    if last_total >= 15:
        return "xiu", "Cầu Đảo (Điểm Cực Cao)", 0.76, f"Điểm {last_total} cực cao, bẻ XỈU."
    if last_total <= 6:
        return "tai", "Cầu Đảo (Điểm Cực Thấp)", 0.76, f"Điểm {last_total} cực thấp, bẻ TÀI."

    if last_total >= 11:
        return "xiu", "Cầu Đảo Nhẹ", 0.60, f"Điểm {last_total} vùng TÀI, nghiêng XỈU."
    return "tai", "Cầu Đảo Nhẹ", 0.60, f"Điểm {last_total} vùng XỈU, nghiêng TÀI."


def compute_confidence(prediction: str, confidence: float) -> tuple:
    if prediction == "tai":
        return round(confidence, 4), round(1.0 - confidence, 4)
    return round(1.0 - confidence, 4), round(confidence, 4)


def history_signature(processed: List[dict]) -> str:
    """Tạo hash từ history để phát hiện thay đổi."""
    raw = "|".join(f"{p['session']}:{p['result']}" for p in processed)
 HTTP    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------
@app.get("/")
def home():
    """Health check + session mẫu."""
    return {
        "status": "online",
        "service": "Tai Xiu Prediction API - LEMINH",
        "version": "5.0.0",
        "current_session": int(datetime.now().timestamp()) % 100000000,
        "features": ["predict", "confidence_tai_xiu", "cache_by_session", "cooldown_30s"]
    }


@app.post("/predict", response_model=PredictResponse)
def predict_tai_xiu(data: PredictRequest):
    if not data.history:
        raiseException(status_code=400, detail="Mảng 'history' không được để trống.")

    sorted_history = sorted(data.history, key=lambda x: x.session)
    processed = preprocess_history(sorted_history)

    if not processed:
        raise HTTPException(status_code=400, detail="Không có dữ liệu hợp lệ.")

    results = [item["result"] for item in processed]
    totals = [item["total"] for item in processed]
    last_session = processed[-1]["session"]

    target = data.target_session if data.target_session else last_session + 1
    if target <= last_session:
        raise HTTPException(
            status_code=400,
            detail=f"'target_session' ({target}) phải lớn hơn phiên cuối ({last_session})."
        )

    # ---------------------------------------------------------
    # 1. KIỂM TRA CACHE — không đổi kết quả cho cùng phiên
    # ---------------------------------------------------------
    sig = history_signature(processed)
    cache_key = f"{target}_{sig}"

    if cache_key in PREDICTION_CACHE:
        cached = PREDICTION_CACHE[cache_key].copy()
        cached["cached"] = True
        return cached

    # ---------------------------------------------------------
    # 2. COOLDOWN 30s — không dự đoán lại cùng phiên trong 30s
    # ---------------------------------------------------------
    now = time.time()
    if target in LAST_PREDICT_TIME:
        elapsed = now - LAST_PREDICT_TIME[target]
        if elapsed < COOLDOWN_SECONDS:
            # Trả kết quả cache nếu có
            if cache_key in PREDICTION_CACHE:
                cached = PREDICTION_CACHE[cache_key].copy()
                cached["cached"] = True
                return cached
            # Nếu không có cache, trả lỗi 429
            raise HTTPException(
                status_code=429,
                detail=f"Phiên {target} vừa dự đoán {elapsed:.1f}s trước. Chờ thêm {COOLDOWN_SECONDS - elapsed:.1f}s."
            )

    # ---------------------------------------------------------
    # 3. TÍNH DỰ ĐOÁN
    # ---------------------------------------------------------
    gap = target - last_session
    prediction, bridge, confidence, note = analyze_bridge_pattern(results, totals)
    c_tai, c_xiu = compute_confidence(prediction, confidence)

    response = {
        "target_session": target,
        "prediction": prediction,
        "confidence": round(confidence, 4),
        "confidence_tai": c_tai,
        "confidence_xiu": c_xiu,
        "detected_bridge": bridge,
        "analysis": {
            "last_session": last_session,
            "last_total": totals[-1],
            "last_result": results[-1],
            "total_analyzed_sessions": len(processed),
            "gap_from_last": gap,
            "note": note,
            "history_signature": sig
        },
        "gap": gap,
        "cached": False
    }

    # Lưu cache + timestamp
    PREDICTION_CACHE[cache_key] = response
    LAST_PREDICT_TIME[target] = now

    # Giới hạn cache size
    if len(PREDICTION_CACHE) > 500:
        keys = list(PREDICTION_CACHE.keys())[:100]
        for k in keys:
            del PREDICTION_CACHE[k]
    if len(LAST_PREDICT_TIME) > 500:
        keys = list(LAST_PREDICT_TIME.keys())[:100]
        for k in keys:
            del LAST_PREDICT_TIME[k]

    return response


@app.get("/cache/status")
def cache_status():
    """Xem trạng thái cache."""
    return {
        "cached_sessions": len(PREDICTION_CACHE),
        "cooldown_seconds": COOLDOWN_SECONDS,
        "sessions_in_cooldown": len(LAST_PREDICT_TIME)
    }


@app.delete("/cache/clear")
def cache_clear():
    """Xoá cache (dùng khi cần reset)."""
    PREDICTION_CACHE.clear()
    LAST_PREDICT_TIME.clear()
    return {"status": "cleared"}
