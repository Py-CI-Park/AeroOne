from datetime import UTC, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import func, select
import jwt
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.admin.models import AdminAuditEvent, LoginEvent, ResourceGrant, UserPermission, UserSessionActivity
from app.modules.auth.models import User
import pytest
from passlib.hash import bcrypt
from scripts import seed as seed_script

from app.core.config import reset_settings_cache
from app.db.base import Base
from app.db.session import reset_db_caches
from app.main import create_app
from app.modules.auth.services import AuthError, AuthService, requires_password_change
_RETIRED_CREDENTIAL = 'change' + '-me'
_RETIRED_PASSWORD_VARIANTS = (
    _RETIRED_CREDENTIAL,
    f' {_RETIRED_CREDENTIAL.upper()} ',
)


def _configure_auth_env(monkeypatch, tmp_path, **overrides) -> None:
    values = {
        'APP_ENV': 'test',
        'DATABASE_URL': f"sqlite:///{tmp_path / 'auth.db'}",
        'NEWSLETTER_IMPORT_ROOT_CONTAINER': str(tmp_path / 'import_root'),
        'STORAGE_ROOT': str(tmp_path / 'storage'),
        'JWT_SECRET_KEY': 'test-secret',
        'ADMIN_USERNAME': 'admin',
        'ADMIN_PASSWORD': 'current-bootstrap-password',
        'CORS_ORIGINS': 'http://localhost:3000',
        **overrides,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()
    reset_db_caches()


def _configure_production_env(monkeypatch, tmp_path, **overrides) -> None:
    values = {
        'APP_ENV': 'production',
        'DATABASE_URL': f"sqlite:///{tmp_path / 'prod.db'}",
        'JWT_SECRET_KEY': 'production-secret-key-with-enough-entropy',
        'ADMIN_PASSWORD': 'production-admin-password',
        'CORS_ORIGINS': 'https://aeroone.example',
        **overrides,
    }
    _configure_auth_env(monkeypatch, tmp_path, **values)


def test_login_sets_session_and_csrf_cookie(client) -> None:
    response = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})

    assert response.status_code == 200
    assert 'csrf_token' in response.cookies
    set_cookie = response.headers.get('set-cookie', '')
    assert 'httponly' in set_cookie.lower()


def test_logout_clears_cookies_records_event_and_removes_session_activity(client, app) -> None:
    login_response = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert login_response.status_code == 200

    assert client.get('/api/v1/auth/me').status_code == 200

    response = client.post('/api/v1/auth/logout')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
    assert 'max-age=0' in response.headers.get('set-cookie', '').lower()
    assert client.get('/api/v1/auth/me').status_code == 401
    with app.state.db.session() as session:
        statuses = session.execute(select(LoginEvent.status).order_by(LoginEvent.id)).scalars().all()
        active_rows = session.scalar(select(func.count(UserSessionActivity.id)))
    assert statuses == ['success', 'logout']
    assert active_rows == 0

    second_login = client.post('/api/v1/auth/login', json={'username': 'admin', 'password': 'password'})
    assert second_login.status_code == 200
    sessions_response = client.get('/api/v1/admin/sessions')
    assert sessions_response.status_code == 200
    assert any(event['status'] == 'logout' for event in sessions_response.json()['recent_login_events'])


def test_admin_route_requires_auth(client) -> None:
    response = client.get('/api/v1/admin/newsletters')
    assert response.status_code == 401

def test_authenticated_routes_reject_versionless_session_tokens(client, app) -> None:
    with app.state.db.session() as session:
        admin = session.scalar(select(User).where(User.username == 'admin'))
        assert admin is not None
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                'sub': str(admin.id),
                'role': admin.role,
                'csrf': 'csrf-token',
                'iat': int(now.timestamp()),
                'exp': int((now + timedelta(minutes=30)).timestamp()),
            },
            'test-secret',
            algorithm='HS256',
        )

    client.cookies.set('admin_session', token)
    assert client.get('/api/v1/auth/me').status_code == 401
    assert client.get('/api/v1/admin/newsletters').status_code == 401
def test_startup_rejects_active_retired_nonconfigured_account_before_serving(monkeypatch, tmp_path) -> None:
    bootstrap_password = 'current-bootstrap-password'
    _configure_auth_env(monkeypatch, tmp_path, ADMIN_PASSWORD=bootstrap_password)
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    legacy_hash = hash_password(_RETIRED_CREDENTIAL)
    try:
        with app.state.db.session() as session:
            session.add(User(username='retired-operator', password_hash=legacy_hash, session_version=3))

        with pytest.raises(RuntimeError, match='Active accounts use the retired password'):
            with TestClient(app):
                pass

        with app.state.db.session() as session:
            legacy_user = session.scalar(select(User).where(User.username == 'retired-operator'))
            configured_admin = session.scalar(select(User).where(User.username == 'admin'))
        assert legacy_user is not None
        assert legacy_user.password_hash == legacy_hash
        assert legacy_user.session_version == 3
        assert configured_admin is None
    finally:
        Base.metadata.drop_all(bind=app.state.db.engine)
        reset_settings_cache()
        reset_db_caches()


