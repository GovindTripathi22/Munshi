# munshi/agents/bookkeeper.py
import re
from typing import List
from ..ledger.models import JournalEntry, JournalLine, round_money
from .gst import GSTAgent

class BookkeeperAgent:
    def __init__(self, home_state_code: str = "27", hitl_threshold: float = 50000.0):
        self.gst_agent = GSTAgent(home_state_code=home_state_code)
        self.hitl_threshold = hitl_threshold
        self._seq = 100

    def parse_and_create_entry(self, raw_text: str, date: str = "2026-10-16", entry_id: str | None = None) -> JournalEntry:
        self._seq += 1
        eid = entry_id or f"JE-{self._seq}"
        lower = raw_text.lower()

        lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs)", lower)
        crore_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:crore|crores|cr)\b", lower)
        amt_match = re.search(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)|(\d[\d,]{2,}(?:\.\d{1,2})?)", raw_text, re.I)

        if crore_match:
            base_amount = round_money(float(crore_match.group(1)) * 10000000.0)
        elif lakh_match:
            base_amount = round_money(float(lakh_match.group(1)) * 100000.0)
        elif amt_match:
            raw_amt = (amt_match.group(1) or amt_match.group(2)).replace(",", "")
            base_amount = round_money(float(raw_amt))
        else:
            base_amount = 10000.0

        is_cash = "cash" in lower
        pay_code, pay_name = ("1000", "Cash in Hand") if is_cash else ("1010", "HDFC Bank Current A/c")

        is_inter = any(k in lower for k in ("inter-state", "igst", "bengaluru", "bangalore", "karnataka", "delhi", "gujarat"))
        state_code = "29" if is_inter else "27"

        gst_rate = 18.0
        if "5%" in lower or "food" in lower or "catering" in lower or "restaurant" in lower:
            gst_rate = 5.0
        elif "12%" in lower:
            gst_rate = 12.0
        elif "28%" in lower:
            gst_rate = 28.0
        elif "0%" in lower or "exempt" in lower or "capital" in lower or "salary" in lower:
            gst_rate = 0.0

        is_capital = "capital" in lower and ("promoter" in lower or "owner" in lower or "infusion" in lower)
        is_revenue = any(k in lower for k in ("sold", "sale", "billed", "revenue", "received from client"))
        is_rent = "rent" in lower
        is_prof = any(k in lower for k in ("legal", "professional", "consultant", "audit fee"))
        is_food = any(k in lower for k in ("food", "catering", "restaurant", "dinner", "lunch"))
        is_equip = any(k in lower for k in ("laptop", "macbook", "computer", "equipment"))

        if is_capital:
            lines = [
                JournalLine(pay_code, pay_name, debit=base_amount, credit=0.0),
                JournalLine("3000", "Owner Capital Account", debit=0.0, credit=base_amount),
            ]
            return JournalEntry(entry_id=eid, date=date, narration=raw_text, lines=lines, payment_mode="BANK")

        category = "food" if is_food else "general"
        gst_info = self.gst_agent.compute_gst_split(base_amount, gst_rate, state_code, category=category)
        cgst, sgst, igst = gst_info["cgst"], gst_info["sgst"], gst_info["igst"]
        total_gst = gst_info["total_gst"]

        tds = 0.0
        if not is_revenue and (is_rent or is_prof) and base_amount >= 20000:
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
            elif "cloud" in lower or "aws" in lower or "software" in lower:
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
        requires_hitl = (not is_revenue and gross_val > self.hitl_threshold) or (is_cash and gross_val > 10000)

        return JournalEntry(
            entry_id=eid,
            date=date,
            narration=raw_text,
            lines=lines,
            payment_mode="CASH" if is_cash else "BANK",
            status="PENDING_HITL" if requires_hitl else "POSTED",
            taxable_value=base_amount,
            cgst=cgst,
            sgst=sgst,
            igst=igst,
            tds=tds,
            itc_eligible=gst_info["itc_eligible"],
        )
