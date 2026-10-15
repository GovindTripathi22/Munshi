# Munshi: Quantitative Evaluation & Benchmark Report

This document outlines the benchmark evaluation methodology, dataset composition, and empirical test results for **Munshi: Multi-Agent Finance Assistant**.

---

## 📊 Summary of Benchmark Results

| Metric | Target Goal | Munshi Result | Status |
| :--- | :---: | :---: | :---: |
| **Categorization Accuracy** | > 95.0% | **100.0%** | Passed |
| **Reconciliation Match Precision** | > 95.0% | **100.0%** | Passed |
| **Reconciliation Recall** | > 95.0% | **100.0%** | Passed |
| **Planted Phantom / Fee Detection** | 100% | **100.0% (2/2 caught)** | Passed |
| **Anomaly Detection Precision** | > 90.0% | **100.0%** | Passed |
| **Anomaly Detection Recall** | > 90.0% | **100.0%** | Passed |
| **Anomaly Detection F1-Score** | > 90.0% | **100.0%** | Passed |

---

## 🧪 Benchmark Dataset Design

The evaluation dataset (`data/synthetic_dataset.json`) is designed to mirror typical Indian Small-and-Medium Enterprise (SME) accounting environments with intentionally planted real-world discrepancies:

### 1. Bookkeeping & Categorization Benchmark
- Evaluates classification of narrative bank & expense descriptions into standard Chart of Accounts (COA) codes:
  - `5200` Software & Cloud Subscriptions (AWS, GitHub, Google Workspace, Slack)
  - `5100` Office Rent & Facility Leases (WeWork, DLF CyberCity)
  - `5300` Legal & Professional Fees (Advocates, Statutory Audit, Retainers)
  - `5400` Bank Charges & Processing Fees (NEFT, Forex, Card Maintenance)
  - `5500` Office Supplies & Utilities (Electricity, Stationery, Courier)
  - `5600` Travel & Conveyance (Uber, Ola, Indigo Flights)
  - `4000` Product Sales Revenue (Retail buyers, export receipts)
  - `4100` Professional Consulting Services Revenue (Enterprise advisory billing)

### 2. Bank Reconciliation Benchmark
- **Input:** 10 bank statement lines compared against 10 internal ledger invoices.
- **Planted Conditions:**
  - 8 valid transactions with exact amounts and UTR / invoice reference numbers.
  - 1 planted unauthorized / phantom ATM withdrawal (no invoice counterpart).
  - 1 planted bank maintenance debit fee (no prior ledger invoice).
- **Evaluation Criteria:**
  - Precision: Correct invoice matches / Total proposed matches.
  - Recall: Correct invoice matches / Ground truth matchable pairs.
  - Discrepancy Capture: Ability to flag unmatched bank charges for human adjustment.

### 3. Anomaly & Fraud Detection Benchmark
- **Input:** 10 financial transactions with 5 clean records and 5 planted anomalies:
  - **Duplicate Invoices:** Identical invoice numbers (`INV-2001`, `INV-2002`) issued across separate entries.
  - **Illegal GST Rates:** Non-standard rates (15% and 22%) outside statutory Indian GST slabs (0%, 5%, 12%, 18%, 28%).
  - **Arithmetic Discrepancies:** Taxable Amount + Tax != Total Invoice Amount (e.g., ₹10,000 + ₹1,800 != ₹14,000).
  - **Ledger Imbalances:** Journal items where Total Debits != Total Credits.

---

## 📈 Detailed Test Results Breakdown

### A. Categorization Accuracy
```json
{
  "total_tested": 20,
  "correct": 20,
  "accuracy_percent": 100.0
}
```
- **100.0%** of tested corporate transactions were classified into their exact general ledger account codes with high confidence scores.

### B. Bank Reconciliation
```json
{
  "total_bank_lines": 10,
  "ground_truth_matches": 8,
  "matched_by_agent": 8,
  "match_rate_percent": 80.0,
  "precision_percent": 100.0,
  "recall_percent": 100.0,
  "planted_unmatched_caught": 2
}
```
- **80% overall statement clearing rate**: All 8 legitimate invoices were matched with 100% precision and zero false positives.
- **Both planted discrepancies (unauthorized ATM withdrawal and bank fee)** were isolated and routed to human review without polluting the general ledger.

### C. Anomaly Detection
```json
{
  "total_transactions": 10,
  "planted_errors_count": 5,
  "detected_count": 5,
  "true_positives": 5,
  "false_positives": 0,
  "false_negatives": 0,
  "precision_percent": 100.0,
  "recall_percent": 100.0,
  "f1_score": 100.0
}
```
- **100% detection rate**: Every single planted duplicate, illegal tax slab, and calculation disparity was detected and flagged with appropriate severity levels (HIGH / CRITICAL).

---

## 🔬 How to Reproduce

Run the automated evaluation benchmark runner at any time:
```bash
python -m munshi.evaluation.benchmark
```
Results will update in `benchmark_results.json`.
