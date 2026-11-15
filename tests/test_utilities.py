"""Tests for src/utilities.py: turning app objects into plain JSON-friendly data."""
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from utilities import EnumJSONEncoder, serialize_config


class Colour(Enum):
    RED = "red"


@dataclass
class Box:
    name: str
    colour: Colour


class HasToDict:
    def to_dict(self):
        return {"kind": "custom"}


def encode(value):
    return json.loads(json.dumps(value, cls=EnumJSONEncoder))


def test_enum_is_written_as_its_value():
    assert encode({"c": Colour.RED}) == {"c": "red"}


def test_datetime_and_path_are_written_as_text():
    moment = datetime(2024, 1, 2, 3, 4, 5)
    assert encode([moment, Path("a/b")]) == [str(moment), str(Path("a/b"))]


def test_object_with_to_dict_uses_it():
    assert encode(HasToDict()) == {"kind": "custom"}


def test_plain_object_uses_its_attributes():
    assert encode(Box(name="x", colour=Colour.RED)) == {"name": "x", "colour": "red"}


def test_object_without_attributes_falls_back_to_text():
    # object() has no __dict__, so the encoder falls back to str().
    value = object()
    assert encode(value) == str(value)


def test_serialize_config_returns_plain_dict():
    result = serialize_config(Box(name="x", colour=Colour.RED))
    assert result == {"colour": "red", "name": "x"}


def test_serialize_config_falls_back_to_text_when_it_cannot_serialize():
    # A dict with a non-text key can't be written as JSON with sort_keys
    # alongside text keys, so the function returns str(config) instead.
    bad = {1: "a", "b": 2}
    assert serialize_config(bad) == str(bad)
