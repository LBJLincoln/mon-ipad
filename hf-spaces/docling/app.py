#!/usr/bin/env python3
"""
Nomos Docling Document Processor — HF Space S6
Converts complex PDFs (SEC filings, DTU norms, legal codes, ISO standards)
into clean structured text for RAG pipelines.

Architecture: Gradio Blocks + FastAPI custom routes (same pattern as nomos-reranker-api).
  1. Build Gradio Blocks (demo UI)
  2. Create FastAPI app with custom routes
  3. Mount Gradio onto FastAPI via gr.mount_gradio_app()
  4. uvicorn serves the FastAPI parent

Endpoints:
  POST /convert      — Upload PDF file, returns JSON with extracted text/tables/metadata
  POST /convert-url  — Provide URL to PDF, downloads and converts
  GET  /health       — Health check
  GET  /info         — Service info
"""

import os
import io
import json
import time
import uuid
import shutil
import hashlib
import logging
import tempfile
import traceback
from pathlib import Path
from typing import Optional

import gradio as gr

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "1000"))  # chars per chunk
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "200"))  # overlap chars
TABLE_MODE = os.environ.get("TABLE_MODE", "fast")  # fast or accurate
TEMP_DIR = Path(tempfile.gettempdir()) / "docling_uploads"
TEMP_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Lazy converter loading (heavy imports deferred)
# ---------------------------------------------------------------------------
_converter = None
_load_time = None


def get_converter():
    """Lazily initialize DocumentConverter on first request."""
    global _converter, _load_time
    if _converter is not None:
        return _converter

    logger.info("Loading Docling DocumentConverter (first request)...")
    t0 = time.time()

    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat

    # Configure for CPU-basic memory efficiency
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True

    # Use FAST table mode by default for memory efficiency
    try:
        from docling.datamodel.pipeline_options import TableFormerMode
        if TABLE_MODE == "accurate":
            pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
            logger.info("Table structure mode: ACCURATE")
        else:
            pipeline_options.table_structure_options.mode = TableFormerMode.FAST
            logger.info("Table structure mode: FAST")
    except (ImportError, AttributeError) as e:
        logger.warning(f"Could not set TableFormerMode: {e}")

    _converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )
    _load_time = time.time() - t0
    logger.info(f"DocumentConverter loaded in {_load_time:.1f}s")
    return _converter


