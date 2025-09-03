from bot import respond, Bot


def test_respond():
    assert respond("Denis") == "Hello, Denis!"


def test_conversation_flow():
    bot = Bot()
    assert bot.respond("My name is Denis") == "Nice to meet you, Denis!"
    assert bot.respond("hi") == "Hello, Denis!"
    assert bot.respond("something else") == "Denis, you said: something else"
