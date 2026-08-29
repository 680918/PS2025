import config


def test_config_defaults():

    assert config.DEEPSEEK_BASE_URL == "https://api.deepseek.com/v1"

    assert config.DEEPSEEK_MODEL == "deepseek-v4-flash"

    assert config.LLM_TIMEOUT == 30

    assert config.LLM_TEMPERATURE == 0.7

    assert config.LLM_MAX_RETRIES == 1
