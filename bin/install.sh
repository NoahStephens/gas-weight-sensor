#!/bin/bash

# Installs a system manager service



if [ -n "$ZSH_VERSION" ]; then
  echo "zsh: ${ZSH_VERSION}"
  PWD="$(cd "$(dirname "${0}")" && pwd)/.."
elif [ -n "$BASH_VERSION" ]; then
  echo "bash: ${BASH_VERSION}"
  PWD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
fi

echo "Creating and installing a systemctl service"
# Only raspberry pi supported
if [[ "$OSTYPE" == "linux-gnueabi"* ]]; then
  echo "linux Supported"
else
  echo $OSTYPE "Unsupported"
  echo "Exiting..."
  exit
fi

PYTHONPATH=$PWD $PWD/venv/bin/python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Build system control serice
PYTHONPATH=$PWD $PWD/venv/bin/python sysctl/build.py
deactivate

# Install Service (Must be sudoer) also systemctl isn't supported by MacOS
for file in sysctl/*.service; do
  echo "copying " $file "to /etc/systemd/system"
  cp $file /etc/systemd/system/
  systemctl deamon-reload
  systemctl start "${file##*/}"
done