def test_startup_leaves_inactive_retired_account_untouched(monkeypatch, tmp_path) -> None:
    _configure_auth_env(monkeypatch, tmp_path)
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    legacy_hash = hash_password(_RETIRED_CREDENTIAL)
    try:
        with app.state.db.session() as session:
            session.add(
                User(
                    username='retired-inactive',
                    password_hash=legacy_hash,
                    is_active=False,
                    session_version=3,
                )
            )

        with TestClient(app):
            pass

        with app.state.db.session() as session:
            inactive_user = session.scalar(select(User).where(User.username == 'retired-inactive'))
            configured_admin = session.scalar(select(User).where(User.username == 'admin'))
        assert inactive_user is not None
        assert inactive_user.password_hash == legacy_hash
        assert inactive_user.session_version == 3
        assert configured_admin is not None
        assert requires_password_change(configured_admin)
    finally:
        Base.metadata.drop_all(bind=app.state.db.engine)
        reset_settings_cache()
        reset_db_caches()


def test_startup_rotates_legacy_admin_and_invalidates_prior_sessions(monkeypatch, tmp_path) -> None:
    bootstrap_password = 'current-bootstrap-password'
    _configure_auth_env(monkeypatch, tmp_path, ADMIN_PASSWORD=bootstrap_password)
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    legacy_hash = hash_password(_RETIRED_CREDENTIAL)
    try:
        with app.state.db.session() as session:
            legacy_admin = User(username='admin', password_hash=legacy_hash, session_version=3)
            session.add(legacy_admin)
            session.flush()
            old_token = create_access_token(
                'test-secret',
                str(legacy_admin.id),
                legacy_admin.role,
                'old-csrf-token',
                30,
                session_version=legacy_admin.session_version,
            )

        with TestClient(app) as client:
            client.cookies.set('admin_session', old_token)
            assert client.get('/api/v1/auth/me').status_code == 401
            assert client.post(
                '/api/v1/auth/login',
                json={'username': 'admin', 'password': _RETIRED_CREDENTIAL},
            ).status_code == 401

            login_response = client.post(
                '/api/v1/auth/login',
                json={'username': 'admin', 'password': bootstrap_password},
            )
            assert login_response.status_code == 200
            assert client.get('/api/v1/admin/newsletters').status_code == 403

        restarted_app = create_app()
        with TestClient(restarted_app) as restarted_client:
            restarted_client.cookies.set('admin_session', old_token)
            assert restarted_client.get('/api/v1/auth/me').status_code == 401
        with app.state.db.session() as session:
            admin = session.scalar(select(User).where(User.username == 'admin'))
        assert admin is not None
        assert admin.password_hash != legacy_hash
        assert admin.session_version == 4
        assert requires_password_change(admin)
    finally:
        Base.metadata.drop_all(bind=app.state.db.engine)
        reset_settings_cache()
        reset_db_caches()


def test_auth_service_rejects_retired_login_without_lifespan_preflight(monkeypatch, tmp_path) -> None:
    _configure_auth_env(monkeypatch, tmp_path)
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    legacy_hash = hash_password(_RETIRED_CREDENTIAL)
    try:
        with app.state.db.session() as session:
            session.add(User(username='legacy-login', password_hash=legacy_hash, session_version=6))

        with app.state.db.session() as session:
            service = AuthService(session, 'test-secret', 30)
            with pytest.raises(AuthError, match='Invalid credentials'):
                service.login('legacy-login', _RETIRED_CREDENTIAL)

        with app.state.db.session() as session:
            legacy_user = session.scalar(select(User).where(User.username == 'legacy-login'))
            statuses = session.execute(select(LoginEvent.status).where(LoginEvent.username == 'legacy-login')).scalars().all()
        assert legacy_user is not None
        assert legacy_user.password_hash == legacy_hash
        assert legacy_user.session_version == 6
        assert statuses == ['failure']
    finally:
        Base.metadata.drop_all(bind=app.state.db.engine)
        reset_settings_cache()
        reset_db_caches()


