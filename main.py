from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Literal, List, Optional
from pyproj import Transformer, CRS

app = FastAPI(
    title="Reprojection Service",
    version="1.2.0",
    description="Microservicio para reproyectar coordenadas entre EPSG:25829, EPSG:25830 y EPSG:4326"
)

# CORS (permite llamadas desde n8n, front, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Si quieres, cámbialo a tu dominio
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    lon: Optional[float] = Field(None, description="Longitud WGS84")
    lat: Optional[float] = Field(None, description="Latitud WGS84")
    x: Optional[float] = None
    y: Optional[float] = None
    crs: Optional[EPSG] = None

    @validator("crs")
    def crs_guard(cls, v, values):
        if (values.get("lon") is None or values.get("lat") is None) and v is None:
            raise ValueError("Debes proporcionar lon/lat o (x,y,crs)")
        return v

class DetectOut(BaseModel):
    zone: Literal["25829", "25830"]
    epsg: EPSG

def _transform(x: float, y: float, src: str, dst: str):
    try:
        transformer = Transformer.from_crs(
            CRS.from_user_input(src),
            CRS.from_user_input(dst),
            always_xy=True
        )
        X, Y = transformer.transform(x, y)
        return X, Y
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Transform error: {e}")

@app.get("/")
def root():
    return {
        "service": "Reprojection Service",
        "version": "1.2.0",
        "endpoints": ["/health", "/reproject", "/reproject/bulk", "/detect", "/docs"]
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/reproject", response_model=ReprojectOut)
def reproject(p: ReprojectIn):
    X, Y = _transform(p.x, p.y, p.src, p.dst)
    return ReprojectOut(x=round(X, 8), y=round(Y, 8), src=p.src, dst=p.dst)

@app.post("/reproject/bulk", response_model=List[ReprojectOut])
def reproject_bulk(b: BulkReprojectIn):
    out: List[ReprojectOut] = []
    for p in b.points:
        X, Y = _transform(p.x, p.y, p.src, p.dst)
        out.append(ReprojectOut(x=round(X, 8), y=round(Y, 8), src=p.src, dst=p.dst))
    return out

@app.post("/detect", response_model=DetectOut)
def detect_zone(d: DetectIn):
    if d.lon is not None and d.lat is not None:
        lon, _ = d.lon, d.lat
    else:
        if d.x is None or d.y is None or d.crs is None:
            raise HTTPException(status_code=400, detail="Faltan parámetros (lon/lat o x/y/crs)")
        lon, _ = _transform(d.x, d.y, d.crs, "EPSG:4326")

    zone = "25829" if lon < -6.0 else "25830"
    return DetectOut(zone=zone, epsg=f"EPSG:{zone}")
