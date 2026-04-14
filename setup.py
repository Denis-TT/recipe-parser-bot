from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="recipe-parser-bot",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Telegram бот для парсинга и нормализации кулинарных рецептов",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/recipe-parser-bot",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    python_requires=">=3.8",
    install_requires=[
        "python-telegram-bot>=20.0",
        "aiohttp>=3.8.0",
        "beautifulsoup4>=4.11.0",
        "readability-lxml>=0.8.1",
        "lxml>=4.9.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "recipe-bot=run:main",
        ],
    },
)