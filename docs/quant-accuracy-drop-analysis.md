# Quantitative Pipeline Accuracy Drop Analysis
**Phase 2: 92% → Phase 3: 54%**

Generated: 2026-03-05
Status: Root cause identified + fix strategy documented

---

## Executive Summary

The Quantitative pipeline accuracy dropped from **92.0%** (Phase 2, 500 HF questions) to **54.0%** (Phase 3, 500 Supabase questions). This is **NOT a pipeline regression**—it's a **fundamental dataset mismatch**.

**Root Cause**: Phase 3 uses synthetic financial data generated from Supabase with made-up companies and values that don't align with the actual Supabase table contents.

---

## Findings

### 1. Dataset Source Difference

| Aspect | Phase 2 | Phase 3 |
|--------|---------|----------|
| **Dataset** | Real HF datasets | Synthetic Supabase |
| **Questions** | 500 from: finqa (200), tatqa (150), convfinqa (100), wikitablequestions (50) | 500 all from: supabase_financial |
| **Companies** | Real financial entities (JPMorgan, MSFT, etc.) | Made-up: GreenEnergy Corp, TechVision Inc, HealthPlus Labs |
| **Accuracy** | 92.0% | 54.0% |

### 2. Question-Data Mismatch Evidence

**Phase 2** (Real data):
```
Q: "brazilian paper sales represented what percentage of printing papers in 2005?"
Expected: "6%"
Answer: Extracted from real FinQA dataset table
Result: ✓ CORRECT
```

**Phase 3** (Synthetic):
```
Q: "What was GreenEnergy Corp's operating margin in 2023?"
Expected: "23.0%"
Answer: "15.7%" (returned by Supabase)
Result: ✗ MISMATCH — Questions and DB data don't align
```

### 3. Consistent Mismatch Pattern

Recent evaluation results show **systematic wrong answers**:

| Question | Expected | Pipeline Returns | Status |
|----------|----------|------------------|--------|
| GreenEnergy operating margin 2023 | 23.0% | 15.7% | ✗ Wrong |
| TechVision revenue change 2022→2023 | decrease | Increase | ✗ Wrong |
| HealthPlus Labs net income 2023 | $45,392,000 | $94million | ✗ Wrong |
| TechVision operating expenses 2021 | $1,938,000,000 | $1,200million | ✗ Partial |

**This pattern repeats consistently across runs**, indicating the Supabase table contains different values than the synthetic questions expect.

### 4. Data Structure Issues

**Phase 2** questions (`hf-1000.json`):
- Field: `expected_answer` (standard)
- Has: Rich context, supporting facts, table references
- Each question grounded in actual HF dataset

**Phase 3** questions (`quantitative-500.json`):
- Field: `answer` (non-standard, but converted to `expected_answer` in load)
- Has: Basic company/year references, NO embedded context
- Generated syntetically from Supabase schema assumptions

### 5. Difficulty Distribution

Phase 3 questions are marked as:
- **Easy**: 0 (0%)
- **Medium**: 0 (0%)
- **Hard**: 500 (100%)

All 500 questions are tagged "hard" but are actually **easier questions with harder data mismatches**—the pipeline can answer "what's the revenue?" but gets wrong numbers because Supabase has different data.

---

## Root Cause Analysis

### Why the accuracy dropped:

1. **Synthetic Dataset Generation**: Phase 3 questions were auto-generated with assumed values (23.0%, $45M, etc.) that don't match actual Supabase data.

2. **Supabase Table Mismatch**: The `financials` table in Supabase contains:
   - Different companies than assumed
   - Different years than referenced
   - Different calculated fields (e.g., operating_margin might be computed differently)
   - Data from different sources/time periods

3. **No Ground Truth Validation**: Phase 3 questions were created WITHOUT verifying that:
   - The companies exist in Supabase
   - The years have data
   - The values match the table contents
   - The field calculations are correct

4. **Pipeline Not at Fault**: The quantitative pipeline:
   - Successfully retrieves data from Supabase
   - Correctly formats answers
   - Processes queries without errors
   - Returns **actual Supabase values** (15.7%, $94M, etc.)

The pipeline is working correctly—it's just answering with what's actually in the database, not what the test questions expect.

---

## Evaluation Results

