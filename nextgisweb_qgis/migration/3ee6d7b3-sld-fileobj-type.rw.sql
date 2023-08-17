/*** { "revision": "3ee6d7b3" } ***/

ALTER TABLE qgis_raster_style DROP COLUMN qgis_format;
ALTER TABLE qgis_raster_style RENAME CONSTRAINT qgis_raster_style_qgis_fileobj_id_fkey TO qgis_raster_style_qml_fileobj_id_fkey;
ALTER TABLE qgis_raster_style RENAME qgis_fileobj_id TO qml_fileobj_id;

ALTER TABLE qgis_vector_style DROP COLUMN qgis_format;
ALTER TABLE qgis_vector_style RENAME CONSTRAINT qgis_vector_style_qgis_fileobj_id_fkey TO qgis_vector_style_qml_fileobj_id_fkey;
ALTER TABLE qgis_vector_style RENAME qgis_fileobj_id TO qml_fileobj_id;
