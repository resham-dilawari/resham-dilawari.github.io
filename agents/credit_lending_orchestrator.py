"""
Credit & Lending Orchestrator
Coordinates all agents for a business credit / lending decision.

Execution order (phased, not fully parallel):
  Phase 1 (parallel): RedFlag + Sanctions + FinancialHealth
  Phase 2 (parallel): CreditScoring + RepaymentCapacity   ← uses Phase 1 output
  Phase 3:            LoanStructuring                     ← uses Phase 2 output
  Phase 4:            Synthesize Credit Memo
"""
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor

from .underwriting_base import UnderwritingBaseAgent
from .red_flag_agent import RedFlagAgent
from .sanctions_watchlist_agent import SanctionsWatchlistAgent
from .financial_health_agent import FinancialHealthAgent
from .credit_scoring_agent import CreditScoringAgent
from .repayment_capacity_agent import RepaymentCapacityAgent
from .loan_structuring_agent import LoanStructuringAgent


class CreditLendingOrchestrator(UnderwritingBaseAgent):
    """
    Master orchestrator for credit & lending decisions.
    Reuses Phase 1 underwriting agents, then adds credit-specific agents.
    """

    def __init__(self):
        super().__init__(
            agent_name="Credit & Lending Orchestrator",
            specialization=(
                "credit decision orchestration, multi-phase risk synthesis, "
                "loan approval and structuring coordination"
            )
        )
        # Phase 1 — shared with underwriting
        self.phase1_agents = {
            "red_flag":       RedFlagAgent(),
            "sanctions":      SanctionsWatchlistAgent(),
            "financial_health": FinancialHealthAgent(),
        }
        # Phase 2 — credit-specific
        self.phase2_agents = {
            "credit_scoring":      CreditScoringAgent(),
            "repayment_capacity":  RepaymentCapacityAgent(),
        }
        # Phase 3
        self.loan_structuring = LoanStructuringAgent()

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run all phases and return a credit decision with full Credit Memo.

        Required data keys (in addition to standard underwriting fields):
        - loan_amount_requested (float, ₹)
        - loan_purpose (str)
        - loan_tenure_months (int)
        - collateral_type (str, key from LoanStructuringAgent.COLLATERAL_TYPES)
        - collateral_value (float, ₹)
        """
        self.log_action("credit_lending_start", {
            "company": data.get("company_name"),
            "loan_requested": data.get("loan_amount_requested"),
        })

        agent_results: Dict[str, Any] = {}

        # ── Phase 1: Parallel risk screening ────────────────────────────────
        self.log_action("phase1_start", {"agents": list(self.phase1_agents.keys())})
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures1 = {
                name: ex.submit(agent.analyze, data)
                for name, agent in self.phase1_agents.items()
            }
            for name, future in futures1.items():
                try:
                    agent_results[name] = future.result(timeout=45)
                except Exception as e:
                    agent_results[name] = {"error": str(e), "risk_level": "UNKNOWN"}
        self.log_action("phase1_complete", {
            k: v.get("risk_level") for k, v in agent_results.items()
        })

        # Hard-stop: if sanctions or red-flag is CRITICAL → instant reject
        if (agent_results.get("sanctions", {}).get("risk_level") == "CRITICAL" or
                agent_results.get("red_flag", {}).get("risk_level") == "CRITICAL"):
            return self._instant_reject(agent_results, data, reason="Critical risk flag detected in Phase 1")

        # ── Phase 2: Credit scoring + repayment capacity ─────────────────────
        # Enrich data with Phase 1 results for Phase 2 agents
        phase2_data = {
            **data,
            "red_flag_result":   agent_results.get("red_flag", {}),
            "sanctions_result":  agent_results.get("sanctions", {}),
            "financial_health_result": agent_results.get("financial_health", {}),
        }

        # Run credit scoring first to get interest rate estimate for EMI calc
        self.log_action("phase2_start", {})
        cs_result = self.phase2_agents["credit_scoring"].analyze(phase2_data)
        agent_results["credit_scoring"] = cs_result

        # Derive interest rate estimate for repayment capacity
        credit_rating = cs_result.get("credit_rating", "BB")
        rate_min, rate_max = LoanStructuringAgent.RATE_BANDS.get(credit_rating, (16.0, 20.0))
        rate_estimate = ((rate_min or 20.0) + (rate_max or 24.0)) / 2

        repay_data = {
            **phase2_data,
            "credit_score": cs_result.get("credit_score", 50),
            "credit_rating": credit_rating,
            "interest_rate_estimate": rate_estimate,
        }
        rc_result = self.phase2_agents["repayment_capacity"].analyze(repay_data)
        agent_results["repayment_capacity"] = rc_result
        self.log_action("phase2_complete", {
            "credit_score": cs_result.get("credit_score"),
            "credit_rating": credit_rating,
            "dscr": rc_result.get("dscr"),
            "repayment_verdict": rc_result.get("repayment_verdict"),
        })

        # ── Phase 3: Loan structuring ────────────────────────────────────────
        phase3_data = {
            **data,
            "credit_score":      cs_result.get("credit_score", 50),
            "credit_rating":     credit_rating,
            "dscr":              rc_result.get("dscr", 0.0),
            "max_viable_loan":   rc_result.get("max_viable_loan", data.get("loan_amount_requested", 0)),
            "repayment_verdict": rc_result.get("repayment_verdict", "VIABLE"),
            "interest_rate_estimate": rate_estimate,
        }
        ls_result = self.loan_structuring.analyze(phase3_data)
        agent_results["loan_structuring"] = ls_result
        self.log_action("phase3_complete", {
            "loan_decision": ls_result.get("loan_decision"),
            "recommended_amount": ls_result.get("recommended_amount"),
        })

        # ── Phase 4: Synthesise Credit Memo ──────────────────────────────────
        credit_memo = self._synthesize_credit_memo(agent_results, data)
        overall_risk = self._calculate_overall_risk(agent_results)
        final_decision = ls_result.get("loan_decision", "REQUEST_MORE_INFO")

        self.log_action("credit_lending_complete", {
            "overall_risk": overall_risk,
            "final_decision": final_decision,
        })

        return {
            "orchestrator": self.agent_name,
            "agent_results": agent_results,
            "credit_memo": credit_memo,
            "overall_risk": overall_risk,
            "decision": final_decision,
            "credit_score": cs_result.get("credit_score"),
            "credit_rating": credit_rating,
            "dscr": rc_result.get("dscr"),
            "recommended_amount": ls_result.get("recommended_amount"),
            "interest_rate": ls_result.get("interest_rate"),
            "interest_rate_band": ls_result.get("interest_rate_band"),
            "tenure_months": ls_result.get("tenure_months"),
            "collateral_type": ls_result.get("collateral_type"),
            "collateral_cover": ls_result.get("collateral_cover"),
            "collateral_adequate": ls_result.get("collateral_adequate"),
            "timestamp": self.execution_log[-1]["timestamp"],
        }

    # ── synthesis ────────────────────────────────────────────────────────────

    def _synthesize_credit_memo(self, agent_results: Dict[str, Any],
                                context: Dict[str, Any]) -> str:
        company_name  = context.get("company_name", "Unknown")
        loan_req      = context.get("loan_amount_requested", 0)
        loan_purpose  = context.get("loan_purpose", "Not specified")
        cs            = agent_results.get("credit_scoring", {})
        rc            = agent_results.get("repayment_capacity", {})
        ls            = agent_results.get("loan_structuring", {})

        summaries = "\n\n".join([
            f"**{name.upper().replace('_', ' ')} AGENT:**\n{result.get('analysis', str(result))}"
            for name, result in agent_results.items()
            if not result.get("error")
        ])

        prompt = f"""{self.get_system_prompt()}

