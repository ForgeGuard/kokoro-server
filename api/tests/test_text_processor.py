import pytest

from api.src.services.text_processing.text_processor import (
    get_sentence_info,
    process_text_chunk,
    smart_split,
)


def test_process_text_chunk_basic():
    """Test basic text chunk processing."""
    text = "Hello world"
    tokens = process_text_chunk(text)
    assert isinstance(tokens, list)
    assert len(tokens) > 0


def test_process_text_chunk_empty():
    """Test processing empty text."""
    text = ""
    tokens = process_text_chunk(text)
    assert isinstance(tokens, list)
    assert len(tokens) == 0


def test_process_text_chunk_phonemes():
    """Test processing with skip_phonemize."""
    phonemes = "h @ l @U"  # Example phoneme sequence
    tokens = process_text_chunk(phonemes, skip_phonemize=True)
    assert isinstance(tokens, list)
    assert len(tokens) > 0


def test_get_sentence_info():
    """Test sentence splitting and info extraction."""
    text = "This is sentence one. This is sentence two! What about three?"
    results = get_sentence_info(text)

    assert len(results) == 3
    for sentence, tokens, count in results:
        assert isinstance(sentence, str)
        assert isinstance(tokens, list)
        assert isinstance(count, int)
        assert count == len(tokens)
        assert count > 0


@pytest.mark.asyncio
async def test_smart_split_short_text():
    """Test smart splitting with text under max tokens."""
    text = "This is a short test sentence."
    chunks = []
    async for chunk_text, chunk_tokens, _ in smart_split(text):
        chunks.append((chunk_text, chunk_tokens))

    assert len(chunks) == 1
    assert isinstance(chunks[0][0], str)
    assert isinstance(chunks[0][1], list)


@pytest.mark.asyncio
async def test_smart_custom_phenomes():
    """Test smart splitting with text under max tokens."""
    text = "This is a short test sentence. [Kokoro](/kˈOkəɹO/) has a feature called custom phenomes. This is made possible by [Misaki](/misˈɑki/), the custom phenomizer that [Kokoro](/kˈOkəɹO/) version 1.0 uses"
    chunks = []
    async for chunk_text, chunk_tokens, pause_duration in smart_split(text):
        chunks.append((chunk_text, chunk_tokens, pause_duration))

    # Should have 1 chunks: text
    assert len(chunks) == 1

    # First chunk: text
    assert chunks[0][2] is None  # No pause
    assert (
        "This is a short test sentence. [Kokoro](/kˈOkəɹO/) has a feature called custom phenomes. This is made possible by [Misaki](/misˈɑki/), the custom phenomizer that [Kokoro](/kˈOkəɹO/) version one uses"
        in chunks[0][0]
    )
    # smart_split no longer yields token lists (only KokoroV1 backend remains,
    # which re-phonemizes chunk text itself)
    assert chunks[0][1] == []


@pytest.mark.asyncio
async def test_smart_split_only_phenomes():
    """Test input that is entirely made of phenome annotations."""
    text = "[Kokoro](/kˈOkəɹO/) [Misaki 1.2](/misˈɑki/) [Test](/tɛst/)"
    chunks = []
    async for chunk_text, chunk_tokens, pause_duration in smart_split(
        text, max_tokens=10
    ):
        chunks.append((chunk_text, chunk_tokens, pause_duration))

    assert len(chunks) == 1
    assert "[Kokoro](/kˈOkəɹO/) [Misaki 1.2](/misˈɑki/) [Test](/tɛst/)" in chunks[0][0]


@pytest.mark.asyncio
async def test_smart_split_long_text():
    """Test smart splitting with longer text."""
    # Create text that should split into multiple chunks
    text = ". ".join(["This is test sentence number " + str(i) for i in range(20)])

    chunks = []
    async for chunk_text, chunk_tokens, _ in smart_split(text):
        chunks.append((chunk_text, chunk_tokens))

    assert len(chunks) > 1
    for chunk_text, chunk_tokens in chunks:
        assert isinstance(chunk_text, str)
        assert isinstance(chunk_tokens, list)


@pytest.mark.asyncio
async def test_smart_split_with_punctuation():
    """Test smart splitting handles punctuation correctly."""
    text = "First sentence! Second sentence? Third sentence; Fourth sentence: Fifth sentence."

    chunks = []
    async for chunk_text, chunk_tokens, _ in smart_split(text):
        chunks.append(chunk_text)

    # Verify punctuation is preserved
    assert all(any(p in chunk for p in "!?;:.") for chunk in chunks)


def test_process_text_chunk_chinese_phonemes():
    """Test processing with Chinese pinyin phonemes."""
    pinyin = "nǐ hǎo lì"  # Example pinyin sequence with tones
    tokens = process_text_chunk(pinyin, skip_phonemize=True, language="z")
    assert isinstance(tokens, list)
    assert len(tokens) > 0


def test_get_sentence_info_chinese():
    """Test Chinese sentence splitting and info extraction."""
    text = "这是一个句子。这是第二个句子！第三个问题？"
    results = get_sentence_info(text, lang_code="z")

    assert len(results) == 3
    for sentence, tokens, count in results:
        assert isinstance(sentence, str)
        assert isinstance(tokens, list)
        assert isinstance(count, int)
        assert count == len(tokens)
        assert count > 0


