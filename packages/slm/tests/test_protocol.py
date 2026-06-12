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


def test_coerces_dict_plan_items_and_infers_tool():
    step = AgentStep.model_validate(
        {
            "goal": "read main.py",
            "thought": "read file",
            "plan": [{"action": "read_file", "path": "packages/slm/src/slm/cli/main.py"}],
        }
    )
    assert step.plan == ["read_file(path='packages/slm/src/slm/cli/main.py')"]
    assert step.tool is not None
    assert step.tool.name == "read_file"
    assert step.tool.args == {"path": "packages/slm/src/slm/cli/main.py"}


def test_coerces_dict_plan_without_overriding_explicit_tool():
    step = AgentStep.model_validate(
        {
            "goal": "g",
            "plan": [{"action": "read_file", "path": "a.py"}],
            "tool": {"name": "list_dir", "args": {"path": "."}},
        }
    )
    assert step.tool is not None
    assert step.tool.name == "list_dir"
