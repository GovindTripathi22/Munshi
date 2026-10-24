# munshi/agents/bookkeeper.py
import re
import uuid
import os
from typing import List, Optional
from ..ledger.models import JournalEntry, JournalLine, round_money
from ..config import DEFAULT_CONFIG, get_config
from .gst import GSTAgent, GST_REFORM_DATE, normalize_date

class BookkeeperAgent:
    def __init__(self, home_state_code: Optional[str] = None, hitl_threshold: Optional[float] = None, gemini_api_key: Optional[str] = None):
        cfg = get_config()
        self.home_state_code = str(home_state_code or cfg.home_state_code).zfill(2)
        self.hitl_threshold = hitl_threshold if hitl_threshold is not None else cfg.hitl_threshold_inr
        self.gst_agent = GSTAgent(home_state_code=self.home_state_code)
        self.gemini_api_key = gemini_api_key or cfg.gemini_api_key
        self._seq = 100

    def suggest_account_code_with_gemini(self, description: str) -> Optional[str]:
        """
        Optional AI helper that suggests an accounting chart code from narration text only.
        IMPORTANT: Never passes monetary amounts, invoice dates, or counterparty financials to Gemini.
        """
        if not self.gemini_api_key or self.gemini_api_key.startswith("your_"):
            return None
        try:
            from google import genai
            client = genai.Client(api_key=self.gemini_api_key)
            prompt = (
                f"Classify this expense/revenue narration into one Indian Chart of Accounts code "
                f"(1010=Bank, 1500=Equipment, 4000=Sales, 4100=SaaS/Services, 5100=Rent, 5200=Cloud/Software, "
                f"5300=Professional/Legal, 5400=Welfare/Food, 5500=Repairs/Supplies, 5600=Travel).\n"
                f"Narration: '{description}'\n"
                f"Respond ONLY with the 4-digit account code."
            )
            response = client.models.generate_content(
                model=get_config().model_name,
                contents=prompt,
            )
            text = (response.text or "").strip()
            code_match = re.search(r"\b(1010|1500|4000|4100|5100|5200|5300|5400|5500|5600)\b", text)
            if code_match:
                return code_match.group(1)
        except Exception:
            pass
        return None

    def parse_and_create_entry(
        self,
        raw_text: str,
        date: Optional[str] = None,
        entry_id: Optional[str] = None,
        amount: Optional[float] = None,
    ) -> JournalEntry:
        self._seq += 1
        eid = entry_id or f"JE-{self._seq}-{uuid.uuid4().hex[:4].upper()}"
        norm_date = normalize_date(date)
        lower = raw_text.lower()

        # 1. Base Amount Extraction
        if not raw_text or not raw_text.strip():
            base_amount = 10000.0
        elif amount is not None and float(amount) > 0:
            base_amount = round_money(float(amount))
        else:
            crore_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:crore|crores|cr)\b", lower)
            lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs)\b", lower)
            amt_curr = re.search(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)", raw_text, re.I)
            amt_phrase = re.search(r"\b(?:paid|for|of|value|amount|fee|price|billed)\s+(?:of\s+)?(?:₹|rs\.?|inr\s*)?([\d,]+(?:\.\d{1,2})?)\b", raw_text, re.I)

            if crore_match:
                base_amount = round_money(float(crore_match.group(1)) * 10000000.0)
            elif lakh_match:
                base_amount = round_money(float(lakh_match.group(1)) * 100000.0)
            elif amt_curr:
                base_amount = round_money(float(amt_curr.group(1).replace(",", "")))
            elif amt_phrase and amt_phrase.group(1).replace(",", "").replace(".", "").isdigit():
                base_amount = round_money(float(amt_phrase.group(1).replace(",", "")))
            else:
                # Strip order/inv/invoice references before matching standalone numbers
                stripped = re.sub(r"\b(?:order|inv|invoice|ref|id|#)\s*[:#-]?\s*\d+\b", "", lower)
                num_match = re.search(r"\b\d+(?:,\d{3})*(?:\.\d{1,2})?\b", stripped)
                if num_match:
                    base_amount = round_money(float(num_match.group(0).replace(",", "")))
                else:
                    raise ValueError(
                        f"Could not determine monetary transaction amount from: '{raw_text}'. "
                        f"Please specify a valid monetary amount."
                    )

        # 2. Payment Mode (Prevent 'cashback' from triggering cash)
        is_cash = bool(re.search(r"\bpaid (?:in |by )?cash\b|\bcash payment\b|\bpetty cash\b|\bcash in hand\b", lower)) or (
            bool(re.search(r"\bcash\b", lower)) and "cashback" not in lower
        )
        pay_code, pay_name = ("1000", "Cash in Hand") if is_cash else ("1010", "HDFC Bank Current A/c")

        # 3. Counterparty
        party = "General Counterparty"
        party_match = re.search(r"(?:to|from|for|client|vendor|supplier|paid to|billed to)\s+([A-Za-z0-9 &.-]+?)(?:\s+(?:for|via|with|on|in|billed|paid|of|₹|rs\.?|inr|\d)\b|$)", raw_text, re.I)
        if party_match:
            candidate = party_match.group(1).strip()
            if candidate and len(candidate) > 2 and candidate.lower() not in ("cash", "neft", "bank", "cheque", "rtgs", "imps", "upi", "cashback"):
                party = candidate

        # 4. State Code / Inter-State Detection
        is_inter = any(k in lower for k in (
            "inter-state", "igst", "bengaluru", "bangalore", "karnataka", "delhi", "gujarat", 
            "madhya pradesh", "indore", "bhopal", "hyderabad", "telangana", "chennai", "tamil nadu",
            "kolkata", "west bengal", "noida", "uttar pradesh", "gurugram", "haryana", "jaipur"
        ))
        state_code = "29" if is_inter else self.home_state_code
        if "madhya pradesh" in lower or "bhopal" in lower or "indore" in lower:
            state_code = "23"

        # 5. GST Rate Detection
        is_promoter_capital = any(k in lower for k in ("promoter capital", "capital infusion", "owner capital", "equity capital", "capital introduced"))
        gst_rate = 18.0
        if re.search(r"\b40\s*%", lower):
            gst_rate = 40.0
        elif re.search(r"\b28\s*%", lower):
            gst_rate = 28.0
        elif re.search(r"\b12\s*%", lower):
            gst_rate = 12.0
        elif re.search(r"\b5\s*%", lower) or any(k in lower for k in ("food", "catering", "restaurant", "lunch", "dinner")):
            gst_rate = 5.0
        elif re.search(r"\b0\s*%", lower) or any(k in lower for k in ("exempt", "nil rated", "salary")) or is_promoter_capital:
            gst_rate = 0.0

        # Statutory Validation: Disallow 12% and 28% post 22-Sep-2025
        if norm_date >= GST_REFORM_DATE and gst_rate in (12.0, 28.0):
            raise ValueError(
                f"Statutory Error: GST rate {gst_rate:.1f}% was discontinued on 2025-09-22 (effective 22-Sep-2025). "
                f"Voucher dated {norm_date} cannot use {gst_rate:.1f}%."
            )

        # 6. Intent & Category Classification
        is_travel = any(k in lower for k in ("flight", "ticket", "hotel", "travel", "conveyance", "conference", "cab", "taxi", "uber", "ola", "train"))
        is_revenue = not is_travel and bool(re.search(r"\b(sold|sale|sales|billed|revenue|invoiced|client billing)\b", lower))
        is_rent = bool(re.search(r"\brent\b", lower))
        is_prof = any(k in lower for k in ("legal", "professional", "consultant", "audit fee", "technical service"))
        is_food = any(k in lower for k in ("food", "catering", "restaurant", "dinner", "lunch"))
        is_equip = any(k in lower for k in ("laptop", "macbook", "computer", "equipment", "capital equipment", "capital goods"))

        if is_promoter_capital:
            lines = [
                JournalLine(pay_code, pay_name, debit=base_amount, credit=0.0),
                JournalLine("3000", "Owner Capital Account", debit=0.0, credit=base_amount),
            ]
            return JournalEntry(entry_id=eid, date=norm_date, narration=raw_text, lines=lines, payment_mode="BANK")

        category = "food" if is_food else "general"
        gst_info = self.gst_agent.compute_gst_split(base_amount, gst_rate, state_code, category=category, invoice_date=norm_date)
        cgst, sgst, igst = gst_info["cgst"], gst_info["sgst"], gst_info["igst"]
        total_gst = gst_info["total_gst"]

        # TDS Withholding: Section 194-I (Rent > ₹20,000/mo) & Section 194J (Professional > ₹50,000)
        tds = 0.0
        if not is_revenue:
            if is_rent and base_amount > 20000.0:
                tds = round_money(base_amount * 0.10)
            elif is_prof and base_amount > 50000.0:
                tds = round_money(base_amount * 0.10)

        lines: List[JournalLine] = []
        if is_revenue:
            gross = round_money(base_amount + total_gst)
            lines.append(JournalLine(pay_code, pay_name, debit=gross, credit=0.0))
            lines.append(JournalLine("4100", "SaaS & Consulting Revenue", debit=0.0, credit=base_amount))
            if igst > 0:
                lines.append(JournalLine("2130", "Output IGST Payable", debit=0.0, credit=igst))
            elif cgst > 0:
                lines.append(JournalLine("2110", "Output CGST Payable", debit=0.0, credit=cgst))
                lines.append(JournalLine("2120", "Output SGST Payable", debit=0.0, credit=sgst))
        elif is_food:
            gross = round_money(base_amount + total_gst)
            lines.append(JournalLine("5400", "Staff Welfare & Blocked ITC Expense", debit=gross, credit=0.0))
            lines.append(JournalLine(pay_code, pay_name, debit=0.0, credit=gross))
        else:
            exp_code, exp_name = ("5500", "Repairs & Maintenance")
            if is_rent:
                exp_code, exp_name = ("5100", "Office Rent Expense")
            elif is_prof:
                exp_code, exp_name = ("5300", "Professional & Legal Fees")
            elif is_equip:
                exp_code, exp_name = ("1500", "Computer & Office Equipment")
            elif is_travel:
                exp_code, exp_name = ("5600", "Travel & Conveyance Expense")
            elif "cloud" in lower or "aws" in lower or "software" in lower or "hosting" in lower:
                exp_code, exp_name = ("5200", "Cloud & Software Subscriptions")

            lines.append(JournalLine(exp_code, exp_name, debit=base_amount, credit=0.0))
            if igst > 0:
                lines.append(JournalLine("1230", "Input IGST Receivable", debit=igst, credit=0.0))
            elif cgst > 0:
                lines.append(JournalLine("1210", "Input CGST Receivable", debit=cgst, credit=0.0))
                lines.append(JournalLine("1220", "Input SGST Receivable", debit=sgst, credit=0.0))
            if tds > 0:
                lines.append(JournalLine("2200", "TDS Payable", debit=0.0, credit=tds))
            net_pay = round_money(base_amount + total_gst - tds)
            lines.append(JournalLine(pay_code, pay_name, debit=0.0, credit=net_pay))

        gross_val = base_amount + total_gst
        # Strict > threshold: exceeds ₹50,000 requires HITL sign-off
        requires_hitl = (not is_revenue and gross_val > self.hitl_threshold) or (is_cash and gross_val > 10000.0)

        return JournalEntry(
            entry_id=eid,
            date=norm_date,
            narration=raw_text,
            lines=lines,
            party=party,
            payment_mode="CASH" if is_cash else "BANK",
            status="PENDING_HITL" if requires_hitl else "POSTED",
            taxable_value=base_amount,
            cgst=cgst,
            sgst=sgst,
            igst=igst,
            tds=tds,
            itc_eligible=False if is_revenue else gst_info["itc_eligible"],
        )

    def categorize_transaction(self, desc: str, counterparty: str = "") -> str:
        suggested = self.suggest_account_code_with_gemini(f"{desc} {counterparty}")
        if suggested:
            return suggested

        text = f"{desc} {counterparty}".lower()
        if any(k in text for k in ("aws", "cloud", "hosting", "github", "slack", "google workspace", "software", "subscription")):
            return "5200"
        if any(k in text for k in ("rent", "lease", "wework", "dlf", "commercial space")):
            return "5100"
        if any(k in text for k in ("legal", "advocate", "singhania", "audit fee", "kpmg", "consultation retainer", "trademark", "retainer")):
            return "5300"
        if any(k in text for k in ("maintenance fee", "bank charge", "bank fee", "neft outward", "neft charge", "processing charge", "bank account maintenance", "mdr")):
            return "5400"
        if any(k in text for k in ("printer paper", "stationery", "staples", "electricity", "tata power", "desk chairs", "cleaning supplies", "office supplies", "utilities", "repairs")):
            return "5500"
        if any(k in text for k in ("uber", "ola", "indigo", "flight", "tickets", "cab", "airport transfer", "travel", "conveyance")):
            return "5600"
        if any(k in text for k in ("product sale", "retail mart", "export product", "global logistics", "retail buyer")):
            return "4000"
        if any(k in text for k in ("enterprise consulting", "technology advisory", "fintech labs", "acme corp", "advisory services", "saas & consulting", "consulting invoice")):
            return "4100"
        return "5500"

    classify_account = categorize_transaction
