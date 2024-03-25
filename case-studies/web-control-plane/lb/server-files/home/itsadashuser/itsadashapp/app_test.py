import os
import random
import socket
import sqlite3
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from faker import Faker

from app import (
    VARIABLES,
    clean_url,
    connect_to_sqlite,
    flaskApp,
    load_url,
    read_from_sqlite,
    validate_token,
    write_to_sqlite,
)

TEST_SQLITE_FILE = "sqlite-test.db"


fake = Faker()


@pytest.fixture
def client():
    with flaskApp.test_client() as client:
        yield client


@pytest.fixture
def sqlConnect():
    conn = connect_to_sqlite(TEST_SQLITE_FILE)
    yield conn
    conn.close()
    Path(TEST_SQLITE_FILE).unlink(missing_ok=True)


TEST_SITE_NAME = "example.com"
TEST_SITE_IP = "10.0.0.1"
TEST_SITE_PATH = f"sites/{TEST_SITE_NAME}.conf"
TEST_GUNICORN_PORT = "14041"


def test_connect_to_sqlite():
    # Test creating a fake sqldb file
    sqlite_random_filename = "sqlite-fake-e1b1f5e5-c123-40de-a23f-05e99a8b64d9.db"
    if Path(sqlite_random_filename).exists():
        print("Removing existing file")
        Path(sqlite_random_filename).unlink(missing_ok=True)
    try:
        # Generate a random filename
        connect_to_sqlite(sqlite_random_filename)
        assert os.path.exists(sqlite_random_filename)
    finally:
        Path(sqlite_random_filename).unlink(missing_ok=True)


def test_write_to_sqlite():
    # Create a temporary sqlite.db
    with sqlite3.connect(":memory:") as conn:
        c = conn.cursor()
        c.execute(
            "CREATE TABLE sites (id INTEGER PRIMARY KEY, site TEXT, ip TEXT, last_updated TEXT)"
        )

        # Test writing to sqlite
        write_to_sqlite(conn, TEST_SITE_IP, TEST_SITE_NAME)
        c.execute("SELECT * FROM sites WHERE site=?", (TEST_SITE_NAME,))
        row = c.fetchone()
        assert row[1] == TEST_SITE_NAME
        assert row[2] == TEST_SITE_IP


def test_read_from_sqlite():
    # Prepare test data
    with sqlite3.connect(":memory:") as conn:
        c = conn.cursor()
        c.execute(
            "CREATE TABLE sites (id INTEGER PRIMARY KEY, site TEXT, ip TEXT, last_updated TEXT)"
        )
        c.execute(
            "INSERT INTO sites (site, ip, last_updated) VALUES (?, ?, ?)",
            (TEST_SITE_NAME, TEST_SITE_IP, time.time()),
        )

        # Test reading from sqlite
        rows = read_from_sqlite(conn, TEST_SITE_NAME)
        print("Rows:", rows)  # Add this line to see the fetched rows
        assert len(rows) == 1
        assert rows[0][1] == TEST_SITE_NAME
        assert rows[0][2] == TEST_SITE_IP


def test_clean_url():
    url = "http://www.example.com:8080/path/to/page"
    cleaned_url = clean_url(url)
    assert cleaned_url == "www.example.com/path/to/page"


@patch("socket.create_connection")
def test_load_url(mock_socket):
    ip = "10.0.0.1"
    # Test loading a valid url
    mock_socket.return_value = MagicMock()
    mock_socket.return_value.getsockname.return_value = (ip, 80)
    response = load_url("http://www.example.com", 2)
    assert response == ip

    # Test loading an invalid url
    mock_socket.side_effect = socket.timeout
    response = load_url("http://www.example.com", 2)
    assert response == ""


@patch("os.environ.get")
def test_validate_token(mock_env):
    # Mock load_dotenv to do nothing
    with patch("dotenv.load_dotenv"):
        val = "123"
        mock_env.return_value = val
        VARIABLES["token"] = val
        result = validate_token(lambda x: x)(VARIABLES["token"])
        assert result == val

        VARIABLES["token"] = "456"
        result = validate_token(lambda x: x)()
        assert result == "Invalid token: 456"


