/*** { "revision": "3ee6d7b3" } ***/

ALTER TABLE qgis_raster_style DROP COLUMN qgis_format;
ALTER TABLE qgis_raster_style RENAME qgis_fileobj_id TO qml_fileobj_id;

ALTER TABLE qgis_vector_style DROP COLUMN qgis_format;
ALTER TABLE qgis_vector_style RENAME qgis_fileobj_id TO qml_fileobj_id;
