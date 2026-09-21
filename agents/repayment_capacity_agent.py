"""
Repayment Capacity Agent
Determines whether a business can service the requested loan.
Key metric: DSCR (Debt Service Coverage Ratio) ≥ 1.25 is the threshold.
"""
from typing import Dict, Any
from .underwriting_base import UnderwritingBaseAgent


class RepaymentCapacityAgent(UnderwritingBaseAgent):
    """
    Assesses whether the business generates enough free cash flow
    to comfortably repay the requested loan, including a stress test.
    """

    def __init__(self):
        super().__init__(
            agent_name="Repayment Capacity Agent",
            specialization=(
                "debt service coverage ratio, free cash flow analysis, "
                "EMI affordability, stress testing, maximum loan sizing"
            )
        )

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute DSCR and repayment capacity.

        Expected data keys:
        - company_name, financial_data
        - loan_amount_requested (₹)
        - loan_tenure_months (int)
        - interest_rate_estimate (float, %, e.g. 13.0) — passed by orchestrator
          from credit score output
        """
        self.log_action("repayment_capacity_start", {"company": data.get("company_name")})

        company_name     = data.get("company_name", "Unknown")
        fin              = data.get("financial_data", {})
        loan_requested   = data.get("loan_amount_requested", 0)
        tenure_months    = data.get("loan_tenure_months", 24)
        rate_estimate    = data.get("interest_rate_estimate", 14.0)
        credit_score     = data.get("credit_score", 50)

        # Pre-compute EMI so the LLM can reason about it
        emi = self._compute_emi(loan_requested, rate_estimate, tenure_months)
        annual_debt_service = emi * 12

        prompt = f"""You are the Repayment Capacity Agent. Assess whether this business
can repay the requested loan without financial distress.

## ENTITY
- **Company**: {company_name}
- **Credit Score**: {credit_score}/100

## LOAN REQUEST
- **Amount Requested**: ₹{loan_requested:,.0f}
- **Tenure**: {tenure_months} months
- **Estimated Interest Rate**: {rate_estimate:.1f}% p.a.
- **Estimated Monthly EMI**: ₹{emi:,.0f}
- **Annual Debt Service (EMI × 12)**: ₹{annual_debt_service:,.0f}

## FINANCIAL DATA
{self._format_financials(fin)}

## YOUR ANALYSIS TASKS

### Task 1 — Compute DSCR
DSCR = Net Operating Income (NOI) / Annual Debt Service
- NOI ≈ Net Profit + Interest Expense + Depreciation (use net profit as proxy if EBITDA not available)
- DSCR ≥ 1.25 → Adequate (lender standard)
- DSCR 1.0–1.25 → Borderline (tight coverage)
- DSCR < 1.0 → Insufficient (business cannot cover payments from operations)

### Task 2 — Free Cash Flow (FCF) Check
- FCF = Revenue − Operating Costs − Existing Debt Payments (estimate if not given)
- Can FCF cover the proposed EMI with ≥ 25% buffer?

### Task 3 — Stress Test (Revenue Shock)
- Assume revenue drops 20% — can the business still cover the EMI?
- At what revenue level does the business fail to cover debt service?

### Task 4 — Maximum Viable Loan Amount
- Based on actual cash flows, what is the MAXIMUM loan this business can comfortably service?
- This may be less than, equal to, or (rarely) more than the requested amount.

## OUTPUT FORMAT

## 💵 REPAYMENT CAPACITY SUMMARY
[2–3 sentence overall verdict]

## 📐 DSCR CALCULATION
- **Net Operating Income (NOI)**: ₹[X]
- **Annual Debt Service**: ₹{annual_debt_service:,.0f}
- **DSCR**: [X.XX] → [ADEQUATE / BORDERLINE / INSUFFICIENT]

## 📊 FREE CASH FLOW CHECK
- **Estimated FCF**: ₹[X] per year
- **EMI Annual Burden**: ₹{annual_debt_service:,.0f}
- **FCF Buffer After EMI**: ₹[X] ([X]%) → [COMFORTABLE / TIGHT / NEGATIVE]

## 🧪 STRESS TEST (−20% Revenue)
- **Stressed Revenue**: ₹[X]
- **Stressed NOI**: ₹[X]
- **Can Cover EMI at Stressed Revenue?**: [YES / NO]
- **Break-even Revenue (min to cover EMI)**: ₹[X]

