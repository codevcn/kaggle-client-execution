"""
routers/filters.py — Available filters API
============================================
Endpoints:
  GET /api/available-filters : liệt kê tất cả filter plugin trong src/filters/
"""

from fastapi import APIRouter

from config import FILTERS_DIR, FLOW_MODULES_DIR

router = APIRouter(prefix="/api", tags=["filters"])


@router.get("/available-filters")
def get_available_filters():
    """
    Quét thư mục src/filters và trả về danh sách tên filter (stem của .py file).
    Bỏ qua file __init__.py và các file không phải .py.
    """
    if not FILTERS_DIR.exists():
        return []
    return sorted(
        f.stem
        for f in FILTERS_DIR.iterdir()
        if f.is_file() and f.name.endswith(".py") and f.name != "__init__.py"
    )

@router.get("/available-flow-modules")
def get_available_flow_modules():
    """
    Quét thư mục src/flow_modules và trả về danh sách tên flow module (stem của .py file).
    """
    if not FLOW_MODULES_DIR.exists():
        return []
    return sorted(
        f.stem
        for f in FLOW_MODULES_DIR.iterdir()
        if f.is_file() and f.name.endswith(".py") and f.name != "__init__.py"
    )
