from slm.protocol.schema import AgentStep, ToolCall, VerificationStatus


def test_agent_step_roundtrip():
    step = AgentStep(
        goal="test goal",
        thought="thinking",
        plan=["a", "b"],
        tool=ToolCall(name="read_file", args={"path": "main.py"}),
    )
    data = step.model_dump(mode="json")
    restored = AgentStep.model_validate(data)
    assert restored.goal == "test goal"
    assert restored.tool is not None
    assert restored.tool.name == "read_file"


def test_verification_enum():
    step = AgentStep(goal="x", verification={"status": "pass", "reason": "ok"})
    assert step.verification.status == VerificationStatus.PASS
