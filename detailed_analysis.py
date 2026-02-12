
import os
import subprocess
import json
from datetime import datetime, timezone, timedelta

def main():
    exec_ids_to_analyze = [
        "19429", "19430", "19431", "19432", "19433", "19435", "19436", "19437", "19438", "19439",
        "19440", "19441", "19442", "19443", "19444", "19445", "19446", "19447", "19448", "19449",
        "19455", "19456"
    ]

    # Ensure N8N_API_KEY is available in the environment for subprocess calls
    n8n_api_key = os.environ.get("N8N_API_KEY")
    if not n8n_api_key:
        print("N8N_API_KEY environment variable is not set. Please set it before running this script.")
        return

    # Counter for successful analyses
    successful_analyses = 0

    print(f"\nStarting detailed analysis for {len(exec_ids_to_analyze)} execution IDs...")

    for exec_id in exec_ids_to_analyze:
        print(f"\n{'='*80}")
        print(f"Analyzing N8n Execution ID: {exec_id}")
        print(f"{'='*80}")

        command = f'python3 analyze_n8n_executions.py --execution-id {exec_id}'
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True, env=os.environ)
            print(result.stdout)
            if "Details saved to" in result.stdout:
                successful_analyses += 1
        except subprocess.CalledProcessError as e:
            print(f"Error analyzing execution {exec_id}:")
            print(e.stderr)
        except Exception as e:
            print(f"An unexpected error occurred for execution {exec_id}: {e}")
    
    print(f"\n{'='*80}")
    print(f"Detailed analysis complete. Successfully analyzed {successful_analyses} out of {len(exec_ids_to_analyze)} executions.")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
