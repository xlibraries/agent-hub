import pytest
from slm.output.parser import StructuredOutputError, parse_structured
from slm.protocol.schema import AgentStep


def test_parse_fenced_json():
    text = """Here is the plan:
```json
{"goal": "g", "thought": "t", "plan": ["1"]}
```
"""
    step = parse_structured(text, AgentStep)
    assert step.goal == "g"
    assert step.plan == ["1"]


def test_parse_invalid_raises():
    with pytest.raises(StructuredOutputError):
        parse_structured("not json at all", AgentStep)


def test_parse_coerces_null_plan_and_metrics():
    text = """{
      "goal": "g",
      "thought": "t",
      "output": "Agent Hub SLM stack.",
      "plan": null,
      "metrics": null
    }"""
    step = parse_structured(text, AgentStep)
    assert step.plan == []
    assert step.output == "Agent Hub SLM stack."
    assert step.metrics.tokens == 0


def test_parse_strips_unknown_fields():
    text = """{"goal": "g", "thought": "t", "output": "hello", "plan": [], "extra": true}"""
    step = parse_structured(text, AgentStep)
    assert step.output == "hello"
    assert step.goal == "g"
