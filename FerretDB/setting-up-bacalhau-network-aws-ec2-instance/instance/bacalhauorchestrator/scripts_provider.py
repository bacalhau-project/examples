import os

from util.scripts_provider import ScriptsProvider


class BacalhauorchestratorScriptsProvider(ScriptsProvider):

    def _file_path(self, *path_parts):
        return os.path.join(os.path.dirname(__file__), '.', *path_parts)
