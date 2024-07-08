#!/bin/bash
# Starts generated and installed service using "bin/install.sh"


# Install Service (Must be sudoer) also systemctl isn't supported by MacOS
for file in sysctl/*.service; do
  echo "copying " $file "to /etc/systemd/system"
  cp $file /etc/systemd/system/
  systemctl deamon-reload
  systemctl start "${file##*/}"
done