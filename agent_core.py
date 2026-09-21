"""
agent_core.py — Agentic loop for the Portfolio Advisor.

Uses Gemini's function-calling API in a ReAct loop:
  Reason → call tool(s) → observe results → repeat → final answer
"""
import os
import json
import logging
from typing import Generator
from google import genai
from google.genai import types
from tools import TOOL_DECLARATIONS, TOOL_FUNCTIONS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert AI financial advisor specializing in the Indian stock market (NSE/BSE).

You have access to real-time tools to fetch stock prices, company info, news, and financial ratios.
Use them proactively — don't assume you know current prices or recent events from memory.

Guidelines:
- Always fetch live data before making any price-based statements
- When comparing stocks, use the compare_stocks tool for efficiency
- Clearly flag risks alongside any recommendation
- End every response with a standard disclaimer:
  "⚠️ This is AI-generated analysis for educational purposes only — not professional financial advice."
- Be concise and structured. Use bullet points and markdown headings.
"""


class AdvisorAgent:
    """
    Agentic advisor with a persistent chat session and tool-use loop.
    """

    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set.")
        self.client = genai.Client(api_key=api_key)
        self.chat = None
        self.config = {}

    def initialize(self, tickers: list[str], corpus: float, preferences: str):
        """
        Start a new chat session pre-loaded with the user's portfolio config.
        Returns the agent's opening analysis as a streamed generator.
        """
        self.config = {
            "tickers": tickers,
            "corpus": corpus,
            "preferences": preferences,
        }

        tickers_str = ", ".join(tickers) if tickers else "None"
        opening_message = (
            f"The user's portfolio configuration:\n"
            f"- Current holdings: {tickers_str}\n"
            f"- Available investment corpus: ₹{corpus:,.2f}\n"
            f"- Risk appetite & preferences: {preferences}\n\n"
            f"Please greet the user warmly, briefly acknowledge their config, "
            f"then immediately fetch live data for their holdings and give them "
            f"a concise portfolio snapshot to kick off the conversation."
        )

        self.chat = self.client.chats.create(
            model="gemini-2.0-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[TOOL_DECLARATIONS],
                temperature=0.7,
            ),
        )

        return self._run_loop(opening_message)

    def chat_turn(self, user_message: str) -> Generator[str, None, None]:
        """
        Send a user message and run the agentic loop, yielding status updates
        and finally the model's text response.
        """
        if self.chat is None:
            yield "⚠️ Please configure your portfolio first."
            return
        yield from self._run_loop(user_message)

    def _run_loop(self, message: str) -> Generator[str, None, None]:
        """
        Core ReAct loop:
          1. Send message to model
          2. If model returns tool calls → execute them, feed results back
          3. Repeat until model returns a final text response
          4. Yield tool-call status lines + final text
        """
        current_message = message

        while True:
            response = self.chat.send_message(current_message)
            candidate = response.candidates[0]
            parts = candidate.content.parts

            # Check if any part is a function call
            function_calls = [p for p in parts if p.function_call]

            if not function_calls:
                # Final text response — yield it
                text = "".join(p.text for p in parts if p.text)
                yield ("TEXT", text)
                return

            # Execute each tool call and collect results
            tool_results = []
            for part in function_calls:
                fc = part.function_call
                fn_name = fc.name
                fn_args = dict(fc.args)

                yield ("TOOL", fn_name, fn_args)

                if fn_name in TOOL_FUNCTIONS:
                    try:
                        result = TOOL_FUNCTIONS[fn_name](**fn_args)
                    except Exception as e:
                        result = {"error": str(e)}
                else:
                    result = {"error": f"Unknown tool: {fn_name}"}

                tool_results.append(
                    types.Part.from_function_response(
                        name=fn_name,
                        response=result,
                    )
                )

            # Feed tool results back as the next message
            current_message = tool_results
