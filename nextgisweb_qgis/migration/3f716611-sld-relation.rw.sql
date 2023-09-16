/*** { "revision": "3f716611" } ***/
ALTER TABLE qgis_raster_style DROP CONSTRAINT qgis_format_check;
ALTER TABLE qgis_vector_style DROP CONSTRAINT qgis_format_check;

ALTER TABLE qgis_raster_style DROP COLUMN qgis_sld_id;
ALTER TABLE qgis_vector_style DROP COLUMN qgis_sld_id;
