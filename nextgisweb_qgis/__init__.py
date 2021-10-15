import qgis_headless

from nextgisweb.lib.config import Option, OptionAnnotations
from nextgisweb.component import Component

from .model import Base


class QgisComponent(Component):
    identity = 'qgis'
    metadata = Base.metadata

    def initialize(self):
        super(QgisComponent, self).initialize()
        self._qgis_initialized = False

    def configure(self):
        super(QgisComponent, self).configure()

    def setup_pyramid(self, config):
        super(QgisComponent, self).setup_pyramid(config)

        from . import view, api
        api.setup_pyramid(self, config)
        view.setup_pyramid(self, config)

    def sys_info(self):
        return (
            ("QGIS", qgis_headless.get_qgis_version()),
        )

    def qgis_init(self):
        if not self._qgis_initialized:
            # Set up logging level before initialization. Default is CRITICAL in
            # production mode and INFO in development mode.
            logging_level = self.options['logging_level']
            if logging_level is None:
                logging_level = 'INFO' if self.env.core.debug else 'CRITICAL'
            else:
                logging_level = logging_level.upper()
            qgis_headless.set_logging_level(getattr(
                qgis_headless.LogLevel, logging_level))

            qgis_headless.init([])

            if 'svg_path' in self.options:
                qgis_headless.set_svg_paths(self.options['svg_path'])
            self._qgis_initialized = True

    option_annotations = OptionAnnotations((
        Option('svg_path', list, doc="Search paths for SVG icons."),
        Option('logging_level', str, default=None),
    ))


def pkginfo():
    return dict(components=dict(qgis="nextgisweb_qgis"))


def amd_packages():
    return ((
        'ngw-qgis', 'nextgisweb_qgis:amd/ngw-qgis'
    ),)
