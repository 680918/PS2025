import pytest
from argon2 import Type, extract_parameters

from security.passwords import hash_password, verify_password


@pytest.fixture(scope="module")
def stored_hash():
    return hash_password("a quiet place to learn")


def test_password_hash_uses_argon2id_and_unique_random_salts(stored_hash):
    second_hash = hash_password("a quiet place to learn")
    assert second_hash != stored_hash
    assert "a quiet place to learn" not in stored_hash
    first = extract_parameters(stored_hash)
    second = extract_parameters(second_hash)
    assert first.type == second.type == Type.ID
    assert first.memory_cost >= 19456
    assert first.time_cost >= 2
    assert first.salt_len >= 16
    assert verify_password("a quiet place to learn", stored_hash)
    assert verify_password("a quiet place to learn", second_hash)


@pytest.mark.parametrize(
    "password",
    ["a quiet place to LEARN", "a quiet place to learn ", "a quiet place to lear"],
)
def test_wrong_password_and_changed_suffix_are_rejected(stored_hash, password):
    assert not verify_password(password, stored_hash)


@pytest.mark.parametrize(
    "password",
    [
        "中文学习与成长可以成为一件长期有趣的事情🌱",
        "  a quiet place to learn  ",
        "a" * 128,
    ],
)
def test_unicode_spaces_and_long_passwords_are_preserved(password):
    encoded = hash_password(password)
    assert verify_password(password, encoded)
    if password != password.strip():
        assert not verify_password(password.strip(), encoded)
    assert not verify_password(password[:-1], encoded)


@pytest.mark.parametrize(
    "password",
    [None, b"bytes are not accepted", "", "x" * 14, " " * 15, "x" * 129, "\ud800" * 15],
)
def test_invalid_new_password_never_appears_in_error_message(password):
    with pytest.raises(ValueError) as error:
        hash_password(password)
    assert (
        str(error.value)
        == "password must contain 15 to 128 characters and not be blank"
    )


@pytest.mark.parametrize(
    "encoded",
    [
        None,
        "",
        "plain-text-is-not-a-hash",
        "$argon2id$broken",
        "$argon2id$v=19$m=no,t=3,p=4$c2FsdA$aGFzaA",
        "x" * 513,
    ],
)
def test_missing_or_corrupted_hash_is_not_a_password_match(encoded):
    assert not verify_password("a quiet place to learn", encoded)


@pytest.mark.parametrize("password", [None, b"invalid", "", "x" * 129, "\ud800"])
def test_invalid_verification_input_fails_closed(stored_hash, password):
    assert not verify_password(password, stored_hash)


def test_corrupted_hash_cannot_request_unbounded_work(stored_hash):
    excessive_memory = stored_hash.replace("m=65536", "m=999999999")
    excessive_iterations = stored_hash.replace("t=3", "t=999999999")
    assert not verify_password("a quiet place to learn", excessive_memory)
    assert not verify_password("a quiet place to learn", excessive_iterations)