## 📏 MAXIMUM VIABLE LOAN
- **Recommended Maximum**: ₹[X]
- **Vs Requested (₹{loan_requested:,.0f})**: [WITHIN CAPACITY / OVER CAPACITY by ₹X]

## ⚠️ REPAYMENT RISK FLAGS
[List any concerns about repayment ability]

## ✅ REPAYMENT VERDICT
**Decision**: [VIABLE / VIABLE_WITH_REDUCED_AMOUNT / NOT_VIABLE]
**Confidence**: [HIGH / MEDIUM / LOW]
**Reasoning**: [Concise explanation]

IMPORTANT: Show all arithmetic. If financial data is insufficient, state clearly and
recommend what additional documents to request (e.g. bank statements, GST returns).
"""
        analysis = self.generate_response(prompt, temperature=0.2)

        dscr, max_loan, verdict = self._extract_metrics(
            analysis, fin, loan_requested, annual_debt_service)
        risk_level = self._verdict_to_risk(verdict)

        self.log_action("repayment_capacity_complete", {
            "dscr": dscr, "max_loan": max_loan,
            "verdict": verdict, "risk_level": risk_level
        })

        return {
            "agent": self.agent_name,
            "analysis": analysis,
            "dscr": dscr,
            "max_viable_loan": max_loan,
            "repayment_verdict": verdict,
            "risk_level": risk_level,
            "emi": emi,
            "annual_debt_service": annual_debt_service,
            "timestamp": self.execution_log[-1]["timestamp"]
        }

    # ── helpers ──────────────────────────────────────────────────────────────

    def _compute_emi(self, principal: float, annual_rate: float, months: int) -> float:
        """Standard reducing-balance EMI formula."""
        if principal <= 0 or months <= 0:
            return 0.0
        r = (annual_rate / 100) / 12          # monthly rate
        if r == 0:
            return principal / months
        return principal * r * (1 + r) ** months / ((1 + r) ** months - 1)

    def _format_financials(self, fin: dict) -> str:
        if not fin:
            return "No financial data provided — DSCR estimation will rely on qualitative assessment."
        lines = []
        mapping = [
            ("revenue",           "Annual Revenue (₹)"),
            ("net_profit",        "Net Profit (₹)"),
            ("total_assets",      "Total Assets (₹)"),
            ("total_liabilities", "Total Liabilities (₹)"),
            ("total_equity",      "Total Equity (₹)"),
            ("cash",              "Cash & Equivalents (₹)"),
            ("total_debt",        "Total Debt (₹)"),
        ]
        for key, label in mapping:
            if key in fin:
                lines.append(f"- {label}: ₹{fin[key]:,.0f}")
        return "\n".join(lines) if lines else "No recognised financial keys found."

    def _extract_metrics(self, analysis: str, fin: dict,
                         loan_requested: float, annual_debt_service: float):
        """Parse DSCR, max loan, and verdict from LLM output with fallbacks."""
        import re

        # DSCR
        dscr_match = re.search(r'\*\*DSCR\*\*[:\s]+([\d.]+)', analysis)
        if dscr_match:
            dscr = float(dscr_match.group(1))
        else:
            # Heuristic: NOI ≈ net profit
            noi = fin.get("net_profit", 0) if fin else 0
            dscr = (noi / annual_debt_service) if annual_debt_service > 0 else 0.0

        # Max viable loan
        max_match = re.search(r'Recommended Maximum[:\s*]+₹([\d,]+)', analysis)
        if max_match:
            max_loan = float(max_match.group(1).replace(",", ""))
        else:
            # Heuristic: if DSCR < 1, scale down
            if dscr >= 1.25:
                max_loan = loan_requested
            elif dscr > 0:
                max_loan = loan_requested * (dscr / 1.25)
            else:
                max_loan = 0.0

        # Verdict
        if "NOT_VIABLE" in analysis or "NOT VIABLE" in analysis:
            verdict = "NOT_VIABLE"
        elif "VIABLE_WITH_REDUCED" in analysis or "OVER CAPACITY" in analysis:
            verdict = "VIABLE_WITH_REDUCED_AMOUNT"
        else:
            verdict = "VIABLE"

        return round(dscr, 2), round(max_loan, 0), verdict

    def _verdict_to_risk(self, verdict: str) -> str:
        return {
            "VIABLE":                    "LOW",
            "VIABLE_WITH_REDUCED_AMOUNT": "MEDIUM",
            "NOT_VIABLE":                "HIGH",
        }.get(verdict, "MEDIUM")
