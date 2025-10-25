from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
from typing import Literal, List, Optional
from pyproj import Transformer, CRS

app = FastAPI(title="Reprojection Service", version="1.0.0")

EPSG = Literal["EPSG:25829", "EPSG:25830", "EPSG:4326"]

class ReprojectIn(BaseModel):
    x: float
    y: float
    src: EPSG
    dst: EPSG

class ReprojectOut(ReprojectIn):
    ...

class BulkReprojectIn(BaseModel):
    points: List[ReprojectIn]

class DetectIn(BaseModel):
    lon: Optional[float] = Field(None, description="Longitude in degrees (WGS84)")
    lat: Optional[float] = Field(None, description="Latitude in degrees (WGS84)")
    x: Optional[float] = None
    y: Optional[float] = None
    crs: Optional[EPSG] = None

    @validator("crs")
    def crs_guard(cls, v, values):
        if (values.get("lon") is None or values.get("lat") is None) and v is None:
            raise ValueError("Provide lon/lat in WGS84 or (x,y,crs)")
        return v

class DetectOut(BaseModel):
    zone: Literal["25829", "25830"]
    epsg: EPSG

def _transform(x: float, y: float, src: str, dst: str):
    try:
        transformer = Transformer.from_crs(CRS.from_user_input(src),
                                           CRS.from_user_input(dst),
                                           always_xy=True)
        X, Y = transformer.transform(x, y)
        return X, Y
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Transform error: {e}")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/reproject", response_model=ReprojectOut)
def reproject(p: ReprojectIn):
    X, Y = _transform(p.x, p.y, p.src, p.dst)
    return ReprojectOut(x=round(X, 8), y=round(Y, 8), src=p.src, dst=p.dst)

@app.post("/detect", response_model=DetectOut)
def detect_zone(d: DetectIn):
    if d.lon is not None and d.lat is not None:
        lon, lat = d.lon, d.lat
    else:
        if d.x is None or d.y is None or d.crs is None:
            raise HTTPException(status_code=400, detail="Provide lon/lat or (x,y,crs)")
        lon, lat = _transform(d.x, d.y, d.crs, "EPSG:4326")

    zone = "25829" if lon < -6.0 else "25830"
    return DetectOut(zone=zone, epsg=f"EPSG:{zone}")
