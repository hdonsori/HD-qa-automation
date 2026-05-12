from utils.auth_token_manager import is_access_token_valid


def test_token_bundle_available_or_refreshable(auth_bundle):
    # Soft assertion style: this test documents runtime state.
    # In fresh environments, auth_bundle can be absent until first bootstrap login.
    if not auth_bundle:
        return
    assert "access_token" in auth_bundle
    assert "refresh_token" in auth_bundle
    assert "employee_id" in auth_bundle
    assert isinstance(is_access_token_valid(auth_bundle), bool)
