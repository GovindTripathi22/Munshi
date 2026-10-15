"""Bookkeeper Agent: Categorizes transactions and constructs balanced journal entries."""

import re
from decimal import Decimal
from typing import Dict, Any, List, Optional
from munshi.config import MunshiConfig
from munshi.ledger.models import JournalEntryItem, LedgerTransaction, TransactionStatus
from munshi.agents.gst import GSTComputationAgent


class BookkeeperAgent:
    """Classifies financial transactions and compiles double-entry journal items."""

    # Rule-based semantic keyword dictionary for deterministic, offline classification
    CATEGORY_RULES = {
        "5200": {
            "name": "Software & Cloud Subscriptions",
            "keywords": ["aws", "cloud", "github", "slack", "google workspace", "azure", "openai", "software", "hosting", "saas", "api"],
            "default_rate": Decimal("0.18"),
        },
        "5100": {
            "name": "Office Rent Expense",
            "keywords": ["rent", "lease", "wework", "coworking", "office space", "landlord"],
            "default_rate": Decimal("0.18"),
        },
        "5300": {
            "name": "Legal & Professional Fees",
            "keywords": ["legal", "advocate", "consultant", "audit fee", "chartered accountant", "retainer"],
            "default_rate": Decimal("0.18"),
        },
        "5400": {
            "name": "Bank Charges & Fees",
            "keywords": ["bank charges", "neft", "processing charges", "maintenance fee", "bank account", "forex fee", "card fee", "interest debit"],
            "default_rate": Decimal("0.18"),
        },
        "5500": {
            "name": "Office Supplies & Utilities",
            "keywords": ["stationery", "electricity", "water", "printer paper", "supplies", "courier", "cleaning"],
            "default_rate": Decimal("0.12"),
        },
        "5600": {
            "name": "Travel & Conveyance",
            "keywords": ["uber", "ola", "flight", "indigo", "hotel", "travel", "taxi", "train"],
            "default_rate": Decimal("0.05"),
        },
        "4000": {
            "name": "Product Sales Revenue",
            "keywords": ["sale", "sales", "invoice to customer", "product delivery", "ecommerce receipt", "product sales", "export"],
            "default_rate": Decimal("0.18"),
        },
        "4100": {
            "name": "Professional Services Revenue",
            "keywords": ["consulting", "advisory", "advisory services", "service billing", "retainer received", "client contract"],
            "default_rate": Decimal("0.18"),
        },
    }

    def __init__(self, config: Optional[MunshiConfig] = None):
        self.config = config or MunshiConfig()
        self.gst_agent = GSTComputationAgent(self.config)

    def classify_transaction(self, description: str, counterparty: str = "") -> Dict[str, Any]:
        """Classifies narrative text into chart-of-accounts code and confidence score."""
        text = f"{description} {counterparty}".lower()

        best_code = "5500"  # Default generic expense
        best_score = 0.50
        matched_rule = "General & Administrative"

        for code, rule in self.CATEGORY_RULES.items():
            for kw in rule["keywords"]:
                if re.search(r"\b" + re.escape(kw) + r"\b", text):
                    best_code = code
                    best_score = 0.95
                    matched_rule = rule["name"]
                    break
            if best_score > 0.8:
                break

        return {
            "account_code": best_code,
            "account_name": matched_rule,
            "confidence": best_score,
            "default_rate": self.CATEGORY_RULES.get(best_code, {}).get("default_rate", Decimal("0.18")),
        }

    def create_journal_transaction(
        self,
        tx_id: str,
        date: str,
        description: str,
        amount: Decimal,
        is_sale: bool = False,
        counterparty_gstin: Optional[str] = None,
        gst_rate: Optional[Decimal] = None,
        payment_method: str = "BANK",  # "BANK" or "CASH" or "CREDIT"
    ) -> LedgerTransaction:
        """
        Creates a balanced double-entry transaction including applicable GST.
        Enforces Debits == Credits strictly.
        """
        classification = self.classify_transaction(description)
        selected_account = classification["account_code"]
        rate = gst_rate if gst_rate is not None else classification["default_rate"]

        # Calculate GST
        gst_breakdown = self.gst_agent.compute_gst(
            taxable_value=amount,
            rate=rate,
            counterparty_gstin=counterparty_gstin,
        )

        cgst = Decimal(gst_breakdown["cgst"])
        sgst = Decimal(gst_breakdown["sgst"])
        igst = Decimal(gst_breakdown["igst"])
        total_tax = Decimal(gst_breakdown["total_tax"])
        total_amount = amount + total_tax

        # Payment settlement account
        settlement_acc = "1010" if payment_method == "BANK" else ("1000" if payment_method == "CASH" else "2000")

        items: List[JournalEntryItem] = []

        if is_sale:
            # Sale: Debit Bank/Receivable (total_amount), Credit Revenue (taxable), Credit Output GST
            settlement_side = "1010" if payment_method == "BANK" else "1200"
            items.append(JournalEntryItem(
                account_code=settlement_side,
                debit=total_amount,
                credit=Decimal("0.00"),
                narration=f"Received/Due for {description}",
            ))
            revenue_code = "4100" if "consult" in description.lower() else "4000"
            items.append(JournalEntryItem(
                account_code=revenue_code,
                debit=Decimal("0.00"),
                credit=amount,
                narration=f"Revenue for {description}",
            ))
            if igst > 0:
                items.append(JournalEntryItem(
                    account_code="2120", debit=Decimal("0.00"), credit=igst, narration="Output IGST"
                ))
            else:
                if cgst > 0:
                    items.append(JournalEntryItem(
                        account_code="2100", debit=Decimal("0.00"), credit=cgst, narration="Output CGST"
                    ))
                if sgst > 0:
                    items.append(JournalEntryItem(
                        account_code="2110", debit=Decimal("0.00"), credit=sgst, narration="Output SGST"
                    ))
        else:
            # Expense: Debit Expense (taxable), Debit Input GST, Credit Bank/Payable (total_amount)
            items.append(JournalEntryItem(
                account_code=selected_account,
                debit=amount,
                credit=Decimal("0.00"),
                narration=f"Expense: {description}",
            ))
            if igst > 0:
                items.append(JournalEntryItem(
                    account_code="1320", debit=igst, credit=Decimal("0.00"), narration="Input IGST Credit"
                ))
            else:
                if cgst > 0:
                    items.append(JournalEntryItem(
                        account_code="1300", debit=cgst, credit=Decimal("0.00"), narration="Input CGST Credit"
                    ))
                if sgst > 0:
                    items.append(JournalEntryItem(
                        account_code="1310", debit=sgst, credit=Decimal("0.00"), narration="Input SGST Credit"
                    ))
            items.append(JournalEntryItem(
                account_code=settlement_acc,
                debit=Decimal("0.00"),
                credit=total_amount,
                narration=f"Paid via {payment_method} for {description}",
            ))

        # Check approval requirement
        requires_approval = (
            total_amount >= self.config.high_value_approval_threshold
            or classification["confidence"] < self.config.low_confidence_threshold
        )

        return LedgerTransaction(
            id=tx_id,
            date=date,
            description=description,
            items=items,
            status=TransactionStatus.PENDING_APPROVAL if requires_approval else TransactionStatus.DRAFT,
            requires_approval=requires_approval,
            metadata={
                "category_confidence": str(classification["confidence"]),
                "gst_rate": str(rate),
                "is_sale": str(is_sale),
            },
        )
