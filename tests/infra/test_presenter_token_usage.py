from src.infra.writer.present import create_presenter


def test_present_token_usage_includes_model_identifiers() -> None:
    presenter = create_presenter(session_id="session-1", agent_id="search", agent_name="Search")

    event = presenter.present_token_usage(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        duration=1.2,
        model_id="b715de30-38",
        model="openai/gpt-4.1",
    )

    assert event["event"] == "token:usage"
    assert event["data"]["model_id"] == "b715de30-38"
    assert event["data"]["model"] == "openai/gpt-4.1"
