"""Settings must tolerate process-level variables in .env.

Regression cover for a deploy failure: .env doubles as systemd's EnvironmentFile,
so it carries variables the Settings model does not declare (PYTHONUNBUFFERED).
pydantic rejected them with extra_forbidden and the app could not import at all.
"""

from app.config import Settings


def test_ignores_variables_the_model_does_not_declare(tmp_path):
    """Constructing must not raise — that is what broke the deploy."""
    env = tmp_path / ".env"
    env.write_text("PYTHONUNBUFFERED=1\nSOME_FUTURE_PROCESS_VAR=whatever\n")

    settings = Settings(_env_file=str(env))

    # Undeclared keys are dropped rather than rejected.
    assert not hasattr(settings, "PYTHONUNBUFFERED")
    assert not hasattr(settings, "SOME_FUTURE_PROCESS_VAR")


def test_still_reads_the_variables_it_does_declare(tmp_path, monkeypatch):
    # Real environment variables outrank .env, and CI exports several of these.
    # Clear them so this actually exercises the file rather than the environment.
    for name in ("AZURE_SPEECH_REGION", "GOOGLE_APPLICATION_CREDENTIALS"):
        monkeypatch.delenv(name, raising=False)

    env = tmp_path / ".env"
    env.write_text(
        "SECRET_KEY=k\n"
        "PYTHONUNBUFFERED=1\n"
        "GOOGLE_APPLICATION_CREDENTIALS=/root/ielts-tts-key.json\n"
        "AZURE_SPEECH_REGION=southeastasia\n"
    )

    settings = Settings(_env_file=str(env))

    assert settings.GOOGLE_APPLICATION_CREDENTIALS == "/root/ielts-tts-key.json"
    assert settings.AZURE_SPEECH_REGION == "southeastasia"
