
from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='pyvidia',
    version='1.0.0b1',
    description='Nvidia driver version detector for Linux',
    long_description=long_description,
    url='https://github.com/ntpeters/pyvidia',
    author='Nate Peterson',
    author_email='ntpeters@mtu.edu',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Topic :: System :: Hardware :: Hardware Drivers',
        'Topic :: Utilities',
    ],

    keywords='nvidia linux driver',

    packages=find_packages(),

    install_requires=['beautifulsoup4', 'lxml'],

    package_data={
        'pyvidia': [],
    },

    entry_points={
        'console_scripts': [
            'pyvidia=pyvidia:__main',
        ],
    },
)
