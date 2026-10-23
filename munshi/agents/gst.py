# munshi/agents/gst.py
import re
from typing import Dict, Any, List, Optional, Tuple
from ..ledger.models import JournalEntry, round_money

GSTIN_REGEX = re.compile(r"^([0-9]{2})([A-Z]{5}[0-9]{4}[A-Z]{1})([1-9A-Z]{1})Z([0-9A-Z]{1})$")

# Statutory GST Reform Date (Sunsetting 12% & 28% slabs)
GST_REFORM_DATE = "2025-09-22"

# Complete 37 State/UT codes under Indian GST
STATE_MAP = {
    "01": "Jammu & Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "25": "Daman & Diu",
    "26": "Dadra & Nagar Haveli and Daman & Diu",
    "27": "Maharashtra",
    "28": "Andhra Pradesh (Old)",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman & Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh (New)",
    "38": "Ladakh",
    "97": "Other Territory",
    "99": "Centre Jurisdiction",
}

HSN_SLABS = {
    "9983": 18.0,  # IT, Consulting & SaaS Services
    "9982": 18.0,  # Legal & Accounting Services
    "9984": 18.0,  # Telecommunications & Cloud Infrastructure
    "9972": 18.0,  # Commercial Real Estate / Office Rent
    "9963": 5.0,   # Restaurant & Catering (Blocked ITC u/s 17(5))
    "9964": 5.0,   # Passenger Transport & Cab aggregators
    "8471": 18.0,  # Computers, Servers & Laptops
    "8517": 18.0,  # Smartphones & Telecom Equipment
    "4820": 18.0,  # Stationery & Registers (18% post 22-Sep-2025 reform)
    "0401": 0.0,   # Fresh Milk / Exempt Agricultural
}

