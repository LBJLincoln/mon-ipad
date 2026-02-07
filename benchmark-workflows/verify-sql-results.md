# Verification Report: SQL & Graph RAG Query Results
**Date:** 2026-02-07
**Tenant:** benchmark

## 1. TechVision Revenue SQL Query — FAILURE

### Query Executed
```sql
SELECT SUM(revenue) FROM financials
WHERE company_name = 'TechVision'
  AND fiscal_year = 2023
  AND tenant_id = 'benchmark'
LIMIT 1000
```

### Result: `SUM = null`

### Root Cause
The query uses `company_name = 'TechVision'` but the seed data contains `company_name = 'TechVision Inc'`.
No rows match, so `SUM()` returns `null`.

**Source:** `financial-tables-migration.sql` line 164:
```sql
('benchmark','techvision','TechVision Inc',2023,'FY', 6745000000, ...)
```

### Expected Result
With the correct company name, the FY 2023 revenue for TechVision Inc is **$6,745,000,000**.

Quarterly breakdown:
- Q1: $1,552,350,000
- Q2: $1,619,400,000
- Q3: $1,721,750,000
- Q4: $1,851,500,000

### Corrected Query
```sql
SELECT SUM(revenue) FROM financials
WHERE company_name = 'TechVision Inc'
  AND fiscal_year = 2023
  AND period = 'FY'
  AND tenant_id = 'benchmark';
-- Expected result: 6745000000
```

> **Note:** Without filtering on `period = 'FY'`, the SUM would include both the full-year and quarterly rows, resulting in double-counting.

### Validation Bug
The QUANTITATIVE engine marked `validation_status: "PASSED"` despite the query returning `null`. This is a false positive — the validator should flag null results on aggregation queries as failures.

---

## 2. Marie Curie Graph RAG Query — SUCCESS

### Query
"What is the relationship between Marie Curie and the Nobel Prize?"

### Response
> Marie Curie a remporté deux prix Nobel : le prix Nobel de physique en 1903 et le prix Nobel de chimie en 1911.

### Verification Against Data Sources
- **Neo4j:** `Marie Curie → Nobel Foundation` (CONNECTE relationship) ✓
- **Community Summary (comm-science-01):** "Marie Curie pioneered radioactivity research in Paris and won Nobel Prizes in Physics and Chemistry" ✓
- **Community Summary (comm-health-01):** Marie Curie linked to Cancer research via radioactivity ✓

Response is factually correct and consistent with the knowledge graph.

---

## Summary

| Query | Status | Issue |
|-------|--------|-------|
| TechVision Revenue SQL | **FAIL** | Wrong `company_name` ('TechVision' vs 'TechVision Inc') |
| Marie Curie Graph RAG | **PASS** | Correct, well-sourced response |

## Recommended Fixes
1. **Text-to-SQL engine (WF4):** Use fuzzy matching (`ILIKE '%TechVision%'`) or lookup `company_id` first
2. **QUANTITATIVE validator:** Flag `null` results on SUM/COUNT/AVG aggregations as validation failures
3. **Schema awareness:** Ensure the LLM generating SQL has access to sample `company_name` values
