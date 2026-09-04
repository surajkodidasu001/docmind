from app.agent import memory


def test_add_and_retrieve_turns():
    memory.clear_session("test-session")
    memory.add_turn("test-session", "What is DocMind?", "It's a RAG platform.")
    history = memory.get_history("test-session")
    assert len(history) == 1
    assert history[0][0] == "What is DocMind?"


def test_history_respects_max_turns():
    memory.clear_session("test-session-2")
    from app.config import settings
    for i in range(settings.memory_max_turns + 3):
        memory.add_turn("test-session-2", f"q{i}", f"a{i}")
    history = memory.get_history("test-session-2")
    assert len(history) == settings.memory_max_turns
    # oldest turns should have been dropped, most recent kept
    assert history[-1][0] == f"q{settings.memory_max_turns + 2}"


def test_format_history_includes_question_and_answer():
    memory.clear_session("test-session-3")
    memory.add_turn("test-session-3", "hello?", "hi there")
    formatted = memory.format_history("test-session-3")
    assert "hello?" in formatted
    assert "hi there" in formatted


def test_clear_session_empties_history():
    memory.add_turn("test-session-4", "q", "a")
    memory.clear_session("test-session-4")
    assert memory.get_history("test-session-4") == []
