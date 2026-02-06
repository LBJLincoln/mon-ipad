-- ============================================================
-- Purge all error results from benchmark_results
-- Run BEFORE re-testing to clear the 28K+ "fetch is not defined" errors
-- ============================================================

-- 1. Check current state
SELECT
    'BEFORE PURGE' as phase,
    COUNT(*) as total_results,
    COUNT(*) FILTER (WHERE error IS NOT NULL) as error_results,
    COUNT(*) FILTER (WHERE error IS NULL AND actual_answer IS NOT NULL AND actual_answer != '') as valid_results
FROM benchmark_results
WHERE tenant_id = 'benchmark';

-- 2. Delete error results
DELETE FROM benchmark_results
WHERE tenant_id = 'benchmark'
  AND (error IS NOT NULL OR actual_answer IS NULL OR actual_answer = '');

-- 3. Verify after purge
SELECT
    'AFTER PURGE' as phase,
    COUNT(*) as total_results,
    COUNT(*) FILTER (WHERE error IS NOT NULL) as error_results,
    COUNT(*) FILTER (WHERE error IS NULL AND actual_answer IS NOT NULL AND actual_answer != '') as valid_results
FROM benchmark_results
WHERE tenant_id = 'benchmark';

-- 4. Also reset accuracy scores to allow re-evaluation
UPDATE benchmark_results
SET accuracy = NULL, f1_score = NULL
WHERE tenant_id = 'benchmark'
  AND accuracy = 0
  AND actual_answer IS NOT NULL
  AND actual_answer != '';
