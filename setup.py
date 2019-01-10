import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="crawler",
    version="0.1.0",
    author="Alexandr Arnautov",
    author_email="flo0.webmaster@gmail.com",
    description="A set of tools to develop web scrapers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/flo0web/crawler",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