def test_startup_restricts_configured_bootstrap_and_invalidates_prior_token(monkeypatch, tmp_path) -> None:
    bootstrap_password = 'current-bootstrap-password'
    predecessor_timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    _configure_auth_env(monkeypatch, tmp_path, ADMIN_PASSWORD=bootstrap_password)
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    try:
        with app.state.db.session() as session:
            admin = User(
                username='admin',
                password_hash=hash_password(bootstrap_password),
                password_changed_at=predecessor_timestamp,
                session_version=3,
            )
            session.add(admin)
            session.flush()
            prior_token = create_access_token(
                'test-secret',
                str(admin.id),
                admin.role,
                'prior-csrf-token',
                30,
                session_version=admin.session_version,
            )

        with TestClient(app) as client:
            client.cookies.set('admin_session', prior_token)
            assert client.get('/api/v1/auth/me').status_code == 401

            login_response = client.post(
                '/api/v1/auth/login',
                json={'username': 'admin', 'password': bootstrap_password},
            )
            assert login_response.status_code == 200
            assert client.get('/api/v1/admin/newsletters').status_code == 403

        with app.state.db.session() as session:
            admin = session.scalar(select(User).where(User.username == 'admin'))
        assert admin is not None
        assert admin.password_changed_at is not None
        assert admin.password_changed_at != predecessor_timestamp
        assert requires_password_change(admin)
        assert admin.session_version == 4
    finally:
        Base.metadata.drop_all(bind=app.state.db.engine)
        reset_settings_cache()
        reset_db_caches()


@pytest.mark.parametrize(
    'predecessor_kind',
    ['retired', 'configured-bootstrap'],
    ids=['retired-predecessor', 'configured-bootstrap-predecessor'],
)
def test_startup_preflight_commit_survives_later_seed_sync_failure(
    monkeypatch,
    tmp_path,
    predecessor_kind: str,
) -> None:
    bootstrap_password = 'current-bootstrap-password'
    predecessor_password = (
        _RETIRED_CREDENTIAL
        if predecessor_kind == 'retired'
        else bootstrap_password
    )
    _configure_auth_env(monkeypatch, tmp_path, ADMIN_PASSWORD=bootstrap_password)
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)

    def fail_external_sync(*_args, **_kwargs):
        raise RuntimeError('simulated external seed failure')

    try:
        with app.state.db.session() as session:
            predecessor = User(
                username='admin',
                password_hash=hash_password(predecessor_password),
                session_version=3,
            )
            session.add(predecessor)
            session.flush()
            predecessor_id = predecessor.id

        monkeypatch.setattr(seed_script, '_sync_external_newsletters', fail_external_sync)
        with pytest.raises(RuntimeError, match='simulated external seed failure'):
            seed_script.main()

        with app.state.db.session() as session:
            persisted_admin = session.scalar(select(User).where(User.username == 'admin'))
            admin_count = session.scalar(select(func.count(User.id)))
        assert persisted_admin is not None
        assert persisted_admin.id == predecessor_id
        assert persisted_admin.session_version == 4
        assert requires_password_change(persisted_admin)
        assert verify_password(bootstrap_password, persisted_admin.password_hash)
        assert admin_count == 1
    finally:
        Base.metadata.drop_all(bind=app.state.db.engine)
        reset_settings_cache()
        reset_db_caches()


def test_startup_preflight_creation_is_idempotent_on_restart(monkeypatch, tmp_path) -> None:
    _configure_auth_env(monkeypatch, tmp_path)
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    try:
        with TestClient(app):
            pass

        with app.state.db.session() as session:
            initial_admin = session.scalar(select(User).where(User.username == 'admin'))
        assert initial_admin is not None
        initial_id = initial_admin.id
        initial_session_version = initial_admin.session_version
        assert requires_password_change(initial_admin)

        restarted_app = create_app()
        with TestClient(restarted_app):
            pass

        with restarted_app.state.db.session() as session:
            restarted_admin = session.scalar(select(User).where(User.username == 'admin'))
            admin_count = session.scalar(select(func.count(User.id)))
        assert restarted_admin is not None
        assert restarted_admin.id == initial_id
        assert restarted_admin.session_version == initial_session_version
        assert requires_password_change(restarted_admin)
        assert admin_count == 1
    finally:
        Base.metadata.drop_all(bind=app.state.db.engine)
        reset_settings_cache()
        reset_db_caches()


def test_optional_auth_endpoint_degrades_first_change_user_to_anonymous(monkeypatch, tmp_path) -> None:
    # 초기 비밀번호 미변경(강제 변경) 계정이라도 공개(optional-auth) 엔드포인트는 익명으로
    # 강등해 200 을 돌려줘야 한다 — 대시보드 공개 모듈 목록까지 403 나던 데드락을 막는다.
    bootstrap_password = 'current-bootstrap-password'
    _configure_auth_env(monkeypatch, tmp_path, ADMIN_PASSWORD=bootstrap_password)
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    try:
        with TestClient(app) as client:
            login_response = client.post(
                '/api/v1/auth/login',
                json={'username': 'admin', 'password': bootstrap_password},
            )
            assert login_response.status_code == 200
            session_cookie = client.cookies.get('admin_session')

            optional_response = client.get('/api/v1/admin/service-modules/public')

            assert optional_response.status_code == 200
            assert isinstance(optional_response.json(), list)
            assert client.cookies.get('admin_session') == session_cookie

        with app.state.db.session() as session:
            statuses = session.execute(select(LoginEvent.status).order_by(LoginEvent.id)).scalars().all()
        assert statuses == ['success']
    finally:
        Base.metadata.drop_all(bind=app.state.db.engine)
        reset_settings_cache()
        reset_db_caches()


