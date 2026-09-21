"""
Loan Structuring Agent
Designs the actual loan terms: disbursement amount, interest rate band,
tenure options, and type-specific collateral adequacy check.
"""
from typing import Dict, Any, Optional
from .underwriting_base import UnderwritingBaseAgent


class LoanStructuringAgent(UnderwritingBaseAgent):
    """
    Produces the final loan term sheet based on credit score, repayment
    capacity, and type-specific collateral valuation with haircuts.
    """

    # ── Collateral haircut table ─────────────────────────────────────────────
    # (type_key, display_name, max_ltv, notes)
    COLLATERAL_TYPES = {
        "real_estate": {
            "name": "Real Estate / Property",
            "max_ltv": 0.65,   # lend up to 65% of value
            "haircut": 0.35,
            "notes": "Illiquid; subject to market fluctuation. 35% haircut applied.",
        },
        "machinery": {
            "name": "Machinery / Equipment",
            "max_ltv": 0.55,
            "haircut": 0.45,
            "notes": "Depreciates quickly; 45% haircut to account for resale risk.",
        },
        "invoice_discounting": {
            "name": "Invoice Discounting / Receivables",
            "max_ltv": 0.75,
            "haircut": 0.25,
            "notes": "Short-duration; 25% haircut for collection risk.",
        },
        "pledge_receivables": {
            "name": "Pledge of Book Receivables",
            "max_ltv": 0.75,
            "haircut": 0.25,
            "notes": "Ongoing pool; 25% haircut for dilution and bad debt risk.",
        },
        "fd_securities": {
            "name": "Fixed Deposits / Liquid Securities",
            "max_ltv": 0.90,
            "haircut": 0.10,
            "notes": "Most liquid; only 10% haircut. Near-cash collateral.",
        },
        "none": {
            "name": "No Collateral (Unsecured)",
            "max_ltv": 0.0,
            "haircut": 1.0,
            "notes": "Unsecured lending. Higher rate, lower quantum.",
        },
    }

    # ── Interest rate bands by credit rating ─────────────────────────────────
    RATE_BANDS = {
        "AAA": (9.5,  11.0),
        "AA":  (10.5, 12.0),
        "A":   (11.5, 13.0),
        "BBB": (12.5, 14.5),
        "BB":  (14.0, 17.0),
        "B":   (16.0, 20.0),
        "C":   (20.0, 24.0),
        "D":   (None, None),   # Reject
    }

    def __init__(self):
        super().__init__(
            agent_name="Loan Structuring Agent",
            specialization=(
                "loan term design, interest rate pricing, collateral adequacy, "
                "LTV assessment, tenure optimisation, covenant structuring"
            )
        )

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Structure the final loan offer.

        Expected data keys (populated by orchestrator):
        - company_name
        - loan_amount_requested, loan_tenure_months, loan_purpose
        - collateral_type (key from COLLATERAL_TYPES)
        - collateral_value (₹)
        - credit_score, credit_rating (from CreditScoringAgent)
        - max_viable_loan (from RepaymentCapacityAgent)
        - dscr (from RepaymentCapacityAgent)
        - repayment_verdict
        """
        self.log_action("loan_structuring_start", {"company": data.get("company_name")})

        company_name      = data.get("company_name", "Unknown")
        loan_requested    = data.get("loan_amount_requested", 0)
        tenure_months     = data.get("loan_tenure_months", 24)
        loan_purpose      = data.get("loan_purpose", "Not specified")
        collateral_key    = data.get("collateral_type", "none")
        collateral_value  = data.get("collateral_value", 0)
        credit_score      = data.get("credit_score", 50)
        credit_rating     = data.get("credit_rating", "BB")
        max_viable_loan   = data.get("max_viable_loan", loan_requested)
        dscr              = data.get("dscr", 0.0)
        repay_verdict     = data.get("repayment_verdict", "VIABLE")

        # Collateral analysis
        coll_info     = self.COLLATERAL_TYPES.get(collateral_key, self.COLLATERAL_TYPES["none"])
        coll_cover    = collateral_value * coll_info["max_ltv"]
        coll_adequate = coll_cover >= loan_requested if collateral_key != "none" else False

        # Interest rate band
        rate_min, rate_max = self.RATE_BANDS.get(credit_rating, (18.0, 24.0))
        if rate_min is None:
            rate_band_str = "N/A — Reject"
        else:
            rate_band_str = f"{rate_min:.1f}% – {rate_max:.1f}% p.a."
            # Adjust for collateral (secured → lower end)
            midpoint = (rate_min + rate_max) / 2
            if collateral_key != "none" and coll_adequate:
                suggested_rate = rate_min
            elif collateral_key != "none":
                suggested_rate = midpoint
            else:
                suggested_rate = rate_max
        if rate_min is not None:
            suggested_rate_str = f"{suggested_rate:.1f}%"
        else:
            suggested_rate_str = "N/A"

        prompt = f"""You are the Loan Structuring Agent. Design the final loan term sheet.

