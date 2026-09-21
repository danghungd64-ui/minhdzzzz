from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

app = FastAPI(
    title="Tai Xiu Prediction API - Cau Analysis",
    description="API dự đoán Tài Xỉu theo thuật toán phân tích cầu dựa trên dữ liệu lịch sử.",
    version="1.0.0"
)

# ---------------------------------------------------------
# Models (Data Schemas)
# ---------------------------------------------------------
class SessionData(BaseModel):
    session: int = Field(..., description="Mã phiên")
    dice: List[int] = Field(..., min_items=3, max_items=3, description="Mảng 3 xúc xắc, ví dụ: [4, 1, 3]")
    total: Optional[int] = None
    result: Optional[str] = None

class PredictRequest(BaseModel):
    history: List[SessionData]
    target_session: Optional[int] = None

class PredictResponse(BaseModel):
    target_session: int
    prediction: str
    confidence: float
    detected_bridge: str
    analysis: dict

# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------
def preprocess_history(history: List[SessionData]) -> List[dict]:
    """Tự động tính tổng và gán nhãn tai/xiu nếu chưa có."""
    processed = []
    for item in history:
        dice_sum = sum(item.dice) if item.dice else item.total
        if dice_sum is None:
            continue
        
        res = item.result.lower() if item.result else ("tai" if dice_sum >= 11 else "xiu")
        processed.append({
            "session": item.session,
            "dice": item.dice,
            "total": dice_sum,
            "result": res
        })
    return processed

def analyze_bridge_pattern(results: List[str], totals: List[int]) -> tuple[str, str, float, str]:
    """
    Phân tích mẫu cầu dựa trên lịch sử kết quả.
    Trả về: (Dự đoán, Tên cầu, Độ tin cậy, Ghi chú)
    """
    n = len(results)
    if n == 0:
        return "tai", "Chưa đủ dữ liệu", 0.50, "Cần tối thiểu dữ liệu lịch sử."

    last_res = results[-1]
    opposite_res = "xiu" if last_res == "tai" else "tai"
    last_total = totals[-1]

    # 1. Kiểm tra Cầu Bệt (Rơi liên tục >= 4 phiên cùng kết quả)
    if n >= 4 and results[-4:] == [last_res] * 4:
        return last_res, "Cầu Bệt", 0.70, f"Đang bệt {last_res.upper()} 4 phiên liên tiếp. Theo cầu bệt."

    # 2. Kiểm tra Cầu 1-1 (Xung nhịp bẻ liên tục: T - X - T - X)
    if n >= 3:
        is_1_1 = True
        for i in range(1, min(5, n)):
            if results[-i] == results[-(i+1)]:
                is_1_1 = False
                break
        if is_1_1:
            return opposite_res, "Cầu 1-1", 0.68, f"Chuỗi đan xen {results[-1].upper()} -> Đổi sang {opposite_res.upper()}."

    # 3. Kiểm tra Cầu 2-2 (TT - XX - TT)
    if n >= 4:
        if results[-4:] == ["tai", "tai", "xiu", "xiu"]:
            return "tai", "Cầu 2-2", 0.65, "Mẫu XX-TT hoàn tất, phiên tiếp theo dự đoán TÀI."
        if results[-4:] == ["xiu", "xiu", "tai", "tai"]:
            return "xiu", "Cầu 2-2", 0.65, "Mẫu TT-XX hoàn tất, phiên tiếp theo dự đoán XỈU."

    # 4. Phân tích bẻ cầu theo biên độ tổng điểm (Point Reversion)
    if last_total >= 15:
        return "xiu", "Cầu Đảo (Điểm Cực Hạn)", 0.72, f"Điểm cực cao ({last_total}), khả năng bẻ XỈU rất cao."
    if last_total <= 6:
        return "tai", "Cầu Đảo (Điểm Cực Hạn)", 0.72, f"Điểm cực thấp ({last_total}), khả năng bẻ TÀI rất cao."

    # 5. Mặc định: Đánh theo xu hướng bẻ nhẹ theo giá trị điểm
    if last_total >= 11:
        return "xiu", "Cầu Đảo Nhẹ", 0.58, f"Điểm {last_total} thuộc vùng TÀI, dự báo quay đầu XỈU."
    else:
        return "tai", "Cầu Đảo Nhẹ", 0.58, f"Điểm {last_total} thuộc vùng XỈU, dự báo quay đầu TÀI."

# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------
@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Tai Xiu Prediction API",
        "version": "1.0.0",
        "docs_url": "/docs"
    }

@app.post("/predict", response_model=PredictResponse)
def predict_tai_xiu(data: PredictRequest):
    if not data.history:
        raise HTTPException(status_code=400, detail="Mảng 'history' không được để trống.")

    # Sắp xếp lịch sử theo phiên tăng dần
    sorted_history = sorted(data.history, key=lambda x: x.session)
    processed_history = preprocess_history(sorted_history)

    results = [item["result"] for item in processed_history]
    totals = [item["total"] for item in processed_history]

    # Xác định phiên cần dự đoán
    last_session = sorted_history[-1].session
    target_session = data.target_session if data.target_session else last_session + 1

    # Phân tích thuật toán cầu
    prediction, bridge_type, confidence, note = analyze_bridge_pattern(results, totals)

    return {
        "target_session": target_session,
        "prediction": prediction,
        "confidence": confidence,
        "detected_bridge": bridge_type,
        "analysis": {
            "last_session": last_session,
            "last_total": totals[-1],
            "last_result": results[-1],
            "total_analyzed_sessions": len(processed_history),
            "note": note
        }
    }
