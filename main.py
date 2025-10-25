from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
from typing import Literal, List, Optional
from pyproj import Transformer, CRS

# Inicialización de la aplicación FastAPI
app = FastAPI(
    title="Reprojection Service",
    version="1.1.0",
    description="Microservicio para reproyectar coordenadas entre EPSG:25829, EPSG:25830 y EPSG:4326"
)

# Tipos válidos de CRS
EPSG = Literal["EPSG:25829", "EPSG:25830", "EPSG:4326"]

# -----------------------------
#   MODELOS DE DATOS
# -----------------------------
class ReprojectIn(BaseModel):
    x: float
    y: float
    src: EPSG
    dst: EPSG


class ReprojectOut(ReprojectIn):
    """Resultado con coordenadas reproyectadas."""
    ...


class BulkReprojectIn(BaseModel):
    """Reproyección múltiple (lista de puntos)."""
    points: List[ReprojectIn]


class DetectIn(BaseModel):
    """Entrada para detección de huso UTM."""
    lon: Optional[float] = Field(None, description="Longitud en grados (WGS84)")
    lat: Optional[float] = Field(None, description="Latitud en grados (WGS84)")
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


# -----------------------------
#   FUNCIONES AUXILIARES
# -----------------------------
def _transform(x: float, y: float, src: str, dst: str):
    """Reproyecta coordenadas entre CRS usando pyproj."""
    try:
        transformer = Transformer.from_crs(CRS.from_user_input(src),
                                           CRS.from_user_input(dst),
                                           always_xy=True)
        X, Y = transformer.transform(x, y)
        return X, Y
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Transform error: {e}")


# -----------------------------
#   ENDPOINTS
# -----------------------------
@app.get("/")
def root():
    """Ruta raíz informativa."""
    return {
        "service": "Reprojection Service",
        "version": "1.1.0",
        "endpoints": ["/health", "/reproject", "/detect", "/docs"]
    }


@app.get("/health")
def health():
    """Comprueba el estado del servicio."""
    return {"status": "ok"}


@app.post("/reproject", response_model=ReprojectOut)
def reproject(p: ReprojectIn):
    """Reproyecta un punto entre sistemas de referencia."""
    X, Y = _transform(p.x, p.y, p.src, p.dst)
    return ReprojectOut(
        x=round(X, 8),
        y=round(Y, 8),
        src=p.src,
        dst=p.dst
    )


@app.post("/detect", response_model=DetectOut)
def detect_zone(d: DetectIn):
    """Detecta el huso UTM correcto en España."""
    if d.lon is not None and d.lat is not None:
        lon, lat = d.lon, d.lat
    else:
        if d.x is None or d.y is None or d.crs is None:
            raise HTTPException(status_code=400, detail="Faltan parámetros (lon/lat o x/y/crs)")
        lon, lat = _transform(d.x, d.y, d.crs, "EPSG:4326")

    # Meridiano de separación aproximado entre husos 29 y 30
    zone = "25829" if lon < -6.0 else "25830"
    return DetectOut(zone=zone, epsg=f"EPSG:{zone}")
