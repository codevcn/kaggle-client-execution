"""
routers/docs.py — Documentation API
=====================================
Endpoints:
  GET /api/docs           : liệt kê tất cả file markdown trong thư mục doc/
  GET /api/docs/{filename}: đọc nội dung một file markdown cụ thể
"""

from fastapi import APIRouter, HTTPException

from config import DOCS_DIR

router = APIRouter(prefix="/api", tags=["docs"])


@router.get("/docs")
def list_docs():
    """Lấy danh sách tên các file markdown (.md) trong thư mục doc/."""
    if not DOCS_DIR.exists():
        return []
    return sorted(f.name for f in DOCS_DIR.glob("*.md") if f.is_file())


@router.get("/docs/{filename}")
def get_doc(filename: str):
    """
    Lấy nội dung của một file markdown.
    Từ chối filename chứa path traversal (/, \\, ..).
    """
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Tên file không hợp lệ.")

    doc_path = DOCS_DIR / filename
    if not doc_path.exists() or not doc_path.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy file tài liệu.")

    try:
        return {"content": doc_path.read_text(encoding="utf-8")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đọc file: {str(e)}")
