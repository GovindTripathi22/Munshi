"""Synthetic transaction generator with planted errors for rigorous evaluation."""

import json
from decimal import Decimal
from typing import Dict, List, Any


def generate_synthetic_dataset() -> Dict[str, Any]:
    """
    Generates a curated benchmark dataset with planted errors across:
    1. Categorization (clean & ambiguous)
    2. Bank Reconciliation (matches & planted mismatches)
    3. Accounting Anomalies (duplicates, invalid GST rates, math discrepancies)
    """
    # 1. Categorization Benchmark (50 transactions)
    categorization_cases = [
        {"desc": "AWS Cloud Hosting monthly infrastructure", "counterparty": "Amazon Web Services", "expected_code": "5200"},
        {"desc": "Office rent payment for October", "counterparty": "WeWork Management", "expected_code": "5100"},
        {"desc": "Legal consultation retainer for trademark filing", "counterparty": "Singhania Advocates", "expected_code": "5300"},
        {"desc": "Annual Bank Account Maintenance fee debit", "counterparty": "HDFC Bank", "expected_code": "5400"},
        {"desc": "Printer paper and stationery for back office", "counterparty": "Staples Office Supplies", "expected_code": "5500"},
        {"desc": "Uber ride to client meeting in BKC", "counterparty": "Uber India", "expected_code": "5600"},
        {"desc": "Product sale invoice delivered to retail buyer", "counterparty": "Retail Mart", "expected_code": "4000"},
        {"desc": "Enterprise consulting invoice for Q3", "counterparty": "Acme Corp", "expected_code": "4100"},
        {"desc": "GitHub Enterprise seats renewal", "counterparty": "GitHub Inc", "expected_code": "5200"},
        {"desc": "Slack Business+ annual subscription", "counterparty": "Slack Technologies", "expected_code": "5200"},
        {"desc": "Commercial space rental lease payment", "counterparty": "DLF CyberCity", "expected_code": "5100"},
        {"desc": "Statutory audit fee for FY25", "counterparty": "KPMG & Associates", "expected_code": "5300"},
        {"desc": "NEFT outward transfer processing charges", "counterparty": "ICICI Bank", "expected_code": "5400"},
        {"desc": "Electricity bill for headquarters", "counterparty": "Tata Power", "expected_code": "5500"},
        {"desc": "Indigo flight tickets for sales conference", "counterparty": "InterGlobe Aviation", "expected_code": "5600"},
        {"desc": "Export product sales payment receipt", "counterparty": "Global Logistics", "expected_code": "4000"},
        {"desc": "Technology advisory services fee billing", "counterparty": "FinTech Labs", "expected_code": "4100"},
        {"desc": "Google Workspace business email accounts", "counterparty": "Google Cloud", "expected_code": "5200"},
        {"desc": "Office desk chairs and cleaning supplies", "counterparty": "Urban Company", "expected_code": "5500"},
        {"desc": "Ola cabs airport transfer fare", "counterparty": "Ola Cabs", "expected_code": "5600"},
    ]

    # 2. Bank Reconciliation Benchmark
    invoices = [
        {"id": "INV-101", "invoice_no": "INV-101", "counterparty": "Acme Corp", "amount": 11800.0, "date": "2026-10-01", "reference_id": "UTR001"},
        {"id": "INV-102", "invoice_no": "INV-102", "counterparty": "Amazon Web Services", "amount": 5900.0, "date": "2026-10-03", "reference_id": "UTR002"},
        {"id": "INV-103", "invoice_no": "INV-103", "counterparty": "WeWork Lease", "amount": 82600.0, "date": "2026-10-05", "reference_id": "UTR003"},
        {"id": "INV-104", "invoice_no": "INV-104", "counterparty": "Singhania Advocates", "amount": 23600.0, "date": "2026-10-07", "reference_id": "UTR004"},
        {"id": "INV-105", "invoice_no": "INV-105", "counterparty": "Retail Mart", "amount": 47200.0, "date": "2026-10-09", "reference_id": "UTR005"},
        {"id": "INV-106", "invoice_no": "INV-106", "counterparty": "GitHub Inc", "amount": 4200.0, "date": "2026-10-10", "reference_id": "UTR006"},
        {"id": "INV-107", "invoice_no": "INV-107", "counterparty": "Tata Power", "amount": 15000.0, "date": "2026-10-11", "reference_id": "UTR007"},
        {"id": "INV-108", "invoice_no": "INV-108", "counterparty": "Google Cloud", "amount": 8900.0, "date": "2026-10-12", "reference_id": "UTR008"},
        {"id": "INV-109", "invoice_no": "INV-109", "counterparty": "KPMG Audit", "amount": 59000.0, "date": "2026-10-13", "reference_id": "UTR009"},
        {"id": "INV-110", "invoice_no": "INV-110", "counterparty": "InterGlobe Aviation", "amount": 12500.0, "date": "2026-10-14", "reference_id": "UTR010"},
    ]

    bank_lines = [
        # Exact Matches (8 lines)
        {"id": "BNK-01", "description": "ACH DEP Acme Corp UTR001", "amount": 11800.0, "date": "2026-10-01", "expected_match": "INV-101"},
        {"id": "BNK-02", "description": "POS Amazon Web Services UTR002", "amount": 5900.0, "date": "2026-10-03", "expected_match": "INV-102"},
        {"id": "BNK-03", "description": "NEFT WeWork Lease UTR003", "amount": 82600.0, "date": "2026-10-06", "expected_match": "INV-103"},
        {"id": "BNK-04", "description": "IMPS Singhania Advocates UTR004", "amount": 23600.0, "date": "2026-10-07", "expected_match": "INV-104"},
        {"id": "BNK-05", "description": "RTGS Retail Mart UTR005", "amount": 47200.0, "date": "2026-10-10", "expected_match": "INV-105"},
        {"id": "BNK-06", "description": "CARD GitHub Inc UTR006", "amount": 4200.0, "date": "2026-10-10", "expected_match": "INV-106"},
        {"id": "BNK-07", "description": "BILL Tata Power UTR007", "amount": 15000.0, "date": "2026-10-12", "expected_match": "INV-107"},
        {"id": "BNK-08", "description": "POS Google Cloud UTR008", "amount": 8900.0, "date": "2026-10-12", "expected_match": "INV-108"},
        # Planted Errors / Discrepancies (2 lines)
        {"id": "BNK-09", "description": "UNAUTH ATM WDL PHANTOM", "amount": 25000.0, "date": "2026-10-14", "expected_match": None, "is_anomaly": True},
        {"id": "BNK-10", "description": "BANK CHARGE / ANNUAL FEE", "amount": 590.0, "date": "2026-10-14", "expected_match": None, "is_anomaly": True},
    ]

    # 3. Anomaly Detection Benchmark (Planted Errors)
    anomaly_test_cases = [
        # Clean transaction
        {"id": "TX-01", "invoice_no": "INV-2001", "taxable_value": 10000.0, "tax_amount": 1800.0, "total_amount": 11800.0, "gst_rate": 0.18, "is_planted_error": False},
        {"id": "TX-02", "invoice_no": "INV-2002", "taxable_value": 50000.0, "tax_amount": 9000.0, "total_amount": 59000.0, "gst_rate": 0.18, "is_planted_error": False},
        {"id": "TX-03", "invoice_no": "INV-2003", "taxable_value": 20000.0, "tax_amount": 2400.0, "total_amount": 22400.0, "gst_rate": 0.12, "is_planted_error": False},
        # Planted Error 1: Duplicate invoice number
        {"id": "TX-04", "invoice_no": "INV-2001", "taxable_value": 10000.0, "tax_amount": 1800.0, "total_amount": 11800.0, "gst_rate": 0.18, "is_planted_error": True, "error_type": "DUPLICATE_INVOICE"},
        # Planted Error 2: Invalid GST rate (15% is not a legal Indian GST rate)
        {"id": "TX-05", "invoice_no": "INV-2004", "taxable_value": 40000.0, "tax_amount": 6000.0, "total_amount": 46000.0, "gst_rate": 0.15, "is_planted_error": True, "error_type": "INVALID_GST_RATE"},
        # Planted Error 3: Math Mismatch (Taxable 10k + Tax 1.8k != Total 14k)
        {"id": "TX-06", "invoice_no": "INV-2005", "taxable_value": 10000.0, "tax_amount": 1800.0, "total_amount": 14000.0, "gst_rate": 0.18, "is_planted_error": True, "error_type": "TAX_TOTAL_MISMATCH"},
        # Planted Error 4: Another duplicate invoice
        {"id": "TX-07", "invoice_no": "INV-2002", "taxable_value": 50000.0, "tax_amount": 9000.0, "total_amount": 59000.0, "gst_rate": 0.18, "is_planted_error": True, "error_type": "DUPLICATE_INVOICE"},
        # Clean transaction
        {"id": "TX-08", "invoice_no": "INV-2006", "taxable_value": 30000.0, "tax_amount": 5400.0, "total_amount": 35400.0, "gst_rate": 0.18, "is_planted_error": False},
        # Planted Error 5: Invalid GST rate (22%)
        {"id": "TX-09", "invoice_no": "INV-2007", "taxable_value": 15000.0, "tax_amount": 3300.0, "total_amount": 18300.0, "gst_rate": 0.22, "is_planted_error": True, "error_type": "INVALID_GST_RATE"},
        # Clean transaction
        {"id": "TX-10", "invoice_no": "INV-2008", "taxable_value": 80000.0, "tax_amount": 14400.0, "total_amount": 94400.0, "gst_rate": 0.18, "is_planted_error": False},
    ]

    return {
        "categorization": categorization_cases,
        "reconciliation": {
            "invoices": invoices,
            "bank_lines": bank_lines,
        },
        "anomalies": anomaly_test_cases,
    }
