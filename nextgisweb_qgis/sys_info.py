from nextgisweb.core.sys_info import SysInfoResult, sys_info_hook

import qgis_headless as qh

from .component import QgisComponent


@sys_info_hook()
def sys_info(comp: QgisComponent) -> SysInfoResult:
    yield (
        "QGIS",
        qh.get_qgis_version(),
    )