@pytest.mark.asyncio
async def test_smart_split_chinese_short():
    """Test Chinese smart splitting with short text."""
    text = "这是一句话。"
    chunks = []
    async for chunk_text, chunk_tokens, _ in smart_split(text, lang_code="z"):
        chunks.append((chunk_text, chunk_tokens))

    assert len(chunks) == 1
    assert isinstance(chunks[0][0], str)
    assert isinstance(chunks[0][1], list)


@pytest.mark.asyncio
async def test_smart_split_chinese_long():
    """Test Chinese smart splitting with longer text."""
    text = "。".join([f"测试句子 {i}" for i in range(20)])

    chunks = []
    async for chunk_text, chunk_tokens, _ in smart_split(text, lang_code="z"):
        chunks.append((chunk_text, chunk_tokens))

    assert len(chunks) > 1
    for chunk_text, chunk_tokens in chunks:
        assert isinstance(chunk_text, str)
        assert isinstance(chunk_tokens, list)


@pytest.mark.asyncio
async def test_smart_split_chinese_punctuation():
    """Test Chinese smart splitting with punctuation preservation."""
    text = "第一句！第二问？第三句；第四句：第五句。"

    chunks = []
    async for chunk_text, _, _ in smart_split(text, lang_code="z"):
        chunks.append(chunk_text)

    # Verify Chinese punctuation is preserved
    assert all(any(p in chunk for p in "！？；：。") for chunk in chunks)


@pytest.mark.asyncio
async def test_smart_split_with_pause():
    """Test smart splitting with pause tags."""
    text = "Hello world [pause:2.5s] How are you?"

    chunks = []
    async for chunk_text, chunk_tokens, pause_duration in smart_split(text):
        chunks.append((chunk_text, chunk_tokens, pause_duration))

    # Should have 3 chunks: text, pause, text
    assert len(chunks) == 3

    # First chunk: text
    assert chunks[0][2] is None  # No pause
    assert "Hello world" in chunks[0][0]
    assert isinstance(chunks[0][1], list)

    # Second chunk: pause
    assert chunks[1][2] == 2.5  # 2.5 second pause
    assert chunks[1][0] == ""  # Empty text
    assert len(chunks[1][1]) == 0  # No tokens

    # Third chunk: text
    assert chunks[2][2] is None  # No pause
    assert "How are you?" in chunks[2][0]
    assert isinstance(chunks[2][1], list)


@pytest.mark.asyncio
async def test_smart_split_with_two_pause():
    """Test smart splitting with two pause tags."""
    text = "[pause:0.5s][pause:1.67s]0.5"

    chunks = []
    async for chunk_text, chunk_tokens, pause_duration in smart_split(text):
        chunks.append((chunk_text, chunk_tokens, pause_duration))

    # Should have 3 chunks: pause, pause, text
    assert len(chunks) == 3

    # First chunk: pause
    assert chunks[0][2] == 0.5  # 0.5 second pause
    assert chunks[0][0] == ""  # Empty text
    assert len(chunks[0][1]) == 0

    # Second chunk: pause
    assert chunks[1][2] == 1.67  # 1.67 second pause
    assert chunks[1][0] == ""  # Empty text
    assert len(chunks[1][1]) == 0  # No tokens

    # Third chunk: text
    assert chunks[2][2] is None  # No pause
    assert "zero point five" in chunks[2][0]
    assert isinstance(chunks[2][1], list)


def test_get_sentence_info_passes_language_to_token_counter(monkeypatch):
    """get_sentence_info must count tokens with the requested language (K13).

    Without passing the language through, Chinese text is phonemized with the
    default US English backend, producing bogus token counts for chunking.
    """
    import api.src.services.text_processing.text_processor as tp

    captured_languages = []

    def fake_process_text_chunk(text, language="a", skip_phonemize=False):
        captured_languages.append(language)
        return [1] * len(text)

    monkeypatch.setattr(tp, "process_text_chunk", fake_process_text_chunk)

    results = tp.get_sentence_info("这是一个句子。这是第二个句子！", lang_code="z")

    assert len(results) == 2
    assert captured_languages  # token counting happened
    assert all(language == "z" for language in captured_languages)


def test_get_phonemizer_language_mapping():
    """Pipeline lang codes map onto phonemizer-supported codes."""
    from api.src.services.text_processing.text_processor import (
        get_phonemizer_language,
    )

    assert get_phonemizer_language("a") == "a"
    assert get_phonemizer_language("en-us") == "a"
    assert get_phonemizer_language("b") == "b"
    assert get_phonemizer_language("en-gb") == "b"
    assert get_phonemizer_language("z") == "z"
    # Unsupported languages fall back to US English (previous behavior)
    assert get_phonemizer_language("j") == "a"


@pytest.mark.asyncio
async def test_smart_split_clause_path_passes_language(monkeypatch):
    """The over-max-tokens clause splitting path must also count tokens with
    the requested language (K13)."""
    import api.src.services.text_processing.text_processor as tp

    captured_languages = []

    def fake_process_text_chunk(text, language="a", skip_phonemize=False):
        captured_languages.append(language)
        return [1] * len(text)

    monkeypatch.setattr(tp, "process_text_chunk", fake_process_text_chunk)

    # Single long sentence (> max_tokens with the fake counter) forces the
    # clause splitting branch inside smart_split.
    text = "这是第一部分这是第二部分这是第三部分。"
    chunks = []
    async for chunk_text, _, _ in tp.smart_split(text, max_tokens=10, lang_code="z"):
        chunks.append(chunk_text)

    assert chunks
    assert captured_languages
    assert all(language == "z" for language in captured_languages)
