"""
Base Agent Class for Multi-Agent Portfolio Advisor System
"""
import os
import logging
from google import genai
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all specialized financial agents."""
    
    def __init__(self, agent_name: str, specialization: str, model: str = "gemini-3.6-flash"):
        self.agent_name = agent_name
        self.specialization = specialization
        self.model = model
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")
        self.client = genai.Client(api_key=self.api_key)
        self.execution_log = []
        
    def log_action(self, action: str, details: Dict[str, Any]):
        """Log agent actions for transparency and debugging."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.agent_name,
            "action": action,
            "details": details
        }
        self.execution_log.append(log_entry)
        
    def get_system_prompt(self) -> str:
        """Returns the system prompt defining agent's role and capabilities."""
        return f"""You are {self.agent_name}, a specialized AI agent focused on {self.specialization}.

Your role in the multi-agent portfolio advisory system:
- Provide expert analysis within your domain of expertise
- Be precise, data-driven, and actionable in your recommendations
- Clearly state confidence levels and assumptions
- Highlight risks and limitations in your analysis
- Collaborate with other agents by providing structured, parseable insights

Always format your response in a clear, structured manner with:
1. Executive Summary (2-3 sentences)
2. Detailed Analysis
3. Key Insights (bullet points)
4. Confidence Level (High/Medium/Low)
5. Risks & Limitations
"""
    
    def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main analysis method to be implemented by each specialized agent.
        
        Args:
            context: Dictionary containing relevant data for analysis
            
        Returns:
            Dictionary with analysis results, insights, and metadata
        """
        raise NotImplementedError("Each agent must implement its own analyze method")
    
    def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        """Generate response using Gemini API with retry logic for rate limits."""
        import time
        max_retries = 5
        base_delay = 5
        
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={
                        "temperature": temperature,
                        "top_p": 0.95,
                        "top_k": 40,
                    }
                )
                return response.text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "Quota exceeded" in error_str:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Rate limit hit (429). Retrying in {delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        continue
                
                logger.error(f"Error generating response: {e}")
                return f"Error generating response: {e}"
        
        return "Error: Maximum retries reached due to rate limits."
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """Return the agent's execution log."""
        return self.execution_log
    
    def __repr__(self):
        return f"<{self.agent_name}: {self.specialization}>"
