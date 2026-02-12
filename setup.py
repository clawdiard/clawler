from setuptools import setup, find_packages

setup(
    name="clawler",
    version="1.8.0",
    description="Advanced news crawling service — no API keys required",
    author="Clawdia @ OpenClaw",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "feedparser>=6.0.0",
        "python-dateutil>=2.8.0",
        "rich>=13.0.0",
        "pyyaml>=6.0.0",
    ],
    entry_points={
        "console_scripts": [
            "clawler=clawler.cli:main",
        ],
    },
    python_requires=">=3.9",
)
