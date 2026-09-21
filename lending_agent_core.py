import os
import json
import logging
from typing import Generator, Optional
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

BASE_SYSTEM_PROMPT = """You are a Senior B2B Credit & Risk Analyst AI.
You assist loan officers in evaluating merchant onboarding and business credit applications.

You have been provided with the merchant's initial application data and the automated multi-agent underwriting report.
Your job is to:
1. Discuss the merchant's risk profile with the loan officer.
2. Answer questions about the provided data.
3. Help the officer structure the loan or finalize the onboarding decision.

When you and the loan officer reach a final decision, you MUST emit a structured recommendation block so the system can log and track the loan's performance.

[RECOMMENDATION]
ACTION: <APPROVE | REJECT | CONDITIONAL>
AMOUNT: <amount in rupees, e.g. 5000000>
RATE: <interest rate, e.g. 12.5>
RATIONALE: <1-3 sentences explaining the decision>
RISK: <key risks>
[/RECOMMENDATION]

Rules for the block:
- Emit the block ONLY when a final decision is reached.
- The block will be extracted automatically; do not explain the block formatting to the user.
"""

class LendingAgent:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set.")
        self.client = genai.Client(api_key=api_key)
        self.chat = None

    def initialize(
        self,
        merchant_name: str,
        form_data: dict,
        orchestrator_results: dict,
        chat_id: str,
        track_record_text: Optional[str] = None
    ) -> Generator:
        
        parts = [BASE_SYSTEM_PROMPT]
        
        if track_record_text:
            parts.append(
                f"\n\n## Your Track Record (Lending & Underwriting)\n"
                f"Review your historical performance before making new credit decisions:\n"
                f"{track_record_text}\n"
                f"Use this self-analysis to calibrate your risk appetite."
            )
            
        parts.append(
            f"\n\n## Current Application Context\n"
            f"Merchant Name: {merchant_name}\n"
            f"Form Data: {json.dumps(form_data, default=str)}\n"
            f"Automated Underwriting Results: {json.dumps(orchestrator_results, default=str)}\n"
        )
        
        system_prompt = "\n".join(parts)
        
        self.chat = self.client.chats.create(
            model="gemini-3.6-flash",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.4,
            ),
        )
        
        opening = (
            f"Review the automated underwriting report for {merchant_name}. "
            f"Provide a 2-3 sentence executive summary of their creditworthiness and "
            f"ask the loan officer what aspects they'd like to dive into before finalizing the decision."
        )
        
        yield from self._run_loop(opening)

    def chat_turn(self, user_message: str) -> Generator:
        if self.chat is None:
            yield ("TEXT", "Agent not initialized.")
            return
        yield from self._run_loop(user_message)

    def _run_loop(self, message: str) -> Generator:
        try:
            response = self.chat.send_message(message)
            yield ("TEXT", response.text)
        except Exception as e:
            logger.error(f"Lending agent error: {e}")
            yield ("TEXT", f"⚠️ Error: {e}")
