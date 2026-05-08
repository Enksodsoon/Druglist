.PHONY: verify

verify:
	python3 scripts/build_all.py
	python3 scripts/validate_engine.py
	python3 scripts/build_dist.py
	python3 scripts/ui_smoke_test.py
	python3 scripts/check_runtime_artifacts.py
