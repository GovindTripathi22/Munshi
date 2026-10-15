"""Indian GST (Goods and Services Tax) Computation Agent."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional
from munshi.config import MunshiConfig, VALID_GST_RATES, INDIAN_STATE_GST_CODES


class GSTComputationAgent:
    """Computes CGST, SGST, IGST, ITC eligibility, and RCM under Indian tax law."""

    def __init__(self, config: Optional[MunshiConfig] = None):
        self.config = config or MunshiConfig()

    def extract_state_code(self, gstin: Optional[str]) -> Optional[str]:
        """Extracts 2-digit state code from GSTIN (e.g. '27AAAAA0000A1Z5' -> '27')."""
        if not gstin or len(gstin) < 2:
            return None
        code = gstin[:2]
        return code if code in INDIAN_STATE_GST_CODES else None

    def compute_gst(
        self,
        taxable_value: Decimal,
        rate: Decimal,
        counterparty_gstin: Optional[str] = None,
        is_inter_state: Optional[bool] = None,
        is_itc_eligible: bool = True,
        is_rcm: bool = False,
        hsn_sac: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculates exact GST breakdown with zero hallucination.
        
        Rules:
        - If Intra-state (Supplier state == Company state):
            CGST = taxable_value * (rate / 2)
            SGST = taxable_value * (rate / 2)
            IGST = 0
        - If Inter-state (Supplier state != Company state):
            IGST = taxable_value * rate
            CGST = 0
            SGST = 0
        """
        # Quantize rate and round to 2 decimals
        if rate not in VALID_GST_RATES:
            # Check if rate is in percentage (e.g. 18 instead of 0.18)
            if rate / Decimal("100") in VALID_GST_RATES:
                rate = rate / Decimal("100")
            else:
                raise ValueError(
                    f"Invalid GST rate: {rate}. Must be one of {[float(r) for r in VALID_GST_RATES]}."
                )

        # Determine inter-state vs intra-state
        supplier_state = self.extract_state_code(counterparty_gstin)
        if is_inter_state is None:
            if supplier_state:
                is_inter_state = (supplier_state != self.config.home_state_code)
            else:
                # Default to intra-state if counterparty GSTIN is missing/local
                is_inter_state = False

        total_tax = (taxable_value * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if is_inter_state:
            cgst = Decimal("0.00")
            sgst = Decimal("0.00")
            igst = total_tax
        else:
            cgst = (total_tax / Decimal("2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            # Ensure cgst + sgst == total_tax exactly (handle 1 paisa rounding disparity)
            sgst = total_tax - cgst
            igst = Decimal("0.00")

        total_invoice_amount = taxable_value + total_tax

        return {
            "taxable_value": str(taxable_value),
            "rate_percent": float(rate * 100),
            "is_inter_state": is_inter_state,
            "home_state": self.config.home_state_code,
            "counterparty_state": supplier_state or self.config.home_state_code,
            "cgst": str(cgst),
            "sgst": str(sgst),
            "igst": str(igst),
            "total_tax": str(total_tax),
            "total_invoice_amount": str(total_invoice_amount),
            "itc_eligible": is_itc_eligible,
            "is_rcm": is_rcm,
            "hsn_sac": hsn_sac or "",
        }
