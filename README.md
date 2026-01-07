# Void Tax System

Real-time car plate scanning system for road tax and insurance verification. Uses webcam to continuously scan for license plates and automatically issues fines for non-compliant vehicles.

## Features

- **Real-time Scanning**: Continuous webcam frame processing
- **Smart Deduplication**: Cache prevents duplicate API calls for recently scanned plates
- **Automatic Fine Issuance**: Issues fines for expired road tax or insurance
- **Modern Dashboard**: Live results display with statistics
- **FastAPI Backend**: High-performance async API with auto-documentation

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)

```bash
cp .env.example .env
# Edit .env as needed
```

### 3. Run the Application

```bash
python run.py
```

The application will be available at:
- **Dashboard**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## How It Works

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Web Browser   │────▶│  FastAPI Server │────▶│  External API   │
│   (Webcam)      │     │  (OCR + Cache)  │     │  (Validation)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        │ Frames (500ms)        │ Check Cache
        ▼                       ▼
   ┌─────────┐            ┌──────────┐
   │  EasyOCR │            │  SQLite  │
   │  Engine  │            │ Database │
   └─────────┘            └──────────┘
```

1. **Webcam** captures frames every 500ms (configurable)
2. **EasyOCR** processes each frame to detect license plates
3. **Cache** checks if plate was recently scanned (5-minute cooldown)
4. If not cached, calls **External API** to validate road tax and insurance
5. **Fines** are automatically issued for non-compliant vehicles
6. Results displayed in real-time on the **Dashboard**

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web dashboard |
| POST | `/api/scan-frame` | Process video frame (file upload) |
| POST | `/api/scan-frame-base64` | Process video frame (base64) |
| GET | `/api/fines` | List all fines |
| GET | `/api/fines/summary` | Fine statistics |
| GET | `/api/cache/stats` | Cache statistics |
| GET | `/docs` | Swagger API documentation |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `SCAN_INTERVAL_MS` | 500 | Frontend frame send interval |
| `CACHE_COOLDOWN_MIN` | 5 | Minutes before re-checking same plate |
| `OCR_CONFIDENCE_MIN` | 0.7 | Minimum OCR confidence threshold |
| `ROAD_TAX_FINE_AMOUNT` | 150.00 | Fine for expired road tax |
| `INSURANCE_FINE_AMOUNT` | 300.00 | Fine for expired insurance |

## Project Structure

```
void-tax/
├── app/
│   ├── main.py               # FastAPI application
│   ├── config.py             # Pydantic settings
│   ├── routers/
│   │   ├── scan.py           # Scanning endpoints
│   │   └── fines.py          # Fine management
│   ├── services/
│   │   ├── ocr_service.py    # EasyOCR integration
│   │   ├── plate_cache.py    # Deduplication cache
│   │   ├── validation_api.py # External API client
│   │   └── fine_service.py   # Fine processing
│   └── models/
│       ├── schemas.py        # Pydantic models
│       └── database.py       # SQLAlchemy models
├── static/
│   ├── css/styles.css
│   └── js/realtime-scanner.js
├── templates/
│   └── index.html
├── requirements.txt
└── run.py
```

## External API Integration

The system expects an external validation API with these endpoints:

```
GET /api/vehicle/{plate_number}
Response: {
    "plate_number": "ABC1234",
    "owner_name": "John Doe",
    "owner_id": "123456789012",
    "road_tax_valid": true,
    "road_tax_expiry": "2025-12-31T00:00:00",
    "insurance_valid": false,
    "insurance_expiry": "2024-06-15T00:00:00"
}
```

If the external API is unavailable, the system uses mock data for demo purposes.

## Demo Mode

When the external API is not available, the system automatically falls back to mock data:
- ~60% of vehicles will be road tax compliant
- ~70% of vehicles will have valid insurance
- Results are deterministic based on plate number (same plate = same result)

## License

MIT License

