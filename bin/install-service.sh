#!/bin/bash

# Installs a system manager service (This is ment to be run as Susoer (sudo !!))



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

source venv/bin/activate

# Build system control serice
echo "building systemd script"
PYTHONPATH=$PWD $PWD/venv/bin/python sysctl/build.py
deactivate

# Install Service (Must be sudoer) also systemctl isn't supported by MacOS
for file in sysctl/*.service; do
  echo "copying " $file " to /etc/systemd/system"
  cp $file /etc/systemd/system/
  systemctl daemon-reload
  echo "starting service..."
  systemctl start "${file##*/}"
  systemctl enable "${file##*/}"
done