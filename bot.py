from app import greet


def respond(message: str) -> str:
    """Return a greeting for the provided message."""
    return greet(message)


class Bot:
    """Stateful bot that remembers the user's name."""

    def __init__(self) -> None:
        self.name: str | None = None

    def respond(self, message: str) -> str:
        """Generate a response based on user input and state."""
        text = message.strip()
        lowered = text.lower()

        if self.name is None:
            if lowered.startswith("my name is "):
                self.name = text[11:].strip()
                return f"Nice to meet you, {self.name}!"
            return "What's your name? You can say 'My name is ...'"
        else:
            if lowered in {"hi", "hello"}:
                return greet(self.name)
            elif lowered == "help":
                return "I know how to greet you. Try saying 'hi'."
            else:
                return f"{self.name}, you said: {text}"


def run_bot() -> None:
    """Simple command-line bot that greets the user."""
    bot = Bot()
    print("Bot: Hello! Type 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() in {"exit", "quit"}:
            print("Bot: Goodbye!")
            break
        print("Bot:", bot.respond(user_input))


if __name__ == "__main__":
    run_bot()
