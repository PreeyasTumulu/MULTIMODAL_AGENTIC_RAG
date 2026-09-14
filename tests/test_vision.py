"""Figure triage without a model: a blank image must never reach one (ADR-010)."""

from pathlib import Path
from typing import cast

import pymupdf
import pytest

from analyst.llm import LLM
from analyst.vision import BLANK, describe, is_blank

WHITE, BLACK = (255, 255, 255), (0, 0, 0)


def image(tmp_path: Path, colour: tuple[int, int, int], square: bool = False) -> Path:
    """A 40x40 image of one colour, optionally with a black square drawn on it."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
    pix.set_rect(pix.irect, colour)
    if square:
        pix.set_rect(pymupdf.IRect(10, 10, 30, 30), BLACK)
    path = tmp_path / f"{sum(colour)}-{square}.png"
    pix.save(str(path))
    return path


@pytest.mark.parametrize("colour", [WHITE, BLACK])  # a white box, a black mask
def test_one_flat_colour_is_blank(tmp_path: Path, colour: tuple[int, int, int]) -> None:
    assert is_blank(image(tmp_path, colour))


def test_anything_drawn_is_not_blank(tmp_path: Path) -> None:
    assert not is_blank(image(tmp_path, WHITE, square=True))


def test_a_blank_image_is_never_shown_to_the_model(tmp_path: Path) -> None:
    """Regression: gemma3:4b described 8 of 12 blank images as revenue charts, numbers invented."""
    no_model = cast(LLM, object())  # any call to it raises
    assert describe(no_model, image(tmp_path, WHITE)) == (BLANK, "")
