import setuptools

with open("README.md", "r") as fh:
  long_description = fh.read()

setuptools.setup(
    name='py-moc-mbueti',
    version='0.0.1',
    description="A simple model suite for the MOC",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://pymoc.github.io',
    package_dir={'pymoc': 'src'},
    packages=['pymoc', 'pymoc.modules', 'pymoc.utils'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)