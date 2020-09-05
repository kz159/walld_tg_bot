all: install

install:
	pip3 install -r requirements

install-dev:
	pip3 install -r requirements-dev.txt
	pip3 install -e ../db