## ENTITY
- **Company**: {company_name}
- **Loan Purpose**: {loan_purpose}

## CREDIT INPUTS
- **Credit Score**: {credit_score}/100
- **Credit Rating**: {credit_rating}
- **DSCR**: {dscr:.2f}
- **Repayment Verdict**: {repay_verdict}
- **Max Viable Loan (capacity-based)**: ₹{max_viable_loan:,.0f}

## LOAN REQUEST
- **Amount Requested**: ₹{loan_requested:,.0f}
- **Preferred Tenure**: {tenure_months} months

## COLLATERAL
- **Type**: {coll_info['name']}
- **Stated Value**: ₹{collateral_value:,.0f}
- **Haircut**: {coll_info['haircut']*100:.0f}%
- **Effective Cover (post-haircut)**: ₹{coll_cover:,.0f}
- **Max LTV**: {coll_info['max_ltv']*100:.0f}%
- **Collateral Notes**: {coll_info['notes']}
- **Collateral Adequate for Requested Amount?**: {'YES' if coll_adequate else 'NO — under-collateralised'}

## INTEREST RATE BAND (based on {credit_rating} rating)
- **Band**: {rate_band_str}
- **Suggested Rate**: {suggested_rate_str} (adjusted for collateral)

## YOUR TASKS

1. **Determine recommended disbursement amount** (minimum of: requested, max viable, collateral cover)
2. **Set interest rate** within the band (lower end if secured and DSCR ≥ 1.5, upper end if borderline)
3. **Recommend tenure options** (offer 2–3 options; shorter = less risk for lender)
4. **List loan covenants** appropriate for the risk level
5. **State any pre-disbursement conditions**

## OUTPUT FORMAT

## 💳 LOAN TERM SHEET — {company_name}

### 📋 LOAN SUMMARY
| Parameter | Requested | Recommended |
|-----------|-----------|-------------|
| Principal | ₹{loan_requested:,.0f} | ₹[X] |
| Interest Rate | — | [X]% p.a. (reducing balance) |
| Tenure | {tenure_months} months | [X] months |
| Monthly EMI | — | ₹[X] |
| Processing Fee | — | [X]% of principal |
| Total Cost of Loan | — | ₹[X] |

### 🏠 COLLATERAL ASSESSMENT
- **Collateral Type**: {coll_info['name']}
- **Gross Value**: ₹{collateral_value:,.0f}
- **Haircut Applied**: {coll_info['haircut']*100:.0f}%
- **Net Effective Value**: ₹{coll_cover:,.0f}
- **Coverage Ratio**: [X]% (effective cover / recommended loan)
- **Status**: [ADEQUATE / UNDER-COLLATERALISED / UNSECURED]
- **Recommendation**: [Action if under-collateralised]

