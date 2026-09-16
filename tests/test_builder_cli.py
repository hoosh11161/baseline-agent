from __future__ import annotations

import pytest

from arenaagent.builder import _parse_args


def test_get_vlm_model_does_not_require_agent_name() -> None:
    args = _parse_args(["--get_vlm_model"])
    assert args.get_vlm_model is True
    assert args.agent_name is None


def test_normal_run_still_requires_agent_name_in_main_guard() -> None:
    args = _parse_args([])
    assert args.get_vlm_model is False
    assert args.agent_name is None


def test_unknown_arguments_are_rejected() -> None:
    with pytest.raises(SystemExit):
        _parse_args(["--unknown-option"])
