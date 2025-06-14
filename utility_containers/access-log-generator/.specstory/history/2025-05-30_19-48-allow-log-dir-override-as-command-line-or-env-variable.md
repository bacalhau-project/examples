<!-- Generated by SpecStory -->

# Allow LOG_DIR_OVERRIDE as command line or env variable (2025-05-30 12:48:41)

_**User**_

make it so that LOG_DIR_OVERRIDE can be set as a command line argument OR an environment variable to override what is set in the config file.

---

_**Assistant**_



---

Okay, I'll update the script to allow `LOG_DIR_OVERRIDE` to be set as an environment variable, with the command-line argument taking precedence if both are provided.

I will modify the `main` function to check for the `LOG_DIR_OVERRIDE` environment variable and use its value if the `--log-dir-override` command-line argument is not set. The logic will prioritize the command-line argument, then the environment variable, and finally the configuration file.

---

```diff
      all_initial_messages = pre_log_messages + messages_from_load_config
  
-     # Override log directory if specified -- this must happen *after* load_config has populated config['output']
+     # Determine the log directory override
+     log_dir_override_value = None
+     override_source = None
+ 
      if args.log_dir_override:
-         # This message will be logged after logger setup
+         log_dir_override_value = args.log_dir_override
+         override_source = "command-line argument"
+     else:
+         env_log_dir_override = os.environ.get("LOG_DIR_OVERRIDE")
+         if env_log_dir_override:
+             log_dir_override_value = env_log_dir_override
+             override_source = "environment variable LOG_DIR_OVERRIDE"
+ 
+     # Override log directory if specified by CLI or environment variable
+     if log_dir_override_value:
          log_override_message = (
              "info",
-             f"Overriding log directory with: {args.log_dir_override}",
+             f"Overriding log directory with: {log_dir_override_value} (from {override_source})",
          )
          all_initial_messages.append(log_override_message)
          # Ensure 'output' key exists, though load_config should have created it or errored.
          if "output" not in config:
              config["output"] = {}
-         config["output"]["directory"] = args.log_dir_override
+         config["output"]["directory"] = log_dir_override_value
  
      # Initialize logging with possibly overridden directory and rotation settings
```

---

The script has been updated. Now, the log directory can be overridden using the `LOG_DIR_OVERRIDE` environment variable. If both the `--log-dir-override` command-line argument and the `LOG_DIR_OVERRIDE` environment variable are set, the command-line argument will take precedence.

---

_**User**_

update the tests to test for either/or and/or both.

---

_**Assistant**_



---

I'll start by looking for existing test files.

---

<details>
            <summary>Listed current directory • **25** results</summary>
        
| Name |
|-------|
| 📄 `access-log-generator.py` |
| 📁 `logs` |
| 📄 `README.md` |
| 📄 `run-docker.sh` |
| 📄 `docker-compose.yml` |
| 📄 `Dockerfile` |
| 📁 `config` |
| 📄 `CLAUDE.md` |
| 📄 `pyproject.toml` |
| 📄 `.gitignore` |
| 📄 `pytest.ini` |
| 📁 `tests` |
| 📁 `__pycache__` |
| 📁 `.pytest_cache` |
| 📄 `uv.lock` |
| 📄 `log_schema_outputter.py` |
| 📄 `.cursorindexingignore` |
| 📁 `.cursor` |
| 📁 `.claude` |
| 📄 `build.sh` |
| 📁 `.cspell` |
| 📁 `.venv` |
| 📁 `.specstory` |
| 📄 `.envrc` |
| 📄 `clean_words_alpha.txt` |

</details>

---

It looks like there's a `tests/` directory. I'll examine its contents to see where to add the new tests.

---

<details>
            <summary>Listed directory tests • **3** results</summary>
        
| Name |
|-------|
| 📁 `__pycache__` |
| 📄 `test_integration.py` |
| 📄 `test_access_log_generator.py` |

</details>

---

Okay, it seems like `test_access_log_generator.py` is the most relevant file for these tests. I'll add tests to this file to cover the following scenarios:

1.  `--log-dir-override` command-line argument is used.
2.  `LOG_DIR_OVERRIDE` environment variable is used.
3.  Both `--log-dir-override` and `LOG_DIR_OVERRIDE` are used (command-line should take precedence).
4.  Neither is used (config file value should be used).

I'll start by reading the contents of `test_access_log_generator.py` to understand its current structure and how to best integrate the new tests.

---

Read file: tests/test_access_log_generator.py

---

I've reviewed the `test_access_log_generator.py` file. It uses the `unittest` framework and has several test classes. I'll create a new test class, `TestLogDirectoryOverride`, to house the tests for the log directory override functionality. This class will include tests for the different scenarios mentioned earlier.

Here's the plan:
1.  Create a new class `TestLogDirectoryOverride(unittest.TestCase)`.
2.  Add a `setUp` method to this class to:
    *   Create a temporary directory for logs.
    *   Create a dummy `config.yaml` file with a default log directory.
    *   Import necessary modules and functions from `access-log-generator.py` (similar to how `TestConfigValidation` does it).
3.  Add a `tearDown` method to clean up the temporary directory and dummy config file.
4.  Add test methods for each scenario:
    *   `test_cli_override`: Mocks `sys.argv` to simulate command-line argument.
    *   `test_env_override`: Mocks `os.environ` to simulate environment variable.
    *   `test_cli_takes_precedence`: Mocks both `sys.argv` and `os.environ`.
    *   `test_config_default`: No mocks for override, uses config file default.
5.  In each test method, call the `main()` function of `access-log-generator.py` and assert that the `config['output']['directory']` is set to the expected path. I'll use `unittest.mock.patch` to spy on the `setup_logging` function to check the `output_dir` passed to it, or inspect the `config` object if it's easier to access after `main()` runs.

I'll now implement these tests.

---

