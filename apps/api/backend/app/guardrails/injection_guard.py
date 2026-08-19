import re
from typing import Optional

# ──────────────────────────────────────────────────────
#  NARROW PATTERNS — stuff no real user would ever say.
#  These target the SYSTEM PROMPT, not general conversation.
# ──────────────────────────────────────────────────────
INJECTION_PATTERNS = [
    # --- System prompt extraction ---
    r"(reveal|show|output|print|repeat|display)\s+(your|the)\s+(full\s+)?(system\s+)?(prompt|instructions)",
    r"what\s+(is|are)\s+your\s+(system\s+)?(prompt|instructions|rules)\s*\??",

    # --- Instruction override (targeting SYSTEM, not conversation) ---
    r"ignore\s+(all\s+)?(previous|prior|system|above)\s+(instructions|rules|prompts)",
    r"disregard\s+(all\s+)?(your|the|system)\s+(instructions|rules|prompts|guidelines)",
    r"override\s+(all\s+)?(your|the|system)\s+(instructions|rules|settings)",
    r"forget\s+(all\s+)?(your|the|system)\s+(instructions|rules|training|programming)",

    # --- Role hijacking (very specific) ---
    r"you\s+are\s+now\s+(DAN|evil|unrestricted|jailbroken|unfiltered)",
    r"(enter|switch\s+to|activate)\s+(DAN|jailbreak|developer|god)\s*(mode)?",
    r"from\s+now\s+on[,\s]+(you\s+)?(are|will\s+be|must\s+act\s+as)\s+",

    # --- LLM format injection (zero ambiguity) ---
    r"\[INST\]",
    r"\[/INST\]",
    r"<<SYS>>",
    r"<</SYS>>",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"###\s*System\s*:",    # Role marker injection

    # --- Webo-specific: schema/confidence manipulation ---
    r"(always\s+)?(set|return|use)\s+(confidence|score)\s+(to|=|at)\s+\d",
    r"always\s+(use|call|return)\s+tool\s",
    r"always\s+(use|call|return)\s+(final_answer|web_search)\s",
]

_compiled = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def detect_injection(text: str) -> tuple[bool, Optional[str]]:
    """
    Narrow regex-based injection detection.
    Returns (is_blocked, matched_pattern).
    
    Designed for minimal false positives.
    """
    for pattern in _compiled:
        match = pattern.search(text)
        if match:
            return True, match.group()
    return False, None
