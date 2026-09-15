from nextgisweb.env import Component
from nextgisweb.lib.config import Option, OptionAnnotations

import qgis_headless as qh


class QgisComponent(Component):
    def initialize(self):
        super().initialize()
        self._qgis_initialized = False

    def setup_pyramid(self, config):
        from . import api, view

        api.setup_pyramid(self, config)
        view.setup_pyramid(self, config)

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

    # fmt: off
    option_annotations = OptionAnnotations((
        Option("svg_path", list, doc="Search paths for SVG icons."),
        Option("default_style", bool, default=True),
        Option("logging_level", str, default=None),
        Option("test.qgis_headless_path", str, default=None, doc=(
            "Path to QGIS headless package for loading test data.")),
    ))
    # fmt: on
