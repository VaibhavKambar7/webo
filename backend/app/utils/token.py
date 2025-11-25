import tiktoken
from typing import List, Dict
enc = tiktoken.encoding_for_model("gpt-4o")

def count_tokens(conversation: List[Dict[str,str]]) -> int:
    text = ""

    for msg in conversation:
        text += f"{msg['role']}:{msg['content']}\n"
    return len(enc.encode(text))