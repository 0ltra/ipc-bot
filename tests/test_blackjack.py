import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cogs.blackjack import hand_value


def test_hand_value_simple():
    assert hand_value(["5♠", "6♥"]) == 11


def test_hand_value_face_cards():
    assert hand_value(["K♠", "Q♥"]) == 20


def test_hand_value_ace_high():
    assert hand_value(["A♠", "9♥"]) == 20


def test_hand_value_ace_low_when_busting():
    assert hand_value(["A♠", "A♥", "9♦"]) == 21


def test_hand_value_bust():
    assert hand_value(["K♠", "Q♥", "5♦"]) == 25
