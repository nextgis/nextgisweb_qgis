/*** {
    "revision": "3f716611", "parents": ["3ee6d7b3"],
    "date": "2023-09-04T04:23:30",
    "message": "SLD relation"
} ***/
ALTER TABLE qgis_raster_style ADD COLUMN qgis_sld_id integer;
ALTER TABLE qgis_raster_style ADD CONSTRAINT qgis_raster_style_qgis_sld_id_fkey
    FOREIGN KEY (qgis_sld_id)
    REFERENCES sld (id);

ALTER TABLE qgis_vector_style ADD COLUMN qgis_sld_id integer;
ALTER TABLE qgis_vector_style ADD CONSTRAINT qgis_vector_style_qgis_sld_id_fkey
    FOREIGN KEY (qgis_sld_id)
    REFERENCES sld (id);

ALTER TABLE qgis_raster_style ADD CONSTRAINT qgis_format_check CHECK (
    CASE qgis_format
        WHEN 'default' THEN qgis_sld_id IS NULL AND qgis_fileobj_id IS NULL
        WHEN 'sld' THEN qgis_sld_id IS NOT NULL AND qgis_fileobj_id IS NULL
        WHEN 'sld_file' THEN qgis_fileobj_id IS NOT NULL AND qgis_sld_id IS NULL
        WHEN 'qml_file' THEN qgis_fileobj_id IS NOT NULL AND qgis_sld_id IS NULL
        ELSE false
    END
);
ALTER TABLE qgis_vector_style ADD CONSTRAINT qgis_format_check CHECK (
    CASE qgis_format
        WHEN 'default' THEN qgis_sld_id IS NULL AND qgis_fileobj_id IS NULL
        WHEN 'sld' THEN qgis_sld_id IS NOT NULL AND qgis_fileobj_id IS NULL
        WHEN 'sld_file' THEN qgis_fileobj_id IS NOT NULL AND qgis_sld_id IS NULL
        WHEN 'qml_file' THEN qgis_fileobj_id IS NOT NULL AND qgis_sld_id IS NULL
        ELSE false
    END
);