class GSTAgent:
    def __init__(self, home_state_code: str = "27"):
        self.home_state_code = str(home_state_code).zfill(2)

    @staticmethod
    def validate_gstin(gstin: str) -> Dict[str, Any]:
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

    @staticmethod
    def validate_gst_rate(rate: float, invoice_date: str = "2026-10-16") -> Tuple[bool, Optional[str]]:
        """
        Validate GST rate against statutory rules.
        Effective 22-Sep-2025, 12% and 28% slabs were dropped/rationalized.
        """
        rate = float(rate)
        if invoice_date > GST_REFORM_DATE:
            if rate in (12.0, 28.0):
                return False, (
                    f"GST rate {rate:.1f}% was rationalized and sunset effective 22-Sep-2025. "
                    f"Post-reform standard slabs are 0%, 5%, and 18%. Invoices dated after "
                    f"{GST_REFORM_DATE} cannot use {rate:.1f}%."
                )
        valid_slabs = (0.0, 0.25, 3.0, 5.0, 12.0, 18.0, 28.0)
        if rate not in valid_slabs:
            return False, f"Invalid statutory GST rate {rate}%. Must be one of {valid_slabs}."
        return True, None

    def compute_gst_split(
        self,
        taxable_amount: float,
        gst_rate: float,
        counterparty_state_code: str = "27",
        category: str = "general",
        invoice_date: str = "2026-10-16",
    ) -> Dict[str, Any]:
        is_valid, err_msg = self.validate_gst_rate(gst_rate, invoice_date)
        if not is_valid:
            raise ValueError(err_msg)

        c_state = str(counterparty_state_code).zfill(2)
        is_inter_state = c_state != self.home_state_code
        total_gst = round_money(taxable_amount * (gst_rate / 100.0))
        if is_inter_state:
            cgst, sgst, igst = 0.0, 0.0, total_gst
        else:
            cgst = round_money(total_gst / 2.0)
            sgst = round_money(total_gst - cgst)
            igst = 0.0

        blocked_itc = category.lower() in ("food", "catering", "restaurant", "club", "personal_vehicle")
        return {
            "taxable_value": round_money(taxable_amount),
            "gst_rate": gst_rate,
            "supply_type": "INTER_STATE" if is_inter_state else "INTRA_STATE",
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "total_gst": total_gst,
            "gross_total": round_money(taxable_amount + total_gst),
            "itc_eligible": not blocked_itc,
            "sec_17_5_blocked": blocked_itc,
        }

    def generate_gstr3b_summary(self, entries: List[JournalEntry]) -> Dict[str, Any]:
        posted = [e for e in entries if e.status == "POSTED"]
        out_cgst = round_money(sum(l.credit for e in posted for l in e.lines if l.account_code == "2110"))
        out_sgst = round_money(sum(l.credit for e in posted for l in e.lines if l.account_code == "2120"))
        out_igst = round_money(sum(l.credit for e in posted for l in e.lines if l.account_code == "2130"))

        in_cgst = round_money(sum(l.debit for e in posted for l in e.lines if l.account_code == "1210"))
        in_sgst = round_money(sum(l.debit for e in posted for l in e.lines if l.account_code == "1220"))
        in_igst = round_money(sum(l.debit for e in posted for l in e.lines if l.account_code == "1230"))

        # Statutory Section 49 & 49A ITC Set-off:
        # Step 1: Utilize IGST Credit against Output IGST, then Output CGST, then Output SGST
        rem_out_igst = out_igst
        rem_out_cgst = out_cgst
        rem_out_sgst = out_sgst

        igst_credit = in_igst
        use_igst_for_igst = min(igst_credit, rem_out_igst)
        rem_out_igst = round_money(rem_out_igst - use_igst_for_igst)
        igst_credit = round_money(igst_credit - use_igst_for_igst)

        use_igst_for_cgst = min(igst_credit, rem_out_cgst)
        rem_out_cgst = round_money(rem_out_cgst - use_igst_for_cgst)
        igst_credit = round_money(igst_credit - use_igst_for_cgst)

        use_igst_for_sgst = min(igst_credit, rem_out_sgst)
        rem_out_sgst = round_money(rem_out_sgst - use_igst_for_sgst)
        igst_credit = round_money(igst_credit - use_igst_for_sgst)

        # Step 2: Utilize CGST Credit against remaining Output CGST, then remaining Output IGST (NO cross-utilization with SGST u/s 49(5)(e))
        cgst_credit = in_cgst
        use_cgst_for_cgst = min(cgst_credit, rem_out_cgst)
        rem_out_cgst = round_money(rem_out_cgst - use_cgst_for_cgst)
        cgst_credit = round_money(cgst_credit - use_cgst_for_cgst)

        use_cgst_for_igst = min(cgst_credit, rem_out_igst)
        rem_out_igst = round_money(rem_out_igst - use_cgst_for_igst)
        cgst_credit = round_money(cgst_credit - use_cgst_for_igst)

        # Step 3: Utilize SGST Credit against remaining Output SGST, then remaining Output IGST (NO cross-utilization with CGST u/s 49(5)(f))
        sgst_credit = in_sgst
        use_sgst_for_sgst = min(sgst_credit, rem_out_sgst)
        rem_out_sgst = round_money(rem_out_sgst - use_sgst_for_sgst)
        sgst_credit = round_money(sgst_credit - use_sgst_for_sgst)

        use_sgst_for_igst = min(sgst_credit, rem_out_igst)
        rem_out_igst = round_money(rem_out_igst - use_sgst_for_igst)
        sgst_credit = round_money(sgst_credit - use_sgst_for_igst)

        total_output = round_money(out_cgst + out_sgst + out_igst)
        total_itc = round_money(in_cgst + in_sgst + in_igst)
        net_payable = round_money(rem_out_cgst + rem_out_sgst + rem_out_igst)
        itc_carry_forward = round_money(cgst_credit + sgst_credit + igst_credit)

        return {
            "output_tax": {"cgst": out_cgst, "sgst": out_sgst, "igst": out_igst, "total": total_output},
            "eligible_itc": {"cgst": in_cgst, "sgst": in_sgst, "igst": in_igst, "total": total_itc},
            "net_payable_breakdown": {"cgst": rem_out_cgst, "sgst": rem_out_sgst, "igst": rem_out_igst},
            "itc_carry_forward_breakdown": {"cgst": cgst_credit, "sgst": sgst_credit, "igst": igst_credit},
            "net_gst_payable": net_payable,
            "itc_credit_carry_forward": itc_carry_forward,
        }
