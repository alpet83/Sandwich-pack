
import logging
import re
import math


def estimate_tokens(content):
    """Estimates tokens by counting words and spaces more accurately."""
    if not content:
        return 0
    tokens = 0
    words = re.findall(r'\S+', content)
    for word in words:
        if len(word) >= 5:
            tokens += math.ceil(len(word) / 4)
        else:
            tokens += 1
    spaces = len(re.findall(r'\s+', content))
    tokens += spaces
    logging.debug("Estimated tokens for content (length=%d): %d tokens (words=%d, spaces=%d)",
                  len(content), tokens, len(words), spaces)
    return tokens
