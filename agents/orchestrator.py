"""
Orchestrator Agent - The Master Coordinator
Manages the multi-agent workflow, delegates tasks, and synthesizes insights
"""
from typing import Dict, Any, List
from .base_agent import BaseAgent
from .fundamental_agent import FundamentalAnalysisAgent
from .technical_agent import TechnicalAnalysisAgent
from .sentiment_agent import SentimentAnalysisAgent
from .risk_agent import RiskAssessmentAgent
from .optimizer_agent import PortfolioOptimizerAgent
from .research_agent import MarketResearchAgent
from .tax_agent import TaxOptimizationAgent
from .rag_agent import RAGAgent
import asyncio
from concurrent.futures import ThreadPoolExecutor


class OrchestratorAgent(BaseAgent):
    """
    Master orchestrator that coordinates all specialized agents.
    
    Responsibilities:
    - Understand user intent and requirements
    - Determine which agents to activate
    - Manage agent execution (parallel when possible)
    - Synthesize multi-agent insights into coherent recommendations
    - Detect conflicts between agent recommendations
    - Make final strategic decisions
    """
    
    def __init__(self):
        super().__init__(
            agent_name="Orchestrator Agent",
            specialization="multi-agent coordination, strategic decision-making, and insight synthesis"
        )
        
        # Initialize all specialized agents
        self.agents = {
            "fundamental": FundamentalAnalysisAgent(),
            "technical": TechnicalAnalysisAgent(),
            "sentiment": SentimentAnalysisAgent(),
            "risk": RiskAssessmentAgent(),
            "optimizer": PortfolioOptimizerAgent(),
            "research": MarketResearchAgent(),
            "tax": TaxOptimizationAgent(),
            "rag": RAGAgent(use_real_db=True)
        }
        
    def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main orchestration method - determines workflow and coordinates agents.
        
        Context should include:
        - request_type: "portfolio_analysis", "investment_suggestion", "full_advisory"
        - data: All relevant data for analysis
        - user_profile: Risk tolerance, goals, etc.
        """
        request_type = context.get("request_type", "full_advisory")
        self.log_action("orchestration_start", {
            "request_type": request_type,
            "data_keys": list(context.keys())
        })
        
        if request_type == "portfolio_analysis":
            return self._analyze_portfolio(context)
        elif request_type == "investment_suggestion":
            return self._suggest_investments(context)
        elif request_type == "full_advisory":
            return self._full_advisory(context)
        else:
            return {"error": f"Unknown request type: {request_type}"}
    
    def _analyze_portfolio(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze current portfolio using multiple agents."""
        self.log_action("portfolio_analysis_workflow", {})

        # portfolio_data is now a list of per-ticker data dicts
        portfolio_data = context.get("portfolio_data", [])
        if isinstance(portfolio_data, dict):
            portfolio_data = [portfolio_data]  # backwards-compat if a single dict is passed
        tickers = context.get("tickers", context.get("current_holdings", []))

        agent_results = {}

        
        # Execute agents in parallel where possible
        with ThreadPoolExecutor(max_workers=4) as executor:
            
            def _run_agent_on_list(agent, data_list):
                if not data_list:
                    return {"analysis": "No data provided."}
                results = []
                for item in data_list:
                    try:
                        res = agent.analyze(item)
                        ticker = item.get("ticker", "Unknown")
                        analysis_text = res.get("analysis", str(res))
                        results.append(f"#### {ticker}\n{analysis_text}")
                    except Exception as e:
                        results.append(f"#### {item.get('ticker', 'Unknown')}\nError: {e}")
                return {"analysis": "\n\n".join(results)}

            # These can run in parallel - they analyze the same data independently
            futures = {
                "fundamental": executor.submit(
                    _run_agent_on_list,
                    self.agents["fundamental"],
                    portfolio_data
                ),
                "technical": executor.submit(
                    _run_agent_on_list,
                    self.agents["technical"],
                    portfolio_data
                ),
                "sentiment": executor.submit(
                    _run_agent_on_list,
                    self.agents["sentiment"],
                    portfolio_data
                ),
            }
            
            for agent_name, future in futures.items():
                try:
                    agent_results[agent_name] = future.result(timeout=60)
                except Exception as e:
                    agent_results[agent_name] = {"error": str(e)}
        
        # Risk analysis needs results from previous agents
        try:
            agent_results["risk"] = self.agents["risk"].portfolio_diversification_check(portfolio_data)
        except Exception as e:
            agent_results["risk"] = {"error": str(e)}

        
        # Synthesize all agent insights
        synthesis = self._synthesize_insights(agent_results, "portfolio_analysis")
        
        return {
            "orchestrator": self.agent_name,
            "workflow": "portfolio_analysis",
            "agent_results": agent_results,
            "synthesis": synthesis,
            "timestamp": self.execution_log[-1]["timestamp"] if self.execution_log else None
        }
    
    def _suggest_investments(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate investment suggestions using multiple agents."""
        self.log_action("investment_suggestion_workflow", {})

        user_profile = context.get("user_profile", {})
        agent_results = {}

        # Research and optimizer are independent — run them in parallel
        research_context = {
            "user_preferences": user_profile.get("preferences"),
            "risk_tolerance": user_profile.get("risk_tolerance"),
            "market_context": context.get("market_context", {})
        }
        optimizer_context = {
            "available_cash": context.get("corpus", 0),
            "risk_tolerance": user_profile.get("risk_tolerance"),
            "current_portfolio": context.get("current_holdings", []),
            "investment_goals": user_profile.get("goals")
        }

        with ThreadPoolExecutor(max_workers=2) as executor:
            research_future = executor.submit(self.agents["research"].analyze, research_context)
            optimizer_future = executor.submit(self.agents["optimizer"].analyze, optimizer_context)

            try:
                agent_results["research"] = research_future.result(timeout=60)
            except Exception as e:
                agent_results["research"] = {"error": str(e)}

            try:
                agent_results["optimizer"] = optimizer_future.result(timeout=60)
            except Exception as e:
                agent_results["optimizer"] = {"error": str(e)}

        # Risk assessment needs results from research/optimizer
        agent_results["risk"] = self.agents["risk"].analyze({
            "proposed_investments": agent_results,
            "user_risk_profile": user_profile.get("risk_tolerance")
        })

        # Tax implications
        tax_context = {
            "proposed_investments": agent_results,
            "income_bracket": user_profile.get("tax_bracket", "30%")
        }
        agent_results["tax"] = self.agents["tax"].analyze(tax_context)

        # Synthesize recommendations
        synthesis = self._synthesize_insights(agent_results, "investment_suggestion")

        return {
            "orchestrator": self.agent_name,
            "workflow": "investment_suggestion",
            "agent_results": agent_results,
            "synthesis": synthesis,
            "timestamp": self.execution_log[-1]["timestamp"] if self.execution_log else None
        }

    
    def _full_advisory(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Complete advisory service - analysis + suggestions, run in parallel."""
        self.log_action("full_advisory_workflow", {})

        # Run portfolio analysis and investment suggestions concurrently —
        # they read the same context but are otherwise fully independent.
        with ThreadPoolExecutor(max_workers=2) as executor:
            analysis_future = executor.submit(self._analyze_portfolio, context)
            suggestion_future = executor.submit(self._suggest_investments, context)

            try:
                analysis_result = analysis_future.result(timeout=120)
            except Exception as e:
                analysis_result = {"error": str(e), "synthesis": f"Analysis failed: {e}"}

            try:
                suggestion_result = suggestion_future.result(timeout=120)
            except Exception as e:
                suggestion_result = {"error": str(e), "synthesis": f"Suggestions failed: {e}"}

        # Final synthesis combining both
        final_synthesis = self._synthesize_full_advisory(
            analysis_result,
            suggestion_result,
            context
        )

        return {
            "orchestrator": self.agent_name,
            "workflow": "full_advisory",
            "portfolio_analysis": analysis_result,
            "investment_suggestions": suggestion_result,
            "final_synthesis": final_synthesis,
            "timestamp": self.execution_log[-1]["timestamp"] if self.execution_log else None
        }

    
    def _synthesize_insights(self, agent_results: Dict[str, Any], context_type: str) -> str:
        """
        Synthesize insights from multiple agents into coherent recommendations.
        This is where the orchestrator's intelligence shines.
        """
        self.log_action("synthesizing_insights", {
            "agents_count": len(agent_results),
            "context": context_type
        })
        
        # Prepare summary of all agent findings
        agent_summaries = "\n\n".join([
            f"**{agent_name.upper()} AGENT:**\n{result.get('analysis', result)}"
            for agent_name, result in agent_results.items()
            if not result.get("error")
        ])
        
        synthesis_prompt = f"""{self.get_system_prompt()}

You are the master orchestrator synthesizing insights from multiple specialized AI agents.

CONTEXT: {context_type}

AGENT INSIGHTS:
{agent_summaries}

Your task:
1. Identify consensus views among agents (where multiple agents agree)
2. Highlight conflicting recommendations and resolve them
3. Weigh each agent's input based on their specialization relevance
4. Generate a unified, coherent recommendation
5. Create a clear action plan with prioritized steps
6. Assign confidence levels to recommendations
7. Identify blind spots or areas needing more data

Format your synthesis:
## 🎯 Executive Summary
[2-3 sentence overview]

## 🤝 Agent Consensus
[Where agents agree]

## ⚠️ Conflicting Views & Resolution
[Where agents disagree and your resolution]

## 📋 Unified Recommendations
[Clear, actionable recommendations]

## 🎬 Action Plan
[Step-by-step what to do next]

## 💡 Key Insights
- [Insight 1]
- [Insight 2]
- [Insight 3]

## ⚡ Confidence Level & Risks
[Overall confidence and major risks]

Be decisive, clear, and actionable. This is the final recommendation the user will see.
"""
        
        synthesis_text = self.generate_response(synthesis_prompt, temperature=0.5)
        
        self.log_action("synthesis_complete", {"success": True})
        
        return synthesis_text
    
    def _synthesize_full_advisory(self, analysis: Dict, suggestions: Dict, context: Dict) -> str:
        """Final synthesis for complete advisory workflow."""
        
        prompt = f"""You are the master orchestrator providing comprehensive financial advisory.

PORTFOLIO ANALYSIS SUMMARY:
{analysis.get('synthesis', 'N/A')}

INVESTMENT SUGGESTIONS SUMMARY:
{suggestions.get('synthesis', 'N/A')}

USER CONTEXT:
- Corpus Available: ₹{context.get('corpus', 0):,}
- Risk Tolerance: {context.get('user_profile', {}).get('risk_tolerance', 'N/A')}
- Goals: {context.get('user_profile', {}).get('goals', 'N/A')}

Create a comprehensive advisory report:

## 📊 Portfolio Health Check
[Overall portfolio assessment]

## 🎯 Strategic Recommendations
[Key strategic moves]

## 💰 Specific Actions
[Exact actions: buy X, sell Y, rebalance Z]

## 📅 Implementation Timeline
[30-day, 90-day, 6-month plan]

## 🚨 Risk Alerts
[Key risks to monitor]

## 📈 Expected Outcomes
[What to expect from following these recommendations]

Make it comprehensive yet easy to understand and implement.
"""
        
        return self.generate_response(prompt, temperature=0.5)
    
    def get_agent_health_status(self) -> Dict[str, Any]:
        """Check health status of all agents."""
        status = {}
        for name, agent in self.agents.items():
            status[name] = {
                "name": agent.agent_name,
                "specialization": agent.specialization,
                "execution_log_size": len(agent.get_execution_log()),
                "status": "healthy"
            }
        return status
    
    def explain_decision(self, decision_context: Dict[str, Any]) -> str:
        """Explain orchestrator's decision-making process (XAI feature)."""
        prompt = f"""Explain the reasoning behind the orchestrator's decision:

Decision Context:
{decision_context}

Provide:
1. Why certain agents were activated
2. How agent outputs were weighed
3. Decision-making logic
4. Alternative approaches considered
5. Confidence in the decision

Make it transparent and educational.
"""
        
        return self.generate_response(prompt, temperature=0.4)
