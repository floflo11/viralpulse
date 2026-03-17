"""Query expansion and core subject extraction."""

import re
from typing import List, Set

NOISE_WORDS = frozenset({
    'best', 'top', 'good', 'great', 'awesome', 'killer',
    'latest', 'new', 'news', 'update', 'updates',
    'trending', 'hottest', 'popular', 'viral',
    'practices', 'features', 'tips',
    'recommendations', 'advice',
    'prompt', 'prompts', 'prompting',
    'methods', 'strategies', 'approaches',
})

PREFIXES = [
    'what are the best', 'what is the best', 'what are the latest',
    'what are people saying about', 'what do people think about',
    'how do i use', 'how to use', 'how to',
    'what are', 'what is', 'tips for', 'best practices for',
]

STOPWORDS = frozenset({
    'the', 'a', 'an', 'to', 'for', 'how', 'is', 'in', 'of', 'on',
    'and', 'with', 'from', 'by', 'at', 'this', 'that', 'it', 'my',
    'your', 'i', 'me', 'we', 'you', 'what', 'are', 'do', 'can',
    'its', 'be', 'or', 'not', 'no', 'so', 'if', 'but', 'about',
    'all', 'just', 'get', 'has', 'have', 'was', 'will',
})

SYNONYMS = {
    'js': {'javascript'}, 'javascript': {'js'},
    'ts': {'typescript'}, 'typescript': {'ts'},
    'ai': {'artificial', 'intelligence'},
    'ml': {'machine', 'learning'},
    'react': {'reactjs'}, 'reactjs': {'react'},
}


def extract_core_subject(topic: str) -> str:
    """Strip meta/research words, keep core product/concept name."""
    text = topic.strip()
    text_lower = text.lower()

    for p in PREFIXES:
        if text_lower.startswith(p + ' '):
            text = text[len(p):].strip()
            break

    words = text.split()
    filtered = [w for w in words if w.lower() not in NOISE_WORDS]
    result = ' '.join(filtered) if filtered else text
    return result.rstrip('?!.')


def tokenize(text: str) -> Set[str]:
    """Lowercase, strip punctuation, remove stopwords, expand synonyms."""
    words = re.sub(r'[^\w\s]', ' ', text.lower()).split()
    tokens = {w for w in words if w not in STOPWORDS and len(w) > 1}
    expanded = set(tokens)
    for t in tokens:
        if t in SYNONYMS:
            expanded.update(SYNONYMS[t])
    return expanded


def expand_queries(topic: str) -> List[str]:
    """Generate search query variants from a topic."""
    core = extract_core_subject(topic)
    queries = [core]

    original = topic.strip().rstrip('?!.')
    if core.lower() != original.lower() and len(original.split()) <= 8:
        queries.append(original)

    queries.append(f"{core} worth it OR thoughts OR review")
    return queries