def test_setup_credential_requires_password_change_before_normal_routes(monkeypatch, tmp_path) -> None:
    bootstrap_password = 'current-bootstrap-password'
    new_password = 'personal-admin-password'
    _configure_auth_env(monkeypatch, tmp_path, ADMIN_PASSWORD=bootstrap_password)
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    try:
        with app.state.db.session() as session:
            session.add(User(username='admin', password_hash=hash_password(_RETIRED_CREDENTIAL), session_version=3))

        with TestClient(app) as client:
            assert client.post(
                '/api/v1/auth/login',
                json={'username': 'admin', 'password': _RETIRED_CREDENTIAL},
            ).status_code == 401
            setup_login = client.post(
                '/api/v1/auth/login',
                json={'username': 'admin', 'password': bootstrap_password},
            )

            assert setup_login.status_code == 200
            assert client.get('/api/v1/auth/me').status_code == 200
            assert client.get('/api/v1/auth/effective-permissions').status_code == 403
            assert client.get('/api/v1/admin/newsletters').status_code == 403
            assert client.post('/api/v1/auth/logout').status_code == 200

            setup_login = client.post(
                '/api/v1/auth/login',
                json={'username': 'admin', 'password': bootstrap_password},
            )
            password_change_response = client.post(
                '/api/v1/auth/change-password',
                json={'current_password': bootstrap_password, 'new_password': new_password},
                headers={'x-csrf-token': setup_login.json()['csrf_token']},
            )

            assert password_change_response.status_code == 200
            assert client.get('/api/v1/auth/effective-permissions').status_code == 200
            assert client.get('/api/v1/admin/newsletters').status_code == 200
    finally:
        Base.metadata.drop_all(bind=app.state.db.engine)
        reset_settings_cache()
        reset_db_caches()

def test_requires_password_change_flag_exposed_in_auth_responses(monkeypatch, tmp_path) -> None:
    bootstrap_password = 'current-bootstrap-password'
    new_password = 'personal-admin-password'
    _configure_auth_env(monkeypatch, tmp_path, ADMIN_PASSWORD=bootstrap_password)
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    try:
        with app.state.db.session() as session:
            session.add(User(username='admin', password_hash=hash_password(_RETIRED_CREDENTIAL), session_version=3))

        with TestClient(app) as client:
            setup_login = client.post(
                '/api/v1/auth/login',
                json={'username': 'admin', 'password': bootstrap_password},
            )
            assert setup_login.status_code == 200
            # 강제 변경 상태에서는 login/me 응답이 플래그로 프런트에 강제 변경 화면을 안내한다.
            assert setup_login.json()['user']['requires_password_change'] is True
            me_response = client.get('/api/v1/auth/me')
            assert me_response.status_code == 200
            assert me_response.json()['requires_password_change'] is True

            change_response = client.post(
                '/api/v1/auth/change-password',
                json={'current_password': bootstrap_password, 'new_password': new_password},
                headers={'x-csrf-token': setup_login.json()['csrf_token']},
            )
            assert change_response.status_code == 200
            # 변경 직후 응답과 이어지는 me 응답 모두 플래그가 내려가야 정상 상태로 돌아온 것이다.
            assert change_response.json()['user']['requires_password_change'] is False
            assert client.get('/api/v1/auth/me').json()['requires_password_change'] is False
    finally:
        Base.metadata.drop_all(bind=app.state.db.engine)
        reset_settings_cache()
        reset_db_caches()

@pytest.mark.parametrize(
    'retired_password',
    _RETIRED_PASSWORD_VARIANTS,
    ids=['retired', 'retired-case-variant'],
)
def test_retired_password_writes_leave_users_sessions_and_audits_unchanged(
    csrf_client,
    app,
    retired_password: str,
) -> None:
    target_password = 'recipient-password'
    target_username = 'retired-write-target'
    rejected_username = 'retired-write-candidate'
    with app.state.db.session() as session:
        recipient = User(
            username=target_username,
            password_hash=hash_password(target_password),
            session_version=6,
        )
        session.add(recipient)
        session.flush()
        recipient_id = recipient.id
        admin = session.scalar(select(User).where(User.username == 'admin'))
        assert admin is not None
        admin_state = (admin.password_hash, admin.password_changed_at, admin.session_version)
        recipient_state = (recipient.password_hash, recipient.password_changed_at, recipient.session_version)

    create_response = csrf_client.post(
        '/api/v1/admin/users',
        json={'username': rejected_username, 'password': retired_password},
    )
    assert create_response.status_code == 400
    assert create_response.json()['detail'] == 'Retired password cannot be used'

    reset_response = csrf_client.post(
        f'/api/v1/admin/users/{recipient_id}/password-reset',
        json={'temporary_password': retired_password},
    )
    assert reset_response.status_code == 400
    assert reset_response.json()['detail'] == 'Retired password cannot be used'

    change_response = csrf_client.post(
        '/api/v1/auth/change-password',
        json={'current_password': 'password', 'new_password': retired_password},
    )
    assert change_response.status_code == 400
    assert change_response.json()['detail'] == 'Retired password cannot be used'

    with app.state.db.session() as session:
        admin = session.scalar(select(User).where(User.username == 'admin'))
        recipient = session.get(User, recipient_id)
        rejected_user = session.scalar(select(User).where(User.username == rejected_username))
        audit_actions = session.scalars(
            select(AdminAuditEvent.action).where(
                AdminAuditEvent.action.in_(
                    (
                        'account.password_change',
                        'user.create',
                        'user.password_reset',
                    )
                )
            )
        ).all()
    assert admin is not None
    assert recipient is not None
    assert (admin.password_hash, admin.password_changed_at, admin.session_version) == admin_state
    assert (recipient.password_hash, recipient.password_changed_at, recipient.session_version) == recipient_state
    assert rejected_user is None
    assert audit_actions == []

