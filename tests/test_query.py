from viralpulse.query import extract_core_subject, expand_queries, tokenize


def test_extract_strips_noise():
    assert extract_core_subject("what are the best AI video tools") == "AI video tools"
    assert extract_core_subject("tips for prompt engineering") == "engineering"


def test_extract_preserves_core():
    assert extract_core_subject("Claude Code") == "Claude Code"
    assert extract_core_subject("Remotion") == "Remotion"


def test_expand_queries():
    queries = expand_queries("AI video tools")
    assert len(queries) >= 1
    assert "AI video tools" in queries


def test_tokenize_expands_synonyms():
    tokens = tokenize("js framework")
    assert "javascript" in tokens
    assert "js" in tokens


def test_tokenize_removes_stopwords():
    tokens = tokenize("the best way to do it")
    assert "the" not in tokens
    assert "to" not in tokens
