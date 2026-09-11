"""
download_statutes.py — Downloads Indian law statute PDFs from government sources
Run once before first boot: python download_statutes.py

All documents are from legislative.gov.in (public domain).
"""

import os
import urllib.request
from pathlib import Path

STATUTES_DIR = Path(__file__).parent / "data" / "statutes"
STATUTES_DIR.mkdir(parents=True, exist_ok=True)

# Public domain Indian law documents from legislative.gov.in
STATUTES = [
    {
        "name": "Indian_Contract_Act_1872.pdf",
        "url": "https://legislative.gov.in/sites/default/files/A1872-09.pdf",
        "description": "Indian Contract Act, 1872",
    },
    {
        "name": "Indian_Penal_Code_1860.pdf",
        "url": "https://legislative.gov.in/sites/default/files/A1860-45.pdf",
        "description": "Indian Penal Code, 1860",
    },
    {
        "name": "Arbitration_Conciliation_Act_1996.pdf",
        "url": "https://legislative.gov.in/sites/default/files/A1996-26.pdf",
        "description": "Arbitration and Conciliation Act, 1996",
    },
    {
        "name": "Code_of_Civil_Procedure_1908.pdf",
        "url": "https://legislative.gov.in/sites/default/files/A1908-05.pdf",
        "description": "Code of Civil Procedure, 1908",
    },
    {
        "name": "Consumer_Protection_Act_2019.pdf",
        "url": "https://legislative.gov.in/sites/default/files/A2019-35.pdf",
        "description": "Consumer Protection Act, 2019",
    },
    {
        "name": "Specific_Relief_Act_1963.pdf",
        "url": "https://legislative.gov.in/sites/default/files/A1963-47.pdf",
        "description": "Specific Relief Act, 1963",
    },
    {
        "name": "Sale_of_Goods_Act_1930.pdf",
        "url": "https://legislative.gov.in/sites/default/files/A1930-03.pdf",
        "description": "Sale of Goods Act, 1930",
    },
]


def download_statutes():
    print(f"Downloading {len(STATUTES)} Indian law statutes to {STATUTES_DIR}/\n")
    for statute in STATUTES:
        dest = STATUTES_DIR / statute["name"]
        if dest.exists():
            print(f"  [skip]  {statute['description']} (already downloaded)")
            continue
        try:
            print(f"  ↓  {statute['description']}  …", end=" ", flush=True)
            urllib.request.urlretrieve(statute["url"], dest)
            size_kb = dest.stat().st_size // 1024
            print(f"✓ {size_kb} KB")
        except Exception as e:
            print(f"✗ FAILED: {e}")
            print(f"     Manual download: {statute['url']}")

    print("\nDone! Place any additional PDFs in data/statutes/ before starting the server.")


if __name__ == "__main__":
    download_statutes()