def test_custom_admin_password_is_not_replaced_by_bootstrap_password(monkeypatch, tmp_path) -> None:
    bootstrap_password = 'current-bootstrap-password'
    custom_password = 'custom-admin-password'
    _configure_auth_env(monkeypatch, tmp_path, ADMIN_PASSWORD=bootstrap_password)
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    custom_hash = hash_password(custom_password)
    try:
        with app.state.db.session() as session:
            session.add(User(username='admin', password_hash=custom_hash, session_version=3))

        with TestClient(app) as client:
            custom_password_response = client.post(
                '/api/v1/auth/login',
                json={'username': 'admin', 'password': custom_password},
            )
            bootstrap_password_response = client.post(
                '/api/v1/auth/login',
                json={'username': 'admin', 'password': bootstrap_password},
            )

            assert custom_password_response.status_code == 200
            assert bootstrap_password_response.status_code == 401
            assert client.get('/api/v1/admin/newsletters').status_code == 200
        with app.state.db.session() as session:
            admin = session.scalar(select(User).where(User.username == 'admin'))
        assert admin is not None
        assert admin.password_hash == custom_hash
        assert admin.session_version == 3
    finally:
        Base.metadata.drop_all(bind=app.state.db.engine)
        reset_settings_cache()
        reset_db_caches()


def test_production_rejects_default_auth_secrets(monkeypatch, tmp_path) -> None:
    _configure_production_env(
        monkeypatch,
        tmp_path,
        JWT_SECRET_KEY=_RETIRED_CREDENTIAL,
        ADMIN_PASSWORD=_RETIRED_CREDENTIAL,
    )

    try:
        with pytest.raises(ValueError, match='JWT_SECRET_KEY'):
            create_app()
    finally:
        reset_settings_cache()
        reset_db_caches()


def test_production_login_sets_secure_configured_csrf_cookie(monkeypatch, tmp_path) -> None:
    _configure_production_env(monkeypatch, tmp_path, CSRF_COOKIE_NAME='aeroone_csrf')
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    try:
        with TestClient(app, base_url='https://aeroone.example') as client:
            response = client.post(
                '/api/v1/auth/login',
                json={'username': 'admin', 'password': 'production-admin-password'},
            )

            assert response.status_code == 200
            assert 'aeroone_csrf' in response.cookies
            assert 'csrf_token' not in response.cookies
            set_cookie = response.headers.get('set-cookie', '').lower()
            assert 'secure' in set_cookie

            csrf_token = response.json()['csrf_token']
            password_change_response = client.post(
                '/api/v1/auth/change-password',
                json={
                    'current_password': 'production-admin-password',
                    'new_password': 'production-admin-personal-password',
                },
                headers={'x-csrf-token': csrf_token},
            )
            assert password_change_response.status_code == 200
            csrf_token = password_change_response.json()['csrf_token']
            category_response = client.post(
                '/api/v1/admin/categories',
                json={'name': '운영'},
                headers={'x-csrf-token': csrf_token},
            )
            assert category_response.status_code == 200
    finally:
        Base.metadata.drop_all(bind=app.state.db.engine)
        reset_settings_cache()
        reset_db_caches()


def test_effective_permissions_requires_auth(client) -> None:
    response = client.get('/api/v1/auth/effective-permissions')

    assert response.status_code == 401


