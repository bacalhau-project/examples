import os

from dotenv import load_dotenv

# Constants with default values
CONTINUATION_EXIT_PHRASE = "AUTOMODE_COMPLETE"
MAX_CONTINUATION_ITERATIONS = 25
MAX_TOKENS = 10000
DB_FILE = "conversation_state.db"

# Models with default values
MAINMODEL = "claude-3-5-sonnet-20240620"
TOOLCHECKERMODEL = "claude-3-5-sonnet-20240620"

# API Keys
ANTHROPIC_API_KEY = None
TAVILY_API_KEY = None


def load_env():
    global CONTINUATION_EXIT_PHRASE, MAX_CONTINUATION_ITERATIONS, MAX_TOKENS, DB_FILE
    global MAINMODEL, TOOLCHECKERMODEL
    global ANTHROPIC_API_KEY, TAVILY_API_KEY

    # Load environment variables from .env file
    load_dotenv()

    # Check if we're in testing mode
    TESTING = os.getenv("TESTING", "false").lower() == "true"

    # Override constants if set in environment
    CONTINUATION_EXIT_PHRASE = os.getenv(
        "CONTINUATION_EXIT_PHRASE", CONTINUATION_EXIT_PHRASE
    )
    MAX_CONTINUATION_ITERATIONS = int(
        os.getenv("MAX_CONTINUATION_ITERATIONS", str(MAX_CONTINUATION_ITERATIONS))
    )
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", str(MAX_TOKENS)))
    DB_FILE = os.getenv("DB_FILE", DB_FILE)

    MAINMODEL = os.getenv("MAINMODEL", MAINMODEL)
    TOOLCHECKERMODEL = os.getenv("TOOLCHECKERMODEL", TOOLCHECKERMODEL)

    # API Keys
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

    # Validate that API keys are set
    if not TESTING:
        if not ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set in the environment variables"
            )
        if not TAVILY_API_KEY:
            raise ValueError("TAVILY_API_KEY is not set in the environment variables")
    else:
        # Use default values for testing if not set
        ANTHROPIC_API_KEY = ANTHROPIC_API_KEY or "test_anthropic_key"
        TAVILY_API_KEY = TAVILY_API_KEY or "test_tavily_key"


# Load environment variables when the module is imported
load_env()
