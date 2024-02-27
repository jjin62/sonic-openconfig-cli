## High level design
see [here](doc/openconfig-cli-autogen-HLD.md).

## Development environment

You need to have ```j2cli```, ```Jinja2```, ```libyang```, ```libyang-python``` and ```docker``` installed.

###
Install libyang
```
git clone https://github.com/CESNET/libyang.git
cd libyang
mkdir build; cd build
cmake ..
make
sudo make install
```

###
Install libyang-python
```
sudo apt-get install python3-dev gcc python3-cffi
pip install pyproject-toml
pip install libyang
```

###
Install j2cli
```
pip install j2cli
```

###
Install Jinja2
```
pip install Jinja2
```

###
Build SONiC SDK docker images using sonic-buildimage repository:

```
$ git clone https://github.com/sonic-net/sonic-buildimage
$ cd sonic-buildimage
$ make init
$ make configure PLATFORM=generic
$ make target/sonic-sdk.gz target/sonic-sdk-buildenv.gz
```

###
Load into docker:

```
$ docker load < target/sonic-sdk.gz
$ docker load < target/sonic-sdk-buildenv.gz
```

## Build

To build SONiC Package:

```
$ make
```

In case you want to override version pass it as parameter to make:

```
$ make VERSION=1.0.0
```

## Publish via DockerHub

Login to DockerHub user `molex1/abc123mbox` using ```docker login``` command and push the image to your repository.

```
docker tag openconfig-cli:1.0.0 molex1/openconfig-cli:1.0.0
docker push molex1/openconfig-cli:1.0.0
```

## Install on the switch

Add repository entry to the database:

```
admin@sonic:~$ sudo sonic-package-manager repository add openconfig-cli \
    molex1/openconfig-cli \
    --description="SONiC application extension for CLI based on openconfig yang model" \
    --default-reference=1.0.0
```

Install the package:

```
admin@sonic:~$ sudo sonic-package-manager install openconfig-cli
```

For developer convenience or for unpublished SONiC packages, it is possible to install the extension from a Docker image tarball.

```
admin@sonic:~$ ls openconfig-cli.gz
openconfig-cli.gz
admin@sonic:~$ sudo sonic-package-manager install --from-tarball openconfig-cli.gz
```
## Reference link of building SONiC image with this application

Create a file rules/openconfig-cli.mk.
```
# rules to define remote packages that need to be installed
# during SONiC image build

DOCKER_OPENCONFIG_CLI = docker-openconfig-cli
$(DOCKER_OPENCONFIG_CLI)_REPOSITORY = molex1/docker-openconfig-cli
$(DOCKER_OPENCONFIG)_VERSION = 1.0.0
SONIC_PACKAGES += $(DOCKER_OPENCONFIG_CLI)
$(DOCKER_OPENCONFIG_CLI)_DEFAULT_FEATURE_STATE_ENABLED = y
```
See [sonic application extension](https://github.com/sonic-net/SONiC/blob/master/doc/sonic-application-extension/sonic-application-extension-guide.md) for details.
