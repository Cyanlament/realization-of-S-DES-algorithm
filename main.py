"""Start the desktop application: python main.py."""
import argparse

from sdes.gui import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="S-DES desktop application")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    run(smoke_test=parser.parse_args().smoke_test)
