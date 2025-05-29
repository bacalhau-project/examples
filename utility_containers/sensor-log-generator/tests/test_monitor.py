import json
import threading
import time
from unittest.mock import Mock, patch

import pytest

from src.monitor import MonitoringServer


class TestMonitoringServer:
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_simulator = Mock()
        self.mock_simulator.running = True

    def test_init(self):
        """Test MonitoringServer initialization."""
        server = MonitoringServer(self.mock_simulator, host="127.0.0.1", port=8080)
        
        assert server.simulator == self.mock_simulator
        assert server.host == "127.0.0.1"
        assert server.port == 8080
        assert server.running is False

    @patch('src.monitor.HTTPServer')
    @patch('threading.Thread')
    def test_start_success(self, mock_thread, mock_http_server):
        """Test successful server start."""
        mock_server_instance = Mock()
        mock_http_server.return_value = mock_server_instance
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        server = MonitoringServer(self.mock_simulator, port=8080)
        server.start()
        
        assert server.running is True
        mock_http_server.assert_called_once()
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    @patch('src.monitor.HTTPServer', side_effect=Exception("Port in use"))
    def test_start_failure(self, mock_http_server):
        """Test server start failure."""
        server = MonitoringServer(self.mock_simulator, port=8080)
        
        with patch('src.monitor.logging.error') as mock_log_error:
            server.start()
            
        assert server.running is False
        mock_log_error.assert_called()

    def test_start_already_running(self):
        """Test starting server when already running."""
        server = MonitoringServer(self.mock_simulator, port=8080)
        server.running = True
        
        with patch('src.monitor.logging.warning') as mock_log_warning:
            server.start()
            
        mock_log_warning.assert_called_once()

    def test_stop_when_not_running(self):
        """Test stopping server when not running."""
        server = MonitoringServer(self.mock_simulator, port=8080)
        
        # Should not raise any errors
        server.stop()

    def test_stop_success(self):
        """Test successful server stop."""
        server = MonitoringServer(self.mock_simulator, port=8080)
        server.running = True
        server.server = Mock()
        
        server.stop()
        
        assert server.running is False
        server.server.shutdown.assert_called_once()
        server.server.server_close.assert_called_once()

    def test_stop_with_exception(self):
        """Test stopping server with exception."""
        server = MonitoringServer(self.mock_simulator, port=8080)
        server.running = True
        server.server = Mock()
        server.server.shutdown.side_effect = Exception("Stop error")
        
        with patch('src.monitor.logging.error') as mock_log_error:
            server.stop()
            
        mock_log_error.assert_called()

    def test_run_server_exception(self):
        """Test _run_server method with exception."""
        server = MonitoringServer(self.mock_simulator, port=8080)
        server.server = Mock()
        server.server.serve_forever.side_effect = Exception("Server error")
        server.running = True
        
        with patch('src.monitor.logging.error') as mock_log_error:
            server._run_server()
            
        assert server.running is False
        mock_log_error.assert_called()


class TestMonitoringRequestHandlerMethods:
    """Test specific methods of MonitoringRequestHandler without instantiation."""

    def test_format_bytes_function(self):
        """Test the byte formatting logic."""
        from src.monitor import MonitoringRequestHandler
        
        # Test with a mock instance
        handler = Mock()
        handler._format_bytes = MonitoringRequestHandler._format_bytes.__get__(handler)
        
        assert handler._format_bytes(0) == "0 B"
        assert handler._format_bytes(1024) == "1.00 KB"
        assert handler._format_bytes(1048576) == "1.00 MB"
        assert handler._format_bytes(1073741824) == "1.00 GB"

    def test_log_message_suppression(self):
        """Test log message filtering logic."""
        from src.monitor import MonitoringRequestHandler
        
        handler = Mock(spec=MonitoringRequestHandler)
        # Bind the actual method to our mock
        handler.log_message = MonitoringRequestHandler.log_message.__get__(handler)
        
        with patch('src.monitor.logging.info') as mock_log:
            # Should log successful requests to valid endpoints
            handler.log_message("%s %s %s", "GET /healthz HTTP/1.1", "200", "1234")
            mock_log.assert_called()
            
            mock_log.reset_mock()
            
            # Should not log requests to ignored paths
            handler.log_message("%s %s %s", "GET / HTTP/1.1", "200", "1234")
            mock_log.assert_not_called()
            
            # Should not log favicon requests
            handler.log_message("%s %s %s", "GET /favicon.ico HTTP/1.1", "200", "1234")
            mock_log.assert_not_called()

    def test_log_error_suppression(self):
        """Test that error logging is suppressed."""
        from src.monitor import MonitoringRequestHandler
        
        handler = Mock(spec=MonitoringRequestHandler)
        handler.log_error = MonitoringRequestHandler.log_error.__get__(handler)
        
        with patch('src.monitor.logging.error') as mock_log:
            handler.log_error("Test error message")
            mock_log.assert_not_called()


class TestMonitoringServerIntegration:
    """Integration tests for the monitoring server."""
    
    def test_server_integration_basic(self):
        """Test basic server creation and teardown."""
        mock_simulator = Mock()
        mock_simulator.running = True
        mock_simulator.database = Mock()
        mock_simulator.database.is_healthy.return_value = True
        mock_simulator.get_status.return_value = {"status": "running", "readings": 100}
        
        # Find an available port
        import socket
        sock = socket.socket()
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()
        
        server = MonitoringServer(mock_simulator, host="127.0.0.1", port=port)
        
        # Should initialize without errors
        assert server.simulator == mock_simulator
        assert server.port == port
        assert server.running is False