import sys
from unittest.mock import MagicMock

# Create a mock pyaudio module
mock_pyaudio = MagicMock()
mock_pyaudio.__version__ = "0.2.14"
mock_pyaudio.paInt16 = 8
mock_pyaudio.paContinue = 0
mock_pyaudio.paComplete = 1
mock_pyaudio.paAbort = 2

class PyAudio:
    def __init__(self, **kwargs):
        pass
    def open(self, **kwargs):
        return MagicMock()
    def terminate(self):
        pass
    def get_device_count(self):
        return 0
    def get_device_info_by_index(self, index):
        return {}
    def get_default_input_device_info(self):
        return {}
    def get_default_output_device_info(self):
        return {}
    def get_host_api_count(self):
        return 0
    def get_host_api_info(self, index):
        return {}

mock_pyaudio.PyAudio = PyAudio

sys.modules["pyaudio"] = mock_pyaudio
