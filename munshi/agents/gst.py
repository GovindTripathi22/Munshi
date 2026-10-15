# munshi/agents/gst.py
import re
from typing import Dict, Any, List
from ..ledger.models import JournalEntry, round_Money

GSTIN_REGEX = re.compile(r"^([0-9]{2})([A-Z]{5}[0-9]{4}[A-Z]{1})([1-9A-Z]{1})Z([0-9A-Z]{1})$")

STATE_MAP = {
    "07": "Delhi",
    "09": "Uttar Pradesh",
    "19": "West Bengal",
    "24": "Gujarat",
    "27": "Maharashtra",
    "29": "Karnataka",
    "33": "Tamil Nadu",
    "36": "Telangana",
}

HSN_SLABS = {
    "9983": 18.0,  # IT & SaaS Services
    "9972": 18.0,  # Commercial Real Estate / Office Rent
    "9963": 5.0,   # Restaurant & Catering (Blocked ITC u/s 17(5))
    "8471": 18.0,  # Computers / Laptops
    "0401": 0.0,   # Fresh Milk / Exempt Agricultural
}

class GSTAgent:
    def __init__(self, home_state_code: str = "27"):
        self.home_state_code = home_state_code

    def validate_gstin(self, gstin: str) -> Dict[str, Any]:
        clean = (gstin or "").strip().upper()
        match = GSTIN_REGEX.match(clean)
        if not match:
            return {"valid": False, "gstin": clean, "state_code": None, "state_name": None, "pan": None}
        state_code = match.group(1)
        return {
            "valid": True,
            "gstin": clean,
            "state_code": state_code,
            "state_name": STATE_MAP.get(state_code, f"State-{state_code}"),
            "pan": match.group(2),
        }

    def compute_gst_split(
        self,
        taxable_amount: float,
        gst_rate: float,
        counterparty_state_code: str = "27",
        category: str = "general",
    ) -> Dict[str, Any]:
        is_inter_state = counterparty_state_code != self.home_state_code
        total_gst = round_Money(taxable_amount * (gst_rate / 100.0))
        if is_inter_state:
            cgst, sgst, igst = 0.0, 0.0, total_gst
        else:
            cgst = round_Money(total_gst / 2.0)
            sgst = round_Money(total_gst - cgst)
            igst = 0.0

        blocked_itc = category.lower() in ("food", "catering", "restaurant", "club", "personal_vehicle")
        return {
            "taxable_value": round_Money(taxable_amount),
            "gst_rate": gst_rate,
            "supply_type": "INTER_STATE" if is_inter_state else "INTRA_STATE",
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "total_gst": total_gst,
            "gross_total": round_Money(taxable_amount + total_gst),
            "itc_eligible": not blocked_itc,
            "sec_17_5_blocked": blocked_itc,
        }

    def generate_gstr3b_summary(self, entries: List[JournalEntry]) -> Dict[str, Any]:
        posted = [e for e in entries if e.status == "POSTED"]
        out_cgst = round_Money(sum(l.credit for e in posted for l in e.lines if l.account_code == "2110"))
        out_sgst = round_Money(sum(l.credit for e in posted for l in e.lines if l.account_code == "2120"))
        out_igst = round_Money(sum(l.credit for e in posted for l in e.lines if l.account_code == "2130"))

        in_cgst = round_Money(sum(l.debit for e in posted for l in e.lines if l.account_code == "1210"))
        in_sgst = round_Money(sum(l.debit for e in posted for l in e.lines if l.account_code == "1220"))
        in_igst = round_Money(sum(l.debit for e in posted for l in e.lines if l.account_code == "1230"))

        total_output = round_Money(out_cgst + out_sgst + out_igst)
        total_itc = round_Money(in_cgst + in_sgst + in_igst)
        net_payable = round_Money(max(0.0, total_output - total_itc))
        itc_carry_forward = round_Money(max(0.0, total_itc - total_output))

        return {
            "output_tax": {"cgst": out_cgst, "sgst": out_sgst, "igst": out_igst, "total": total_output},
            "eligible_itc": {"cgst": in_cgst, "sgst": in_sgst, "igst": in_igst, "total": total_itc},
            "net_gst_payable": net_payable,
            "itc_credit_Carry_forward": itc_carry_forward,
        }

GSTComputationAgent = GSTAgent

