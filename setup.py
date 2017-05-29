from setuptools import find_packages, setup
from io import open


setup(
    name='camel',
    version='0.1.2',
    description="Python serialization for adults",
    long_description=open('README.txt', encoding='utf8').read(),
    url="https://github.com/eevee/camel",
    author="Eevee (Lexy Munroe)",
    author_email="eevee.camel@veekun.com",
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    packages=find_packages(),
    install_requires=['pyyaml'],
    tests_require=['pytest'],
)
