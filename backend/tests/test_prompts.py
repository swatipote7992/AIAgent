import pytest
from langchain_core.prompts import ChatPromptTemplate

from data.prompts import available_versions, load_system_prompt


@pytest.mark.parametrize("version", available_versions())
def test_every_version_has_only_context_placeholder(version):
    text, loaded = load_system_prompt(version)
    assert loaded == version
    template = ChatPromptTemplate.from_messages([("system", text), ("human", "{question}")])
    assert sorted(template.input_variables) == ["context", "question"]


def test_latest_is_default(monkeypatch):
    monkeypatch.delenv("SYS_PROMPT_VERSION", raising=False)
    assert load_system_prompt()[1] == available_versions()[-1]


def test_env_var_selects_version(monkeypatch):
    monkeypatch.setenv("SYS_PROMPT_VERSION", "v1")
    assert load_system_prompt()[1] == "v1"


def test_unknown_version_fails():
    with pytest.raises(ValueError):
        load_system_prompt("v999")


def test_v3_has_at_least_50_examples_and_no_braces_in_them():
    text = load_system_prompt("v3")[0]
    assert text.count("\nExample ") >= 50
    assert text.count("{") == 1 and text.count("}") == 1  # only the {context} placeholder


def test_v3_has_underwriter_broker_persona():
    assert "underwriter and broker" in load_system_prompt("v3")[0]


def test_v2_has_examples_and_v1_has_none():
    assert "Example 1" in load_system_prompt("v2")[0]
    assert "Example 1" not in load_system_prompt("v1")[0]
