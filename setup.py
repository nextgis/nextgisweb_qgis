import io
from setuptools import setup, find_packages

with io.open('VERSION', 'r') as fd:
    VERSION = fd.read().rstrip()

requires = (
    'nextgisweb>=3.7.0.dev1',
)

entry_points = {
    'nextgisweb.packages': [
        'nextgisweb_qgis = nextgisweb_qgis:pkginfo',
    ],
    'nextgisweb.amd_packages': [
        'nextgisweb_qgis = nextgisweb_qgis:amd_packages',
    ],
}

setup(
    name='nextgisweb_qgis',
    version=VERSION,
    python_requires="<3",
    description="",
    long_description="",
    classifiers=[],
    keywords='',
    author='',
    author_email='',
    url='',
    license='',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    include_package_data=True,
    zip_safe=False,
    install_requires=requires,
    entry_points=entry_points,
)
