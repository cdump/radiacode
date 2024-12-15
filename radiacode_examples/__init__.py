"""
RadiaCode Examples

This package contains example scripts for using the RadiaCode library.

Available examples:
- basic: A simple command-line interface for RadiaCode
- show_spectrum:   Reads spectrum data from Radiacode 102 device, displays and 
                   stores the count rate history and the spectrum of deposited energies.  
- webserver: A web-based interface for RadiaCode data
- webserver_logger: ...with rotating file logging
- radiacode_exporter: Stores radiacode data in a Prometheus database
- narodmon: Script for sending data to the narodmon.ru monitoring project

To run an example, use:
python -m radiacode_examples.<example_name>

For instance:
python -m radiacode_examples.webserver
"""

__all__ = ['basic', 'show_spectrum', 'webserver', 'webserver_logger', 'radiacode_exporter', 'narodmon']