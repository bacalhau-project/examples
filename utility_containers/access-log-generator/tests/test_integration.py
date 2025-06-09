#!/usr/bin/env python3
"""Integration test for access-log-generator.py"""

import unittest
import tempfile
import shutil
import os
import subprocess
import time
import re
import pytest


@pytest.mark.integration
class TestAccessLogGeneratorIntegration(unittest.TestCase):
    """Integration tests that actually run the generator"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, 'test_config.yaml')
        
        # Create a minimal test config
        config_content = """
output:
  directory: {output_dir}
  rate: 10
  debug: false
  pre_warm: false
  log_rotation:
    enabled: false

state_transitions:
  START:
    LOGIN: 0.7
    DIRECT_ACCESS: 0.3
  LOGIN:
    BROWSING: 0.9
    ABANDON: 0.1
  DIRECT_ACCESS:
    BROWSING: 0.8
    LEAVE: 0.2
  BROWSING:
    LOGOUT: 0.4
    ABANDON: 0.3
    ERROR: 0.05
    BROWSING: 0.25

navigation:
  index:
    "/about": 0.3
    "/products": 0.5
    "/search": 0.2

error_rates:
  global_500_rate: 0.01
  product_404_rate: 0.05

session:
  min_browsing_duration: 1
  max_browsing_duration: 5
  min_page_view_interval: 0.1
  max_page_view_interval: 0.5

traffic_patterns:
  - time: "0-23"
    multiplier: 1.0
""".format(output_dir=self.temp_dir)
        
        with open(self.config_file, 'w') as f:
            f.write(config_content)
        
        # NCSA log pattern for validation
        self.ncsa_pattern = re.compile(
            r'^(\S+) (\S+) (\S+) \[([\w:/]+\s[+\-]\d{4})\] '
            r'"(\S+) (\S+) (\S+)" (\d{3}) (\d+|-) '
            r'"([^"]*)" "([^"]*)"$'
        )
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)
    
    def test_generator_produces_valid_logs(self):
        """Test that the generator produces valid NCSA format logs"""
        # Run the generator for a short time
        generator_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            'access-log-generator.py'
        )
        
        # Start the generator process
        process = subprocess.Popen(
            ['python', generator_path, self.config_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Let it run for 3 seconds
        time.sleep(3)
        
        # Terminate the process
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        
        # Print any errors for debugging
        if stderr:
            print(f"Generator stderr: {stderr.decode()}")
        
        # Check that log files were created
        access_log = os.path.join(self.temp_dir, 'access.log')
        error_log = os.path.join(self.temp_dir, 'error.log')
        system_log = os.path.join(self.temp_dir, 'system.log')
        
        self.assertTrue(os.path.exists(access_log), "access.log not created")
        self.assertTrue(os.path.exists(error_log), "error.log not created")
        self.assertTrue(os.path.exists(system_log), "system.log not created")
        
        # Validate access.log entries
        valid_lines = 0
        invalid_lines = []
        
        with open(access_log, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:  # Skip empty lines
                    if self.ncsa_pattern.match(line):
                        valid_lines += 1
                    else:
                        invalid_lines.append((line_num, line))
        
        # Should have generated some logs
        self.assertGreater(valid_lines, 0, "No valid log lines generated")
        
        # All lines should be valid NCSA format
        if invalid_lines:
            msg = "Invalid NCSA format lines found:\n"
            for line_num, line in invalid_lines[:5]:  # Show first 5
                msg += f"  Line {line_num}: {line}\n"
            self.fail(msg)
        
        print(f"✓ Generated {valid_lines} valid NCSA format log entries")
    
    def test_log_content_variety(self):
        """Test that generated logs have variety in content"""
        # Run the generator for a short time
        generator_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            'access-log-generator.py'
        )
        
        # Start the generator process
        process = subprocess.Popen(
            ['python', generator_path, self.config_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Let it run for 2 seconds
        time.sleep(2)
        
        # Terminate the process
        process.terminate()
        process.wait(timeout=5)
        
        # Analyze log variety
        access_log = os.path.join(self.temp_dir, 'access.log')
        
        ips = set()
        paths = set()
        status_codes = set()
        user_agents = set()
        
        with open(access_log, 'r') as f:
            for line in f:
                match = self.ncsa_pattern.match(line.strip())
                if match:
                    ip, _, user, timestamp, method, path, protocol, status, size, referrer, user_agent = match.groups()
                    ips.add(ip)
                    paths.add(path)
                    status_codes.add(status)
                    user_agents.add(user_agent)
        
        # Should have variety in content
        self.assertGreater(len(ips), 1, "Should have multiple IP addresses")
        self.assertGreater(len(paths), 1, "Should have multiple paths")
        self.assertGreater(len(status_codes), 1, "Should have multiple status codes")
        self.assertGreater(len(user_agents), 1, "Should have multiple user agents")
        
        print(f"✓ Log variety: {len(ips)} IPs, {len(paths)} paths, "
              f"{len(status_codes)} status codes, {len(user_agents)} user agents")


if __name__ == '__main__':
    unittest.main()