def test_effective_permissions_returns_user_permissions_and_resource_grants(client, app) -> None:
    with app.state.db.session() as session:
        user = User(username='nsa-reader', password_hash=hash_password('password'), role='user', is_active=True)
        session.add(user)
        session.flush()
        session.add(UserPermission(user_id=user.id, permission_key='collections.nsa.read'))
        session.add(
            ResourceGrant(
                subject_type='user',
                subject_id=user.id,
                resource_type='collection',
                resource_id='nsa',
                permission_key='collections.nsa.read',
            )
        )
        session.commit()

    login_response = client.post('/api/v1/auth/login', json={'username': 'nsa-reader', 'password': 'password'})
    assert login_response.status_code == 200

    response = client.get('/api/v1/auth/effective-permissions')

    assert response.status_code == 200
    payload = response.json()
    assert 'collections.nsa.read' in payload['permissions']
    assert {
        'resource_type': 'collection',
        'resource_id': 'nsa',
        'permission_key': 'collections.nsa.read',
    } in payload['resources']
def test_admin_reset_requires_first_change_and_preserves_opaque_password_text(csrf_client, app) -> None:
    username = 'opaque-reset-user'
    initial_password = '  initial password  '
    temporary_password = '  temporary password  '
    personal_password = '  personal password  '

    create_response = csrf_client.post(
        '/api/v1/admin/users',
        json={'username': username, 'password': initial_password},
    )
    assert create_response.status_code == 200
    user_id = create_response.json()['id']

    with app.state.db.session() as session:
        user = session.get(User, user_id)
        assert user is not None
        initial_hash = user.password_hash
        assert initial_hash.startswith('$bcrypt-sha256$')
        assert verify_password(initial_password, initial_hash)
        assert not verify_password(initial_password.strip(), initial_hash)
        assert user.session_version == 0
        assert not requires_password_change(user)

    target_client = TestClient(app)
    initial_login = target_client.post(
        '/api/v1/auth/login',
        json={'username': username, 'password': initial_password},
    )
    assert initial_login.status_code == 200
    initial_token = target_client.cookies.get('admin_session')
    assert initial_token is not None
    assert jwt.decode(initial_token, 'test-secret', algorithms=['HS256'])['ver'] == 0

    reset_response = csrf_client.post(
        f'/api/v1/admin/users/{user_id}/password-reset',
        json={'temporary_password': temporary_password},
    )
    assert reset_response.status_code == 200

    with app.state.db.session() as session:
        user = session.get(User, user_id)
        assert user is not None
        temporary_hash = user.password_hash
        assert temporary_hash.startswith('$bcrypt-sha256$')
        assert temporary_hash != initial_hash
        assert verify_password(temporary_password, temporary_hash)
        assert not verify_password(temporary_password.strip(), temporary_hash)
        assert user.session_version == 1
        assert requires_password_change(user)

    assert target_client.get('/api/v1/auth/me').status_code == 401
    assert target_client.post(
        '/api/v1/auth/login',
        json={'username': username, 'password': initial_password},
    ).status_code == 401

    temporary_login = target_client.post(
        '/api/v1/auth/login',
        json={'username': username, 'password': temporary_password},
    )
    assert temporary_login.status_code == 200
    temporary_token = target_client.cookies.get('admin_session')
    assert temporary_token is not None
    assert jwt.decode(temporary_token, 'test-secret', algorithms=['HS256'])['ver'] == 1
    assert target_client.get('/api/v1/auth/me').status_code == 200
    assert target_client.get('/api/v1/auth/effective-permissions').status_code == 403

    change_response = target_client.post(
        '/api/v1/auth/change-password',
        json={'current_password': temporary_password, 'new_password': personal_password},
        headers={'x-csrf-token': temporary_login.json()['csrf_token']},
    )
    assert change_response.status_code == 200
    personal_token = target_client.cookies.get('admin_session')
    assert personal_token is not None
    assert jwt.decode(personal_token, 'test-secret', algorithms=['HS256'])['ver'] == 2

    stale_temporary_client = TestClient(app)
    stale_temporary_client.cookies.set('admin_session', temporary_token)
    assert stale_temporary_client.get('/api/v1/auth/me').status_code == 401
    assert target_client.get('/api/v1/auth/effective-permissions').status_code == 200

    with app.state.db.session() as session:
        user = session.get(User, user_id)
        admin = session.scalar(select(User).where(User.username == 'admin'))
        audits = session.scalars(
            select(AdminAuditEvent)
            .where(AdminAuditEvent.target_id == str(user_id))
            .order_by(AdminAuditEvent.id)
        ).all()
    assert user is not None
    assert admin is not None
    assert user.password_hash.startswith('$bcrypt-sha256$')
    assert user.password_hash != temporary_hash
    assert verify_password(personal_password, user.password_hash)
    assert not verify_password(personal_password.strip(), user.password_hash)
    assert user.session_version == 2
    assert not requires_password_change(user)
    assert [audit.action for audit in audits] == [
        'user.create',
        'user.password_reset',
        'account.password_change',
    ]
    assert [audit.actor_username for audit in audits] == ['admin', 'admin', username]
    assert audits[1].metadata_json == '{"temporary_password": "[REDACTED]"}'
    assert audits[2].metadata_json == '{"self": true}'


