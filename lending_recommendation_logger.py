import re
from typing import Tuple, List, Dict

_REC_PATTERN = re.compile(
    r"\[RECOMMENDATION\](.*?)\[/RECOMMENDATION\]",
    re.DOTALL | re.IGNORECASE,
)

class LendingRecommendationLogger:
    def __init__(self, chat_id: str, merchant_name: str, credit_score: float = None):
        self.chat_id = chat_id
        self.merchant_name = merchant_name
        self.credit_score = credit_score

    def process(self, response_text: str) -> Tuple[str, List[Dict]]:
        recs = self._parse_blocks(response_text)
        clean_text = _REC_PATTERN.sub("", response_text).strip()

        if recs:
            self._save_to_db(recs)

        return clean_text, recs

    def _parse_blocks(self, text: str) -> List[Dict]:
        matches = _REC_PATTERN.findall(text)
        recs = []
        for match in matches:
            rec = {}
            for line in match.split("\n"):
                line = line.strip()
                if ":" in line:
                    key, val = line.split(":", 1)
                    rec[key.strip().upper()] = val.strip()
            if rec:
                recs.append(rec)
        return recs

    def _save_to_db(self, recs: List[Dict]):
        from memory_store import MemoryStore
        mem = MemoryStore()
        for rec in recs:
            mem.save_lending_recommendation(
                self.chat_id, 
                self.merchant_name, 
                rec, 
                self.credit_score
            )
