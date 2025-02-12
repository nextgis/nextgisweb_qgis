import transaction

from nextgisweb.env import Component
from nextgisweb.lib.config import Option, OptionAnnotations
from nextgisweb.lib.logging import logger

import qgis_headless as qh

from .model import QgisRasterStyle, QgisVectorStyle


class QgisComponent(Component):
    def initialize(self):
        super(QgisComponent, self).initialize()
        self._qgis_initialized = False

    def configure(self):
        super(QgisComponent, self).configure()

    def setup_pyramid(self, config):
        super(QgisComponent, self).setup_pyramid(config)

        from . import api, view

        api.setup_pyramid(self, config)
        view.setup_pyramid(self, config)

    def sys_info(self):
        return (("QGIS", qh.get_qgis_version()),)

    def qgis_init(self):
        if not self._qgis_initialized:
            # Set up logging level before initialization. Default is CRITICAL in
            # production mode and INFO in development mode.
            logging_level = self.options["logging_level"]
            if logging_level is None:
                logging_level = "INFO" if self.env.core.debug else "CRITICAL"
            else:
                logging_level = logging_level.upper()
            qh.set_logging_level(getattr(qh.LogLevel, logging_level))

            qh.init([])

            if "svg_path" in self.options:
                qh.set_svg_paths(self.options["svg_path"])
            self._qgis_initialized = True

    def maintenance(self):
        with transaction.manager:
            for cls in (QgisRasterStyle, QgisVectorStyle):
                for resource in cls.filter_by(qgis_scale_range_cache=None):
                    try:
                        resource._update_scale_range_cache()
                    except qh.StyleValidationError as e:
                        logger.warning(f"QGIS style (id={resource.id}) error: {e}")

    # fmt: off
    option_annotations = OptionAnnotations((
        Option("svg_path", list, doc="Search paths for SVG icons."),
        Option("default_style", bool, default=True),
        Option("logging_level", str, default=None),
        Option("test.qgis_headless_path", str, default=None, doc=(
            "Path to QGIS headless package for loading test data.")),
    ))
    # fmt: on
