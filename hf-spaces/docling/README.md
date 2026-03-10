---
title: Nomos Docling API
emoji: "📄"
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: "5.12.0"
app_file: app.py
pinned: false
license: mit
short_description: PDF document processor for RAG pipelines
---

# Nomos Docling Document Processor

Convert complex PDFs (SEC filings, DTU norms, legal codes, ISO standards) into clean structured text for RAG pipelines.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/convert` | POST | Upload PDF file, returns JSON with text + tables + chunks |
| `/convert-url` | POST | Convert PDF from URL |
| `/health` | GET | Health check |
| `/info` | GET | Service information |

## Usage

### Convert uploaded file

```bash
curl -X POST https://lbjlincoln-nomos-docling-api.hf.space/convert \
  -F "file=@document.pdf" \
  -F "chunk_size=1000" \
  -F "chunk_overlap=200"
```

### Convert from URL

```bash
curl -X POST https://lbjlincoln-nomos-docling-api.hf.space/convert-url \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/document.pdf",
    "chunk_size": 1000,
    "chunk_overlap": 200
  }'
```

### Health check

```bash
curl https://lbjlincoln-nomos-docling-api.hf.space/health
```

## Response Format

```json
{
  "status": "success",
  "file_name": "document.pdf",
  "file_size_bytes": 1234567,
  "file_hash": "a1b2c3d4e5f6g7h8",
  "full_text": "# Document Title\n\nExtracted markdown text...",
  "text_length": 45000,
  "pages": [
    {"page_number": 1, "text": "...", "char_count": 5000}
  ],
  "num_pages": 10,
  "tables": [
    {"index": 0, "markdown": "| Col1 | Col2 |\n|---|---|\n| A | B |", "data": [...]}
  ],
  "num_tables": 3,
  "chunks": [
    {"index": 0, "text": "...", "char_start": 0, "char_end": 1000}
  ],
  "num_chunks": 50,
  "processing_time_s": 12.5,
  "_self_hosted": true,
  "_cost": 0.0
}
```

## Features

- Full markdown text extraction via Docling
- Table structure recognition (FAST mode for memory efficiency)
- OCR for scanned documents
- Per-page text splitting
- Configurable chunking with overlap
- SHA-256 file dedup hash
- Up to 50MB PDF files

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload file size |
| `CHUNK_SIZE` | `1000` | Default chunk size in chars |
| `CHUNK_OVERLAP` | `200` | Default chunk overlap in chars |
| `TABLE_MODE` | `fast` | Table extraction mode: `fast` or `accurate` |

## Tech Stack

- [Docling](https://github.com/docling-project/docling) — Document conversion (MIT license)
- Gradio — Web UI
- FastAPI — REST API
- CPU-only PyTorch — No GPU required