You are writing a **Credit Memo** — the formal document a credit analyst produces
to recommend a lending decision to a credit committee.

## BORROWER
- **Company**: {company_name}
- **Loan Requested**: ₹{loan_req:,.0f}
- **Purpose**: {loan_purpose}

## AGENT FINDINGS
{summaries}

## KEY NUMBERS TO HIGHLIGHT
- Credit Score: {cs.get('credit_score', 'N/A')}/100
- Credit Rating: {cs.get('credit_rating', 'N/A')}
- DSCR: {rc.get('dscr', 'N/A')}
- Recommended Disbursement: ₹{ls.get('recommended_amount', 0):,.0f}
- Interest Rate: {ls.get('interest_rate', 'N/A')}%
- Tenure: {ls.get('tenure_months', 'N/A')} months
- Collateral Adequate: {ls.get('collateral_adequate', 'N/A')}

## CREDIT MEMO FORMAT

# 🏦 CREDIT MEMO

**Borrower**: {company_name}
**Date**: [Today's date]
**Prepared by**: AI Credit & Lending System
**Memo Reference**: CL-[auto]

---

## 1. EXECUTIVE SUMMARY
[3–4 sentences: who the borrower is, what they want, and the recommendation]

---

## 2. BORROWER PROFILE
[Business description, industry, years in operation, key directors]

---

## 3. CREDIT RISK ASSESSMENT

### 3.1 Credit Score & Rating
[Score, rating, key drivers — positive and negative]

### 3.2 Repayment Capacity (DSCR Analysis)
[DSCR value, interpretation, stress test result]

### 3.3 Red Flags & Compliance
[Summary from red flag and sanctions agents]

### 3.4 Financial Health
[Liquidity, solvency, profitability summary]

---

## 4. COLLATERAL ANALYSIS
[Type, gross value, haircut, effective cover, coverage ratio, adequacy]

---

## 5. PROPOSED LOAN TERMS
| Parameter | Value |
|-----------|-------|
| Principal (Recommended) | ₹[X] |
| Interest Rate | [X]% p.a. (reducing balance) |
| Tenure | [X] months |
| Monthly EMI | ₹[X] |
| Processing Fee | [X]% |
| Security | [collateral type] |

---

## 6. COVENANTS & CONDITIONS
[List key covenants from loan structuring agent]

---

## 7. PRE-DISBURSEMENT CHECKLIST
[List conditions from loan structuring agent]

---

## 8. CREDIT COMMITTEE RECOMMENDATION

**Decision**: [APPROVE / APPROVE WITH CONDITIONS / REJECT]
**Confidence**: [HIGH / MEDIUM / LOW]

**Approving Authority Required**: [Branch Manager / Credit Manager / Credit Committee — based on loan size]

**Reasoning**:
[Concise, balanced paragraph explaining the decision]

**Risks to Monitor**:
- [Risk 1]
- [Risk 2]

---

*This memo was generated by an AI Credit & Lending System. Final approval authority rests with the credit committee and senior management. This document is confidential and for internal use only.*
"""
        memo = self.generate_response(prompt, temperature=0.35)
        self.log_action("credit_memo_complete", {"success": True})
        return memo

    # ── risk aggregation ─────────────────────────────────────────────────────

    def _calculate_overall_risk(self, agent_results: Dict[str, Any]) -> str:
        risk_map = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "CLEAN": 0, "UNKNOWN": 2}
        levels = [r.get("risk_level", "UNKNOWN") for r in agent_results.values() if isinstance(r, dict)]
        if "CRITICAL" in levels:
            return "CRITICAL"
        scores = [risk_map.get(l, 2) for l in levels]
        avg = sum(scores) / len(scores) if scores else 2
        if avg >= 3.0:   return "HIGH"
        if avg >= 2.0:   return "MEDIUM"
        return "LOW"

    # ── instant reject helper ────────────────────────────────────────────────

    def _instant_reject(self, agent_results, data, reason) -> Dict[str, Any]:
        self.log_action("instant_reject", {"reason": reason})
        return {
            "orchestrator": self.agent_name,
            "agent_results": agent_results,
            "credit_memo": f"# ❌ APPLICATION REJECTED\n\n**Reason**: {reason}\n\n"
                           "This application has been automatically rejected due to critical "
                           "risk flags identified in the initial screening phase. "
                           "Please refer to the Agent Details tab for full findings.",
            "overall_risk": "CRITICAL",
            "decision": "REJECT",
            "credit_score": None,
            "credit_rating": None,
            "dscr": None,
            "recommended_amount": 0,
            "interest_rate": None,
            "interest_rate_band": "N/A",
            "tenure_months": None,
            "collateral_type": None,
            "collateral_cover": 0,
            "collateral_adequate": False,
            "timestamp": self.execution_log[-1]["timestamp"] if self.execution_log else "",
        }

    def get_agent_health_status(self) -> Dict[str, Any]:
        status = {}
        all_agents = {**self.phase1_agents, **self.phase2_agents,
                      "loan_structuring": self.loan_structuring}
        for name, agent in all_agents.items():
            status[name] = {
                "name": agent.agent_name,
                "specialization": agent.specialization,
                "execution_log_size": len(agent.get_execution_log()),
                "status": "healthy"
            }
        return status
