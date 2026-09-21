from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

app = FastAPI(
    title="Tai Xiu Prediction API - LEMINH",
    description="API dự đoán Tài Xỉu theo phiên game. Trả về % Tài / % Xỉu chuẩn thuật toán cầu.",
    version="4.0.0"
)

# CORS cho phép mọi nguồn gọi API (kể cả tool HTML)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Models
# ---------------------------------------------------------
class SessionData(BaseModel):
    session: int = Field(..., description="Mã phiên (VD: 7056560)")
    dice: Optional[List[int]] = Field(None, description="3 xúc xắc")
    total: Optional[int] = None
    result: Optional[str] = None

class PredictRequest(BaseModel):
    history: List[SessionData]
    target_session: Optional[int] = None

class PredictResponse(BaseModel):
    target_session: int
    prediction: str                       # "tai" hoặc "xiu"
    confidence: float                     # 0.30 – 0.98
    confidence_tai: float                 # % TÀI
    confidence_xiu: float                 # % XỈU
    detected_bridge: str
    analysis: dict
    gap: Optional[int] = 1

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
    """
    Trả về: (prediction, bridge_name, confidence, note)
    """
    n = len(results)
    if n == 0:
        return "tai", "Chưa đủ dữ liệu", 0.50, "Cần tối thiểu 1 phiên."

    last_res = results[-1]
    opposite = "xiu" if last_res == "tai" else "tai"
    last_total = totals[-1]

    streak = detect_streak(results)
    alt = detect_alternating(results)

    # 1. Cầu 3-3
    p3 = detect_3_3(results)
    if p3:
        return p3, "Cầu 3-3", 0.74, f"Mẫu 3-3 hoàn tất, dự đoán {p3.upper()}."

    # 2. Cầu 2-2
    p2 = detect_2_2(results)
    if p2:
        return p2, "Cầu 2-2", 0.70, f"Mẫu 2-2 hoàn tất, dự đoán {p2.upper()}."

    # 3. Cầu bệt
    if streak >= 5:
        return last_res, "Cầu Bệt Mạnh", 0.80, f"Bệt {last_res.upper()} {streak} phiên liên tiếp."
    if streak >= 4:
        return last_res, "Cầu Bệt", 0.74, f"Bệt {last_res.upper()} {streak} phiên."
    if streak >= 3:
        return last_res, "Cầu Bệt Nhẹ", 0.66, f"Bệt {last_res.upper()} {streak} phiên."

    # 4. Cầu 1-1
    if alt >= 5:
        return opposite, "Cầu 1-1 Mạnh", 0.76, f"Đan xen {alt} phiên, đổi sang {opposite.upper()}."
    if alt >= 3:
        return opposite, "Cầu 1-1", 0.68, f"Đan xen {alt} phiên, đổi sang {opposite.upper()}."

    # 5. Bẻ cầu theo biên độ điểm
    if last_total >= 15:
        return "xiu", "Cầu Đảo (Điểm Cực Cao)", 0.76, f"Điểm {last_total} cực cao, bẻ XỈU."
    if last_total <= 6:
        return "tai", "Cầu Đảo (Điểm Cực Thấp)", 0.76, f"Điểm {last_total} cực thấp, bẻ TÀI."

    # 6. Đảo nhẹ
    if last_total >= 11:
        return "xiu", "Cầu Đảo Nhẹ", 0.60, f"Điểm {last_total} vùng TÀI, nghiêng XỈU."
    return "tai", "Cầu Đảo Nhẹ", 0.60, f"Điểm {last_total} vùng XỈU, nghiêng TÀI."


def compute_both_confidence(prediction: str, confidence: float) -> tuple:
    """
    Tính % Tài và % Xỉu dựa trên prediction + confidence.
    VD: prediction=tai, confidence=0.72 → Tài 72%, Xỉu 28%
    """
    if prediction == "tai":
        c_tai = confidence
        c_xiu = 1.0 - confidence
    else:
        c_xiu = confidence
        c_tai = 1.0 - confidence
    return round(c_tai, 4), round(c_xiu, 4)


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------
@app.get("/")
def home():
    """Health check + trả session mẫu để tool biết API đang online."""
    return {
        "status": "online",
        "service": "Tai Xiu Prediction API - LEMINH",
        "version": "4.0.0",
        "current_session": int(datetime.now().timestamp()) % 100000000,
        "features": ["predict", "confidence_tai_xiu"],
        "docs_url": "/docs"
    }


@app.post("/predict", response_model=PredictResponse)
def predict_tai_xiu(data: PredictRequest):
    if not data.history:
        raise HTTPException(status_code=400, detail="Mảng 'history' không được để trống.")

    sorted_history = sorted(data.history, key=lambda x: x.session)
    processed = preprocess_history(sorted_history)

    if not processed:
        raise HTTPException(status_code=400, detail="Không có dữ liệu hợp lệ.")

    results = [item["result"] for item in processed]
    totals = [item["total"] for item in processed]
    last_session = processed[-1]["session"]

    # Nếu không truyền target → mặc định last + 1
    target = data.target_session if data.target_session else last_session + 1
    if target <= last_session:
        raise HTTPException(
            status_code=400,
            detail=f"'target_session' ({target}) phải lớn hơn phiên cuối ({last_session})."
        )

    gap = target - last_session

    # Phân tích cầu cho phiên kế tiếp
    prediction, bridge, confidence, note = analyze_bridge_pattern(results, totals)

    # Tính % Tài / % Xỉu
    c_tai, c_xiu = compute_both_confidence(prediction, confidence)

    return {
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
            "note": note
        },
        "gap": gap
    }


@app.post("/predict/batch")
def predict_batch(data: PredictRequest):
    """
    Dự đoán nhiều phiên liên tiếp (nếu target_session cách xa).
    """
    if not data.history:
        raise HTTPException(status_code=400, detail="Mảng 'history' không được để trống.")
    if not data.target_session:
        raise HTTPException(status_code=400, detail="Cần truyền 'target_session'.")

    sorted_history = sorted(data.history, key=lambda x: x.session)
    processed = preprocess_history(sorted_history)
    results = [item["result"] for item in processed]
    totals = [item["total"] for item in processed]
    last_session = processed[-1]["session"]

    if data.target_session <= last_session:
        raise HTTPException(status_code=400, detail=f"'target_session' phải lớn hơn {last_session}.")

    steps = []
    MAX_GAP = 200
    gap = data.target_session - last_session
    start = data.target_session - MAX_GAP if gap > MAX_GAP else last_session + 1

    sim_r, sim_t = list(results), list(totals)
    for sess in range(start, data.target_session + 1):
        pred, bridge, conf, _ = analyze_bridge_pattern(sim_r, sim_t)
        c_tai, c_xiu = compute_both_confidence(pred, conf)
        steps.append({
            "session": sess,
            "prediction": pred,
            "confidence": round(conf, 4),
            "confidence_tai": c_tai,
            "confidence_xiu": c_xiu,
            "bridge": bridge
        })
        sim_r.append(pred)
        sim_t.append(12 if pred == "tai" else 9)

    return {
        "from_session": last_session,
        "to_session": data.target_session,
        "total_steps": len(steps),
        "forecast": steps
    }
