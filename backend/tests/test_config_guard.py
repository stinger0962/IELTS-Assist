import pytest

from app.config import INSECURE_SECRET_KEY, assert_secret_key_is_safe


def test_rejects_the_placeholder_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        assert_secret_key_is_safe(INSECURE_SECRET_KEY)


def test_rejects_an_empty_key():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        assert_secret_key_is_safe("")


def test_accepts_a_real_key():
    assert assert_secret_key_is_safe("Zq3n_KpX8sVb2LmT9wYc1RfJ4hGd7aNe0oUiPtSxQvB") is None
