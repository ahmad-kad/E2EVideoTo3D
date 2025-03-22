#!/usr/bin/env python3
"""
E2E3D Test Runner

This script provides a simple interface to run different types of tests for the E2E3D project.
It uses pytest as the underlying test framework.

Usage:
  python run_tests.py [options]

Options:
  --unit        Run only unit tests
  --integration Run only integration tests
  --all         Run all tests (default)
  --verbose     Show verbose output
  --junit       Generate JUnit XML reports
  --html        Generate HTML reports
  --component=COMPONENT Run tests for a specific component (api, metrics, reconstruction, storage)
  
Examples:
  python run_tests.py --unit --component=api
  python run_tests.py --all --verbose --html
"""

import sys
import os
import argparse
import subprocess

def parse_args():
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser(description='Run E2E3D tests')
    
    # Test type options
    test_type = parser.add_mutually_exclusive_group()
    test_type.add_argument('--unit', action='store_true', help='Run only unit tests')
    test_type.add_argument('--integration', action='store_true', help='Run only integration tests')
    test_type.add_argument('--all', action='store_true', help='Run all tests (default)')
    
    # Output options
    parser.add_argument('--verbose', action='store_true', help='Show verbose output')
    parser.add_argument('--junit', action='store_true', help='Generate JUnit XML reports')
    parser.add_argument('--html', action='store_true', help='Generate HTML reports')
    
    # Component options
    parser.add_argument('--component', type=str, help='Run tests for a specific component')
    
    args = parser.parse_args()
    
    # Set default
    if not (args.unit or args.integration or args.all):
        args.all = True
    
    return args

def run_tests(args):
    """Run the tests based on the command line arguments."""
    # Get the absolute path to the tests directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Base command
    cmd = ['pytest']
    
    # Add verbosity
    if args.verbose:
        cmd.append('-v')
    
    # Add report options
    if args.junit:
        cmd.extend(['--junitxml', os.path.join(script_dir, 'test-results.xml')])
    
    if args.html:
        cmd.extend(['--html', os.path.join(script_dir, 'test-report.html'), '--self-contained-html'])
    
    # Add test paths based on options
    if args.all:
        cmd.append(script_dir)
    elif args.unit:
        if args.component:
            cmd.append(os.path.join(script_dir, f'unit/{args.component}/'))
        else:
            cmd.append(os.path.join(script_dir, 'unit/'))
    elif args.integration:
        if args.component:
            # Find integration tests related to the component
            component_tests = []
            integration_dir = os.path.join(script_dir, 'integration/')
            for root, dirs, files in os.walk(integration_dir):
                for dir_name in dirs:
                    if args.component in dir_name:
                        component_tests.append(os.path.join(root, dir_name))
            
            if component_tests:
                cmd.extend(component_tests)
            else:
                print(f"No integration tests found for component '{args.component}'")
                return 1
        else:
            cmd.append(os.path.join(script_dir, 'integration/'))
    
    # Run the tests
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode

if __name__ == '__main__':
    args = parse_args()
    sys.exit(run_tests(args)) 