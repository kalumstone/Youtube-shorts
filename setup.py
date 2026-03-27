"""Optional setup script for the YouTube Shorts bot."""

from setuptools import setup, find_packages

setup(
    name="youtube-shorts-bot",
    version="1.0.0",
    description="Automated YouTube Shorts creation and publishing bot",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=open("requirements.txt").read().splitlines(),
    entry_points={
        "console_scripts": [
            "shorts-bot=main:cli",
        ],
    },
)
