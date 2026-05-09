#!/usr/bin/env python3
from gold_common import build_rx_eligibility, ensure_dirs

if __name__ == "__main__":
    ensure_dirs()
    print(build_rx_eligibility())
