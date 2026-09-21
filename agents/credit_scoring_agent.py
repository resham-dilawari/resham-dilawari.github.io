"""
Credit Scoring Agent
Produces an internal credit score (0-100) and rating (AAA to D)
based on financial statements, ratios, and industry benchmarks.
"""
from typing import Dict, Any
from .underwriting_base import UnderwritingBaseAgent


class CreditScoringAgent(UnderwritingBaseAgent):
    """
    Generates an internal credit score and rating for a business entity.
    Uses financial ratios, profitability, leverage, and industry default rates.
    """

    # Industry-level average default rates (for context in prompt)
    INDUSTRY_DEFAULT_RATES = {
        "E-commerce":            "3.2%",
        "SaaS/Software":         "1.8%",
        "Professional Services": "1.5%",
        "Manufacturing":         "2.9%",
        "Education":             "2.1%",
        "Healthcare":            "1.6%",
        "Travel":                "4.5%",
        "Forex Trading":         "8.0%",
        "MLM":                   "9.5%",
        "Other":                 "3.5%",
    }

    def __init__(self):
        super().__init__(
            agent_name="Credit Scoring Agent",
            specialization=(
                "internal credit scoring, financial ratio analysis, "
                "credit rating assignment, industry default benchmarking"
            )
        )

    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score the business entity on a 0-100 scale and assign a letter rating.

        Expected data keys:
        - company_name, years_in_business, industry, country
        - financial_data: revenue, net_profit, total_assets, total_liabilities,
                          cash, total_debt, total_equity (derived)
        - credit_rating: external rating if available
        - red_flag_result: output from RedFlagAgent (optional, passed by orchestrator)
        - sanctions_result: output from SanctionsWatchlistAgent (optional)
        """
        self.log_action("credit_scoring_start", {"company": data.get("company_name")})

        company_name   = data.get("company_name", "Unknown")
        years          = data.get("years_in_business", 0)
        industry       = data.get("industry", "Other")
        fin            = data.get("financial_data", {})
        ext_rating     = data.get("credit_rating", "Not Available")
        red_flag_risk  = data.get("red_flag_result", {}).get("risk_level", "UNKNOWN")
        sanctions_risk = data.get("sanctions_result", {}).get("risk_level", "UNKNOWN")
        industry_default = self.INDUSTRY_DEFAULT_RATES.get(industry, "3.5%")

        prompt = f"""You are the Credit Scoring Agent. Score this business for creditworthiness.

## ENTITY
- **Company**: {company_name}
- **Industry**: {industry} (sector avg default rate: {industry_default})
- **Years in Business**: {years}
- **External Credit Rating**: {ext_rating}
- **Red Flag Agent Risk Level**: {red_flag_risk}
- **Sanctions Agent Risk Level**: {sanctions_risk}

## FINANCIAL DATA
{self._format_financials(fin)}

## SCORING METHODOLOGY
Score the company 0–100 across 5 dimensions. Return EXACT numeric scores.

### 1. Leverage & Solvency (25 pts)
- Debt-to-Equity < 1.0 → 25 pts
- D/E 1.0–2.0 → 18 pts
- D/E 2.0–3.0 → 10 pts
- D/E > 3.0 or negative equity → 0 pts
- If no debt data: 12 pts (neutral)

### 2. Liquidity (20 pts)
- Cash/Monthly-Revenue > 3 months → 20 pts
- 1–3 months → 14 pts
- < 1 month → 5 pts
- Negative cash → 0 pts
- If no data: 10 pts

### 3. Profitability (25 pts)
- Net Margin > 15% → 25 pts
- 8–15% → 18 pts
- 2–8% → 10 pts
- 0–2% → 5 pts
- Negative (loss-making) → 0 pts
- If no data: 10 pts

### 4. Business Maturity (15 pts)
- > 5 years → 15 pts
- 3–5 years → 10 pts
- 1–3 years → 6 pts
- < 1 year → 2 pts

### 5. Risk Profile (15 pts)
- Red flag CLEAN + sanctions CLEAN → 15 pts
- One LOW → 12 pts
- One MEDIUM → 8 pts
- One HIGH → 3 pts
- Any CRITICAL → 0 pts

## LETTER RATING SCALE
| Score | Rating | Interpretation |
|-------|--------|----------------|
| 85–100 | AAA | Prime — minimal credit risk |
| 75–84  | AA  | High grade |
| 65–74  | A   | Upper medium grade |
| 55–64  | BBB | Lower medium grade — investment grade threshold |
| 45–54  | BB  | Speculative — elevated risk |
| 35–44  | B   | Speculative — significant risk |
| 20–34  | C   | Poor — near default |
| 0–19   | D   | Default / imminent default |

## OUTPUT FORMAT

## 💳 CREDIT SCORE SUMMARY
**Score**: [0–100]
**Rating**: [AAA / AA / A / BBB / BB / B / C / D]
**Grade**: [Prime / High / Upper-Medium / Lower-Medium / Speculative / Poor / Default]

