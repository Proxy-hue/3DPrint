import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.core.exceptions import ValidationError

from users.models import User
from .models import Technology, Material


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email='admin@test.com',
        password='testpassword123',
        role='ADMIN'
    )


@pytest.fixture
def normal_user(db):
    return User.objects.create_user(
        email='client@test.com',
        password='testpassword123',
        role='CLIENT'
    )


@pytest.fixture
def sample_technology(db):
    return Technology.objects.create(
        code='FDM',
        name='FDM Тест',
        fill_factor=0.35,
        hourly_rate=120.00
    )


@pytest.fixture
def sample_material(db, sample_technology):
    return Material.objects.create(
        name='PLA Тест',
        density=1.24,
        price_per_gram=3.00,
        technology=sample_technology
    )


# ==========================================
# 1. ТЕСТЫ МОДЕЛЕЙ (Валидация)
# ==========================================

@pytest.mark.django_db
def test_material_negative_price_validation(sample_technology):
    """Проверка, что нельзя сохранить материал с отрицательной ценой"""
    material = Material(
        name='Bad PLA',
        density=1.24,
        price_per_gram=-5.00,
        technology=sample_technology
    )
    with pytest.raises(ValidationError):
        material.full_clean()


# ==========================================
# 2. ТЕСТЫ API (Чтение)
# ==========================================

@pytest.mark.django_db
def test_get_materials_anonymous(api_client, sample_material):
    """Анонимный пользователь может читать список материалов (200 OK)"""
    url = '/api/catalog/materials/'
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    # Если включена пагинация, данные будут в 'results'
    data = response.data.get('results', response.data)
    assert len(data) == 1
    assert data[0]['name'] == 'PLA Тест'


# ==========================================
# 3. ТЕСТЫ API (Безопасность / RBAC)
# ==========================================

@pytest.mark.django_db
def test_create_material_anonymous_forbidden(api_client, sample_technology):
    """Аноним не может создавать материалы (403 Forbidden)"""
    url = '/api/catalog/materials/'
    payload = {
        'name': 'New Material',
        'density': 1.0,
        'price_per_gram': 5.0,
        'technology': str(sample_technology.id)
    }
    response = api_client.post(url, payload)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_create_material_normal_user_forbidden(api_client,
                                               normal_user,
                                               sample_technology):
    """Клиент не может создавать материалы (403 Forbidden)"""
    api_client.force_authenticate(user=normal_user)
    url = '/api/catalog/materials/'
    payload = {
        'name': 'New Material',
        'density': 1.0,
        'price_per_gram': 5.0,
        'technology': str(sample_technology.id)
    }
    response = api_client.post(url, payload)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_create_material_admin_success(api_client,
                                       admin_user,
                                       sample_technology):
    """Администратор может создавать материалы (201 Created)"""
    api_client.force_authenticate(user=admin_user)
    url = '/api/catalog/materials/'
    payload = {
        'name': 'New Material',
        'density': 1.0,
        'price_per_gram': 5.0,
        'technology': str(sample_technology.id)
    }
    response = api_client.post(url, payload)

    assert response.status_code == status.HTTP_201_CREATED
    assert Material.objects.count() == 1
