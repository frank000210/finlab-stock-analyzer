"""ML Prediction API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date, timedelta

from ..crawler import StockPriceCrawler
from ..ml import StockPredictor

router = APIRouter(prefix="/api/v1/ml", tags=["ml"])


class PredictRequest(BaseModel):
    symbol: str
    horizon_days: int = 5
    threshold: float = 0.02


@router.post("/predict")
async def predict(req: PredictRequest):
    """Run ML prediction for a stock."""
    try:
        # Fetch enough historical data
        end = date.today()
        start = end - timedelta(days=365 * 2)

        crawler = StockPriceCrawler()
        df = await crawler.get_price(req.symbol, str(start), str(end))

        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {req.symbol}")

        predictor = StockPredictor()
        result = predictor.predict(df, horizon=req.horizon_days, threshold=req.threshold)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return {"success": True, "data": {"symbol": req.symbol, **result}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models():
    """List available ML models."""
    return {
        "success": True,
        "data": {
            "models": [
                {
                    "model_id": "random_forest",
                    "name": "Random Forest Classifier",
                    "description": "Predicts price direction using technical indicators as features",
                    "supported_horizons": [1, 3, 5, 10, 20],
                }
            ]
        },
    }
