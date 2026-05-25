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
