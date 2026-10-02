from app.services.localization import Translator


def test_default_chinese_locale_and_english_switch() -> None:
    translator = Translator()
    assert translator.text("app_name") == "本地 Agent 推理服务器管理器"
    assert translator.text("server.start") == "启动"

    translator.load("en_US")
    assert translator.text("server.start") == "Start"