def test_unicode_password_api_contract_uses_bcrypt_sha256_without_aliasing(client, csrf_client, app) -> None:
    username = 'unicode-password-user'
    password = '비밀' * 128
    alias_password = '비밀' * 127 + '비문'
    legacy_username = 'legacy-bcrypt-user'
    legacy_password = 'legacy-bcrypt-password'

    create_response = csrf_client.post(
        '/api/v1/admin/users',
        json={'username': username, 'password': password},
    )
    assert create_response.status_code == 200
    user_id = create_response.json()['id']

    with app.state.db.session() as session:
        user = session.get(User, user_id)
        assert user is not None
        assert len(password) == 256
        assert user.password_hash.startswith('$bcrypt-sha256$')
        assert verify_password(password, user.password_hash)
        assert not verify_password(alias_password, user.password_hash)
        session.add(User(username=legacy_username, password_hash=bcrypt.hash(legacy_password)))

    exact_login = client.post(
        '/api/v1/auth/login',
        json={'username': username, 'password': password},
    )
    assert exact_login.status_code == 200
    alias_login = client.post(
        '/api/v1/auth/login',
        json={'username': username, 'password': alias_password},
    )
    assert alias_login.status_code == 401
    legacy_login = client.post(
        '/api/v1/auth/login',
        json={'username': legacy_username, 'password': legacy_password},
    )
    assert legacy_login.status_code == 200


@pytest.mark.parametrize(
    ('invalid_password', 'create_status', 'login_status', 'candidate_error'),
    [
        ('密' * 257, 422, 422, 'must be at most 256 characters'),
        (' \t\u00a0\n', 400, 401, 'is required'),
        ('short7', 400, 401, 'must be at least 8 characters'),
    ],
    ids=['over-contract', 'whitespace-only', 'too-short'],
)
def test_invalid_password_inputs_are_rejected_without_password_side_effects(
    csrf_client,
    app,
    invalid_password: str,
    create_status: int,
    login_status: int,
    candidate_error: str,
) -> None:
    target_username = 'password-boundary-target'
    rejected_username = 'password-boundary-rejected'
    with app.state.db.session() as session:
        target = User(
            username=target_username,
            password_hash=hash_password('recipient-password'),
            session_version=7,
        )
        session.add(target)
        session.flush()
        target_id = target.id
        admin = session.scalar(select(User).where(User.username == 'admin'))
        assert admin is not None
        admin_state = (
            admin.password_hash,
            admin.password_changed_at,
            admin.session_version,
            admin.last_login_at,
        )
        target_state = (
            target.password_hash,
            target.password_changed_at,
            target.session_version,
            target.last_login_at,
        )

    create_response = csrf_client.post(
        '/api/v1/admin/users',
        json={'username': rejected_username, 'password': invalid_password},
    )
    assert create_response.status_code == create_status
    if create_status == 400:
        assert candidate_error in create_response.json()['detail']

    reset_response = csrf_client.post(
        f'/api/v1/admin/users/{target_id}/password-reset',
        json={'temporary_password': invalid_password},
    )
    assert reset_response.status_code == 400
    assert candidate_error in reset_response.json()['detail']

    change_response = csrf_client.post(
        '/api/v1/auth/change-password',
        json={'current_password': 'password', 'new_password': invalid_password},
    )
    assert change_response.status_code == 400
    assert candidate_error in change_response.json()['detail']

    login_response = csrf_client.post(
        '/api/v1/auth/login',
        json={'username': target_username, 'password': invalid_password},
    )
    assert login_response.status_code == login_status
    assert login_response.status_code != 500

    with app.state.db.session() as session:
        admin = session.scalar(select(User).where(User.username == 'admin'))
        target = session.get(User, target_id)
        rejected = session.scalar(select(User).where(User.username == rejected_username))
        audit_actions = session.scalars(
            select(AdminAuditEvent.action).where(
                AdminAuditEvent.action.in_(
                    ('account.password_change', 'user.create', 'user.password_reset')
                )
            )
        ).all()
    assert admin is not None
    assert target is not None
    assert (
        admin.password_hash,
        admin.password_changed_at,
        admin.session_version,
        admin.last_login_at,
    ) == admin_state
    assert (
        target.password_hash,
        target.password_changed_at,
        target.session_version,
        target.last_login_at,
    ) == target_state
    assert rejected is None
    assert audit_actions == []


