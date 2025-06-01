from fastapi import FastAPI, WebSocket, UploadFile, File
from fastapi.responses import JSONResponse
import asyncio
from src.data_capture.acc_shared_memory import ACCTelemetryCapture
from src.data_capture.lmu_shared_memory import LMUTelemetryCapture

app = FastAPI()
acc_capture = ACCTelemetryCapture()
acc_capture.connect()
acc_capture.start_capture()

lmu_capture = LMUTelemetryCapture()
lmu_capture.connect()
lmu_capture.start_capture()

@app.get("/api/acc/telemetry")
async def get_acc_telemetry():
    data = acc_capture.get_telemetry_data()
    return JSONResponse(content=data)

@app.websocket("/ws/acc/telemetry")
async def ws_acc_telemetry(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = acc_capture.get_telemetry_data()
            await websocket.send_json(data)
            await asyncio.sleep(0.1)
    except Exception:
        await websocket.close()

@app.get("/api/lmu/telemetry")
async def get_lmu_telemetry():
    data = lmu_capture.get_telemetry_data()
    return JSONResponse(content=data)

@app.websocket("/ws/lmu/telemetry")
async def ws_lmu_telemetry(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = lmu_capture.get_telemetry_data()
            await websocket.send_json(data)
            await asyncio.sleep(0.1)
    except Exception:
        await websocket.close()

@app.post("/api/upload/motec")
async def upload_motec(file: UploadFile = File(...)):
    import tempfile, shutil
    from src.data_acquisition.parsers import MotecParser
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ld")
    with tmp as f:
        shutil.copyfileobj(file.file, f)
    parser = MotecParser()
    session = parser.parse(tmp.name)
    return JSONResponse(content=session.dict() if session else {"error": "Parsing failed"})
