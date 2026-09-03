import allure
import pytest

from api.health_api import HealthApi


pytestmark = [pytest.mark.smoke, pytest.mark.regression]


@allure.epic("接口自动化测试")
@allure.feature("服务健康检查")
@allure.story("FastAPI 健康状态")
def test_api_health(health_api: HealthApi) -> None:
    response = health_api.get_health()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
