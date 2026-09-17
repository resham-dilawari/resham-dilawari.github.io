"""
Base Agent for Merchant Underwriting System
Similar to stock advisor but focused on B2B risk assessment
"""
from typing import Dict, Any, List
from google import genai
import os
from datetime import datetime


class UnderwritingBaseAgent:
    """
    Base class for all merchant underwriting agents.
    Provides common functionality like LLM interaction and logging.
    """
    
    def __init__(self, agent_name: str, specialization: str):
        self.agent_name = agent_name
        self.specialization = specialization
        self.execution_log = []
        
        # Initialize Gemini API
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        self.client = genai.Client(api_key=api_key)
    
    def get_system_prompt(self) -> str:
        """Get the system prompt that defines this agent's role."""
        return f"""You are {self.agent_name}, a specialized AI agent for merchant underwriting and risk assessment.

Your expertise: {self.specialization}

Key responsibilities:
1. Analyze merchant/business data for risk factors
2. Identify red flags (fraud, AML, bankruptcy, lawsuits)
3. Provide objective, fact-based assessments
4. ALWAYS cite sources with URLs
5. Say "No data found" rather than guessing
6. Focus on regulatory compliance and risk mitigation

Output format:
- Clear, structured analysis
- Bullet points for key findings
- Red flag warnings prominently highlighted
- Source citations for every claim
- Risk scoring when applicable

Remember: You are an internal tool for risk analysts. Accuracy and auditability are critical.
"""
    
    def generate_response(self, prompt: str, temperature: float = 0.3) -> str:
        """
        Generate a response using the LLM with retry logic.
        Lower temperature for factual accuracy in risk assessment.
        """
        import time
        max_retries = 5
        base_delay = 5
        
        full_prompt = f"{self.get_system_prompt()}\n\n{prompt}"
        
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=full_prompt,
                    config={
                        'temperature': temperature,
                        'max_output_tokens': 2048,
                    }
                )
                return response.text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "Quota exceeded" in error_str:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        print(f"Rate limit hit. Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        continue
                return f"Error generating response: {error_str}"
                
        return "Error: Maximum retries reached due to rate limits."
    
    def log_action(self, action: str, details: Dict[str, Any]):
        """Log an action for transparency and audit trail."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.agent_name,
            "action": action,
            "details": details
        }
        self.execution_log.append(log_entry)
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """Retrieve execution log for audit purposes."""
        return self.execution_log
    
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main analysis method - to be implemented by each specialized agent.
        Must return a dict with at least 'analysis' and 'risk_level' keys.
        """
        raise NotImplementedError("Subclasses must implement the analyze method")
