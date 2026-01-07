"""
YOLOv8 Detection Viewer - Separate server for full-screen detection view
Run on port 8001 to view YOLOv8 detections in a large window
"""

import cv2
import base64
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import numpy as np

# Import the plate detector from main app
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from app.services.plate_detector import plate_detector

app = FastAPI(title="YOLOv8 Detection Viewer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTML page for the detection viewer
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YOLOv8 Detection Viewer</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            background: #0a0a0f;
            color: #e2e8f0;
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 16px 24px;
            border-bottom: 2px solid #10b981;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 1.5rem;
            color: #10b981;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .status {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.9rem;
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #ef4444;
            animation: pulse 1.5s infinite;
        }
        
        .status-dot.active {
            background: #10b981;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .main {
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: 20px;
            gap: 16px;
        }
        
        .video-section {
            flex: 1;
            display: flex;
            gap: 20px;
        }
        
        .video-container {
            flex: 1;
            background: #111;
            border-radius: 12px;
            overflow: hidden;
            position: relative;
            border: 2px solid #1e293b;
        }
        
        .video-container.detection {
            border-color: #10b981;
        }
        
        .video-label {
            position: absolute;
            top: 12px;
            left: 12px;
            background: rgba(0, 0, 0, 0.8);
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            z-index: 10;
        }
        
        .video-label.source {
            color: #06b6d4;
        }
        
        .video-label.detection {
            color: #10b981;
        }
        
        video, #detectionCanvas {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }
        
        .stats-bar {
            display: flex;
            gap: 24px;
            padding: 16px 24px;
            background: #1a1a2e;
            border-radius: 8px;
        }
        
        .stat {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: #10b981;
        }
        
        .stat-value.warning {
            color: #f59e0b;
        }
        
        .stat-value.danger {
            color: #ef4444;
        }
        
        .stat-label {
            font-size: 0.8rem;
            color: #64748b;
            text-transform: uppercase;
        }
        
        .controls {
            display: flex;
            gap: 12px;
            justify-content: center;
        }
        
        .btn {
            padding: 12px 32px;
            border: none;
            border-radius: 8px;
            font-family: inherit;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(16, 185, 129, 0.4);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: white;
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .detection-log {
            max-height: 150px;
            overflow-y: auto;
            background: #0f0f1a;
            border-radius: 8px;
            padding: 12px;
            font-size: 0.85rem;
        }
        
        .log-entry {
            padding: 6px 0;
            border-bottom: 1px solid #1e293b;
            display: flex;
            justify-content: space-between;
        }
        
        .log-entry:last-child {
            border-bottom: none;
        }
        
        .log-plate {
            color: #10b981;
            font-weight: 600;
        }
        
        .log-conf {
            color: #f59e0b;
        }
        
        .log-time {
            color: #64748b;
        }
        
        .device-info {
            font-size: 0.8rem;
            color: #8b5cf6;
            background: rgba(139, 92, 246, 0.1);
            padding: 4px 12px;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <header class="header">
        <h1>🎯 YOLOv8 Detection Viewer</h1>
        <div class="status">
            <span class="status-dot" id="statusDot"></span>
            <span id="statusText">Disconnected</span>
            <span class="device-info" id="deviceInfo">Loading...</span>
        </div>
    </header>
    
    <main class="main">
        <div class="controls">
            <button class="btn btn-primary" id="startBtn">▶️ Start Detection</button>
            <button class="btn btn-danger" id="stopBtn" disabled>⏹️ Stop</button>
        </div>
        
        <div class="video-section">
            <div class="video-container">
                <span class="video-label source">📷 Source Feed</span>
                <video id="sourceVideo" autoplay playsinline muted></video>
            </div>
            <div class="video-container detection">
                <span class="video-label detection">🎯 YOLOv8 Detection</span>
                <canvas id="detectionCanvas"></canvas>
            </div>
        </div>
        
        <div class="stats-bar">
            <div class="stat">
                <span class="stat-value" id="fps">0</span>
                <span class="stat-label">FPS</span>
            </div>
            <div class="stat">
                <span class="stat-value" id="detections">0</span>
                <span class="stat-label">Detections</span>
            </div>
            <div class="stat">
                <span class="stat-value" id="totalPlates">0</span>
                <span class="stat-label">Total Plates</span>
            </div>
            <div class="stat">
                <span class="stat-value" id="avgConf">0%</span>
                <span class="stat-label">Avg Confidence</span>
            </div>
        </div>
        
        <div class="detection-log" id="detectionLog">
            <div style="color: #64748b; text-align: center;">Detection log will appear here...</div>
        </div>
    </main>

    <script>
        class DetectionViewer {
            constructor() {
                this.video = document.getElementById('sourceVideo');
                this.canvas = document.getElementById('detectionCanvas');
                this.ctx = this.canvas.getContext('2d');
                this.startBtn = document.getElementById('startBtn');
                this.stopBtn = document.getElementById('stopBtn');
                this.statusDot = document.getElementById('statusDot');
                this.statusText = document.getElementById('statusText');
                
                this.isRunning = false;
                this.stream = null;
                this.ws = null;
                this.frameCount = 0;
                this.lastFpsTime = Date.now();
                this.totalPlates = 0;
                this.confidences = [];
                this.detectionLog = [];
                
                this.startBtn.addEventListener('click', () => this.start());
                this.stopBtn.addEventListener('click', () => this.stop());
                
                // Get device info
                this.getDeviceInfo();
            }
            
            async getDeviceInfo() {
                try {
                    const response = await fetch('/device-info');
                    const info = await response.json();
                    document.getElementById('deviceInfo').textContent = 
                        `${info.device.toUpperCase()} | ${info.model}`;
                } catch (e) {
                    document.getElementById('deviceInfo').textContent = 'Device info unavailable';
                }
            }
            
            async start() {
                try {
                    this.stream = await navigator.mediaDevices.getUserMedia({
                        video: { width: 1280, height: 720, facingMode: 'environment' }
                    });
                    
                    this.video.srcObject = this.stream;
                    await this.video.play();
                    
                    this.canvas.width = this.video.videoWidth;
                    this.canvas.height = this.video.videoHeight;
                    
                    this.isRunning = true;
                    this.startBtn.disabled = true;
                    this.stopBtn.disabled = false;
                    this.statusDot.classList.add('active');
                    this.statusText.textContent = 'Running';
                    
                    this.processFrames();
                } catch (error) {
                    console.error('Camera error:', error);
                    this.statusText.textContent = 'Camera error: ' + error.message;
                }
            }
            
            stop() {
                this.isRunning = false;
                
                if (this.stream) {
                    this.stream.getTracks().forEach(track => track.stop());
                    this.stream = null;
                }
                
                this.video.srcObject = null;
                this.startBtn.disabled = false;
                this.stopBtn.disabled = true;
                this.statusDot.classList.remove('active');
                this.statusText.textContent = 'Stopped';
            }
            
            async processFrames() {
                if (!this.isRunning) return;
                
                const startTime = performance.now();
                
                // Use smaller canvas for faster processing (640x480)
                const targetWidth = 640;
                const targetHeight = 480;
                
                const offscreen = document.createElement('canvas');
                offscreen.width = targetWidth;
                offscreen.height = targetHeight;
                const offCtx = offscreen.getContext('2d');
                offCtx.drawImage(this.video, 0, 0, targetWidth, targetHeight);
                
                // Lower quality for faster transfer
                const imageData = offscreen.toDataURL('image/jpeg', 0.7);
                
                try {
                    const response = await fetch('/detect', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ image: imageData })
                    });
                    
                    const result = await response.json();
                    
                    // Draw detection result
                    if (result.image) {
                        const img = new Image();
                        img.onload = () => {
                            this.ctx.drawImage(img, 0, 0, this.canvas.width, this.canvas.height);
                        };
                        img.src = result.image;
                    }
                    
                    // Update stats
                    this.frameCount++;
                    const now = Date.now();
                    if (now - this.lastFpsTime >= 1000) {
                        document.getElementById('fps').textContent = this.frameCount;
                        this.frameCount = 0;
                        this.lastFpsTime = now;
                    }
                    
                    document.getElementById('detections').textContent = result.detections || 0;
                    
                    // Log detections
                    if (result.plates && result.plates.length > 0) {
                        this.totalPlates += result.plates.length;
                        document.getElementById('totalPlates').textContent = this.totalPlates;
                        
                        for (const plate of result.plates) {
                            this.confidences.push(plate.confidence);
                            if (this.confidences.length > 100) this.confidences.shift();
                            
                            this.addLogEntry(plate);
                        }
                        
                        const avgConf = this.confidences.reduce((a, b) => a + b, 0) / this.confidences.length;
                        document.getElementById('avgConf').textContent = (avgConf * 100).toFixed(0) + '%';
                    }
                    
                } catch (error) {
                    console.error('Detection error:', error);
                }
                
                // Calculate delay to achieve target FPS (15 FPS = ~66ms per frame)
                const elapsed = performance.now() - startTime;
                const targetDelay = Math.max(1, 66 - elapsed); // Target 15 FPS
                
                // Use requestAnimationFrame for smoother rendering
                setTimeout(() => requestAnimationFrame(() => this.processFrames()), targetDelay);
            }
            
            addLogEntry(plate) {
                const time = new Date().toLocaleTimeString();
                const entry = { plate: plate.label || 'Plate', conf: plate.confidence, time };
                this.detectionLog.unshift(entry);
                if (this.detectionLog.length > 20) this.detectionLog.pop();
                
                const logEl = document.getElementById('detectionLog');
                logEl.innerHTML = this.detectionLog.map(e => `
                    <div class="log-entry">
                        <span class="log-plate">${e.plate}</span>
                        <span class="log-conf">${(e.conf * 100).toFixed(0)}%</span>
                        <span class="log-time">${e.time}</span>
                    </div>
                `).join('');
            }
        }
        
        document.addEventListener('DOMContentLoaded', () => {
            window.viewer = new DetectionViewer();
        });
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the detection viewer page."""
    return HTML_PAGE


@app.get("/device-info")
async def device_info():
    """Get YOLOv8 device information."""
    return {
        "device": plate_detector.device,
        "model": "YOLOv8 License Plate Detector"
    }


@app.post("/detect")
async def detect(request: dict):
    """
    Process a frame and return YOLOv8 detection visualization.
    Optimized for high FPS (~15+ FPS).
    """
    try:
        image_data = request.get("image", "")
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        image_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            return {"image": None, "detections": 0, "plates": []}
        
        # Single inference: Get visualization and extract plate info from results
        annotated, num_detections, plates = plate_detector.get_yolo_visualization_with_info(image)
        
        # Encode result image with lower quality for faster transfer
        _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 65])
        result_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return {
            "image": f"data:image/jpeg;base64,{result_base64}",
            "detections": num_detections,
            "plates": plates
        }
        
    except Exception as e:
        print(f"Detection error: {e}")
        return {"image": None, "detections": 0, "plates": [], "error": str(e)}


def main():
    """Run the detection viewer server on port 8001."""
    print("=" * 50)
    print("🎯 YOLOv8 Detection Viewer")
    print("=" * 50)
    print(f"📡 Server running at: http://localhost:8001")
    print(f"🔧 Device: {plate_detector.device.upper()}")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning")


if __name__ == "__main__":
    main()

