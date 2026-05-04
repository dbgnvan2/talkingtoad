from fastapi.responses import JSONResponse

def _err(code: str, message: str, http_status: int) -> JSONResponse:
  return JSONResponse(
    status_code=http_status,
    content={"error": {"code": code, "message": message, "http_status": http_status}},
  )