@pytest.mark.parametrize(
    'stored_hash',
    ['unrecognized-password-hash', '$2b$12$malformed'],
    ids=['unknown-hash', 'malformed-bcrypt'],
)
def test_invalid_stored_hashes_fail_startup_by_account_and_auth_checks_generically(
    monkeypatch,
    tmp_path,
    stored_hash: str,
) -> None:
    username = 'invalid-hash-user'
    _configure_auth_env(monkeypatch, tmp_path)
    app = create_app()
    Base.metadata.create_all(bind=app.state.db.engine)
    try:
        with app.state.db.session() as session:
            user = User(username=username, password_hash=stored_hash, session_version=4)
            session.add(user)
            session.flush()
            token = create_access_token(
                'test-secret',
                str(user.id),
                user.role,
                'invalid-hash-csrf',
                30,
                session_version=user.session_version,
            )

        with pytest.raises(RuntimeError, match='Active accounts have invalid password hashes') as startup_error:
            with TestClient(app):
                pass
        assert username in str(startup_error.value)

        auth_client = TestClient(app)
        login_response = auth_client.post(
            '/api/v1/auth/login',
            json={'username': username, 'password': 'current-password'},
        )
        assert login_response.status_code == 401
        assert login_response.json()['detail'] == 'Invalid credentials'

        auth_client.cookies.set('admin_session', token)
        auth_client.cookies.set('csrf_token', 'invalid-hash-csrf')
        change_response = auth_client.post(
            '/api/v1/auth/change-password',
            json={'current_password': 'current-password', 'new_password': 'personal-password'},
            headers={'x-csrf-token': 'invalid-hash-csrf'},
        )
        assert change_response.status_code == 401
        assert change_response.json()['detail'] == 'Current password is incorrect'

        with app.state.db.session() as session:
            user = session.scalar(select(User).where(User.username == username))
            login_statuses = session.scalars(
                select(LoginEvent.status).where(LoginEvent.username == username)
            ).all()
            audit_actions = session.scalars(
                select(AdminAuditEvent.action).where(AdminAuditEvent.target_id == str(user.id))
            ).all() if user is not None else []
        assert user is not None
        assert user.password_hash == stored_hash
        assert user.session_version == 4
        assert login_statuses == ['failure']
        assert audit_actions == []
    finally:
        Base.metadata.drop_all(bind=app.state.db.engine)
        reset_settings_cache()
        reset_db_caches()


def test_inactive_retired_or_invalid_hash_users_require_reset_before_activation(csrf_client, app) -> None:
    user_specs = [
        ('retired-inactive-user', hash_password(_RETIRED_CREDENTIAL), 5),
        ('invalid-inactive-user', 'unrecognized-password-hash', 8),
    ]
    user_ids: dict[str, int] = {}
    with app.state.db.session() as session:
        for username, password_hash, session_version in user_specs:
            user = User(
                username=username,
                password_hash=password_hash,
                is_active=False,
                session_version=session_version,
            )
            session.add(user)
            session.flush()
            user_ids[username] = user.id

    for username, _password_hash, _session_version in user_specs:
        response = csrf_client.patch(
            f'/api/v1/admin/users/{user_ids[username]}',
            json={'is_active': True},
        )
        assert response.status_code == 400
        assert response.json()['detail'] == 'Password reset is required before activating this user'

    with app.state.db.session() as session:
        users = {
            username: session.get(User, user_id)
            for username, user_id in user_ids.items()
        }
        failed_activation_audits = session.scalars(
            select(AdminAuditEvent).where(
                AdminAuditEvent.target_id.in_([str(user_id) for user_id in user_ids.values()])
            )
        ).all()
    for username, password_hash, session_version in user_specs:
        user = users[username]
        assert user is not None
        assert user.password_hash == password_hash
        assert user.is_active is False
        assert user.session_version == session_version
    assert failed_activation_audits == []

    for username, _password_hash, session_version in user_specs:
        reset_response = csrf_client.post(
            f'/api/v1/admin/users/{user_ids[username]}/password-reset',
            json={'temporary_password': f'{username}-temporary-password'},
        )
        assert reset_response.status_code == 200
        activation_response = csrf_client.patch(
            f'/api/v1/admin/users/{user_ids[username]}',
            json={'is_active': True},
        )
        assert activation_response.status_code == 200
        assert activation_response.json()['is_active'] is True
        assert activation_response.json()['session_version'] == session_version + 2

    with app.state.db.session() as session:
        users = {
            username: session.get(User, user_id)
            for username, user_id in user_ids.items()
        }
        audits = session.scalars(
            select(AdminAuditEvent)
            .where(AdminAuditEvent.target_id.in_([str(user_id) for user_id in user_ids.values()]))
            .order_by(AdminAuditEvent.id)
        ).all()
    for username, _password_hash, session_version in user_specs:
        user = users[username]
        assert user is not None
        assert user.is_active is True
        assert user.password_hash.startswith('$bcrypt-sha256$')
        assert user.session_version == session_version + 2
        assert requires_password_change(user)
    assert [audit.action for audit in audits] == [
        'user.password_reset',
        'user.update',
        'user.password_reset',
        'user.update',
    ]
    assert [audit.metadata_json for audit in audits if audit.action == 'user.password_reset'] == [
        '{"temporary_password": "[REDACTED]"}',
        '{"temporary_password": "[REDACTED]"}',
    ]