def test_update_sites(client):
    try:
        test_sqlite_file = f"test-{uuid.uuid4()}-{TEST_SQLITE_FILE}"
        conn = connect_to_sqlite(test_sqlite_file)

        with patch("app.connect_to_sqlite") as mock_connect_to_sqlite:
            mock_connect_to_sqlite.return_value = conn

            with patch("app.populate_variables") as mock_populate_variables:
                mock_populate_variables.return_value = (
                    lambda x: x
                )  # Bypass the decorator

                with patch("app.confirm_token_matches") as mock_confirm_token_matches:
                    mock_confirm_token_matches.return_value = True

                    # Assert sqlite is empty
                    rows = read_from_sqlite(conn, TEST_SITE_NAME)
                    assert len(rows) == 0

                    # Send a POST request to the /update route
                    response = client.post(
                        "/update",
                        json={
                            "site": TEST_SITE_NAME,
                            "serverip": TEST_SITE_IP,
                            "token": "123",
                        },
                    )

                    # Assert that the response is as expected
                    assert response.status_code == 200

                    rows = read_from_sqlite(conn, TEST_SITE_NAME)

                    # Assert that the sqlite db has been updated
                    assert len(rows) == 1
                    assert rows[0][1] == TEST_SITE_NAME
                    assert rows[0][2] == TEST_SITE_IP
    finally:
        Path(test_sqlite_file).unlink(missing_ok=True)


def mock_load_url_fn(url, timeout=2):
    ips = [TEST_SITE_IP, "10.0.0.2"]
    return random.choice(ips)


@patch("app.connect_to_sqlite")
@patch("app.load_url")
def test_regen_sites(mock_load_url, mock_connect_to_sqlite, client):
    try:
        test_sqlite_file = f"test-{uuid.uuid4()}-{TEST_SQLITE_FILE}"
        conn = connect_to_sqlite(test_sqlite_file)

        with patch("app.connect_to_sqlite") as mock_connect_to_sqlite:
            mock_connect_to_sqlite.return_value = conn

            # Create a empty config in sites/<SITENAME>.conf and fill it with bad data
            Path(TEST_SITE_PATH).touch()
            example_content = """
    server 256.142.0.51:14041;
    server 256.200.0.23:14041;
    server 256.200.0.22:14041;
    server 256.142.0.50:14041;
    """
            with open(TEST_SITE_PATH, "w") as f:
                f.write(example_content)  # Write bad data to the file

            # Mock the decorators to bypass them
            with patch("app.populate_variables") as mock_populate_variables:
                mock_populate_variables.return_value = (
                    lambda x: x
                )  # Bypass the decorator

                with patch("app.confirm_token_matches") as mock_confirm_token_matches:
                    mock_confirm_token_matches.return_value = True
                    mock_load_url.side_effect = mock_load_url_fn

                    # confirm fake config file exists
                    assert Path(TEST_SITE_PATH).exists()

                    # Confirm file is empty
                    assert Path(TEST_SITE_PATH).stat().st_size > 0

                    # Assert sqlite is empty
                    rows = read_from_sqlite(conn, TEST_SITE_NAME)
                    assert len(rows) == 0

                    # Send a POST request to the /update route
                    response = client.post(
                        "/update",
                        json={
                            "site": TEST_SITE_NAME,
                            "serverip": TEST_SITE_IP,
                            "token": "123",
                        },
                    )

                    # Assert that the response is as expected
                    assert response.status_code == 200

                    rows = read_from_sqlite(conn, TEST_SITE_NAME)
                    assert len(rows) == 1

                    response = client.post(
                        "/regen",
                        json={"site": TEST_SITE_NAME, "token": "123"},
                    )

                    # Assert TEST_SITE_PATH is not empty
                    assert Path(TEST_SITE_PATH).stat().st_size > 0

                    # Assert site path has the correct layout
                    with open(TEST_SITE_PATH, "r") as f:
                        content = f.read()
                        assert (
                            "server {}:{}".format(TEST_SITE_IP, TEST_GUNICORN_PORT)
                            in content
                        )

    finally:
        Path(test_sqlite_file).unlink(missing_ok=True)
        Path(TEST_SITE_PATH).unlink(missing_ok=True)


def test_index(client):
    response = client.get("/")
    assert response.data == b"Hello, ItsADash.work!"