## 📊 DIMENSION BREAKDOWN
| Dimension | Max | Score | Notes |
|-----------|-----|-------|-------|
| Leverage & Solvency | 25 | [X] | [brief note] |
| Liquidity | 20 | [X] | [brief note] |
| Profitability | 25 | [X] | [brief note] |
| Business Maturity | 15 | [X] | [brief note] |
| Risk Profile | 15 | [X] | [brief note] |
| **TOTAL** | **100** | **[X]** | |

## ⚠️ KEY SCORING FACTORS
[3–5 bullet points explaining the most impactful factors, positive and negative]

## 💡 CREDIT ANALYST NOTES
[Any caveats, data gaps, or recommendations for the underwriter]

IMPORTANT: Be precise with numbers. Show your working for each dimension.
"""
        analysis = self.generate_response(prompt, temperature=0.2)

        score, rating = self._extract_score_and_rating(analysis, fin, years,
                                                        red_flag_risk, sanctions_risk)
        risk_level = self._rating_to_risk(rating)

        self.log_action("credit_scoring_complete", {
            "score": score, "rating": rating, "risk_level": risk_level
        })

        return {
            "agent": self.agent_name,
            "analysis": analysis,
            "credit_score": score,
            "credit_rating": rating,
            "risk_level": risk_level,
            "timestamp": self.execution_log[-1]["timestamp"]
        }

    # ── helpers ──────────────────────────────────────────────────────────────

    def _format_financials(self, fin: dict) -> str:
        if not fin:
            return "No financial data provided."
        lines = []
        mapping = [
            ("revenue",           "Revenue (₹)"),
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
        return "\n".join(lines) if lines else "Financial data keys not recognised."

    def _extract_score_and_rating(
        self, analysis: str, fin: dict, years: int,
        red_flag_risk: str, sanctions_risk: str
    ) -> tuple:
        """Parse score and rating from LLM output, with a fallback heuristic."""
        import re

        # Try to parse score from "Score: XX" or "TOTAL** | **XX**"
        score_match = re.search(r'\*\*Score\*\*[:\s]+(\d+)', analysis)
        if not score_match:
            score_match = re.search(r'TOTAL.*?(\d{1,3})', analysis)
        score = int(score_match.group(1)) if score_match else self._heuristic_score(
            fin, years, red_flag_risk, sanctions_risk)
        score = max(0, min(100, score))

        # Try to parse rating
        rating_match = re.search(
            r'\*\*Rating\*\*[:\s]+(AAA|AA|A|BBB|BB|B|C|D)\b', analysis)
        if rating_match:
            rating = rating_match.group(1)
        else:
            rating = self._score_to_rating(score)

        return score, rating

    def _heuristic_score(self, fin: dict, years: int,
                         red_flag_risk: str, sanctions_risk: str) -> int:
        score = 0
        # Maturity
        if years >= 5:   score += 15
        elif years >= 3: score += 10
        elif years >= 1: score += 6
        else:            score += 2
        # Risk profile
        worst = max(
            self._risk_to_num(red_flag_risk),
            self._risk_to_num(sanctions_risk)
        )
        score += max(0, 15 - worst * 4)
        # Profitability
        if fin:
            rev = fin.get("revenue", 0)
            pft = fin.get("net_profit", 0)
            if rev > 0:
                margin = pft / rev
                if margin > 0.15:  score += 25
                elif margin > 0.08: score += 18
                elif margin > 0.02: score += 10
                elif margin > 0:   score += 5
            else:
                score += 10
            # Leverage
            eq  = fin.get("total_equity", 0)
            dbt = fin.get("total_debt", 0)
            if eq > 0 and dbt >= 0:
                de = dbt / eq
                if de < 1.0:   score += 25
                elif de < 2.0: score += 18
                elif de < 3.0: score += 10
            else:
                score += 12
            # Liquidity
            cash = fin.get("cash", 0)
            monthly = rev / 12 if rev > 0 else 0
            if monthly > 0:
                months = cash / monthly
                if months > 3:    score += 20
                elif months >= 1: score += 14
                else:             score += 5
            else:
                score += 10
        else:
            score += 10 + 12 + 10  # neutral for missing data
        return score

    def _risk_to_num(self, risk: str) -> int:
        return {"CLEAN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}.get(risk, 2)

    def _score_to_rating(self, score: int) -> str:
        if score >= 85: return "AAA"
        if score >= 75: return "AA"
        if score >= 65: return "A"
        if score >= 55: return "BBB"
        if score >= 45: return "BB"
        if score >= 35: return "B"
        if score >= 20: return "C"
        return "D"

    def _rating_to_risk(self, rating: str) -> str:
        return {
            "AAA": "LOW",  "AA": "LOW",  "A": "LOW",
            "BBB": "MEDIUM",
            "BB": "HIGH",  "B": "HIGH",
            "C": "CRITICAL", "D": "CRITICAL"
        }.get(rating, "MEDIUM")
