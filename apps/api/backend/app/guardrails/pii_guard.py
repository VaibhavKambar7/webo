import re
from dataclasses import dataclass

@dataclass
class PIIMatch:
    type: str
    value: str
    start: int
    end: int

# Risk levels determine action: HIGH = block, MEDIUM = redact
PII_PATTERNS = {
    # HIGH RISK — block the query entirely
    "ssn": {
        "pattern": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        "risk": "high",
    },
    "credit_card": {
        "pattern": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
        "risk": "high",
    },
    "api_key": {
        "pattern": re.compile(r'(?:sk-|pk_live_|pk_test_|AKIA|AIza)[A-Za-z0-9_-]{10,}'),
        "risk": "high",
    },

    # MEDIUM RISK — redact and continue
    "email": {
        "pattern": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        "risk": "medium",
    },
    "phone": {
        "pattern": re.compile(r'\b(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
        "risk": "medium",
    },
}

def scan_pii(text: str) -> list[PIIMatch]:
    """Scan text for PII. Returns list of matches."""
    matches = []
    for pii_type, config in PII_PATTERNS.items():
        for match in config["pattern"].finditer(text):
            matches.append(PIIMatch(
                type=pii_type,
                value=match.group(),
                start=match.start(),
                end=match.end(),
            ))
    return matches

def has_high_risk_pii(text: str) -> tuple[bool, list[str]]:
    """Check if text contains SSN, credit card, or API key."""
    matches = scan_pii(text)
    high_risk = [m for m in matches if PII_PATTERNS[m.type]["risk"] == "high"]
    types = list(set(m.type for m in high_risk))
    return len(high_risk) > 0, types

def redact_medium_pii(text: str) -> str:
    """Replace email/phone with placeholders."""
    for pii_type, config in PII_PATTERNS.items():
        if config["risk"] == "medium":
            text = config["pattern"].sub(f"[{pii_type.upper()}_REDACTED]", text)
    return text
