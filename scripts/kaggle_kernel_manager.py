#!/usr/bin/env python3
"""
Kaggle Kernel Manager — Automate GPU evolution via Kaggle kernels.

Usage:
    python3 scripts/kaggle_kernel_manager.py \\
        --username <username> \\
        --kernel-slug <nba-quant-gpu-v2> \\
        --notebook <path/to/notebook.ipynb> \\
        --wait \\
        --timeout-minutes 180 \\
        --output-dir ./data/kaggle_results

Steps:
    1. Create/update kernel metadata (kernel-metadata.json)
    2. Push notebook to Kaggle (auto-starts kernel)
    3. Poll status until complete
    4. Download outputs
    5. Parse and report results
"""

import argparse
import json
import subprocess
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class KaggleKernelManager:
    def __init__(self, username: str, kernel_slug: str, verbose: bool = True):
        self.username = username
        self.kernel_slug = kernel_slug
        self.full_id = f"{username}/{kernel_slug}"
        self.verbose = verbose

    def log(self, msg: str):
        if self.verbose:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] {msg}", flush=True)

    def push_kernel(
        self,
        notebook_path: Path,
        enable_gpu: bool = True,
        enable_internet: bool = True,
        timeout_seconds: Optional[int] = None,
    ) -> bool:
        """
        Push notebook to Kaggle and auto-start kernel.

        Args:
            notebook_path: Path to .ipynb file
            enable_gpu: Enable GPU acceleration
            enable_internet: Enable internet access
            timeout_seconds: Kernel execution timeout

        Returns:
            True if push succeeded
        """
        notebook_path = Path(notebook_path)
        if not notebook_path.exists():
            self.log(f"ERROR: Notebook not found: {notebook_path}")
            return False

        # Create kernel working directory
        kernel_dir = Path("/tmp/kaggle_kernel_push") / self.kernel_slug
        kernel_dir.mkdir(parents=True, exist_ok=True)

        # Create metadata file
        metadata = {
            "id": self.full_id,
            "title": f"NBA Quant GPU Evolution — {self.kernel_slug}",
            "language": "python",
            "kernel_type": "notebook",
            "is_private": False,
            "enable_gpu": enable_gpu,
            "enable_internet": enable_internet,
            "code_file": notebook_path.name,
        }

        metadata_file = kernel_dir / "kernel-metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        self.log(f"Metadata: {metadata_file}")

        # Copy notebook
        import shutil
        dest_notebook = kernel_dir / notebook_path.name
        shutil.copy(notebook_path, dest_notebook)
        self.log(f"Copied notebook: {notebook_path} → {dest_notebook}")

        # Push
        cmd = ["kaggle", "kernels", "push", "-p", str(kernel_dir)]
        if timeout_seconds:
            cmd.extend(["--timeout", str(timeout_seconds)])

        self.log(f"Pushing: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.log(f"ERROR: Push failed!")
            self.log(f"STDOUT: {result.stdout}")
            self.log(f"STDERR: {result.stderr}")
            return False

        self.log(f"✓ Kernel {self.full_id} pushed successfully (auto-running)")
        return True

    def wait_for_completion(
        self,
        max_wait_minutes: int = 180,
        initial_poll_interval: int = 30,
        max_poll_interval: int = 120,
    ) -> bool:
        """
        Poll kernel status until complete or timeout.

        Uses exponential backoff: 30s → 60s → 120s.

        Args:
            max_wait_minutes: Maximum wait time
            initial_poll_interval: Initial poll interval (seconds)
            max_poll_interval: Max poll interval (seconds)

        Returns:
            True if kernel completed successfully
        """
        start_time = time.time()
        max_wait_seconds = max_wait_minutes * 60
        current_interval = initial_poll_interval
        last_status = None

        self.log(f"Waiting for completion (max {max_wait_minutes}m)...")

        while time.time() - start_time < max_wait_seconds:
            elapsed = int((time.time() - start_time) / 60)
            status = self.get_status()

            if status != last_status:
                self.log(f"[{elapsed:3d}m] Status: {status}")
                last_status = status

            if status == "complete":
                self.log(f"✓ Kernel completed successfully in {elapsed}m")
                return True
            elif status == "failed":
                self.log(f"✗ Kernel FAILED after {elapsed}m")
                return False
            elif status == "unknown":
                self.log(f"⚠ Status unknown (kernel may not exist yet)")

            # Exponential backoff
            time.sleep(current_interval)
            current_interval = min(current_interval + 30, max_poll_interval)

        self.log(f"✗ TIMEOUT: Kernel did not complete in {max_wait_minutes}m")
        return False

    def get_status(self) -> str:
        """
        Get current kernel execution status.

        Returns:
            status: 'queued', 'running', 'complete', 'failed', 'unknown'
        """
        cmd = ["kaggle", "kernels", "status", self.full_id]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return "unknown"

        # Parse output: "Status: complete"
        output = result.stdout.strip()
        for line in output.split("\n"):
            if line.lower().startswith("status:"):
                status_text = line.split(":", 1)[-1].strip().lower()
                # Normalize
                if status_text in ["queued", "running", "complete", "failed"]:
                    return status_text
                return status_text

        return "unknown"

    def download_outputs(self, output_dir: Path, force_overwrite: bool = True) -> bool:
        """
        Download kernel output files.

        Args:
            output_dir: Destination directory
            force_overwrite: Overwrite existing files

        Returns:
            True if download succeeded
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = ["kaggle", "kernels", "output", self.full_id, "-p", str(output_dir)]
        if force_overwrite:
            cmd.append("-o")

        self.log(f"Downloading outputs to {output_dir}...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.log(f"ERROR: Output download failed!")
            self.log(f"STDERR: {result.stderr}")
            return False

        self.log(f"✓ Outputs downloaded: {output_dir}")

        # List files
        files = list(output_dir.glob("**/*"))
        for f in sorted(files):
            if f.is_file():
                size_mb = f.stat().st_size / (1024 * 1024)
                self.log(f"  - {f.name} ({size_mb:.2f} MB)")

        return True

    def pull_source(self, output_dir: Path, include_metadata: bool = True) -> bool:
        """
        Download kernel source code.

        Args:
            output_dir: Destination directory
            include_metadata: Also download kernel-metadata.json

        Returns:
            True if pull succeeded
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = ["kaggle", "kernels", "pull", self.full_id, "-p", str(output_dir)]
        if include_metadata:
            cmd.append("-m")

        self.log(f"Pulling source to {output_dir}...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            self.log(f"ERROR: Pull failed!")
            self.log(f"STDERR: {result.stderr}")
            return False

        self.log(f"✓ Source pulled: {output_dir}")
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Automate GPU kernel evolution via Kaggle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Push notebook and wait
  python3 scripts/kaggle_kernel_manager.py \\
    --username myusername \\
    --kernel-slug nba-quant-gpu-v2 \\
    --notebook ./nba_gpu_v2.ipynb \\
    --wait \\
    --output-dir ./results

  # Just check status
  python3 scripts/kaggle_kernel_manager.py \\
    --username myusername \\
    --kernel-slug nba-quant-gpu-v2 \\
    --status-only
        """,
    )

    parser.add_argument(
        "--username", required=True, help="Kaggle username"
    )
    parser.add_argument(
        "--kernel-slug", required=True, help="Kernel slug (e.g., nba-quant-gpu-v2)"
    )
    parser.add_argument(
        "--notebook", help="Path to .ipynb notebook to push"
    )
    parser.add_argument(
        "--wait", action="store_true", help="Wait for kernel completion"
    )
    parser.add_argument(
        "--status-only", action="store_true", help="Check status only (no push)"
    )
    parser.add_argument(
        "--timeout-minutes", type=int, default=180, help="Max wait time (default 180)"
    )
    parser.add_argument(
        "--kernel-timeout-seconds",
        type=int,
        default=7200,
        help="Kernel execution timeout in seconds (default 7200)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./kaggle_outputs"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Skip downloading outputs",
    )
    parser.add_argument(
        "--verbose", action="store_true", default=True, help="Verbose logging"
    )

    args = parser.parse_args()

    mgr = KaggleKernelManager(args.username, args.kernel_slug, verbose=args.verbose)

    # Status only
    if args.status_only:
        status = mgr.get_status()
        print(f"Status: {status}")
        return 0 if status in ["complete", "running", "queued"] else 1

    # Push + wait + download
    if args.notebook:
        if not mgr.push_kernel(
            Path(args.notebook),
            enable_gpu=True,
            enable_internet=True,
            timeout_seconds=args.kernel_timeout_seconds,
        ):
            return 1

    # Wait for completion
    if args.wait:
        if not mgr.wait_for_completion(max_wait_minutes=args.timeout_minutes):
            return 1

    # Download outputs
    if not args.no_download:
        if not mgr.download_outputs(args.output_dir, force_overwrite=True):
            return 1

    mgr.log("✓ All steps completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
