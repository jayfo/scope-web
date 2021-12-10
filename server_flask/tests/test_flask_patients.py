from typing import Callable
from urllib.parse import urljoin

import requests
import scope.config


def test_flask_get_all_patients(
    config_flask_client: scope.config.FlaskClientConfig,
    flask_session_unauthenticated_factory: Callable[[], requests.Session],
):
    session = flask_session_unauthenticated_factory()

    response = session.get(
        url=urljoin(
            config_flask_client.baseurl,
            "patients",
        ),
    )
    assert response.ok

    # TODO: Use fixtures to get sample patient account.
    assert {
        "_id": "61b181ab15d6b17541f102e7",
        "created_at": "2021-12-09T04:10:19.719000",
        "name": "Test",
    } in response.json()["patients"]


def test_flask_get_patient(
    config_flask_client: scope.config.FlaskClientConfig,
    flask_session_unauthenticated_factory: Callable[[], requests.Session],
):
    session = flask_session_unauthenticated_factory()

    response = session.get(
        url=urljoin(
            config_flask_client.baseurl,
            "patients/{}".format("61b181ab15d6b17541f102e7"),
        ),
    )
    assert response.ok
    # TODO: Use fixtures to get sample patient account.
    assert response.json() == {
        "_id": "61b181ab15d6b17541f102e7",
        "created_at": "2021-12-09T04:10:19.719000",
        "name": "Test",
        "status": 200,
    }