# ---------------------------------------------------------------------------
# Core conversion logic
# ---------------------------------------------------------------------------
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Split text into overlapping chunks."""
    if not text:
        return []

    chunks = []
    start = 0
    chunk_idx = 0
    while start < len(text):
        end = start + chunk_size
        chunk_text_piece = text[start:end]
        chunks.append({
            "index": chunk_idx,
            "text": chunk_text_piece,
            "char_start": start,
            "char_end": min(end, len(text)),
        })
        chunk_idx += 1
        start += chunk_size - overlap
        if start >= len(text):
            break
    return chunks


def extract_tables(doc) -> list[dict]:
    """Extract tables from a Docling document."""
    tables = []
    try:
        for i, table in enumerate(doc.tables):
            table_data = {
                "index": i,
                "num_rows": getattr(table, "num_rows", None),
                "num_cols": getattr(table, "num_cols", None),
            }
            # Try to export table as markdown or dataframe
            try:
                table_data["markdown"] = table.export_to_markdown()
            except Exception:
                pass
            try:
                df = table.export_to_dataframe()
                table_data["data"] = df.to_dict(orient="records")
                table_data["columns"] = list(df.columns)
            except Exception:
                pass
            # Fallback: just get text
            if "markdown" not in table_data and "data" not in table_data:
                try:
                    table_data["text"] = str(table)
                except Exception:
                    table_data["text"] = "[table extraction failed]"
            tables.append(table_data)
    except Exception as e:
        logger.warning(f"Table extraction error: {e}")
    return tables


def extract_pages(doc) -> list[dict]:
    """Try to extract per-page text from document."""
    pages = []
    try:
        # Docling DoclingDocument may have pages attribute or iterate differently
        md_text = doc.export_to_markdown()
        # Simple page split heuristic: split on page-break-like patterns
        # Docling markdown often uses --- or page markers
        page_texts = md_text.split("\n---\n") if "\n---\n" in md_text else [md_text]
        for i, page_text in enumerate(page_texts):
            page_text = page_text.strip()
            if page_text:
                pages.append({
                    "page_number": i + 1,
                    "text": page_text,
                    "char_count": len(page_text),
                })
    except Exception as e:
        logger.warning(f"Page extraction error: {e}")
    return pages


def convert_file(file_path: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> dict:
    """Convert a PDF file and return structured results."""
    t0 = time.time()
    file_path = Path(file_path)

    if not file_path.exists():
        return {"error": f"File not found: {file_path}"}

    file_size = file_path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        return {"error": f"File too large: {file_size / 1024 / 1024:.1f}MB (max {MAX_FILE_SIZE_MB}MB)"}

    # Compute file hash for dedup
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()[:16]

    try:
        converter = get_converter()
        result = converter.convert(str(file_path))
        doc = result.document

        # Full markdown text
        full_text = doc.export_to_markdown()

        # Extract tables
        tables = extract_tables(doc)

        # Extract pages
        pages = extract_pages(doc)

        # Create chunks
        chunks = chunk_text(full_text, chunk_size, chunk_overlap)

        elapsed = time.time() - t0

        return {
            "status": "success",
            "file_name": file_path.name,
            "file_size_bytes": file_size,
            "file_hash": file_hash,
            "full_text": full_text,
            "text_length": len(full_text),
            "pages": pages,
            "num_pages": len(pages),
            "tables": tables,
            "num_tables": len(tables),
            "chunks": chunks,
            "num_chunks": len(chunks),
            "chunk_config": {
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            },
            "processing_time_s": round(elapsed, 2),
            "_self_hosted": True,
            "_cost": 0.0,
        }

    except Exception as e:
        elapsed = time.time() - t0
        logger.error(f"Conversion error: {e}\n{traceback.format_exc()}")
        return {
            "status": "error",
            "error": str(e),
            "file_name": file_path.name,
            "processing_time_s": round(elapsed, 2),
        }


# ---------------------------------------------------------------------------
# 1. Gradio UI
# ---------------------------------------------------------------------------
def gradio_convert(file_obj, chunk_size: int = 1000, chunk_overlap: int = 200) -> str:
    """Gradio interface for PDF conversion."""
    if file_obj is None:
        return json.dumps({"error": "No file uploaded"}, indent=2)

    try:
        # Gradio file object has a .name attribute with the temp path
        file_path = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
        result = convert_file(file_path, int(chunk_size), int(chunk_overlap))

        # For UI display, truncate full_text if too long
        display_result = result.copy()
        if "full_text" in display_result and len(display_result["full_text"]) > 5000:
            display_result["full_text"] = display_result["full_text"][:5000] + f"\n\n... [truncated, {len(result['full_text'])} total chars]"

        # Truncate chunks for display
        if "chunks" in display_result and len(display_result["chunks"]) > 10:
            display_result["chunks"] = display_result["chunks"][:10]
            display_result["chunks"].append({"note": f"... {result['num_chunks']} total chunks (showing first 10)"})

        return json.dumps(display_result, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


with gr.Blocks(title="Nomos Docling API") as demo:
    gr.Markdown("# Nomos Docling Document Processor")
    gr.Markdown("""
    Convert complex PDFs (SEC filings, DTU norms, legal codes, ISO standards)
    into clean structured text for RAG pipelines.

    **API Endpoints:**
    - `POST /convert` — Upload PDF file, get JSON with text + tables + chunks
    - `POST /convert-url` — Convert PDF from URL
    - `GET /health` — Health check
    - `GET /info` — Service information

    **Features:** Full text extraction, table recognition, page splitting,
    configurable chunking, SHA-256 dedup hash.

    **Powered by:** [Docling](https://github.com/docling-project/docling) (MIT license, runs locally on CPU)
    """)

    with gr.Row():
        with gr.Column():
            file_input = gr.File(
                label="Upload PDF (max 50MB)",
                file_types=[".pdf"],
                type="filepath",
            )
            chunk_size_input = gr.Number(
                label="Chunk size (chars)", value=1000, minimum=100, maximum=10000
            )
            chunk_overlap_input = gr.Number(
                label="Chunk overlap (chars)", value=200, minimum=0, maximum=2000
            )
            convert_btn = gr.Button("Convert", variant="primary")

        with gr.Column():
            output = gr.Textbox(label="Results (JSON)", lines=25, max_lines=50)

    convert_btn.click(
        fn=gradio_convert,
        inputs=[file_input, chunk_size_input, chunk_overlap_input],
        outputs=output,
    )


# ---------------------------------------------------------------------------
# 2. FastAPI custom routes
# ---------------------------------------------------------------------------
from fastapi import FastAPI, Request as FastAPIRequest, UploadFile, File, Form
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Nomos Docling API", version="1.0.0")


@app.post("/convert")
async def api_convert(
    file: UploadFile = File(...),
    chunk_size: int = Form(default=CHUNK_SIZE),
    chunk_overlap: int = Form(default=CHUNK_OVERLAP),
):
    """Convert an uploaded PDF file to structured text."""
    if not file.filename:
        return JSONResponse({"error": "No file provided"}, status_code=400)

    # Check file extension
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            {"error": f"Unsupported file type: {file.filename}. Only PDF files are supported."},
            status_code=400,
        )

    # Save uploaded file to temp
    temp_path = TEMP_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    try:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            return JSONResponse(
                {"error": f"File too large: {len(content) / 1024 / 1024:.1f}MB (max {MAX_FILE_SIZE_MB}MB)"},
                status_code=413,
            )
        with open(temp_path, "wb") as f:
            f.write(content)

        result = convert_file(str(temp_path), chunk_size, chunk_overlap)

        if result.get("status") == "error":
            return JSONResponse(result, status_code=500)
        return JSONResponse(result)

    finally:
        # Cleanup temp file
        if temp_path.exists():
            temp_path.unlink()


@app.post("/convert-url")
async def api_convert_url(request: FastAPIRequest):
    """Convert a PDF from a URL."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    url = body.get("url", "")
    chunk_size = body.get("chunk_size", CHUNK_SIZE)
    chunk_overlap = body.get("chunk_overlap", CHUNK_OVERLAP)

    if not url:
        return JSONResponse({"error": "url is required"}, status_code=400)

    # Download file
    temp_path = TEMP_DIR / f"{uuid.uuid4().hex}_download.pdf"
    try:
        import urllib.request
        import urllib.error

        logger.info(f"Downloading PDF from: {url}")
        t0 = time.time()

        req = urllib.request.Request(url, headers={"User-Agent": "Nomos-Docling/1.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()

        download_time = time.time() - t0
        logger.info(f"Downloaded {len(content)} bytes in {download_time:.1f}s")

        if len(content) > MAX_FILE_SIZE_BYTES:
            return JSONResponse(
                {"error": f"File too large: {len(content) / 1024 / 1024:.1f}MB (max {MAX_FILE_SIZE_MB}MB)"},
                status_code=413,
            )

        with open(temp_path, "wb") as f:
            f.write(content)

        result = convert_file(str(temp_path), chunk_size, chunk_overlap)

        if result.get("status") == "error":
            return JSONResponse(result, status_code=500)

        # Add download metadata
        result["source_url"] = url
        result["download_time_s"] = round(download_time, 2)

        return JSONResponse(result)

    except urllib.error.URLError as e:
        return JSONResponse({"error": f"Failed to download URL: {e}"}, status_code=400)
    except Exception as e:
        logger.error(f"URL conversion error: {e}\n{traceback.format_exc()}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if temp_path.exists():
            temp_path.unlink()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return JSONResponse({
        "status": "ok",
        "service": "nomos-docling-api",
        "converter_loaded": _converter is not None,
        "load_time_s": round(_load_time, 2) if _load_time else None,
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "table_mode": TABLE_MODE,
    })


@app.get("/info")
async def info():
    """Service information endpoint."""
    return JSONResponse({
        "service": "nomos-docling-api",
        "version": "1.0.0",
        "framework": "Docling",
        "description": "PDF document processor for RAG pipelines",
        "supported_formats": ["pdf"],
        "endpoints": {
            "POST /convert": "Upload PDF file, returns structured text + tables + chunks",
            "POST /convert-url": "Convert PDF from URL",
            "GET /health": "Health check",
            "GET /info": "Service information",
        },
        "features": [
            "Full markdown text extraction",
            "Table structure recognition (FAST/ACCURATE modes)",
            "OCR for scanned documents",
            "Per-page text splitting",
            "Configurable chunking with overlap",
            "SHA-256 file dedup hash",
        ],
        "config": {
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "default_chunk_size": CHUNK_SIZE,
            "default_chunk_overlap": CHUNK_OVERLAP,
            "table_mode": TABLE_MODE,
        },
        "converter_loaded": _converter is not None,
        "api_key_required": False,
        "cost": "free",
        "_self_hosted": True,
    })


# ---------------------------------------------------------------------------
# 3. Mount Gradio onto FastAPI (custom routes stay accessible)
# ---------------------------------------------------------------------------
app = gr.mount_gradio_app(app, demo, path="/")

logger.info("Docling API ready. Converter will load on first request.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
