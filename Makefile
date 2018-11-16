SRC := src


install:
	poetry install


init:
	sed -i "s/{{NAME}}/$${NAME:-$$(basename $$(pwd))}/" pyproject.toml
	sed -i "s/{{AUTHOR}}/$${AUTHOR:-$$(git config user.name) <$$(git config user.email)>}/" pyproject.toml


lab:
	poetry run jupyter lab .


validate:
	$(MAKE) lint && \
	$(MAKE) typecheck && \
	$(MAKE) test


lint:
	@echo "\n\n" ======== $@ ========= "\n\n"
	poetry run flake8


typecheck:
	@echo "\n\n" ======== $@ ========= "\n\n"
	poetry run mypy $(SRC)


test:
	@echo "\n\n" ======== $@ ========= "\n\n"
	poetry run pytest


clean:
	find . -type d | grep -P '(\.mypy_cache$$|__pycache__$$|\.pytest_cache$$)' | xargs rm -rf
