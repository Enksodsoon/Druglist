.PHONY: setup queue download dailymed manifest batches all

setup:
	python scripts/00_setup_folders.py

queue:
	python scripts/01_build_source_queue.py --links-xlsx druglist_all_download_links_2026-05-13.xlsx

download:
	python scripts/02_download_http_sources.py --queue reports/source_download_queue.csv

dailymed:
	python scripts/03_dailymed_resolver.py --links-xlsx druglist_all_download_links_2026-05-13.xlsx

manifest:
	python scripts/04_build_manifest.py --root imports/accepted_evidence

batches:
	python scripts/05_prepare_chatgpt_batches.py --links-xlsx druglist_all_download_links_2026-05-13.xlsx --batch-size 25

all: setup queue download dailymed manifest batches
