#!/usr/bin/env python3
"""Kaggle GPU Runner Trigger — Called by Eve to launch GPU training on Kaggle."""
import subprocess, json, sys, time

KERNEL_ID = "alexismoret6/nba-quant-gpu-runner"

def trigger_run():
    """Push the kernel to trigger a new run."""
    result = subprocess.run(
        ["kaggle", "kernels", "push", "-p", "/tmp/kaggle-kernel"],
        capture_output=True, text=True
    )
    print(f"Push result: {result.stdout}")
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    return result.returncode == 0

def check_status():
    """Check kernel run status."""
    result = subprocess.run(
        ["kaggle", "kernels", "status", KERNEL_ID],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def get_output():
    """Get kernel output."""
    subprocess.run(
        ["kaggle", "kernels", "output", KERNEL_ID, "-p", "/tmp/kaggle-output"],
        capture_output=True, text=True
    )

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "trigger":
        trigger_run()
    elif action == "status":
        print(check_status())
    elif action == "output":
        get_output()
    elif action == "poll":
        # Trigger and poll until complete
        trigger_run()
        while True:
            status = check_status()
            print(f"Status: {status}")
            if "complete" in status.lower() or "error" in status.lower():
                break
            time.sleep(30)
        get_output()
