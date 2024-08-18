import os

from config import APP_NAME
from config import WELDER_TYPE

# pwd = os.path.dirname(os.path.abspath(__file__))
pwd = os.getcwd()
print("your working directory: {}".format(pwd))
with open("sysctl/{}-{}.service".format(WELDER_TYPE, APP_NAME), "w+t") as file:
    file.write("[Unit]\n")
    file.write("Description=Weight Tracking Service for {} Welder\n".format(WELDER_TYPE))
    file.writelines(["Wants=network.target systemd-networkd-wait-online.service\n", "After=network.target\n", "StartLimitIntervalSec=500\n", "StartLimitBurst=5\n", "[Service]\n", "Restart=on-failure\n", "RestartSec=5s\n"])
    file.write("WorkingDirectory={}\n".format(pwd))
    file.writelines(["ExecStart=/bin/bash bin/launcher.sh\n", "[Install]\n", "WantedBy=multi-user.target\n"])