### 📅 TENURE OPTIONS
| Option | Tenure | Monthly EMI | Total Interest | Recommendation |
|--------|--------|-------------|----------------|----------------|
| Conservative | [X] months | ₹[X] | ₹[X] | [note] |
| Moderate | [X] months | ₹[X] | ₹[X] | [note] |
| Extended | [X] months | ₹[X] | ₹[X] | [note] |

### 📜 LOAN COVENANTS
[List 4–6 covenants appropriate for this risk level, e.g.:]
- Minimum DSCR of 1.2x to be maintained quarterly
- [Others...]

### ✅ PRE-DISBURSEMENT CONDITIONS
[List 3–5 conditions that must be met before funds are released]

### 🎯 FINAL RECOMMENDATION
**Decision**: [APPROVE / APPROVE_WITH_CONDITIONS / REJECT]
**Disbursement Amount**: ₹[X]
**Interest Rate**: [X]%
**Tenure**: [X] months
**Confidence Level**: [HIGH / MEDIUM / LOW]
**Reasoning**: [2–3 sentence summary]

IMPORTANT: All EMI and total cost calculations must use reducing-balance method.
Show the EMI formula result for the recommended amount.
"""
        analysis = self.generate_response(prompt, temperature=0.25)

        recommend_amount, final_rate, final_tenure, ls_decision = self._extract_terms(
            analysis, loan_requested, max_viable_loan, coll_cover,
            rate_min, rate_max, suggested_rate if rate_min else None,
            tenure_months, credit_rating
        )

        risk_level = "LOW" if ls_decision == "APPROVE" else \
                     "MEDIUM" if ls_decision == "APPROVE_WITH_CONDITIONS" else "HIGH"

        self.log_action("loan_structuring_complete", {
            "decision": ls_decision,
            "recommended_amount": recommend_amount,
            "rate": final_rate,
            "tenure": final_tenure
        })

        return {
            "agent": self.agent_name,
            "analysis": analysis,
            "loan_decision": ls_decision,
            "recommended_amount": recommend_amount,
            "interest_rate": final_rate,
            "interest_rate_band": rate_band_str,
            "tenure_months": final_tenure,
            "collateral_type": coll_info["name"],
            "collateral_cover": coll_cover,
            "collateral_adequate": coll_adequate,
            "risk_level": risk_level,
            "timestamp": self.execution_log[-1]["timestamp"]
        }

    # ── helpers ──────────────────────────────────────────────────────────────

    def _extract_terms(self, analysis, loan_requested, max_viable, coll_cover,
                       rate_min, rate_max, suggested_rate, tenure_months, rating):
        import re

        # Recommended disbursement
        amt_match = re.search(r'Disbursement Amount[:\s*]+₹([\d,]+)', analysis)
        if amt_match:
            recommend_amount = float(amt_match.group(1).replace(",", ""))
        else:
            if rating == "D" or rate_min is None:
                recommend_amount = 0.0
            else:
                caps = [loan_requested, max_viable]
                if coll_cover > 0:
                    caps.append(coll_cover)
                recommend_amount = min(caps)

        # Rate
        rate_match = re.search(r'Interest Rate[:\s*]+([\d.]+)%', analysis)
        final_rate = float(rate_match.group(1)) if rate_match else (suggested_rate or (rate_max or 24.0))

        # Tenure
        tenure_match = re.search(r'Tenure[:\s*]+(\d+)\s*months', analysis)
        final_tenure = int(tenure_match.group(1)) if tenure_match else tenure_months

        # Decision
        if "REJECT" in analysis:
            ls_decision = "REJECT"
        elif "APPROVE_WITH_CONDITIONS" in analysis or "APPROVE WITH CONDITIONS" in analysis:
            ls_decision = "APPROVE_WITH_CONDITIONS"
        else:
            ls_decision = "APPROVE"

        return recommend_amount, final_rate, final_tenure, ls_decision

    @classmethod
    def collateral_type_options(cls):
        """Return list of (key, display_name) for UI dropdowns."""
        return [(k, v["name"]) for k, v in cls.COLLATERAL_TYPES.items()]
