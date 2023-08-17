/*** {
    "revision": "3ee6d7b3", "parents": ["2b9830b4"],
    "date": "2023-08-08T03:43:19",
    "message": "SLD fileobj type"
} ***/
ALTER TABLE qgis_raster_style RENAME qml_fileobj_id TO qgis_fileobj_id;
ALTER TABLE qgis_raster_style RENAME CONSTRAINT qgis_raster_style_qml_fileobj_id_fkey TO qgis_raster_style_qgis_fileobj_id_fkey;
ALTER TABLE qgis_raster_style ADD COLUMN qgis_format character varying(50);
UPDATE qgis_raster_style
    SET qgis_format = CASE WHEN qgis_fileobj_id IS NOT NULL THEN 'qml_file' ELSE 'default' END;
ALTER TABLE qgis_raster_style ALTER COLUMN qgis_format SET NOT NULL;

ALTER TABLE qgis_vector_style RENAME qml_fileobj_id TO qgis_fileobj_id;
ALTER TABLE qgis_vector_style RENAME CONSTRAINT qgis_vector_style_qml_fileobj_id_fkey TO qgis_vector_style_qgis_fileobj_id_fkey;
ALTER TABLE qgis_vector_style ADD COLUMN qgis_format character varying(50);
UPDATE qgis_vector_style
    SET qgis_format = CASE WHEN qgis_fileobj_id IS NOT NULL THEN 'qml_file' ELSE 'default' END;
ALTER TABLE qgis_vector_style ALTER COLUMN qgis_format SET NOT NULL;
