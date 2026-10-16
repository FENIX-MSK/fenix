from fenix.platform.config import Settings
from fenix.telegram.handlers.start import build_start_keyboard


def test_start_keyboard_hidden_without_webapp_url() -> None:
    assert build_start_keyboard(Settings(webapp_url=None)) is None


def test_start_keyboard_opens_webapp() -> None:
    keyboard = build_start_keyboard(Settings(webapp_url="https://example.test"))
    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.web_app is not None
    assert button.web_app.url == "https://example.test"
