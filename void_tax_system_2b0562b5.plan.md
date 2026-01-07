---
name: Void Tax System
overview: Build a real-time car plate scanning system using Python FastAPI with EasyOCR, continuous webcam scanning, and smart deduplication to prevent duplicate API calls for recently scanned plates.
todos:
  - id: setup-project
    content: Set up FastAPI project with requirements.txt and Pydantic config
    status: completed
  - id: plate-cache
    content: Implement PlateCache service with TTL-based deduplication
    status: completed
    dependencies:
      - setup-project
  - id: ocr-service
    content: Implement async OCR service using EasyOCR
    status: completed
    dependencies:
      - setup-project
  - id: realtime-frontend
    content: Build web interface with continuous webcam frame streaming
    status: completed
    dependencies:
      - setup-project
  - id: validation-api
    content: Create async httpx client for external validation API
    status: completed
    dependencies:
      - setup-project
  - id: fine-service
    content: Implement fine generation and database storage
    status: completed
    dependencies:
      - validation-api
  - id: scan-endpoint
    content: Create POST /api/scan-frame endpoint with cache-first logic
    status: completed
    dependencies:
      - ocr-service
      - plate-cache
      - validation-api
      - fine-service
  - id: results-dashboard
    content: Build live dashboard showing scanned plates and status
    status: completed
    dependencies:
      - realtime-frontend
      - scan-endpoint
---

# Void Tax System - Design Plan

## Key Features
- **Real-time scanning**: Continuous webcam frame processing
- **Deduplication**: Cache prevents duplicate API calls for recently scanned plates
- **FastAPI backend**: Async support for high-performance real-time processing

## System Flow Diagram

```mermaid
flowchart TD
    subgraph frontend [Real-Time Frontend]
        A[User Opens Web App] --> B[Initialize Webcam]
        B --> C[Continuous Frame Stream]
        C --> D[Send Frame Every X ms]
    end

    subgraph backend [FastAPI Backend]
        D --> E[Receive Frame]
        E --> F[OCR Processing]
        F --> G{Plate Detected?}
        G -->|No| C
        G -->|Yes| H[Extract Plate Number]
    end

    subgraph dedup [Deduplication Cache]
        H --> I{Plate in Cache?}
        I -->|Yes, Recent| J[Skip API Call]
        J --> K[Return Cached Result]
        K --> C
        I -->|No or Expired| L[Add to Cache with Timestamp]
    end

    subgraph validation [Validation Service]
        L --> M[Call External API]
        M --> N[Check Road Tax Status]
        M --> O[Check Insurance Status]
        N --> P{Tax Paid?}
        O --> Q{Insurance Valid?}
    end

    subgraph fining [Fine Processing]
        P -->|No| R[Flag: Tax Unpaid]
        Q -->|No| S[Flag: Insurance Invalid]
        P -->|Yes| T[Tax OK]
        Q -->|Yes| U[Insurance OK]
        R --> V[Generate Fine Record]
        S --> V
        V --> W[Store in Database]
        W --> X[Notify Owner via API]
    end

    subgraph response [Response to Frontend]
        T --> Y[Return Clean Status]
        U --> Y
        X --> Z[Return Fine Details]
        Y --> AA[Display on Dashboard]
        Z --> AA
        AA --> C
    end
```

## Real-Time Scanning Sequence

```mermaid
sequenceDiagram
    participant Browser
    participant FastAPI as FastAPI Backend
    participant Cache as Plate Cache
    participant OCR as EasyOCR
    participant API as External API

    loop Every 500ms
        Browser->>FastAPI: POST /api/scan-frame (video frame)
        FastAPI->>OCR: Process Frame
        OCR->>FastAPI: Detected Plates Array
        
        loop For Each Plate
            FastAPI->>Cache: Check if plate exists
            
            alt Plate in cache and not expired
                Cache->>FastAPI: Return cached result
                FastAPI->>Browser: Return cached status
            else Plate not in cache or expired
                FastAPI->>API: GET /check-vehicle/{plate}
                API->>FastAPI: Tax & Insurance Status
                FastAPI->>Cache: Store plate with timestamp
                
                alt Not Compliant
                    FastAPI->>API: POST /issue-fine
                end
                
                FastAPI->>Browser: Return new result
            end
        end
    end
```

## Project Structure

```
void-tax/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI app entry point
│   ├── config.py             # Settings with Pydantic
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── scan.py           # Real-time scanning endpoints
│   │   └── fines.py          # Fine management endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ocr_service.py    # EasyOCR integration
│   │   ├── plate_cache.py    # Deduplication cache
│   │   ├── validation_api.py # External API client (httpx async)
│   │   └── fine_service.py   # Fine processing
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py        # Pydantic request/response models
│   │   └── database.py       # SQLAlchemy models
│   └── utils/
│       └── image_processor.py
├── static/
│   ├── css/
│   │   └── styles.css
│   └── js/
│       └── realtime-scanner.js
├── templates/
│   └── index.html
├── requirements.txt
└── run.py
```

## Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Serve web dashboard |
| POST | `/api/scan-frame` | Process single video frame |
| GET | `/api/fines` | List all issued fines |
| GET | `/api/cache/stats` | View cache statistics |
| GET | `/docs` | Auto-generated API docs (Swagger) |

## FastAPI Advantages for This Project

1. **Async Support**: Non-blocking calls to external validation API
2. **High Performance**: Handle rapid frame submissions efficiently
3. **Auto Documentation**: Built-in Swagger UI at `/docs`
4. **Pydantic Models**: Type-safe request/response validation
5. **Easy Testing**: Built-in test client

## Core Code Structure

### Main FastAPI App
```python
# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import scan, fines

app = FastAPI(title="Void Tax System")
app.mount("/static", StaticFiles(directory="static"))
app.include_router(scan.router, prefix="/api")
app.include_router(fines.router, prefix="/api")
```

### Async Scan Endpoint
```python
# app/routers/scan.py
@router.post("/scan-frame")
async def scan_frame(file: UploadFile):
    plates = await ocr_service.detect_plates(file)
    results = []
    for plate in plates:
        if plate_cache.is_recently_scanned(plate):
            results.append(plate_cache.get_cached(plate))
        else:
            status = await validation_api.check_vehicle(plate)
            plate_cache.add(plate, status)
            if not status.is_compliant:
                await fine_service.issue_fine(plate, status)
            results.append(status)
    return {"plates": results}
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| SCAN_INTERVAL_MS | 500 | Frontend frame send interval |
| CACHE_COOLDOWN_MIN | 5 | Minutes before re-checking same plate |
| OCR_CONFIDENCE_MIN | 0.7 | Minimum OCR confidence threshold |
| EXTERNAL_API_URL | - | Base URL for validation API |

## Implementation Todos