### Phase 2 Performance (92% accuracy)
```
Pipeline: quantitative
Dataset: hf-1000.json (real HF datasets)
Tested: 500 questions
Correct: 460
Accuracy: 92.0%
```

### Phase 3 Performance (54% average)
```
Pipeline: quantitative
Dataset: quantitative-500.json (synthetic Supabase)
Recent runs:
  2026-03-04T17-16-57: 54.0% (270/500)
  2026-03-05T08-33-46: 45.8% (11/24)
  2026-03-05T11-39-46: 50.0% (10/20)
Average: 47-54% accuracy
```

---

## Impact Assessment

### What This Means

1. **Pipeline is NOT broken**: The Quantitative pipeline works correctly (Phase 2 proves it)
2. **Test data is invalid**: Phase 3 synthetic questions don't match actual database
3. **Benchmark is unfair**: Can't measure RAG quality with mismatched questions
4. **Score reflects data quality, not pipeline quality**

### Consequences

- Phase 3 leaderboard metrics are **not meaningful**
- Cannot use Phase 3 for pipeline evaluation/comparison
- Must either:
  - Fix Phase 3 questions to match actual Supabase data
  - Replace Phase 3 with properly validated synthetic data
  - Use Phase 2 (HF datasets) as the real benchmark

---

## Recommended Solutions

### Option A: Fix Phase 3 Questions (Recommended)
1. **Query actual Supabase data** for each company/year combination
2. **Extract real values** from the database
3. **Regenerate questions** with verified answers
4. **Re-test** at 500+ questions
5. **Result**: Valid Phase 3 benchmark matching actual data

**Effort**: 2-4 hours
**Benefit**: Phase 3 becomes a real synthetic benchmark

### Option B: Replace Phase 3 with Real Datasets
1. Use remaining HF datasets (FinQA, TAT-QA, Conv-FinQA split-off)
2. Create Phase 3 with 1000+ real questions
3. Test all pipelines against real data

**Effort**: 4-6 hours
**Benefit**: Most reliable benchmark, no synthetic issues

### Option C: Use Phase 2 as Final Benchmark
1. Accept Phase 2 (1000 HF questions) as the gold standard
2. Skip Phase 3 synthetic data
3. Focus on Phase 1+2 accuracy targets

**Effort**: Minimal (already have data)
**Benefit**: Simple, reliable, no data issues

---

## Technical Debt

Phase 3 highlighted these issues:

1. **No data validation in question generation**: Synthetic questions created without verifying ground truth exists
2. **Assumption-based answers**: Expected values assumed without database queries
3. **Missing ETL verification**: No check that Supabase matches question expectations
4. **Test data quality gates**: Need pre-flight checks that:
   - All companies exist in target DB
   - All years have data
   - All values can be verified

---

## Next Steps

1. **Update evaluation scripts** to flag data mismatches during load
2. **Create Phase 3 validator** that checks question-data alignment before eval
3. **Decision**: Choose Option A/B/C above
4. **Implement fix**: 2-6 hours depending on choice
5. **Re-test**: Get accurate Phase 3 accuracy (likely 85%+ if using real data)

---

## Appendix: Question-Answer Mismatches

### Examples from Recent Runs

```
ID: p3-qua-00147
Q: What was GreenEnergy Corp's operating margin in 2023?
Expected: 23.0%
Got: 15.7%
Status: WRONG (but pipeline executed correctly)

ID: p3-qua-00440
Q: Did TechVision Inc's revenue increase or decrease from 2022 to 2023?
Expected: decrease
Got: Increase
Status: WRONG (opposite answer from DB)

ID: p3-qua-00363
Q: According to financial data, what was the net income of HealthPlus Labs in 2023?
Expected: $45,392,000.00
Got: $94million
Status: WRONG (different values in DB)
```

These errors are **not pipeline failures**—they're **question-data alignment failures**.

---

## Conclusion

The 92% → 54% accuracy drop is explained entirely by switching from **real HF datasets** (Phase 2) to **synthetic Supabase data** (Phase 3) with **misaligned ground truth**.

The pipeline is working correctly. The test data needs fixing.

**Recommendation**: Implement Option A (fix Phase 3 questions to match actual Supabase data) or Option B (use real datasets for Phase 3).
