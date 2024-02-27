.ONESHELL:
SHELL = /bin/bash
.SHELLFLAGS += -e

VERSION=1.0.0
CONTAINER_NAME=openconfig-cli

IMAGE_ID := $(shell docker images -q $(CONTAINER_NAME):$(VERSION))

all:
	python ./build.py $(VERSION) $(CONTAINER_NAME)

ifneq ($(strip $(IMAGE_ID)),)
	docker rmi $(IMAGE_ID)
endif

	DOCKER_BUILDKIT=1 docker build . -t $(CONTAINER_NAME):$(VERSION)
