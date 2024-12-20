from edit_color import check_color, edit_color


def test_check_color_valid(mocker):
    # Test for a valid color
    assert check_color("#FFFFFF") is True


def test_check_color_invalid(mocker):
    # Test for an invalid color
    assert check_color("invalid_color") is False


def test_edit_color(mocker):
    # Mocking os.path.exists to always return True
    mocker.patch("os.path.exists", return_value=True)
    # Mocking the open function to simulate file writing
    mock_open = mocker.mock_open()
    mocker.patch("builtins.open", mock_open)

    edit_color("color.txt", "#FFFFFF")

    # Assert if open was called with the correct parameters
    mock_open.assert_called_once_with("color.txt", "w")
    # Assert if write was called with the correct parameter
    mock_open().write.assert_called_once_with("#FFFFFF\n")


# Write unit tests to validate file existence
def test_edit_color_file_not_found(mocker):
    # Mocking os.path.exists to always return False
    mocker.patch("os.path.exists", return_value=False)
    # Mocking the open function to simulate file writing
    mock_open = mocker.mock_open()
    mocker.patch("builtins.open", mock_open)

    # Mock print function
    mock_print = mocker.patch("builtins.print")

    # Catch the SystemExit exception
    try:
        edit_color("color.txt", "#FFFFFF")
    except SystemExit as e:
        # If SystemExit is raised, then the test should check the printed message to the mocked print function and exit code
        assert "color.txt file not found." in mock_print.call_args_list[0][0][0]

        assert e.code == 1

    # Assert if open was not called
    mock_open.assert_not_called()


# Additional tests can be written for other scenarios, such as valid color but file not found, etc.
