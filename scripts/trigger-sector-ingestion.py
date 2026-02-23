#!/usr/bin/env python3
"""
Trigger Sector Ingestion — Send processed documents to n8n workflows
Handles batching, rate limiting, progress tracking, and resume capability
Author: Claude Opus 4.6
Created: 2026-02-20
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IngestionTrigger:
    """Trigger n8n ingestion workflows with rate limiting and progress tracking."""

    # Webhook endpoints for each pipeline
    WEBHOOK_PATHS = {
        "standard": "/webhook/rag-v6-ingestion",
        "graph": "/webhook/ff622742-6d71-4e91-af71-b5c666088717",  # Graph enrichment
        "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9"
    }

    def __init__(
        self,
        n8n_host: str = "https://lbjlincoln-nomos-rag-engine.hf.space",
        batch_dir: str = "/home/termius/mon-ipad/outputs/sector-batches",
        max_concurrent: int = 2,
        delay_seconds: int = 3,
        progress_file: str = "/tmp/ingestion-progress.json"
    ):
        self.n8n_host = n8n_host.rstrip('/')
        self.batch_dir = Path(batch_dir)
        self.max_concurrent = max_concurrent
        self.delay_seconds = delay_seconds
        self.progress_file = Path(progress_file)

        # Stats
        self.stats = {
            "total_batches": 0,
            "processed_batches": 0,
            "total_documents": 0,
            "processed_documents": 0,
            "skipped_documents": 0,
            "errors": 0,
            "by_pipeline": {},
            "start_time": datetime.utcnow().isoformat(),
            "end_time": None
        }

        # Load progress if resuming
        self.processed_items = set()
        self._load_progress()

    def _load_progress(self) -> None:
        """Load progress from previous run if it exists."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    progress = json.load(f)

                self.processed_items = set(progress.get("processed_items", []))
                logger.info(f"Loaded progress: {len(self.processed_items)} items already processed")

            except Exception as e:
                logger.warning(f"Could not load progress file: {e}")

    def _save_progress(self) -> None:
        """Save current progress to file."""
        try:
            progress = {
                "processed_items": list(self.processed_items),
                "stats": self.stats,
                "last_update": datetime.utcnow().isoformat()
            }

            with open(self.progress_file, 'w') as f:
                json.dump(progress, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving progress: {e}")

    def _get_webhook_url(self, pipeline: str) -> str:
        """Get full webhook URL for a pipeline."""
        path = self.WEBHOOK_PATHS.get(pipeline, self.WEBHOOK_PATHS["standard"])
        return f"{self.n8n_host}{path}"

    def send_document(self, doc: Dict[str, Any], pipeline: str) -> Dict[str, Any]:
        """
        Send a single document to n8n webhook.

        Args:
            doc: Processed document with metadata and chunks
            pipeline: Target pipeline (standard/graph/quantitative)

        Returns:
            Response dict with status and details
        """
        doc_id = doc["metadata"]["id"]

        # Check if already processed
        if doc_id in self.processed_items:
            logger.debug(f"Skipping already processed document: {doc_id}")
            self.stats["skipped_documents"] += 1
            return {"status": "skipped", "doc_id": doc_id}

        # Get webhook URL
        webhook_url = self._get_webhook_url(pipeline)

        # Prepare payload
        payload = {
            "document": doc["metadata"],
            "chunks": doc["chunks"],
            "chunk_count": doc["chunk_count"],
            "ingestion_timestamp": datetime.utcnow().isoformat(),
            "source": "sector-processing"
        }

        try:
            # Send POST request
            logger.debug(f"Sending document {doc_id} to {webhook_url}")

            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            response.raise_for_status()

            # Mark as processed
            self.processed_items.add(doc_id)
            self.stats["processed_documents"] += 1

            # Update pipeline stats
            self.stats["by_pipeline"][pipeline] = self.stats["by_pipeline"].get(pipeline, 0) + 1

            # Save progress periodically
            if self.stats["processed_documents"] % 10 == 0:
                self._save_progress()

            return {
                "status": "success",
                "doc_id": doc_id,
                "status_code": response.status_code,
                "response": response.json() if response.text else {}
            }

        except requests.exceptions.Timeout:
            logger.error(f"Timeout sending document {doc_id}")
            self.stats["errors"] += 1
            return {"status": "timeout", "doc_id": doc_id}

        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending document {doc_id}: {e}")
            self.stats["errors"] += 1
            return {"status": "error", "doc_id": doc_id, "error": str(e)}

        except Exception as e:
            logger.error(f"Unexpected error sending document {doc_id}: {e}", exc_info=True)
            self.stats["errors"] += 1
            return {"status": "error", "doc_id": doc_id, "error": str(e)}

    def process_batch_file(self, batch_file: Path) -> Dict[str, Any]:
        """
        Process a single batch file.

        Args:
            batch_file: Path to batch JSON file

        Returns:
            Processing stats for this batch
        """
        logger.info(f"Processing batch file: {batch_file.name}")

        try:
            with open(batch_file, 'r', encoding='utf-8') as f:
                batch_data = json.load(f)

            documents = batch_data.get("documents", [])
            batch_stats = {
                "batch_file": batch_file.name,
                "total_docs": len(documents),
                "processed": 0,
                "skipped": 0,
                "errors": 0
            }

            for doc in documents:
                pipeline = doc["metadata"].get("pipeline", "standard")

                # Send document
                result = self.send_document(doc, pipeline)

                if result["status"] == "success":
                    batch_stats["processed"] += 1
                elif result["status"] == "skipped":
                    batch_stats["skipped"] += 1
                else:
                    batch_stats["errors"] += 1

                # Rate limiting delay
                time.sleep(self.delay_seconds)

            self.stats["processed_batches"] += 1

            logger.info(
                f"Batch {batch_file.name} complete: "
                f"{batch_stats['processed']} processed, "
                f"{batch_stats['skipped']} skipped, "
                f"{batch_stats['errors']} errors"
            )

            return batch_stats

        except Exception as e:
            logger.error(f"Error processing batch file {batch_file}: {e}", exc_info=True)
            self.stats["errors"] += 1
            return {
                "batch_file": batch_file.name,
                "error": str(e)
            }

    def process_batch_file_concurrent(self, batch_file: Path) -> Dict[str, Any]:
        """
        Process a batch file with concurrent requests (respects max_concurrent).

        Args:
            batch_file: Path to batch JSON file

        Returns:
            Processing stats for this batch
        """
        logger.info(f"Processing batch file (concurrent): {batch_file.name}")

        try:
            with open(batch_file, 'r', encoding='utf-8') as f:
                batch_data = json.load(f)

            documents = batch_data.get("documents", [])
            batch_stats = {
                "batch_file": batch_file.name,
                "total_docs": len(documents),
                "processed": 0,
                "skipped": 0,
                "errors": 0
            }

            # Process with thread pool
            with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                # Submit all tasks
                futures = {
                    executor.submit(
                        self.send_document,
                        doc,
                        doc["metadata"].get("pipeline", "standard")
                    ): doc
                    for doc in documents
                }

                # Collect results
                for future in as_completed(futures):
                    doc = futures[future]

                    try:
                        result = future.result()

                        if result["status"] == "success":
                            batch_stats["processed"] += 1
                        elif result["status"] == "skipped":
                            batch_stats["skipped"] += 1
                        else:
                            batch_stats["errors"] += 1

                        # Rate limiting delay between results
                        time.sleep(self.delay_seconds / self.max_concurrent)

                    except Exception as e:
                        logger.error(f"Error processing document {doc['metadata']['id']}: {e}")
                        batch_stats["errors"] += 1

            self.stats["processed_batches"] += 1

            logger.info(
                f"Batch {batch_file.name} complete: "
                f"{batch_stats['processed']} processed, "
                f"{batch_stats['skipped']} skipped, "
                f"{batch_stats['errors']} errors"
            )

            return batch_stats

        except Exception as e:
            logger.error(f"Error processing batch file {batch_file}: {e}", exc_info=True)
            self.stats["errors"] += 1
            return {
                "batch_file": batch_file.name,
                "error": str(e)
            }

    def run(self, resume: bool = False, concurrent: bool = True) -> Dict[str, Any]:
        """
        Run ingestion for all batch files.

        Args:
            resume: Skip already processed items
            concurrent: Use concurrent requests (up to max_concurrent)

        Returns:
            Final statistics
        """
        # Find all batch files
        batch_files = sorted(self.batch_dir.glob("batch_*.json"))
        self.stats["total_batches"] = len(batch_files)

        logger.info(f"Found {len(batch_files)} batch files to process")
        logger.info(f"Mode: {'concurrent' if concurrent else 'sequential'} (max_concurrent={self.max_concurrent})")
        logger.info(f"Resume: {resume}")

        if not batch_files:
            logger.warning("No batch files found")
            return self.stats

        # Count total documents
        for batch_file in batch_files:
            try:
                with open(batch_file, 'r') as f:
                    batch_data = json.load(f)
                self.stats["total_documents"] += len(batch_data.get("documents", []))
            except Exception as e:
                logger.error(f"Error reading batch file {batch_file}: {e}")

        logger.info(f"Total documents to process: {self.stats['total_documents']}")

        # Process each batch
        batch_results = []

        for i, batch_file in enumerate(batch_files, 1):
            logger.info(f"Processing batch {i}/{len(batch_files)}")

            # Choose processing method
            if concurrent:
                result = self.process_batch_file_concurrent(batch_file)
            else:
                result = self.process_batch_file(batch_file)

            batch_results.append(result)

            # Progress update
            logger.info(
                f"Overall progress: {self.stats['processed_documents']}/{self.stats['total_documents']} documents "
                f"({self.stats['processed_batches']}/{self.stats['total_batches']} batches)"
            )

        # Final save
        self.stats["end_time"] = datetime.utcnow().isoformat()
        self._save_progress()

        # Write final stats
        self._write_final_stats(batch_results)

        return self.stats

    def _write_final_stats(self, batch_results: List[Dict[str, Any]]) -> None:
        """Write final statistics to file."""
        stats_file = self.batch_dir / "ingestion_stats.json"

        final_stats = {
            "summary": self.stats,
            "batch_results": batch_results
        }

        with open(stats_file, 'w') as f:
            json.dump(final_stats, f, indent=2)

        logger.info(f"Wrote final stats to {stats_file}")

        # Print summary
        print("\n=== Ingestion Summary ===")
        print(f"Total batches: {self.stats['total_batches']}")
        print(f"Processed batches: {self.stats['processed_batches']}")
        print(f"Total documents: {self.stats['total_documents']}")
        print(f"Processed documents: {self.stats['processed_documents']}")
        print(f"Skipped documents: {self.stats['skipped_documents']}")
        print(f"Errors: {self.stats['errors']}")

        print("\nBy pipeline:")
        for pipeline, count in self.stats["by_pipeline"].items():
            print(f"  {pipeline}: {count}")

        # Calculate duration
        if self.stats["end_time"]:
            start = datetime.fromisoformat(self.stats["start_time"])
            end = datetime.fromisoformat(self.stats["end_time"])
            duration = (end - start).total_seconds()
            print(f"\nTotal duration: {duration:.1f} seconds")
            if self.stats["processed_documents"] > 0:
                print(f"Average: {duration / self.stats['processed_documents']:.2f} sec/doc")


def main():
    parser = argparse.ArgumentParser(
        description="Trigger n8n ingestion workflows for processed sector documents"
    )

    parser.add_argument(
        "--n8n-host",
        default=os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space"),
        help="n8n base URL (default: HF Space)"
    )

    parser.add_argument(
        "--batch-dir",
        default="/home/termius/mon-ipad/outputs/sector-batches",
        help="Directory containing processed batches (default: /home/termius/mon-ipad/outputs/sector-batches)"
    )

    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=2,
        help="Maximum concurrent requests (default: 2)"
    )

    parser.add_argument(
        "--delay",
        type=int,
        default=3,
        help="Delay between requests in seconds (default: 3)"
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous run (skip already processed items)"
    )

    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Process sequentially instead of concurrently"
    )

    parser.add_argument(
        "--progress-file",
        default="/tmp/ingestion-progress.json",
        help="Progress file path (default: /tmp/ingestion-progress.json)"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create trigger
    trigger = IngestionTrigger(
        n8n_host=args.n8n_host,
        batch_dir=args.batch_dir,
        max_concurrent=args.max_concurrent,
        delay_seconds=args.delay,
        progress_file=args.progress_file
    )

    # Run ingestion
    stats = trigger.run(
        resume=args.resume,
        concurrent=not args.sequential
    )

    # Exit code based on errors
    exit_code = 0
    if stats["errors"] > 0:
        logger.warning(f"Completed with {stats['errors']} errors")
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
