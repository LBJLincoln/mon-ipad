
import json
import os
import subprocess
from datetime import datetime, timezone, timedelta

def get_execution_details(exec_id):
    """
    Fetches execution details for a given ID using node-analyzer.py
    and extracts the startedAt timestamp.
    """
    command = f"python3 eval/node-analyzer.py --execution-id {exec_id}"
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        output = result.stdout
        
        started_at_line = next((line for line in output.splitlines() if "Status:" in line), None)
        if started_at_line:
            # Expected format example: "  Status: done | Duration: 5410ms | Started: 2026-02-12T08:18:20.123Z"
            # It seems the `startedAt` is not printed when using `--execution-id`.
            # Let's try to fetch the raw execution with the API and parse it.
            # However, `node-analyzer.py`'s `fetch_execution_by_id` *does* return a dict.
            # It just prints a summary. I will re-parse the output from the fetch directly from the logs.
            pass

        # Since node-analyzer.py prints a summary, I'll need to parse the generated diagnostic JSON directly.
        # However, calling node-analyzer.py --execution-id doesn't save to a file.
        # This means I must modify node-analyzer.py to return JSON or parse its printout more carefully.

        # Let's assume for now that the relevant lines start with "Status:", "Duration:", "Query:" etc.
        # And I'll need to adjust `node-analyzer.py` to print `started_at` or `fetch_execution_by_id`
        # should save its result to a temporary file.

        # The `fetch_execution_by_id` function in `node-analyzer.py` returns a dictionary.
        # I can import it and call it directly.

        # For now, I will modify `node-analyzer.py` to include `startedAt` in the `--execution-id` output.
        # Or, I can directly import `fetch_execution_by_id` from `node-analyzer.py` in this script.

        # The latter is cleaner. I will import `fetch_execution_by_id` directly.
        pass

    except subprocess.CalledProcessError as e:
        print(f"Error fetching details for {exec_id}: {e.stderr}")
        return None
    except FileNotFoundError:
        print(f"Error: python3 command not found. Ensure python3 is in your PATH.")
        return None
    return None

def main():
    # Define the time range in UTC
    # Paris time (CET) is UTC+1 in February
    start_time_paris = datetime(2026, 2, 12, 3, 0, 0, tzinfo=timezone.utc) # User's 3 AM Paris time
    end_time_paris = datetime(2026, 2, 12, 10, 0, 0, tzinfo=timezone.utc) # User's 10 AM Paris time

    # Convert to UTC. Paris is UTC+1 in Feb.
    start_time_utc = start_time_paris - timedelta(hours=1)
    end_time_utc = end_time_paris - timedelta(hours=1)
    
    # Check if the conversion is correct.
    # The user gave 3AM-10AM Paris time.
    # If Paris is UTC+1, then 3AM Paris is 2AM UTC.
    # 10AM Paris is 9AM UTC.
    # So, I need to define start_time_paris and end_time_paris as naive datetime, then localize and convert to UTC.
    # Or simply define them directly in UTC.

    start_time_utc = datetime(2026, 2, 12, 2, 0, 0, tzinfo=timezone.utc)
    end_time_utc = datetime(2026, 2, 12, 9, 0, 0, tzinfo=timezone.utc)


    # File paths for diagnostic reports
    standard_report_path = "logs/diagnostics/latest-standard.json"
    graph_report_path = "logs/diagnostics/latest-graph.json"

    all_exec_ids = set()

    # Read standard report
    if os.path.exists(standard_report_path):
        with open(standard_report_path, 'r') as f:
            report = json.load(f)
            all_exec_ids.update(report.get("execution_ids", []))
    
    # Read graph report
    if os.path.exists(graph_report_path):
        with open(graph_report_path, 'r') as f:
            report = json.load(f)
            all_exec_ids.update(report.get("execution_ids", []))

    if not all_exec_ids:
        print("No execution IDs found in the diagnostic reports.")
        return

    print(f"Found {len(all_exec_ids)} unique execution IDs. Filtering for {start_time_utc.isoformat()} to {end_time_utc.isoformat()} (UTC).")

    filtered_executions = []

    # Dynamically load node-analyzer.py
    import sys
    from importlib.machinery import SourceFileLoader
    EVAL_DIR = os.path.join(os.path.dirname(__file__), 'eval')
    sys.path.insert(0, EVAL_DIR)
    try:
        node_analyzer = SourceFileLoader("node_analyzer", os.path.join(EVAL_DIR, "node-analyzer.py")).load_module()
    except Exception as e:
        print(f"Error loading node-analyzer.py: {e}")
        return

    # Set the N8N_API_KEY for node_analyzer
    n8n_api_key = os.environ.get("N8N_API_KEY")
    if not n8n_api_key:
        print("N8N_API_KEY environment variable is not set. Please set it before running this script.")
        return
    node_analyzer.N8N_API_KEY = n8n_api_key

    for exec_id in all_exec_ids:
        details = node_analyzer.fetch_execution_by_id(exec_id)
        if details and details.get("started_at"):
            try:
                # Convert "2026-02-12T08:18:20.123Z" to datetime object
                started_at_str = details["started_at"].replace("Z", "+00:00")
                started_at_dt = datetime.fromisoformat(started_at_str)

                if start_time_utc <= started_at_dt <= end_time_utc:
                    filtered_executions.append({
                        "execution_id": exec_id,
                        "workflow_name": details.get("pipeline", "unknown"),
                        "started_at": started_at_dt.isoformat()
                    })
            except ValueError:
                print(f"Warning: Could not parse started_at for execution {exec_id}: {details['started_at']}")

    if filtered_executions:
        print("\n--- N8n Executions within the specified time range (2026-02-12 03:00 AM - 10:00 AM Paris Time) ---")
        for exec_info in sorted(filtered_executions, key=lambda x: x["started_at"]):
            print(f"  ID: {exec_info['execution_id']}, Workflow: {exec_info['workflow_name']}, Started At (UTC): {exec_info['started_at']}")
        print(f"\nTotal: {len(filtered_executions)} executions found.")
    else:
        print("No N8n executions found within the specified time range.")

if __name__ == "__main__":
    main()
